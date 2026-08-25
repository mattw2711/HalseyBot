import unittest
from unittest.mock import patch

from main import (
    DiscordWebhookError,
    STATUS_STYLE,
    STORES,
    Store,
    build_discord_payload,
    calculate_retry_delay,
    classify_products,
    publish_discord_notification,
)


def product(
    handle: str,
    available: bool,
    price: str = "20.00",
    image_url: str | None = "https://cdn.example/product.jpg",
) -> dict:
    return {
        "title": handle.replace("-", " "),
        "handle": handle,
        "variants": [
            {
                "available": available,
                "price": price,
                "id": f"{handle}-variant",
            }
        ],
        "images": [{"src": image_url}] if image_url else [],
    }


class ProductClassificationTests(unittest.TestCase):
    def test_new_state_file_establishes_baseline_without_alerts(self) -> None:
        products = [product("existing-one", True), product("existing-two", False)]

        current, changes = classify_products(
            None, products, announce_initial_products=False
        )

        self.assertEqual(
            current, {"existing-one": True, "existing-two": False}
        )
        self.assertEqual(changes, [])

    def test_new_store_can_announce_initial_catalog(self) -> None:
        products = [product("launch-item", True), product("preview", False)]

        _, changes = classify_products(
            None, products, announce_initial_products=True
        )

        self.assertEqual(
            [(item["handle"], status) for item, status in changes],
            [
                ("launch-item", "NEW PRODUCT"),
                ("preview", "NEW PRODUCT (OUT OF STOCK)"),
            ],
        )

    def test_classifies_new_and_inventory_changes(self) -> None:
        previous = {
            "restocked": False,
            "sold-out": True,
            "unchanged": True,
        }
        products = [
            product("restocked", True),
            product("sold-out", False),
            product("unchanged", True),
            product("new-live", True),
            product("new-unavailable", False),
        ]

        current, changes = classify_products(
            previous, products, announce_initial_products=True
        )

        self.assertEqual(
            current,
            {
                "restocked": True,
                "sold-out": False,
                "unchanged": True,
                "new-live": True,
                "new-unavailable": False,
            },
        )
        self.assertEqual(
            [(item["handle"], status) for item, status in changes],
            [
                ("restocked", "BACK IN STOCK"),
                ("sold-out", "OUT OF STOCK"),
                ("new-live", "NEW PRODUCT"),
                ("new-unavailable", "NEW PRODUCT (OUT OF STOCK)"),
            ],
        )


class RetryTests(unittest.TestCase):
    @patch("main.PROTECTED_RETRY_SECONDS", 300)
    def test_password_protection_uses_slow_retry(self) -> None:
        self.assertEqual(calculate_retry_delay(401, failures=10), 300)

    @patch("main.POLL_INTERVAL_SECONDS", 10)
    @patch("main.RATE_LIMIT_RETRY_SECONDS", 60)
    @patch("main.MAX_BACKOFF_SECONDS", 300)
    def test_rate_limit_honors_retry_after_with_cap(self) -> None:
        self.assertEqual(
            calculate_retry_delay(429, failures=1), 60
        )
        self.assertEqual(
            calculate_retry_delay(429, failures=1, retry_after=45), 45
        )
        self.assertEqual(
            calculate_retry_delay(429, failures=1, retry_after=600), 300
        )

    @patch("main.POLL_INTERVAL_SECONDS", 10)
    @patch("main.MAX_BACKOFF_SECONDS", 300)
    def test_transient_failures_back_off_exponentially(self) -> None:
        self.assertEqual(calculate_retry_delay(None, failures=1), 10)
        self.assertEqual(calculate_retry_delay(None, failures=4), 80)
        self.assertEqual(calculate_retry_delay(None, failures=10), 300)


