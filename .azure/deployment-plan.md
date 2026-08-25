# Azure Deployment Plan

> **Status:** Deployed

Generated: 2026-08-25T22:34:00+01:00

---

## 1. Project Overview

**Goal:** Clean up and redeploy the HalseyBot background worker so it monitors the new
Girl in the Tower storefront quickly, reliably, and at low cost.

**Path:** Modernize Existing

---

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | Production |
| Scale | Small; one always-on worker replica |
| Budget | Cost-optimized |
| Compliance | No additional requirements |
| Subscription | Visual Studio Enterprise Subscription (`91bb5510-5bb1-4f85-a022-12f907612b87`) |
| Location | West Europe (`westeurope`) |
| Responsiveness | Fast detection without triggering storefront rate limits |
| Reliability | Independent store loops, bounded retries, and status-aware backoff |

**Policy constraints:** The only subscription assignment is the default Microsoft
Defender for Cloud policy (`SecurityCenterBuiltIn`). It does not constrain this update.

---

## 3. Components Detected

| Component | Type | Technology | Path |
|-----------|------|------------|------|
| Store monitor | Background worker | Python 3.12, asyncio, aiohttp | `main.py` |
| Container image | Container | Docker | `Dockerfile` |
| Deployment automation | Azure CLI | Bash | `deploy.sh` |
| Product state | Data | Azure Blob Storage | Existing `halseybotstorage` |
| Secrets | Security | Azure Key Vault and managed identity | Existing `halseybot-keys` |

Existing Azure hosting uses one Azure Container App on the Consumption workload
profile, Azure Container Registry, Log Analytics, Blob Storage, Key Vault, and a
system-assigned managed identity.

---

## 4. Recipe Selection

**Selected:** AZCLI

**Rationale:** This is an in-place update to an existing deployment with an established
Azure CLI deployment script. No resources are being added or replaced, so introducing
new IaC or an AZD environment would add migration risk without improving this change.

---

## 5. Architecture

**Stack:** Containers

### Service Mapping

| Component | Azure Service | SKU |
|-----------|---------------|-----|
| Background worker | Azure Container Apps | Consumption, one replica |
| Container image | Azure Container Registry | Existing registry |
| Product state | Azure Blob Storage | Existing storage account |
| Secrets | Azure Key Vault | Existing vault |
| Logs | Log Analytics | Existing workspace |

### Planned Application Changes

1. Replace the old storefronts with:
   - EU: `https://www.girlinthetower.com/en-eu`
   - UK: `https://www.girlinthetower.com/en-uk`
   - US: `https://www.girlinthetower.com`
2. Monitor the Halsey collection at
   `https://shop.capitolmusic.com/collections/halsey` using a separate state blob.
3. Create fresh state blobs instead of reusing Halsey store lists. Announce the full
   initial Girl in the Tower catalog when it becomes public, but establish the Capitol
   collection as a silent baseline so existing Capitol items are not tweeted.
4. Use one shared HTTP session and one independent polling task per locale.
5. Poll quickly after successful checks, retry password-protected `401` responses slowly,
   honor `Retry-After` for `429`, and exponentially back off transient failures.
6. Add jitter so all locale requests do not repeatedly hit the host at the same instant.
7. Move blocking Blob Storage and Twitter calls off the asyncio event loop.
8. Retry failed tweets and commit product state only after queued notifications succeed,
   preventing transient Twitter failures from losing announcements.
9. Replace global mutable state and duplicate imports with typed configuration and pure
   state-comparison logic covered by targeted unit tests.
10. Remove unused dependencies and exclude local configuration from the remote build
   context.
11. Disable HTTP ingress and HTTP scaling because this is a background worker with no
   listening port. Retain exactly one always-on replica.
12. Use Azure Container Registry Tasks for remote image builds because Docker is not
   installed in the execution environment. Run tests during the Docker build so a
   failing image cannot be published or deployed.
13. Improve deployment verification so an unhealthy revision fails the deployment.
14. Remove the stale HTTP scale rule with an explicit empty rule set, retain
    `minReplicas=1` and `maxReplicas=1`, reduce routine success logs to five-minute
    heartbeats, and pin transitive dependencies plus the base image digest.

The new Shopify store is currently password-protected. The worker will not bypass the
password; it will retry at a low frequency and automatically become reactive when the
store opens publicly.

---

## 6. Provisioning Limit Checklist

No new Azure resources will be provisioned. The update creates a Container App revision
inside the existing app and reuses all current services.

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| `Microsoft.App/containerApps` | 0 | 1 | Not applicable to in-place revision updates | Existing app only |
| `Microsoft.App/managedEnvironments` | 0 | 1 | Not applicable | Existing environment only |
| `Microsoft.ContainerRegistry/registries` | 0 | 1 | Not applicable | Existing registry only |
| `Microsoft.Storage/storageAccounts` | 0 | 1 | Not applicable | Existing account only |
| `Microsoft.KeyVault/vaults` | 0 | 1 | Not applicable | Existing vault only |

