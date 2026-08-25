import unittest
from unittest.mock import patch

from main import (
    Store,
    build_tweet_text,
    calculate_retry_delay,
    classify_products,
)


def product(handle: str, available: bool, price: str = "20.00") -> dict:
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


class TweetFormattingTests(unittest.TestCase):
    def test_uses_locale_specific_product_link(self) -> None:
        store = Store(
            region="EU",
            base_url="https://www.girlinthetower.com/en-eu",
            feed_path="/products.json?limit=250",
            state_blob="state.csv",
            currency="€",
            flag="🇪🇺",
            announce_initial_products=True,
        )

        text = build_tweet_text(product("tower-shirt", True), "NEW PRODUCT", store)

        self.assertIn("€20.00", text)
        self.assertIn(
            "https://www.girlinthetower.com/en-eu/products/tower-shirt", text
        )


if __name__ == "__main__":
    unittest.main()