class NotificationFormattingTests(unittest.TestCase):
    def test_builds_rich_embed_with_locale_link_and_image(self) -> None:
        store = Store(
            display_name="Girl in the Tower EU",
            region="EU",
            base_url="https://www.girlinthetower.com/en-eu",
            feed_path="/products.json?limit=250",
            state_blob="state.csv",
            webhook_secret="discord-webhook-girl-eu",
            currency="€",
            flag="🇪🇺",
            announce_initial_products=True,
        )

        payload = build_discord_payload(
            product("tower-shirt", True), "NEW PRODUCT", store
        )
        embed = payload["embeds"][0]

        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertEqual(payload["content"], "## ✨ NEW DROP")
        self.assertEqual(embed["color"], STATUS_STYLE["NEW PRODUCT"][2])
        self.assertEqual(embed["fields"][0]["value"], "**€20.00**")
        self.assertEqual(
            embed["fields"][1]["value"], "🇪🇺 Girl in the Tower EU"
        )
        self.assertEqual(
            embed["url"],
            "https://www.girlinthetower.com/en-eu/products/tower-shirt",
        )
        self.assertEqual(
            embed["image"]["url"], "https://cdn.example/product.jpg"
        )

    def test_omits_image_when_storefront_has_none(self) -> None:
        store = Store(
            display_name="Example Store",
            region="US",
            base_url="https://example.com",
            feed_path="/products.json",
            state_blob="state.csv",
            webhook_secret="discord-webhook-example",
            currency="$",
            flag="🇺🇸",
            announce_initial_products=True,
        )

        payload = build_discord_payload(
            product("no-image", True, image_url=None), "NEW PRODUCT", store
        )

        self.assertNotIn("image", payload["embeds"][0])

    def test_every_store_has_a_unique_webhook_and_announces_initially(self) -> None:
        webhook_secrets = {store.webhook_secret for store in STORES}

        self.assertEqual(len(webhook_secrets), len(STORES))
        self.assertTrue(all(store.announce_initial_products for store in STORES))

    def test_sold_out_message_is_visually_distinct(self) -> None:
        store = Store(
            display_name="Example Store",
            region="US",
            base_url="https://example.com",
            feed_path="/products.json",
            state_blob="state.csv",
            webhook_secret="discord-webhook-example",
            currency="$",
            flag="🇺🇸",
            announce_initial_products=True,
        )

        payload = build_discord_payload(
            product("sold-out", False), "OUT OF STOCK", store
        )

        self.assertEqual(payload["content"], "## 💨 SOLD OUT")
        self.assertEqual(
            payload["embeds"][0]["fields"][2]["value"],
            "Currently sold out",
        )


class FakeResponse:
    def __init__(
        self,
        status: int,
        *,
        body: str = "",
        retry_after: str | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.headers = {}
        if retry_after is not None:
            self.headers["Retry-After"] = retry_after

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def json(self, content_type: None = None) -> dict[str, float]:
        del content_type
        return {"retry_after": float(self.headers.get("Retry-After", "0"))}

    async def text(self) -> str:
        return self.body


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.url = ""
        self.payload: dict | None = None

    def post(self, url: str, *, json: dict) -> FakeResponse:
        self.url = url
        self.payload = json
        return self.response


class DiscordPublishingTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_safely_to_discord(self) -> None:
        session = FakeSession(FakeResponse(204))
        store = Store(
            display_name="Example Store",
            region="US",
            base_url="https://example.com",
            feed_path="/products.json",
            state_blob="state.csv",
            webhook_secret="discord-webhook-example",
            currency="$",
            flag="🇺🇸",
            announce_initial_products=True,
        )

        await publish_discord_notification(
            session, "https://discord.example/webhook", product("new-item", True),
            "NEW PRODUCT", store
        )

        self.assertEqual(session.url, "https://discord.example/webhook")
        self.assertEqual(session.payload["allowed_mentions"], {"parse": []})
        self.assertEqual(
            session.payload["embeds"][0]["url"],
            "https://example.com/products/new-item",
        )
        self.assertEqual(
            session.payload["embeds"][0]["image"]["url"],
            "https://cdn.example/product.jpg",
        )

    async def test_surfaces_discord_retry_after(self) -> None:
        session = FakeSession(
            FakeResponse(429, body="rate limited", retry_after="2.5")
        )
        store = Store(
            display_name="Example Store",
            region="US",
            base_url="https://example.com",
            feed_path="/products.json",
            state_blob="state.csv",
            webhook_secret="discord-webhook-example",
            currency="$",
            flag="🇺🇸",
            announce_initial_products=True,
        )

        with self.assertRaises(DiscordWebhookError) as raised:
            await publish_discord_notification(
                session,
                "https://discord.example/webhook",
                product("new-item", True),
                "NEW PRODUCT",
                store,
            )

        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(raised.exception.retry_after, 2.5)


if __name__ == "__main__":
    unittest.main()
