<div align="center">
  
  # 🚧 कारीGAR APP
  **Smart Migrant Labor Welfare Platform**
  
  *An Agentic AI ecosystem designed to safeguard interstate migrant workers by automating welfare eligibility mapping, wage fairness auditing, and hazard detection. Built for the IBM University Engagement Project.*
  
</div>

---

## 📖 System Overview

Gujarat hosts a massive interstate migrant workforce across construction, textiles, and chemical processing. The **Karigar App** bridges the critical gap between vulnerable workers and government welfare schemes (e.g., BOCW, PM-SYM) utilizing a highly scalable, multi-agent AI architecture. 

> **The Agentic Advantage:** Rather than relying on a passive chatbot, the system utilizes specialized IBM Granite AI agents to actively extract artisan skills, audit statutory wage compliance, and autonomously escalate critical safety hazards to a real-time command center.

## 🏛️ Core Architecture

Our platform utilizes a dual-tier edge approach: a Flutter mobile application for raw data collection, securely routed through a custom FastAPI orchestrator, and deeply integrated with IBM Cloud services for AI processing and schema-less data storage.

```mermaid
graph LR
  classDef frontend fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff,rx:8px,ry:8px;
  classDef backend fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff,rx:8px,ry:8px;
  classDef ai fill:#312e81,stroke:#8b5cf6,stroke-width:2px,color:#fff,rx:8px,ry:8px;
  classDef db fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff,rx:8px,ry:8px;

  subgraph Client_Tier ["Client Tier (Edge)"]
    A[Flutter Mobile App <br/> Multi-lingual Worker Input]:::frontend
    B[Tailwind Dashboard <br/> Command Center]:::frontend
  end

  subgraph Orchestration_Tier ["Orchestration Tier (Render)"]
    C[FastAPI Orchestrator <br/> Python API Gateway]:::backend
  end

  subgraph IBM_Cloud_Tier ["Data & AI Tier (IBM Cloud)"]
    D[(IBM Cloudant <br/> NoSQL Document DB)]:::db
    E{IBM watsonx.ai <br/> Granite-4.0-8B-Instruct}:::ai

    subgraph Agentic_Swarm ["Autonomous Multi-Agent Swarm"]
        E1[Skill Mapping Agent]:::ai
        E2[Welfare Scheme Agent]:::ai
        E3[Wage Fairness Agent]:::ai
        E4[Safety Reporting Agent]:::ai
    end
  end

  A -- "Unstructured Input" --> C
  C -- "Schema-less Ops" <--> D
  C -- "Context Routing" --> E
  E --> E1 & E2 & E3 & E4
  E1 & E2 & E3 & E4 -- "Priority JSON Flags" --> E
  E -- "Actionable Intelligence" --> C
  C -- "Idempotent Refresh" --> B
```
## 🛠️ Technology Stack

| Domain | Technologies Used |
| :--- | :--- |
| **AI Infrastructure** | `IBM watsonx.ai`, `IBM Granite-4.0-8B-Instruct` |
| **Database** | `IBM Cloudant` *(NoSQL Document Database)* |
| **Backend Orchestration** | `Python`, `FastAPI`, `Render Cloud` |
| **Frontend (Mobile Edge)** | `Flutter`, `Dart` *(Release APK)* |
| **Frontend (Command Center)**| `HTML5`, `Tailwind CSS`, `Vanilla JS` |

## 🌐 Live System Access

**[🚀 Access Live Command Center Dashboard](https://team-thekedaars-karigar.onrender.com/dashboard)**

> **System Note:** The dashboard updates asynchronously in real-time as incoming grievances are processed, analyzed, and flagged by the autonomous AI agents.

## 👥 Team Thekedaars

| Team Member | Engineering Role |
| :--- | :--- |
| **Anurrag Singh Tomar** | Team Leader & Lead Architecture Engineer |
| **Prasiddhi Mishra** | Lead Frontend Developer & UI/UX Designer |
| **Krish Singh** | Backend Systems & API Integrations Developer |
| **Shrihari H Kulkarni** | Cloud Database & Infrastructure Engineer |
