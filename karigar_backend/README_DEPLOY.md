# Karigar Backend — IBM Cloud Code Engine Deployment Guide

## Prerequisites

```bash
# Install IBM Cloud CLI
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

# Install Code Engine plugin
ibmcloud plugin install code-engine

# Install Container Registry plugin
ibmcloud plugin install container-registry
```

---

## Step 1 — Build & Push the Container Image

```bash
# Login to IBM Cloud
ibmcloud login --apikey $IBM_CLOUD_API_KEY -r us-south

# Login to IBM Container Registry
ibmcloud cr login

# Build the multi-stage image (from karigar_backend/ directory)
cd karigar_backend/
docker build -t us.icr.io/<your-namespace>/karigar-backend:latest .

# Push to IBM Container Registry
docker push us.icr.io/<your-namespace>/karigar-backend:latest
```

---

## Step 2 — Create a Code Engine Secret for IBM credentials

```bash
# Select or create a Code Engine project
ibmcloud ce project select --name karigar-project
# or: ibmcloud ce project create --name karigar-project

# Create a secret from your .env file values
ibmcloud ce secret create --name karigar-secrets \
  --from-literal IBM_CLOUD_API_KEY="$IBM_CLOUD_API_KEY" \
  --from-literal WATSONX_PROJECT_ID="$WATSONX_PROJECT_ID" \
  --from-literal CLOUDANT_API_KEY="$CLOUDANT_API_KEY" \
  --from-literal CLOUDANT_URL="$CLOUDANT_URL" \
  --from-literal CLOUDANT_DB_NAME="karigar_app_db" \
  --from-literal CORS_ORIGIN="*"
```

---

## Step 3 — Deploy the Application

```bash
ibmcloud ce application create \
  --name karigar-backend \
  --image us.icr.io/<your-namespace>/karigar-backend:latest \
  --registry-secret ibmcr-secret \
  --env-from-secret karigar-secrets \
  --port 8080 \
  --cpu 1 \
  --memory 2G \
  --min-scale 1 \
  --max-scale 5 \
  --concurrency 80
```

---

## Step 4 — Get the Public URL

```bash
ibmcloud ce application get --name karigar-backend --output url
# Example output: https://karigar-backend.abcde12345.us-south.codeengine.appdomain.cloud
```

---

## Step 5 — Build Flutter APK with Production API URL

```bash
# From karigar_frontend/ directory
flutter build apk --release \
  --dart-define=API_BASE=https://karigar-backend.abcde12345.us-south.codeengine.appdomain.cloud

# Or for web:
flutter build web --release \
  --dart-define=API_BASE=https://karigar-backend.abcde12345.us-south.codeengine.appdomain.cloud
```

---

## Step 6 — Access the Web Dashboard

```
GET https://karigar-backend.<hash>.us-south.codeengine.appdomain.cloud/dashboard
```

---

## Updating a Deployment

```bash
# Rebuild and push a new image tag
docker build -t us.icr.io/<your-namespace>/karigar-backend:v2 .
docker push us.icr.io/<your-namespace>/karigar-backend:v2

# Zero-downtime update
ibmcloud ce application update \
  --name karigar-backend \
  --image us.icr.io/<your-namespace>/karigar-backend:v2
```

---

## Health Check

```bash
curl https://karigar-backend.<hash>.us-south.codeengine.appdomain.cloud/api/v1/cases
# Expected: {"success": true, "total_cases": N, "cases": [...], "analytics": {...}}
```

---

## Notes

- The `Procfile` (`web: uvicorn main:app ...`) is retained for local development and any Heroku-compatible platform.
- Code Engine auto-scales to zero when idle (min-scale 0) — set `--min-scale 1` for demo to avoid cold starts.
- All IBM credentials are injected via Code Engine secrets — never baked into the image.
- The `CORS_ORIGIN` secret should be set to your frontend's Code Engine URL in production.
