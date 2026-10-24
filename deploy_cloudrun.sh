#!/usr/bin/env bash
set -e

PROJECT_ID="mtsbe-1208613"
REGION="us-central1"
REPO="mtsbe-repo"
INSTANCE_CONN="mtsbe-1208613:us-central1:mtsbe-db"
DB_NAME="mtsbe_data"
DB_USER="postgres"
DB_PASSWORD="ChangeThisStrongPassword123!"
GCS_BUCKET="mtsbe-narratives-1208613"
NARRATIVE_MODEL="gemini-4-argon"

echo "=================================================="
echo "=== Deploying MTSBE to Google Cloud Run ==="
echo "=================================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Cloud SQL Instance: $INSTANCE_CONN"
echo ""

# 1. Build and push API Container
echo "1. Building and pushing Backend API container..."
gcloud builds submit \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --config=cloudbuild.api.yaml .

# 2. Deploy Backend API to Cloud Run
echo "2. Deploying 'mtsbe-api' to Cloud Run..."
gcloud run deploy mtsbe-api \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="us-central1-docker.pkg.dev/$PROJECT_ID/$REPO/mtsbe-api:latest" \
  --platform=managed \
  --allow-unauthenticated \
  --add-cloudsql-instances="$INSTANCE_CONN" \
  --set-env-vars="INSTANCE_CONNECTION_NAME=$INSTANCE_CONN,DB_NAME=$DB_NAME,DB_USER=$DB_USER,DB_PASSWORD=$DB_PASSWORD,GCS_BUCKET_NAME=$GCS_BUCKET,NARRATIVE_MODEL=$NARRATIVE_MODEL" \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=80

API_URL=$(gcloud run services describe mtsbe-api --project="$PROJECT_ID" --region="$REGION" --format="value(status.url)")
echo "✓ Backend API deployed successfully at: $API_URL"
echo ""

# 3. Build and push Frontend Container with API_URL
echo "3. Building and pushing Frontend container (baked API URL: $API_URL)..."
gcloud builds submit \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --config=cloudbuild.frontend.yaml \
  --substitutions="_NEXT_PUBLIC_API_URL=$API_URL" .

# 4. Deploy Frontend to Cloud Run
echo "4. Deploying 'mtsbe-frontend' to Cloud Run..."
gcloud run deploy mtsbe-frontend \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="us-central1-docker.pkg.dev/$PROJECT_ID/$REPO/mtsbe-frontend:latest" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="NEXT_PUBLIC_API_URL=$API_URL" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60

FRONTEND_URL=$(gcloud run services describe mtsbe-frontend --project="$PROJECT_ID" --region="$REGION" --format="value(status.url)")
echo ""
echo "=================================================="
echo "=== Deployment Successfully Completed ==="
echo "=================================================="
echo "Backend API:  $API_URL"
echo "Frontend App: $FRONTEND_URL"
echo "API Docs:     $API_URL/docs"
echo "Health Check: $API_URL/health"
echo "=================================================="
