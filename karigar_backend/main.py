import os
import re
import json
import uuid
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

# IBM SDKs
from ibm_watsonx_ai.foundation_models import ModelInference
from ibmcloudant.cloudant_v1 import CloudantV1, Document
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

# ============================================================
# 1. ENVIRONMENT VAULT
# ============================================================
load_dotenv()
API_KEY          = os.getenv("IBM_CLOUD_API_KEY")
PROJECT_ID       = os.getenv("WATSONX_PROJECT_ID")
CLOUDANT_API_KEY = os.getenv("CLOUDANT_API_KEY")
CLOUDANT_URL     = os.getenv("CLOUDANT_URL")
CLOUDANT_DB_NAME = os.getenv("CLOUDANT_DB_NAME")
CORS_ORIGIN      = os.getenv("CORS_ORIGIN", "*")

app = FastAPI(
    title="Karigar Agentic Core",
    description="IBM-Powered 5-Agent Multi-Agent System for Migrant Worker Welfare",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Cloudant client (module-level; connection is lazy) ──────────────────────
_cloudant_auth = IAMAuthenticator(CLOUDANT_API_KEY)
db_client = CloudantV1(authenticator=_cloudant_auth)
db_client.set_service_url(CLOUDANT_URL)


# ============================================================
# 2. CANONICAL DATA CONTRACTS
# ============================================================

class WorkerInput(BaseModel):
    """
    ST-1 canonical request schema.
    CaseRecord shape produced by the orchestrator:
    {
        "_id": "case_<8hex>",
        "worker_profile": {               # Agent 1
            "mapped_location": str,
            "cluster": str,
            "inferred_skills": list[str],
            "industry": str,
            "skill_confidence": int
        },
        "wage_analysis": {                # Agent 2
            "wage_status": str,
            "is_fair_wage": bool,
            "reported_daily_wage": int,
            "minimum_legal_wage": int,
            "wage_deficit": int,
            "wage_category": str,
            "violation_severity": str
        },
        "safety_report": {                # Agent 3
            "safety_risk_level": str,
            "health_symptoms": list[str],
            "violation_tags": list[str],
            "bocw_compliance_flags": list[str],
            "osha_hazard_categories": list[str],
            "risk_triage_score": str,
            "triage_rationale": str
        },
        "welfare_entitlements": {         # Agent 4
            "eligible_schemes": list[dict],
            "ineligible_schemes": list[str],
            "eligibility_confidence": int
        },
        "raw_input_text": str,
        "timestamp": str
    }
    """
    worker_name:      str
    age:              int
    home_state:       str = "Unknown"
    current_location: str
    industry:         str
    raw_input_text:   str

    @field_validator("worker_name", "home_state", "current_location", "industry", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


# ============================================================
# 3. DOMAIN KNOWLEDGE TABLES
# ============================================================

# ST-2 — Gujarat Industrial Clusters
GUJARAT_CLUSTERS: dict[str, str] = {
    "surat":      "Surat Textile & Diamond Cluster",
    "ahmedabad":  "Ahmedabad Construction & Textile Hub",
    "alang":      "Alang Ship-Breaking Yard",
    "dahej":      "Dahej Petrochemical SEZ",
    "morbi":      "Morbi Ceramics & Tile Belt",
    "rajkot":     "Rajkot Engineering Cluster",
    "vadodara":   "Vadodara Chemical & Pharma Zone",
    "anand":      "Anand Dairy & Agro Processing",
    "gandhinagar":"Gandhinagar IT & Construction Hub",
    "valsad":     "Valsad Chemical Industrial Area",
}

# ST-2 — Canonical Skill Taxonomy
SKILL_TAXONOMY: dict[str, str] = {
    # Masonry / Construction
    "mason": "masonry", "masonry": "masonry", "rajmistri": "masonry",
    "brick": "masonry", "concrete": "masonry", "plastering": "masonry",
    # Textiles
    "tailoring": "tailoring", "sewing": "tailoring", "silai": "tailoring",
    "loom": "power_loom", "weaving": "power_loom", "bunai": "power_loom",
    "dyeing": "textile_dyeing", "embroidery": "embroidery",
    # Diamond
    "diamond": "diamond_bruting", "polishing": "diamond_bruting",
    "hira": "diamond_bruting", "ghisai": "diamond_bruting", "cutting": "diamond_bruting",
    # Ship-breaking
    "ship": "ship_breaking", "welding": "welding_fabrication",
    "gas cutting": "ship_breaking", "dismantling": "ship_breaking",
    # Ceramics
    "ceramic": "ceramics_glazing", "tile": "ceramics_glazing", "pottery": "ceramics_glazing",
    # General
    "painting": "surface_painting", "paint": "surface_painting",
    "plumbing": "plumbing", "electrical": "electrical_work",
    "driving": "transport_driving", "driver": "transport_driving",
    "farming": "agricultural_labour", "agriculture": "agricultural_labour",
    "chemical": "chemical_handling", "loading": "manual_loading",
}

# ST-3 — Gujarat Minimum Wages 2024-25 (INR / day)
GUJARAT_MIN_WAGES: dict[str, int] = {
    "Skilled":       450,
    "Semi-Skilled":  380,
    "Unskilled":     320,
}

INDUSTRY_SKILL_CATEGORY: dict[str, str] = {
    "masonry":            "Skilled",
    "welding_fabrication":"Skilled",
    "diamond_bruting":    "Skilled",
    "ceramics_glazing":   "Skilled",
    "ship_breaking":      "Semi-Skilled",
    "power_loom":         "Semi-Skilled",
    "tailoring":          "Semi-Skilled",
    "textile_dyeing":     "Semi-Skilled",
    "surface_painting":   "Semi-Skilled",
    "electrical_work":    "Skilled",
    "plumbing":           "Semi-Skilled",
    "embroidery":         "Semi-Skilled",
    "transport_driving":  "Skilled",
    "agricultural_labour":"Unskilled",
    "chemical_handling":  "Semi-Skilled",
    "manual_loading":     "Unskilled",
}

# ST-4 — Hazard Taxonomy (keyword → BOCW/OSHA category)
HAZARD_TAXONOMY: dict[str, str] = {
    "silica":       "Silicosis / Respiratory Hazard",
    "dust":         "Silicosis / Respiratory Hazard",
    "fumes":        "Toxic Fume Exposure",
    "smoke":        "Toxic Fume Exposure",
    "chemical":     "Chemical Exposure",
    "acid":         "Chemical Exposure",
    "ppe":          "Lack of PPE",
    "helmet":       "Lack of PPE",
    "gloves":       "Lack of PPE",
    "mask":         "Lack of PPE",
    "bonded":       "Bonded / Forced Labour",
    "forced":       "Bonded / Forced Labour",
    "unpaid":       "Wage Theft",
    "overtime":     "Excessive Overtime",
    "night":        "Night Shift Without Allowance",
    "heat":         "Extreme Heat Exposure",
    "height":       "Working at Height Without Safety",
    "fall":         "Working at Height Without Safety",
    "electric":     "Electrical Hazard",
    "fire":         "Fire / Explosion Risk",
    "noise":        "Noise-Induced Hearing Loss Risk",
    "drinking water":"Inadequate Welfare Facilities",
    "toilet":       "Inadequate Welfare Facilities",
    "shelter":      "Inadequate Welfare Facilities",
}

# BOCW provisions mapped to hazard categories
BOCW_PROVISIONS: dict[str, str] = {
    "Silicosis / Respiratory Hazard":       "BOCW Act §40 — Dust Control Obligation",
    "Toxic Fume Exposure":                  "BOCW Act §41 — Fume Extraction Requirement",
    "Chemical Exposure":                    "BOCW Act §42 — Hazardous Substance Handling",
    "Lack of PPE":                          "BOCW Act §38 — Personal Protective Equipment",
    "Bonded / Forced Labour":               "Bonded Labour System (Abolition) Act 1976",
    "Wage Theft":                           "Payment of Wages Act §5 — Timely Payment",
    "Excessive Overtime":                   "Factories Act §59 — Overtime Compensation",
    "Night Shift Without Allowance":        "Factories Act §70 — Night Shift Restrictions",
    "Extreme Heat Exposure":                "BOCW Act §39 — Working Environment Standards",
    "Working at Height Without Safety":     "BOCW Act §38-A — Fall Protection",
    "Electrical Hazard":                    "BOCW Act §45 — Electrical Safety",
    "Fire / Explosion Risk":                "Factories Act §38 — Fire Safety",
    "Noise-Induced Hearing Loss Risk":      "BOCW Act §44 — Noise Level Control",
    "Inadequate Welfare Facilities":        "BOCW Act §33 — Worker Welfare Amenities",
}

HAZARD_SEVERITY: dict[str, int] = {
    "Bonded / Forced Labour":               4,
    "Silicosis / Respiratory Hazard":       4,
    "Chemical Exposure":                    3,
    "Toxic Fume Exposure":                  3,
    "Working at Height Without Safety":     3,
    "Electrical Hazard":                    3,
    "Fire / Explosion Risk":                3,
    "Wage Theft":                           3,
    "Lack of PPE":                          2,
    "Excessive Overtime":                   2,
    "Extreme Heat Exposure":                2,
    "Night Shift Without Allowance":        1,
    "Noise-Induced Hearing Loss Risk":      1,
    "Inadequate Welfare Facilities":        1,
}
SEVERITY_LABELS = {4: "Critical", 3: "High", 2: "Medium", 1: "Low"}

# ST-5 — Welfare Schemes
WELFARE_SCHEMES: list[dict] = [
    {
        "id": "e_shram",
        "name": "e-Shram Card",
        "name_hi": "ई-श्रम कार्ड",
        "description": "Universal migrant worker ID and benefits portal",
        "apply_url": "https://eshram.gov.in",
        "eligibility_rules": {
            "age_min": 16,
            "age_max": 59,
            "industries": [],   # all industries
            "min_wage_deficit": 0,
            "violation_tags": [],
        },
    },
    {
        "id": "bocw",
        "name": "BOCW Welfare Board",
        "name_hi": "भवन एवं निर्माण कल्याण बोर्ड",
        "description": "Gujarat Building & Construction Workers Welfare Board",
        "apply_url": "https://bocwwb.gujarat.gov.in",
        "eligibility_rules": {
            "age_min": 18,
            "age_max": 60,
            "industries": ["masonry", "welding_fabrication", "surface_painting",
                           "plumbing", "electrical_work", "ship_breaking"],
            "min_wage_deficit": 0,
            "violation_tags": [],
        },
    },
    {
        "id": "pm_sym",
        "name": "PM-SYM Pension Scheme",
        "name_hi": "प्रधानमंत्री श्रम योगी मान-धन",
        "description": "Monthly pension of ₹3000 after age 60 for unorganised workers",
        "apply_url": "https://maandhan.in",
        "eligibility_rules": {
            "age_min": 18,
            "age_max": 40,
            "industries": [],
            "min_wage_deficit": 0,
            "violation_tags": [],
        },
    },
    {
        "id": "shramik_basera",
        "name": "Shramik Basera Yojana",
        "name_hi": "श्रमिक बसेरा योजना",
        "description": "Subsidised worker housing in Gujarat industrial zones",
        "apply_url": "https://labour.gujarat.gov.in",
        "eligibility_rules": {
            "age_min": 18,
            "age_max": 65,
            "industries": ["masonry", "ship_breaking", "ceramics_glazing",
                           "power_loom", "diamond_bruting", "textile_dyeing"],
            "min_wage_deficit": 0,
            "violation_tags": [],
        },
    },
    {
        "id": "dhanvantari",
        "name": "Dhanvantari Arogya Rath",
        "name_hi": "धन्वंतरि आरोग्य रथ",
        "description": "Mobile health camp access for industrial workers in Gujarat",
        "apply_url": "https://health.gujarat.gov.in",
        "eligibility_rules": {
            "age_min": 0,
            "age_max": 99,
            "industries": [],
            "min_wage_deficit": 0,
            "violation_tags": [
                "Silicosis / Respiratory Hazard",
                "Chemical Exposure",
                "Toxic Fume Exposure",
            ],
        },
    },
    {
        "id": "ayushman",
        "name": "Ayushman Bharat (PM-JAY)",
        "name_hi": "आयुष्मान भारत",
        "description": "Health coverage up to ₹5 lakh per family per year",
        "apply_url": "https://pmjay.gov.in",
        "eligibility_rules": {
            "age_min": 0,
            "age_max": 99,
            "industries": [],
            "min_wage_deficit": 1,   # any wage deficit qualifies
            "violation_tags": [],
        },
    },
    {
        "id": "pm_awas",
        "name": "PM Awas Yojana",
        "name_hi": "प्रधानमंत्री आवास योजना",
        "description": "Affordable housing scheme for economically weaker sections",
        "apply_url": "https://pmaymis.gov.in",
        "eligibility_rules": {
            "age_min": 18,
            "age_max": 99,
            "industries": [],
            "min_wage_deficit": 50,  # meaningful deficit required
            "violation_tags": [],
        },
    },
]


# ============================================================
# 4. LLM INTERFACE — SAFE PARSING
# ============================================================

def _safe_parse_llm_response(reply: str) -> dict:
    """
    ST-6: Three-tier fallback so a bad LLM response never crashes the API.
    Tier 1 — direct json.loads
    Tier 2 — regex extraction of first {...} block
    Tier 3 — return a safe default dict
    """
    # Tier 1
    try:
        cleaned = reply.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 2
    try:
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if match:
            return json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 3 — safe default
    return {
        "extracted_data": {
            "skills": [],
            "wage_status": "Unable to determine from input",
            "health_symptoms": [],
            "reported_daily_wage": 0,
            "income_level": "Unknown",
            "housing_status": "Unknown",
        },
        "safety_risk_level": "Medium",
        "violation_tags": ["Requires Manual Review"],
    }


def run_ibm_granite(payload: WorkerInput) -> dict:
    credentials = {"url": "https://us-south.ml.cloud.ibm.com", "apikey": API_KEY}
    model = ModelInference(
        model_id="ibm/granite-4-h-small",
        credentials=credentials,
        project_id=PROJECT_ID,
        params={"max_new_tokens": 512, "temperature": 0.2},
    )

    system_prompt = f"""You are the core intelligence of an AI system protecting migrant workers in India.
Analyze the worker's input in the {payload.industry} industry in {payload.current_location}.
Worker age: {payload.age}. Home state: {payload.home_state}.

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{
  "extracted_data": {{
    "skills": ["skill1", "skill2"],
    "wage_status": "description of wage situation",
    "health_symptoms": ["symptom1", "symptom2"],
    "reported_daily_wage": 0,
    "income_level": "Below Poverty Line / Low / Medium",
    "housing_status": "None / Temporary / Rented / Owned"
  }},
  "safety_risk_level": "High",
  "violation_tags": ["Wage Theft", "Lack of PPE"]
}}

Rules:
- reported_daily_wage must be a number (0 if not mentioned)
- safety_risk_level must be one of: Low, Medium, High, Critical
- Be specific about Gujarat industrial hazards (silicosis, diamond dust, ship-breaking fumes)
- violation_tags should reflect actual violations, not generic labels"""

    response = model.chat(messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": payload.raw_input_text},
    ])
    raw_reply = response["choices"][0]["message"]["content"]
    return _safe_parse_llm_response(raw_reply)


# ============================================================
# 5. AGENT 1 — MIGRANT SKILL & LOCATION MAPPING
# ============================================================
class SkillMappingAgent:
    @staticmethod
    def _normalize_location(location_str: str) -> tuple[str, str]:
        """Returns (mapped_location, cluster_label)."""
        loc_lower = location_str.lower()
        for city_key, cluster_label in GUJARAT_CLUSTERS.items():
            if city_key in loc_lower:
                return location_str, cluster_label
        return location_str, "Gujarat (Unspecified Cluster)"

    @staticmethod
    def _normalize_skills(raw_skills: list[str]) -> tuple[list[str], int]:
        """Returns (canonical_skills, confidence_0_to_100)."""
        if not raw_skills:
            return [], 0
        canonical = []
        matched = 0
        for skill in raw_skills:
            skill_lower = skill.lower()
            found = False
            for keyword, canonical_code in SKILL_TAXONOMY.items():
                if keyword in skill_lower:
                    if canonical_code not in canonical:
                        canonical.append(canonical_code)
                    matched += 1
                    found = True
                    break
            if not found:
                canonical.append(f"raw:{skill.lower()}")
        confidence = min(100, int((matched / len(raw_skills)) * 100))
        return canonical, confidence

    @staticmethod
    def map_skills(ai_data: dict, input_payload: WorkerInput) -> dict:
        raw_skills  = ai_data.get("extracted_data", {}).get("skills", [])
        norm_skills, confidence = SkillMappingAgent._normalize_skills(raw_skills)
        mapped_loc, cluster = SkillMappingAgent._normalize_location(
            input_payload.current_location
        )
        # Normalise the industry field too
        industry_lower = input_payload.industry.lower()
        canonical_industry = next(
            (code for kw, code in SKILL_TAXONOMY.items() if kw in industry_lower),
            input_payload.industry,
        )
        return {
            "mapped_location":  mapped_loc,
            "cluster":          cluster,
            "inferred_skills":  norm_skills,
            "industry":         canonical_industry,
            "skill_confidence": confidence,
        }


# ============================================================
# 6. AGENT 2 — WAGE FAIRNESS MONITORING
# ============================================================
class WageFairnessAgent:
    @staticmethod
    def _infer_skill_category(industry: str, skills: list[str]) -> str:
        for skill in [industry] + skills:
            if skill in INDUSTRY_SKILL_CATEGORY:
                return INDUSTRY_SKILL_CATEGORY[skill]
        # Fallback: scan skill list for partial matches
        for skill in [industry] + skills:
            for key, category in INDUSTRY_SKILL_CATEGORY.items():
                if key in skill.lower():
                    return category
        return "Unskilled"

    @staticmethod
    def analyze_wages(ai_data: dict, skill_data: dict) -> dict:
        wage_status        = ai_data.get("extracted_data", {}).get("wage_status", "Unknown")
        reported_wage      = int(ai_data.get("extracted_data", {}).get("reported_daily_wage", 0))
        industry           = skill_data.get("industry", "")
        skills             = skill_data.get("inferred_skills", [])
        wage_category      = WageFairnessAgent._infer_skill_category(industry, skills)
        minimum_legal_wage = GUJARAT_MIN_WAGES.get(wage_category, 320)
        wage_deficit       = max(0, minimum_legal_wage - reported_wage) if reported_wage > 0 else 0

        # Keyword-based fairness cross-check
        text_lower = wage_status.lower()
        text_flags_unfair = any(w in text_lower for w in ("unpaid", "theft", "withheld", "deducted", "less"))
        is_fair = (wage_deficit == 0) and not text_flags_unfair

        if wage_deficit == 0:
            severity = "None"
        elif wage_deficit <= minimum_legal_wage * 0.15:
            severity = "Minor"
        elif wage_deficit <= minimum_legal_wage * 0.30:
            severity = "Major"
        else:
            severity = "Critical"

        return {
            "wage_status":          wage_status,
            "is_fair_wage":         is_fair,
            "reported_daily_wage":  reported_wage,
            "minimum_legal_wage":   minimum_legal_wage,
            "wage_deficit":         wage_deficit,
            "wage_category":        wage_category,
            "violation_severity":   severity,
        }


# ============================================================
# 7. AGENT 3 — GRIEVANCE & SAFETY REPORTING
# ============================================================
class GrievanceSafetyAgent:
    @staticmethod
    def _detect_hazards(symptoms: list[str], violation_tags: list[str], raw_text: str) -> list[str]:
        """Scan all text sources for hazard keywords; return list of unique category labels."""
        combined = " ".join(symptoms + violation_tags + [raw_text]).lower()
        found = set()
        for keyword, category in HAZARD_TAXONOMY.items():
            if keyword in combined:
                found.add(category)
        return list(found)

    @staticmethod
    def assess_risk(ai_data: dict, raw_text: str) -> dict:
        symptoms       = ai_data.get("extracted_data", {}).get("health_symptoms", [])
        violation_tags = ai_data.get("violation_tags", [])
        llm_risk_level = ai_data.get("safety_risk_level", "Medium")

        osha_categories = GrievanceSafetyAgent._detect_hazards(symptoms, violation_tags, raw_text)
        bocw_flags      = [BOCW_PROVISIONS[cat] for cat in osha_categories if cat in BOCW_PROVISIONS]

        # Compute triage score from worst hazard severity
        max_sev = 1
        for cat in osha_categories:
            sev = HAZARD_SEVERITY.get(cat, 1)
            if sev > max_sev:
                max_sev = sev

        # Also respect LLM-provided risk level as a floor
        llm_floor = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(llm_risk_level.lower(), 2)
        final_sev  = max(max_sev, llm_floor)
        triage     = SEVERITY_LABELS[final_sev]

        if not osha_categories:
            rationale = f"No specific hazards detected; risk assessed as {triage} based on worker report context."
        else:
            top_hazard = max(osha_categories, key=lambda c: HAZARD_SEVERITY.get(c, 1))
            rationale  = (
                f"Risk escalated to {triage} due to: {top_hazard}. "
                f"{len(bocw_flags)} BOCW provision(s) potentially violated."
            )

        return {
            "safety_risk_level":     llm_risk_level,
            "health_symptoms":       symptoms,
            "violation_tags":        violation_tags if violation_tags else osha_categories,
            "bocw_compliance_flags": bocw_flags,
            "osha_hazard_categories":osha_categories,
            "risk_triage_score":     triage,
            "triage_rationale":      rationale,
        }


# ============================================================
# 8. AGENT 4 — WELFARE SCHEME ELIGIBILITY
# ============================================================
class WelfareEligibilityAgent:
    @staticmethod
    def _check_eligibility(
        scheme: dict,
        worker: WorkerInput,
        skill_data: dict,
        wage_data: dict,
        safety_data: dict,
    ) -> tuple[bool, str]:
        rules    = scheme["eligibility_rules"]
        industry = skill_data.get("industry", "")
        skills   = skill_data.get("inferred_skills", [])

        # Age check
        if not (rules["age_min"] <= worker.age <= rules["age_max"]):
            return False, f"Age {worker.age} outside eligibility range {rules['age_min']}–{rules['age_max']}"

        # Industry check (empty list = all industries)
        if rules["industries"]:
            industry_match = (industry in rules["industries"]) or any(
                s in rules["industries"] for s in skills
            )
            if not industry_match:
                return False, f"Industry '{industry}' not in scheme's covered sectors"

        # Wage deficit threshold
        if rules["min_wage_deficit"] > 0:
            if wage_data.get("wage_deficit", 0) < rules["min_wage_deficit"]:
                return False, "Wage deficit below scheme threshold"

        # Specific violation tag requirement
        if rules["violation_tags"]:
            worker_tags = set(safety_data.get("osha_hazard_categories", []))
            if not worker_tags.intersection(set(rules["violation_tags"])):
                return False, "Required health/safety violation not detected"

        return True, f"Eligible: age {worker.age}, industry '{industry}', wage deficit ₹{wage_data.get('wage_deficit', 0)}"

    @staticmethod
    def match_schemes(
        ai_data: dict,
        worker: WorkerInput,
        skill_data: dict,
        wage_data: dict,
        safety_data: dict,
    ) -> dict:
        eligible   = []
        ineligible = []

        for scheme in WELFARE_SCHEMES:
            matched, rationale = WelfareEligibilityAgent._check_eligibility(
                scheme, worker, skill_data, wage_data, safety_data
            )
            if matched:
                eligible.append({
                    "id":       scheme["id"],
                    "name":     scheme["name"],
                    "name_hi":  scheme["name_hi"],
                    "apply_url":scheme["apply_url"],
                    "rationale":rationale,
                })
            else:
                ineligible.append(scheme["name"])

        confidence = min(100, len(eligible) * 20 + (30 if wage_data.get("wage_deficit", 0) > 0 else 0))
        return {
            "eligible_schemes":      eligible,
            "ineligible_schemes":    ineligible,
            "eligibility_confidence":confidence,
        }


# ============================================================
# 9. AGENT 5 — LABOR WELFARE DASHBOARD AGENT
# ============================================================
class DashboardAgent:
    @staticmethod
    async def fetch_all_cases() -> list:
        try:
            response = await asyncio.to_thread(
                lambda: db_client.post_all_docs(
                    db=CLOUDANT_DB_NAME, include_docs=True
                ).get_result()
            )
            return [row["doc"] for row in response.get("rows", []) if "doc" in row]
        except Exception as e:
            print(f"[DashboardAgent] DB fetch error: {e}")
            return []

    @staticmethod
    def compute_analytics(cases: list) -> dict:
        by_risk:    dict[str, int] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        by_industry: dict[str, int] = {}
        by_deficit:  dict[str, int] = {"None": 0, "Minor": 0, "Major": 0, "Critical": 0}
        critical_cases = []
        total_welfare_matches = 0

        for c in cases:
            # Risk level
            risk = (
                c.get("safety_report", {}).get("risk_triage_score")
                or c.get("safety_report", {}).get("safety_risk_level")
                or c.get("risk_level", "Medium")
            )
            risk = risk.capitalize()
            by_risk[risk] = by_risk.get(risk, 0) + 1

            # Industry
            industry = (
                c.get("worker_profile", {}).get("industry")
                or c.get("industry", "Unknown")
            )
            by_industry[industry] = by_industry.get(industry, 0) + 1

            # Wage deficit band
            deficit_band = (
                c.get("wage_analysis", {}).get("violation_severity", "None")
            )
            by_deficit[deficit_band] = by_deficit.get(deficit_band, 0) + 1

            # Critical case list
            if risk in ("Critical", "High"):
                worker_name = (
                    c.get("worker_profile", {}).get("mapped_location", "")
                    and c.get("_id", "unknown")
                )
                critical_cases.append({
                    "id":          c.get("_id", "unknown"),
                    "risk":        risk,
                    "cluster":     c.get("worker_profile", {}).get("cluster", "Unknown"),
                    "triage":      c.get("safety_report", {}).get("triage_rationale", ""),
                })

            # Welfare matches
            total_welfare_matches += len(
                c.get("welfare_entitlements", {}).get("eligible_schemes", [])
            )

        return {
            "by_risk_level":        by_risk,
            "by_industry":          by_industry,
            "by_wage_deficit_band": by_deficit,
            "critical_cases":       critical_cases[:10],  # top 10
            "total_welfare_matches":total_welfare_matches,
        }


# ============================================================
# 10. API ROUTES
# ============================================================

@app.post("/api/v1/analyze")
async def agentic_orchestrator(payload: WorkerInput):
    try:
        # ── Core LLM Processing ─────────────────────────────────────────────
        raw_ai_data = await asyncio.to_thread(run_ibm_granite, payload)

        # ── Multi-Agent Delegation (ST-2 → ST-5) ───────────────────────────
        skill_data   = SkillMappingAgent.map_skills(raw_ai_data, payload)
        wage_data    = WageFairnessAgent.analyze_wages(raw_ai_data, skill_data)
        safety_data  = GrievanceSafetyAgent.assess_risk(raw_ai_data, payload.raw_input_text)
        welfare_data = WelfareEligibilityAgent.match_schemes(
            raw_ai_data, payload, skill_data, wage_data, safety_data
        )

        # ── Consolidate Canonical CaseRecord ───────────────────────────────
        case_record = {
            "_id":                  f"case_{uuid.uuid4().hex[:8]}",
            "worker_profile":       skill_data,
            "wage_analysis":        wage_data,
            "safety_report":        safety_data,
            "welfare_entitlements": welfare_data,
            "raw_input_text":       payload.raw_input_text,
            "timestamp":            datetime.utcnow().isoformat() + "Z",
        }

        # ── Async Cloudant Persist (ST-6) ───────────────────────────────────
        await asyncio.to_thread(
            lambda: db_client.post_document(
                db=CLOUDANT_DB_NAME,
                document=Document(**case_record),
            ).get_result()
        )

        return {"success": True, "data": case_record}

    except json.JSONDecodeError as e:
        return {"success": False, "error_code": "LLM_PARSE_ERROR",   "message": str(e)}
    except ConnectionError as e:
        return {"success": False, "error_code": "DB_WRITE_ERROR",    "message": str(e)}
    except Exception as e:
        return {"success": False, "error_code": "AGENT_ERROR",       "message": str(e)}


@app.get("/api/v1/cases")
async def get_dashboard_data():
    cases     = await DashboardAgent.fetch_all_cases()
    analytics = DashboardAgent.compute_analytics(cases)
    return {
        "success":     True,
        "total_cases": len(cases),
        "cases":       cases,
        "analytics":   analytics,
    }


@app.get("/dashboard")
def serve_dashboard():
    file_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "index.html not found in backend folder"}