The mandatory quota CLI path was attempted after registering `Microsoft.Quota`; Azure
still reported registration propagation pending. This does not block the deployment
because the resource delta is zero and no quota-controlled capacity is requested.

**Status:** All resource counts remain unchanged.

---

## 7. Execution Checklist

### Phase 1: Planning
- [x] Analyze workspace
- [x] Gather requirements
- [x] Confirm subscription and location with user
- [x] Prepare resource inventory
- [x] Attempt quota validation and confirm zero-resource delta
- [x] Scan codebase
- [x] Select recipe
- [x] Plan architecture
- [x] User approved this plan

### Phase 2: Execution
- [x] Refactor and test the Python worker
- [x] Update the Docker and Azure CLI deployment configuration
- [x] Run a no-push ACR validation build (Docker is unavailable locally)
- [x] Update plan status to `Ready for Validation`

### Phase 3: Validation
- [x] Re-run `azure-validate` after final scale/logging/dependency cleanup
- [x] All validation checks pass
  - [x] 1. Core Validation (CLI, auth, build, validate; IaC what-if not applicable)
  - [x] 2. Docker Build (no-push ACR build because Docker is unavailable)
  - [x] 3. Azure Policy Validation
- [x] Validate Python tests and compilation
- [x] Validate the container retries protected stores correctly
- [x] Validate Azure authentication, target resource, ACR access, and configuration
- [x] Record updated validation proof below

### Phase 4: Deployment
- [x] Invoke `azure-deploy`
- [x] Build and push an immutable image
- [x] Disable ingress and deploy one worker replica
- [x] Verify the active revision is healthy and has no restart loop
- [x] Verify logs show controlled password-protected retries
- [x] Update plan status to `Deployed`

---

## 8. Validation Proof

| Check | Command Run | Result | Timestamp |
|-------|-------------|--------|-----------|
| Source and script checks | `python3 -m py_compile main.py tests/test_main.py`; `bash -n deploy.sh`; `git diff --check` | Pass | 2026-08-25T21:43Z |
| Container build and tests | `az acr build --registry halseybotacr --platform linux/amd64 --no-push .` (run `cb3`) | Pass; seven tests | 2026-08-25T21:44Z |
| Azure target | Validate subscription, resource group, Container App, and ACR provisioning states | Pass | 2026-08-25T21:46Z |
| Managed identity | Confirm Container App principal has Key Vault secret `Get` access | Pass | 2026-08-25T21:47Z |
| Storefront behavior | Verify Girl in the Tower returns expected protected `401` and Capitol Halsey feed returns `200` | Pass | 2026-08-25T21:46Z |
| Azure Policy | List effective subscription assignments and check deployment compatibility | Pass; only Defender default assignment | 2026-08-25T21:46Z |
| IaC validation/what-if | Not run because this is an in-place application revision with no IaC or resource delta | Not applicable | 2026-08-25T21:47Z |
| Final reproducible build | `az acr build --registry halseybotacr --platform linux/amd64 --no-push .` (run `cb5`) | Pass; pinned image and seven tests | 2026-08-25T21:55Z |
| Fixed-replica template | Generate the live update template and assert `minReplicas=1`, `maxReplicas=1`, and `rules=[]` | Pass | 2026-08-25T21:55Z |
| Production deployment | ACR build `cb6`; deploy image `20260825215619-b49e375` | Pass | 2026-08-25T21:58Z |
| Live revision | Verify `halseybot--0000014`, one active revision, one ready replica, zero restarts, no ingress, and no scale rules | Pass | 2026-08-25T21:59Z |
| Live worker behavior | Verify Capitol checks with zero changes and Girl in the Tower `401` retries at 300 seconds | Pass | 2026-08-25T21:59Z |

**Validated by:** `azure-validate` workflow

**Validation timestamp:** 2026-08-25T21:55Z

---

## 9. Files to Change

| File | Purpose | Status |
|------|---------|--------|
| `.azure/deployment-plan.md` | Deployment source of truth | Complete |
| `main.py` | Reliable adaptive background worker | Complete |
| `tests/test_main.py` | State and retry behavior tests | Complete |
| `requirements.txt` | Locked runtime dependencies | Complete |
| `.dockerignore` | Exclude local and sensitive build context | Complete |
| `Dockerfile` | Deterministic, responsive container runtime | Complete |
| `deploy.sh` | Safe worker deployment and health verification | Complete |
| `README.MD` | Updated URLs and operating guidance | Complete |

---

## 10. Functional Verification

- **Status:** Verified
- **Backend:** Python compilation, Bash syntax, diff checks, and seven unit tests passed
  in an Azure Container Registry `linux/amd64` no-push build.
- **UI:** Not applicable; this is a background worker with ingress disabled.
- **External feeds:** The Capitol Halsey collection feed returns product data. Girl in
  the Tower correctly returns `401` while password-protected and will use controlled
  retries until it opens.
- **Build:** ACR Task run `cb3` succeeded on 2026-08-25.

---

## 11. Next Steps

> Current: Deployed

1. Monitor the normal five-minute heartbeat and protected-store retries.
2. Run `./deploy.sh` for future tested, remote-build deployments.
