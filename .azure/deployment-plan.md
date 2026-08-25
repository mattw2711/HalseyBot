# Azure Deployment Plan

> **Status:** Deployed

Generated: 2026-08-25T22:34:00+01:00

---

## 1. Project Overview

**Goal:** Run HalseyBot as a fast, reliable, low-cost storefront monitor and migrate
automatic notifications from the paid X API to a free Discord webhook.

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
15. Replace Tweepy and all X API credentials with one Discord webhook URL retrieved from
    Key Vault through the existing managed identity.
16. Publish Discord messages with link previews disabled, suppress mentions, honor
    webhook rate-limit responses, and retain acknowledged retries before product state
    advances.
17. Remove X-only dependencies and documentation. On deployment, the seven pending
    Capitol detections will be rediscovered, delivered to Discord, and then persisted.
18. Render each product as a native Discord embed containing the primary Shopify image,
    price, status, and destination link. Continue suppressing mentions.
19. After the rich-embed revision is healthy, perform one explicit replay of the seven
    previously acknowledged Capitol products without altering their saved state.

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
- [x] Replace X publishing with Discord webhook publishing
- [x] Add Discord formatting, success, retry, and rate-limit tests
- [x] Store the Discord webhook URL in Key Vault
- [x] Remove X-only dependencies and update operating documentation
- [x] Update plan status to `Ready for Validation`
- [x] Add native Discord product embeds and image coverage
- [x] Update plan status to `Ready for Validation`

### Phase 3: Validation
- [x] Re-run `azure-validate` for rich Discord product embeds
  - [x] 1. Core Validation (CLI, auth, build, validate; IaC what-if not applicable)
  - [x] 2. Docker Build (no-push ACR build because Docker is unavailable)
  - [x] 3. Azure Policy Validation
- [x] Re-run `azure-validate` for the Discord migration
  - [x] 1. Core Validation (CLI, auth, build, validate; IaC what-if not applicable)
  - [x] 2. Docker Build (no-push ACR build because Docker is unavailable)
  - [x] 3. Azure Policy Validation
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
- [x] Invoke `azure-deploy` for the Discord revision
- [x] Verify Discord delivery, state recovery, one ready replica, and zero restarts
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
| Discord migration image | `az acr build --registry halseybotacr --platform linux/amd64 --no-push .` (run `cb7`) | Pass; nine tests and Tweepy removed | 2026-08-25T22:29Z |
| Discord webhook | Send mention-safe, embed-suppressed validation message using Key Vault secret | Pass; HTTP 204 | 2026-08-25T22:30Z |
| Discord source checks | `python3 -m py_compile main.py tests/test_main.py`; `bash -n deploy.sh`; `git diff --check` | Pass | 2026-08-25T22:29Z |
| Discord Azure target | Verify authenticated subscription, Container App, ACR, Key Vault secret, single revision, disabled ingress, and fixed one-replica scale | Pass | 2026-08-25T22:31Z |
| Discord managed identity | Confirm the live Container App principal has Key Vault secret `Get` and `List` access | Pass | 2026-08-25T22:31Z |
| Discord Azure Policy | `az policy assignment list --subscription 91bb5510-5bb1-4f85-a022-12f907612b87` | Pass; only Defender default assignment | 2026-08-25T22:31Z |
| Discord IaC validation/what-if | No resource or IaC changes; application revision only | Not applicable | 2026-08-25T22:31Z |
| Discord production deployment | ACR build `cb8`; deploy image `20260825223332-55f1ecb` | Pass | 2026-08-25T22:35Z |
| Discord live revision | Verify `halseybot--0000015`, one ready replica, zero restarts, no ingress, and fixed one-replica scale | Pass | 2026-08-25T22:36Z |
| Pending Capitol delivery | Verify one bulk alert and all seven missing products logged as `Notified Discord` | Pass | 2026-08-25T22:36Z |
| Capitol state recovery | Download `capitol-halsey-products-us.csv` after acknowledgements and count products | Pass; restored from 21 to 28 | 2026-08-25T22:36Z |
| Rich Discord embed image | `az acr build --registry halseybotacr --platform linux/amd64 --no-push .` (run `cb9`) | Pass; ten tests including image and no-image payloads | 2026-08-25T22:38Z |
| Rich embed source checks | `python3 -m py_compile main.py tests/test_main.py`; `bash -n deploy.sh`; `git diff --check` | Pass | 2026-08-25T22:38Z |
| Rich embed Azure target | Verify subscription, running Container App, disabled ingress, single revision, fixed one-replica scale, ACR build `cb9`, and policy assignments | Pass | 2026-08-25T22:40Z |
| Rich embed production deployment | ACR build `cbb`; deploy image `20260825224236-872eca1` | Pass after one transient concurrent-write retry | 2026-08-25T22:43Z |
| Rich embed live revision | Verify `halseybot--0000016` is healthy and running | Pass | 2026-08-25T22:43Z |
| Seven-item rich replay | Fetch the seven requested Capitol products and post one native image embed per product | Pass; seven HTTP successes and seven primary images | 2026-08-25T22:44Z |

### Live Role Verification

- Container App identity `06f8ad24-606e-4264-a42c-977a9114bc90` retains Key Vault
  secret `Get` and `List` access for the storage connection string and Discord webhook.
- Blob Storage and ACR continue using their existing secret-backed configuration; no RBAC
  or resource changes were introduced by this application revision.
- **Status:** Pass

**Validated by:** `azure-validate` workflow

**Validation timestamp:** 2026-08-25T22:40Z

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

- **Status:** Verified for validation hand-off
- **Backend:** Python compilation, Bash syntax, diff checks, and nine unit tests passed
  in Azure Container Registry `linux/amd64` no-push build `cb7`.
- **UI:** Not applicable; this is a background worker with ingress disabled.
- **External feeds:** The Capitol Halsey collection feed returns product data. Girl in
  the Tower correctly returns `401` while password-protected and will use controlled
  retries until it opens.
- **Discord:** The Key Vault-backed webhook accepted a real validation message with
  HTTP `204`; mentions and automatic embeds were disabled.
- **Build:** ACR Task run `cb7` succeeded on 2026-08-25.

---

## 11. Next Steps

> Current: Rich embeds deployed

1. Monitor normal Discord notifications and five-minute store heartbeats.
2. Keep the Discord webhook and destination channel active.
