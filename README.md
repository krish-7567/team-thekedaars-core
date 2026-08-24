# Karigar App - Smart Migrant Labor Welfare Platform

An Agentic AI ecosystem designed to safeguard interstate migrant workers by automating welfare eligibility mapping, wage fairness auditing, and hazard detection. Built for the IBM University Engagement Project.

## System Overview

Gujarat hosts a massive interstate migrant workforce across construction, textiles, and chemical processing. The Karigar App bridges the gap between vulnerable workers and government welfare schemes (e.g., BOCW, PM-SYM) using a multi-agent AI architecture. 

Rather than a passive chatbot, the system utilizes specialized IBM Granite AI agents to extract artisan skills, audit statutory wage compliance, and escalate critical safety hazards to a real-time command center.

## Core Architecture

Our platform utilizes a dual-tier approach: a Flutter mobile application for edge data collection, routed through a custom FastAPI orchestrator, heavily integrated with IBM Cloud services.

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
