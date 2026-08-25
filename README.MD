# HalseyBot

HalseyBot is an asynchronous Python worker that monitors the Girl in the Tower
Shopify storefront and posts product and inventory changes to Twitter. It runs as
one always-on Azure Container Apps Consumption replica.

## Storefronts

| Region | Feed | State blob | Initial behavior |
|--------|------|------------|------------------|
| EU | `https://www.girlinthetower.com/en-eu/products.json` | `girlinthetower-products-eu.csv` | Announce all products |
| UK | `https://www.girlinthetower.com/en-uk/products.json` | `girlinthetower-products-uk.csv` | Announce all products |
| US | `https://www.girlinthetower.com/products.json` | `girlinthetower-products-us.csv` | Announce all products |
| Capitol US | `https://shop.capitolmusic.com/collections/halsey/products.json` | `capitol-halsey-products-us.csv` | Silent baseline |

The store is currently password-protected. The worker treats `401` and `403`
responses as expected temporary conditions and retries every five minutes. Once
the store is public, it automatically switches to the normal polling interval.
When that happens, the initial Girl in the Tower catalog is announced. The existing
Capitol Halsey collection is saved silently, and only later changes are announced.

## Runtime behavior

- Each storefront is monitored independently.
- Successful checks run every 10 seconds by default.
- Rate limits honor `Retry-After`.
- Transient failures use capped exponential backoff and jitter.
- Blob Storage and Twitter SDK calls run outside the asyncio event loop.
- Product state advances only after queued tweets are published successfully.
- HTTP ingress is disabled because this is a background worker, not a web app.
- Routine success logs are emitted every five minutes rather than every poll.
- The Python dependency graph and base container digest are pinned.

Optional environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `POLL_INTERVAL_SECONDS` | `10` | Delay after successful checks |
| `PROTECTED_RETRY_SECONDS` | `300` | Delay while the store is protected |
| `RATE_LIMIT_RETRY_SECONDS` | `60` | Delay for `429` without `Retry-After` |
| `MAX_BACKOFF_SECONDS` | `300` | Maximum transient-failure delay |
| `HEARTBEAT_INTERVAL_SECONDS` | `300` | Routine success-log interval |
| `DRY_RUN` | `false` | Log tweets without publishing |
| `KEY_VAULT_URL` | `https://halseybot-keys.vault.azure.net/` | Secret source |

## Local checks

```bash
python -m unittest discover -s tests -v
python -m py_compile main.py
```

Running the full worker locally also requires access to the Azure Key Vault and
Blob Storage resources:

```bash
python main.py
```

## Deployment

The deployment script uses Azure Container Registry Tasks to build an immutable
`linux/amd64` image. The Docker build runs the test suite before publishing the image.
The script then configures the Container App as a single-revision worker without
ingress, clears all autoscale triggers, hard-caps one replica, and waits for the
revision to become healthy.

```bash
./deploy.sh
```

View application logs:

```bash
az containerapp logs show \
  --name halseybot \
  --resource-group halseybot-rg \
  --tail 100 \
  --format text
```

View platform events:

```bash
az containerapp logs show \
  --name halseybot \
  --resource-group halseybot-rg \
  --type system \
  --tail 100 \
  --format json
```
