# HalseyBot

HalseyBot is an asynchronous Python worker that monitors the Girl in the Tower and
Capitol Music Shopify storefronts and posts product and inventory changes to Discord.
It runs as one always-on Azure Container Apps Consumption replica.

## Storefronts

| Region | Discord channel | Feed | State blob |
|--------|-----------------|------|------------|
| EU | `#girl-eu` | `https://www.girlinthetower.com/en-eu/products.json` | `girlinthetower-products-eu.csv` |
| UK | `#girl-uk` | `https://www.girlinthetower.com/en-uk/products.json` | `girlinthetower-products-uk.csv` |
| US | `#girl-us` | `https://www.girlinthetower.com/products.json` | `girlinthetower-products-us.csv` |
| Capitol US | `#capitol-us` | `https://shop.capitolmusic.com/collections/halsey/products.json` | `capitol-halsey-products-us.csv` |

The store is currently password-protected. The worker treats `401` and `403`
responses as expected temporary conditions and retries every five minutes. Once
the store is public, it automatically switches to the normal polling interval.
When a state blob does not exist, the storefront's complete first successful catalog
is announced before its new state is saved.

## Runtime behavior

- Each storefront is monitored independently.
- Successful checks run every 10 seconds by default.
- Rate limits honor `Retry-After`.
- Transient failures use capped exponential backoff and jitter.
- Blob Storage calls run outside the asyncio event loop.
- Each storefront has its own acknowledged queue and Discord publisher, so one
  channel's rate limit or outage does not delay another location.
- Product state advances only after queued Discord notifications are delivered.
- Discord mentions are disabled. High-visibility embeds use status-specific banners
  and colors plus the primary image, price, store, availability, and shopping link.
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
| `DRY_RUN` | `false` | Log Discord notifications without publishing |
| `KEY_VAULT_URL` | `https://halseybot-keys.vault.azure.net/` | Secret source |

The four Discord webhook URLs are stored in Key Vault as
`discord-webhook-girl-eu`, `discord-webhook-girl-uk`,
`discord-webhook-girl-us`, and `discord-webhook-capitol-us`. The Container App
retrieves them through its existing managed identity; they are never stored in source
control or Container App environment variables.

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
