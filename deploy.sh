#!/bin/bash

# Exit on any error
set -e

# Step 0: Check if Docker is running and start if needed
echo "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Starting Docker..."
    open -a Docker
    echo "Waiting for Docker to start..."
    timeout=60  # 60 second timeout
    elapsed=0
    while ! docker info > /dev/null 2>&1; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [ $elapsed -ge $timeout ]; then
            echo "Error: Docker failed to start within $timeout seconds"
            exit 1
        fi
        echo "Still waiting for Docker... ($elapsed/$timeout seconds)"
    done
    echo "Docker is now running!"
else
    echo "Docker is already running!"
fi

# Step 0.5: Verify Azure CLI is logged in
echo "Verifying Azure CLI authentication..."
if ! az account show > /dev/null 2>&1; then
    echo "Error: Not logged into Azure CLI. Please run 'az login' first."
    exit 1
fi
echo "Azure CLI authenticated successfully!"

# Step 1: Rebuild the Docker image targeting linux/amd64 with timestamped tag
echo "Building Docker image..."
tag=$(date +%s)
docker build --platform linux/amd64 -t halseybot:$tag .

# Step 2: Tag the Docker image for Azure Container Registry
echo "Tagging Docker image for Azure Container Registry..."
docker tag halseybot:$tag halseybotacr.azurecr.io/halseybot:$tag

# Step 3: Log in to Azure Container Registry and push the image
echo "Logging into Azure Container Registry..."
az acr login --name halseybotacr
echo "Pushing Docker image to Azure Container Registry..."
docker push halseybotacr.azurecr.io/halseybot:$tag

# Step 4: Update the Azure Container App with the new image (no stopping needed)
echo "Updating Azure Container App with new image..."
az containerapp update \
  --name halseybot \
  --resource-group halseybot-rg \
  --image halseybotacr.azurecr.io/halseybot:$tag \
  --min-replicas 1 \
  --max-replicas 1

# Step 5: Wait for deployment to complete and verify it's running
echo "Waiting for deployment to complete..."
sleep 20
echo "Verifying deployment status..."
status=$(az containerapp show --name halseybot --resource-group halseybot-rg --query "properties.runningStatus" -o tsv)
if [ "$status" = "Running" ]; then
    echo "✅ Deployment successful! Container app is running."
    echo "🌐 App URL: $(az containerapp show --name halseybot --resource-group halseybot-rg --query "properties.configuration.ingress.fqdn" -o tsv)"
else
    echo "⚠️  Warning: Container app status is: $status"
    echo "Check logs with: az containerapp logs show --name halseybot --resource-group halseybot-rg --tail 50"
fi

active=$(az containerapp revision list --name halseybot --resource-group halseybot-rg --query "[?properties.active==\`true\`].name" -o tsv)
if [ -z "$active" ]; then
    echo "No active revision found. Reactivating the latest revision..."
    latest=$(az containerapp revision list --name halseybot --resource-group halseybot-rg --query "[-1].name" -o tsv)
    if [ -n "$latest" ]; then
        az containerapp revision activate --name halseybot --resource-group halseybot-rg --revision $latest
        echo "Reactivated revision: $latest"
    else
        echo "Error: No revisions available to activate."
    fi
fi

echo "Deployment complete!"