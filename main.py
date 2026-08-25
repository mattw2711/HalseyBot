from __future__ import annotations

import asyncio
import csv
import io
import itertools
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import aiohttp
import tweepy
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient, ContainerClient


DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
KEY_VAULT_URL = os.getenv(
    "KEY_VAULT_URL", "https://halseybot-keys.vault.azure.net/"
)
POLL_INTERVAL_SECONDS = max(1.0, float(os.getenv("POLL_INTERVAL_SECONDS", "10")))
PROTECTED_RETRY_SECONDS = max(
    POLL_INTERVAL_SECONDS, float(os.getenv("PROTECTED_RETRY_SECONDS", "300"))
)
MAX_BACKOFF_SECONDS = max(
    POLL_INTERVAL_SECONDS, float(os.getenv("MAX_BACKOFF_SECONDS", "300"))
)
RATE_LIMIT_RETRY_SECONDS = max(
    POLL_INTERVAL_SECONDS, float(os.getenv("RATE_LIMIT_RETRY_SECONDS", "60"))
)
HEARTBEAT_INTERVAL_SECONDS = max(
    POLL_INTERVAL_SECONDS, float(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "300"))
)


@dataclass(frozen=True)
class Store:
    region: str
    base_url: str
    feed_path: str
    state_blob: str
    currency: str
    flag: str
    announce_initial_products: bool

    @property
    def products_url(self) -> str:
        return f"{self.base_url}{self.feed_path}"


STORES = (
    Store(
        region="EU",
        base_url="https://www.girlinthetower.com/en-eu",
        feed_path="/products.json?limit=250",
        state_blob="girlinthetower-products-eu.csv",
        currency="€",
        flag="🇪🇺",
        announce_initial_products=True,
    ),
    Store(
        region="UK",
        base_url="https://www.girlinthetower.com/en-uk",
        feed_path="/products.json?limit=250",
        state_blob="girlinthetower-products-uk.csv",
        currency="£",
        flag="🇬🇧",
        announce_initial_products=True,
    ),
    Store(
        region="US",
        base_url="https://www.girlinthetower.com",
        feed_path="/products.json?limit=250",
        state_blob="girlinthetower-products-us.csv",
        currency="$",
        flag="🇺🇸",
        announce_initial_products=True,
    ),
    Store(
        region="CAPITOL US",
        base_url="https://shop.capitolmusic.com",
        feed_path="/collections/halsey/products.json?limit=250",
        state_blob="capitol-halsey-products-us.csv",
        currency="$",
        flag="🇺🇸",
        announce_initial_products=False,
    ),
)

PRIORITY_MAP = {
    "NEW PRODUCT": 0,
    "BACK IN STOCK": 1,
    "OUT OF STOCK": 2,
    "NEW PRODUCT (OUT OF STOCK)": 2,
}

Product = dict[str, Any]
TweetQueue = asyncio.PriorityQueue[
    tuple[int, int, tuple[Product, str, Store, asyncio.Future[None]]]
]


class StoreFetchError(Exception):
    def __init__(
        self,
        status: int | None,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def calculate_retry_delay(
    status: int | None,
    failures: int,
    retry_after: float | None = None,
) -> float:
    if status in {401, 403}:
        return PROTECTED_RETRY_SECONDS
    if status == 429:
        requested_delay = retry_after or RATE_LIMIT_RETRY_SECONDS
        return min(
            MAX_BACKOFF_SECONDS,
            max(POLL_INTERVAL_SECONDS, requested_delay),
        )

    exponent = max(0, failures - 1)
    return min(MAX_BACKOFF_SECONDS, POLL_INTERVAL_SECONDS * (2**exponent))


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def read_previous_products(
    container_client: ContainerClient, blob_name: str
) -> dict[str, bool] | None:
    blob_client = container_client.get_blob_client(blob_name)
    if not blob_client.exists():
        return None

    content = blob_client.download_blob().readall().decode("utf-8")
    products: dict[str, bool] = {}
    for row in csv.reader(content.splitlines()):
        if not row or row[0] == "handle":
            continue
        if len(row) != 2 or row[1] not in {"True", "False"}:
            raise ValueError(f"Malformed product state in blob {blob_name}")
        products[row[0]] = row[1] == "True"
    return products


def write_current_products(
    container_client: ContainerClient,
    blob_name: str,
    products: dict[str, bool],
) -> None:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["handle", "available"])
    writer.writerows(sorted(products.items()))
    container_client.get_blob_client(blob_name).upload_blob(
        output.getvalue(), overwrite=True
    )


