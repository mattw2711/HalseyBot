#!/bin/bash

# Step 1: Rebuild the Docker image targeting linux/amd64
echo "Building Docker image..."
docker build --platform linux/amd64 -t halseybot .

# Step 2: Tag the Docker image for Azure Container Registry
echo "Tagging Docker image for Azure Container Registry..."
docker tag halseybot halseybotacr.azurecr.io/halseybot:latest

# Step 3: Log in to Azure Container Registry and push the image
echo "Logging into Azure Container Registry..."
az acr login --name halseybotacr
echo "Pushing Docker image to Azure Container Registry..."
docker push halseybotacr.azurecr.io/halseybot:latest

# Step 4: Update the Azure Container App with the new image
echo "Updating Azure Container App..."
az containerapp update \
  --name halseybot \
  --resource-group halseybot-rg \
  --image halseybotacr.azurecr.io/halseybot:latest

echo "Deployment complete!"