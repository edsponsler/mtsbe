#!/bin/bash
# GCP Setup Script for MTSBE Project
# This script provisions the necessary Cloud SQL instance and sets up budgets.
# It is recommended to run this script in your Google Cloud Shell.

PROJECT_ID="mtsbe-1208613"

echo "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

echo "Enabling necessary APIs..."
gcloud services enable billingbudgets.googleapis.com sqladmin.googleapis.com compute.googleapis.com

echo "Fetching billing account..."
# Note: For setting up budgets, we need the billing account ID.
BILLING_ACCOUNT=$(gcloud beta billing accounts list --format="value(name)" | head -n 1)

if [ -z "$BILLING_ACCOUNT" ]; then
    echo "Warning: No billing account found. Please set up the budget manually in the GCP Console."
else
    echo "Setting up $500 PoC Budget for billing account $BILLING_ACCOUNT..."
    gcloud beta billing budgets create \
        --billing-account="$BILLING_ACCOUNT" \
        --display-name="PoC Phase 2 Budget" \
        --budget-amount=500.00 \
        --threshold-rule=percent=0.5 \
        --threshold-rule=percent=0.9 \
        --threshold-rule=percent=1.0
fi

echo "Provisioning cost-optimized Cloud SQL instance (db-f1-micro)..."
INSTANCE_NAME="mtsbe-db"

# Create the instance (this takes several minutes)
gcloud sql instances create $INSTANCE_NAME \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --storage-type=HDD \
    --storage-size=10GB \
    --root-password="ChangeThisStrongPassword123!"

echo "Creating the database 'mtsbe_data'..."
gcloud sql databases create mtsbe_data --instance=$INSTANCE_NAME

echo "Setup Complete!"
echo "To connect to your database and run the schema, you can use:"
echo "gcloud sql connect $INSTANCE_NAME --user=postgres --quiet"