def classify_products(
    previous_products: dict[str, bool] | None,
    products: list[Product],
    announce_initial_products: bool,
) -> tuple[dict[str, bool], list[tuple[Product, str]]]:
    current_products: dict[str, bool] = {}
    changes: list[tuple[Product, str]] = []

    for product in products:
        handle = product["handle"]
        variants = product.get("variants", [])
        available = any(bool(variant.get("available")) for variant in variants)
        current_products[handle] = available

        if previous_products is None and not announce_initial_products:
            continue
        if previous_products is None or handle not in previous_products:
            status = "NEW PRODUCT" if available else "NEW PRODUCT (OUT OF STOCK)"
            changes.append((product, status))
        elif previous_products[handle] != available:
            status = "BACK IN STOCK" if available else "OUT OF STOCK"
            changes.append((product, status))

    return current_products, changes


async def fetch_products(
    session: aiohttp.ClientSession, store: Store
) -> list[Product]:
    async with session.get(store.products_url) as response:
        if response.status != 200:
            raise StoreFetchError(
                status=response.status,
                message=f"HTTP {response.status}",
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
            )

        payload = await response.json(content_type=None)
        products = payload.get("products")
        if not isinstance(products, list):
            raise ValueError("Store response did not contain a products list")
        return products


async def check_store(
    session: aiohttp.ClientSession,
    container_client: ContainerClient,
    tweet_queue: TweetQueue,
    sequence: itertools.count[int],
    store: Store,
) -> tuple[int, int, bool]:
    previous_products = await asyncio.to_thread(
        read_previous_products, container_client, store.state_blob
    )
    products = await fetch_products(session, store)
    current_products, changes = classify_products(
        previous_products, products, store.announce_initial_products
    )
    acknowledgements: list[asyncio.Future[None]] = []

    new_product_count = sum(
        status.startswith("NEW PRODUCT") for _, status in changes
    )
    if new_product_count > 5:
        alert = {
            "title": "Lots of new items have dropped!",
            "handle": "",
            "variants": [{"price": "", "available": True, "id": ""}],
        }
        acknowledgement = asyncio.get_running_loop().create_future()
        acknowledgements.append(acknowledgement)
        await tweet_queue.put((
            -1,
            next(sequence),
            (alert, "MULTIPLE NEW PRODUCTS", store, acknowledgement),
        ))

    for product, status in changes:
        acknowledgement = asyncio.get_running_loop().create_future()
        acknowledgements.append(acknowledgement)
        await tweet_queue.put(
            (
                PRIORITY_MAP.get(status, 99),
                next(sequence),
                (product, status, store, acknowledgement),
            )
        )

    if acknowledgements:
        await asyncio.gather(*acknowledgements)

    if previous_products is None or current_products != previous_products:
        await asyncio.to_thread(
            write_current_products,
            container_client,
            store.state_blob,
            current_products,
        )

    return len(products), len(changes), previous_products is None


def build_tweet_text(product: Product, status: str, store: Store) -> str:
    if status == "MULTIPLE NEW PRODUCTS":
        return "🚨 Lots of new items have dropped! Individual posts to follow 🚨"

    title = str(product["title"]).title()
    variants = product.get("variants", [])
    if not variants:
        raise ValueError(f"Product {product.get('handle', '<unknown>')} has no variants")

    variant = variants[0]
    if status == "OUT OF STOCK":
        link = ""
    elif "signed" in title.casefold():
        link = f"🔗 Instant Checkout\n{store.base_url}/cart/{variant['id']}:1"
    else:
        link = f"🔗 {store.base_url}/products/{product['handle']}"

    return (
        f"{store.flag} {status} {store.flag}\n"
        f"{title} - {store.currency}{variant['price']}\n{link}"
    ).rstrip()


def publish_tweet(
    twitter_client: tweepy.Client,
    product: Product,
    status: str,
    store: Store,
) -> None:
    tweet_text = build_tweet_text(product, status, store)
    if DRY_RUN:
        print(f"[DRY RUN] Would tweet: {tweet_text}", flush=True)
        return

    response = twitter_client.create_tweet(text=tweet_text)
    if response.errors:
        raise tweepy.TweepyException(f"Twitter returned errors: {response.errors}")
    print(f"Tweeted: {tweet_text}", flush=True)


