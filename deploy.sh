#!/usr/bin/env bash

set -euo pipefail

subscription_id="91bb5510-5bb1-4f85-a022-12f907612b87"
resource_group="halseybot-rg"
app_name="halseybot"
registry_name="halseybotacr"
repository="halseybot"

for command in az git python3; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Error: required command '$command' is not installed." >&2
        exit 1
    fi
done

az account set --subscription "$subscription_id"
current_subscription="$(az account show --query id -o tsv)"
if [[ "$current_subscription" != "$subscription_id" ]]; then
    echo "Error: Azure CLI is using the wrong subscription." >&2
    exit 1
fi

tag="$(date -u +%Y%m%d%H%M%S)-$(git rev-parse --short HEAD)"
remote_image="${registry_name}.azurecr.io/${repository}:${tag}"

echo "Building, testing, and pushing ${remote_image} with Azure Container Registry..."
az acr build \
    --registry "$registry_name" \
    --image "${repository}:${tag}" \
    --platform linux/amd64 \
    --only-show-errors \
    .

echo "Configuring Container Apps as a single-revision background worker..."
az containerapp revision set-mode \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --mode single \
    --output none
az containerapp ingress disable \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --output none

template_file="$(mktemp)"
trap 'rm -f "$template_file"' EXIT
az containerapp show \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --output json |
    REMOTE_IMAGE="$remote_image" python3 -c '
import json
import os
import sys

app = json.load(sys.stdin)
template = app["properties"]["template"]
for container in template["containers"]:
    if container["name"] == "halseybot":
        container["image"] = os.environ["REMOTE_IMAGE"]
        break
else:
    raise SystemExit("Container halseybot was not found")

scale = template.setdefault("scale", {})
scale["minReplicas"] = 1
scale["maxReplicas"] = 1
scale["rules"] = []
json.dump({"properties": {"template": template}}, sys.stdout)
' >"$template_file"

echo "Deploying ${remote_image} with one fixed replica and no scale triggers..."
az containerapp update \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --yaml "$template_file" \
    --output none

revision="$(az containerapp show \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --query properties.latestRevisionName \
    --output tsv)"

echo "Waiting for revision ${revision} to become healthy..."
for _ in {1..60}; do
    health="$(az containerapp revision show \
        --name "$app_name" \
        --resource-group "$resource_group" \
        --revision "$revision" \
        --query properties.healthState \
        --output tsv)"
    if [[ "$health" == "Healthy" ]]; then
        running_status="$(az containerapp show \
            --name "$app_name" \
            --resource-group "$resource_group" \
            --query properties.runningStatus \
            --output tsv)"
        if [[ "$running_status" == "Running" ]]; then
            echo "Deployment succeeded: ${revision} is healthy and running."
            exit 0
        fi
    fi
    if [[ "$health" == "Unhealthy" ]]; then
        break
    fi
    sleep 5
done

echo "Deployment failed: revision ${revision} did not become healthy." >&2
az containerapp revision show \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --revision "$revision" \
    --query "properties.{healthState:healthState,provisioningState:provisioningState}" \
    --output table >&2
az containerapp logs show \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --type system \
    --tail 30 \
    --format json >&2 || true
exit 1