async def tweet_worker(
    tweet_queue: TweetQueue, twitter_client: tweepy.Client
) -> None:
    while True:
        _, _, (product, status, store, acknowledgement) = await tweet_queue.get()
        retry_delay = 10.0
        try:
            while True:
                try:
                    await asyncio.to_thread(
                        publish_tweet,
                        twitter_client,
                        product,
                        status,
                        store,
                    )
                    if not acknowledgement.done():
                        acknowledgement.set_result(None)
                    await asyncio.sleep(2)
                    break
                except tweepy.TooManyRequests:
                    print(
                        "Twitter rate limit hit; retrying in 15 minutes.",
                        flush=True,
                    )
                    await asyncio.sleep(15 * 60)
                except tweepy.TweepyException as error:
                    print(
                        f"Tweet failed ({error}); retrying in "
                        f"{retry_delay:.0f}s.",
                        flush=True,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(MAX_BACKOFF_SECONDS, retry_delay * 2)
                except ValueError as error:
                    if not acknowledgement.done():
                        acknowledgement.set_exception(error)
                    break
        finally:
            tweet_queue.task_done()


async def monitor_store(
    session: aiohttp.ClientSession,
    container_client: ContainerClient,
    tweet_queue: TweetQueue,
    sequence: itertools.count[int],
    store: Store,
) -> None:
    await asyncio.sleep(random.uniform(0, 2))
    failures = 0
    next_heartbeat = 0.0

    while True:
        try:
            product_count, change_count, established_baseline = await check_store(
                session, container_client, tweet_queue, sequence, store
            )
            failures = 0
            delay = POLL_INTERVAL_SECONDS
            now = time.monotonic()
            if established_baseline or change_count or now >= next_heartbeat:
                activity = (
                    "established baseline"
                    if established_baseline
                    else f"queued {change_count} changes"
                )
                print(
                    f"[{store.region}] Checked {product_count} products; "
                    f"{activity}.",
                    flush=True,
                )
                next_heartbeat = now + HEARTBEAT_INTERVAL_SECONDS
        except StoreFetchError as error:
            failures += 1
            delay = calculate_retry_delay(
                error.status, failures, error.retry_after
            )
            print(
                f"[{store.region}] Store unavailable ({error}); "
                f"retrying in {delay:.0f}s.",
                flush=True,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, AzureError, ValueError) as error:
            failures += 1
            delay = calculate_retry_delay(None, failures)
            print(
                f"[{store.region}] Check failed ({error}); "
                f"retrying in {delay:.0f}s.",
                flush=True,
            )

        await asyncio.sleep(delay * random.uniform(0.9, 1.1))


def initialise_clients() -> tuple[
    BlobServiceClient, ContainerClient, tweepy.Client
]:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    try:
        connection_string = secret_client.get_secret("connection-string").value
        twitter_client = tweepy.Client(
            bearer_token=secret_client.get_secret("bearer-token").value,
            consumer_key=secret_client.get_secret("api-key").value,
            consumer_secret=secret_client.get_secret("api-key-secret").value,
            access_token=secret_client.get_secret("access-token").value,
            access_token_secret=secret_client.get_secret(
                "access-token-secret"
            ).value,
            wait_on_rate_limit=True,
        )
    finally:
        secret_client.close()
        credential.close()

    blob_service_client = BlobServiceClient.from_connection_string(
        connection_string
    )
    container_client = blob_service_client.get_container_client(
        "merchbotproducts"
    )
    return blob_service_client, container_client, twitter_client


async def main() -> None:
    blob_service_client, container_client, twitter_client = initialise_clients()
    tweet_queue: TweetQueue = asyncio.PriorityQueue()
    sequence = itertools.count()
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        "Accept": "application/json",
        "User-Agent": "HalseyBot/2.0 (+Azure Container Apps)",
    }

    try:
        async with aiohttp.ClientSession(
            timeout=timeout, headers=headers
        ) as session:
            await asyncio.gather(
                tweet_worker(tweet_queue, twitter_client),
                *(
                    monitor_store(
                        session,
                        container_client,
                        tweet_queue,
                        sequence,
                        store,
                    )
                    for store in STORES
                ),
            )
    finally:
        blob_service_client.close()


if __name__ == "__main__":
    print("Girl in the Tower monitor starting.", flush=True)
    asyncio.run(main())
