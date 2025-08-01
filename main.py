from urllib import response
import tweepy
import csv
import io
import os
import asyncio
import aiohttp
import tweepy
from azure.storage.blob import BlobServiceClient
from azure.identity import ManagedIdentityCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import itertools

counter = itertools.count()
import os

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

keyvault_url = "https://halseybot-keys.vault.azure.net/"
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=keyvault_url, credential=credential)


def initialiseBlobStorage(connection_string):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client("merchbotproducts")

    return container_client


def initialise():
    # Halsey Watch Twitter API credentials
    API_KEY = secret_client.get_secret("api-key").value
    API_SECRET_KEY = secret_client.get_secret("api-key-secret").value
    ACCESS_TOKEN = secret_client.get_secret("access-token").value
    ACCESS_TOKEN_SECRET = secret_client.get_secret("access-token-secret").value
    BEARER_TOKEN = secret_client.get_secret("bearer-token").value

    # Set up tweepy client for OAuth 2.0 User Context
    client = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET_KEY,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )

    return client


# EU URL
url_EU = "https://www.halseymusicstore.eu"
previous_products_file_EU = "previous_productsEU.csv"

# US URL
url_US = "https://www.halseymusicstore.com"
previous_products_file_US = "previous_productsUS.csv"

# UK URL
url_UK = "https://www.halseymusicstore.co.uk"
previous_products_file_UK = "previous_productsUK.csv"

# Global URL
url_Global = "https://www.halseymusicstore.com"
previous_products_file_Global = "previous_productsGlobal.csv"

# Badlands US
url_Badlands = "https://shop.visitbadlands.com"
previous_products_file_Badlands = "previous_productsBadlands.csv"

# Badlands uk
url_Badlands_uk = "https://shopuk.visitbadlands.com"
previous_products_file_Badlands_uk = "previous_productsBadlands_uk.csv"

# Badlands eu
url_Badlands_eu = "https://shopeu.visitbadlands.com"
previous_products_file_Badlands_eu = "previous_productsBadlands_eu.csv"


global container_client
global halseyWatch
tweet_queue = asyncio.PriorityQueue()

PRIORITY_MAP = {
    "NEW PRODUCT": 0,
    "BACK IN STOCK": 1,
    "OUT OF STOCK": 2,
    "NEW PRODUCT (OUT OF STOCK)": 2,
    "UNCHANGED": 3,
}


def read_previous_products(file_path):
    blob_client = container_client.get_blob_client(os.path.basename(file_path))
    if blob_client.exists():
        try:
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode("utf-8")
            reader = csv.reader(content.splitlines())
            return {rows[0]: rows[1] == "True" for rows in reader}
        except (csv.Error, IndexError):
            # Handle empty or malformed CSV file
            return {}
    return {}


def write_current_products(file_path, products):
    # Create an in-memory buffer
    output = io.StringIO()

    # Write products to the in-memory buffer as CSV
    writer = csv.writer(output)
    for title, available in products.items():
        writer.writerow([title, available])

    # Get the CSV content from the buffer
    csv_content = output.getvalue()
    output.close()

    # Upload the CSV content to Azure Blob Storage
    blob_client = container_client.get_blob_client(os.path.basename(file_path))
    blob_client.upload_blob(csv_content, overwrite=True)
    print(f"{file_path} uploaded to Azure Blob Storage.")


def tweet(product, status, url, region):
    title = product["title"].title()
    handle = product["handle"]
    price = product["variants"][0]["price"]

    if status == "OUT OF STOCK":
        link = ""
    elif "Signed" in title:
        link = f"🔗 Instant Checkout \n {url}/cart/{product['variants'][0]['id']}:1"
    else:
        link = f"🔗 {url}/products/{handle}"

    # Set currency and flag depending on url
    if region == "EU":
        currency = "€"
        flag = "🇪🇺"
    elif region == "UK":
        currency = "£"
        flag = "🇬🇧"
    elif region == "US":
        currency = "$"
        flag = "🇺🇸"
    else:
        currency = "€"
        flag = "🌐"

    tweet_text = f"{flag} {status.upper()} {flag}\n{title} - {currency}{price}\n{link}"

    if DRY_RUN:
        print(f"[DRY RUN] Would tweet: {tweet_text}")
        return

    try:
        response = halseyWatch.create_tweet(text=tweet_text)
        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")
        print(f"Tweeted: {tweet_text}")
    except tweepy.TweepyException as e:
        print(f"Error tweeting: {e}")


async def fetch_products(session, url):
    async with session.get(url + "/products.json") as response:
        response.raise_for_status()
        return await response.json()


async def check_for_new_products(file_path, url, region):
    previous_products = read_previous_products(file_path)
    try:
        async with aiohttp.ClientSession() as session:
            data = await fetch_products(session, url)

        current_products = {}
        for item in data["products"]:
            title = item["title"]
            current_products[title] = any(
                variant["available"] for variant in item["variants"]
            )

        new_products = set(current_products.keys()) - set(previous_products.keys())
        restocked_products = {
            title
            for title in current_products
            if title in previous_products
            and not previous_products[title]
            and current_products[title]
        }
        out_of_stock_products = {
            title
            for title in previous_products
            if title in current_products
            and previous_products[title]
            and not current_products[title]
        }
        unchanged_products = {
            title
            for title in current_products
            if title in previous_products
            and previous_products[title] == current_products[title]
        }

        # Send alert tweet if more than 5 new products
        if DRY_RUN:
            if len(new_products) > 5:
                print("[DRY RUN] Would tweet: 🚨 Lots of new items have dropped! 🚨")
        else:
            if len(new_products) > 5:
                try:
                    response = halseyWatch.create_tweet(text="🚨 Lots of new items have dropped! Individual posts to follow 🚨")
                    if response.errors:
                        raise Exception(f"Request returned an error: {response.errors}")
                    print("Tweeted: 🚨 Lots of new items have dropped!")
                except tweepy.TweepyException as e:
                    print(f"Error tweeting alert: {e}")


        for item in data["products"]:
            title = item["title"]
            status = ""
            if title in unchanged_products:
                # print(f"Product unchanged: {title}")
                status = "UNCHANGED"
            elif title in new_products and current_products[title]:
                # print(f"New product added: {title}")
                status = "NEW PRODUCT"
            elif title in new_products and not current_products[title]:
                # print(f"New product added but out of stock: {title}")
                status = "NEW PRODUCT (OUT OF STOCK)"
            elif title in restocked_products:
                # print(f"Product back in stock: {title}")
                status = "BACK IN STOCK"
            elif title in out_of_stock_products:
                # print(f"Product out of stock: {title}")
                status = "OUT OF STOCK"

            # print(status)

            if status != "UNCHANGED":
                priority = PRIORITY_MAP.get(status, 99)
                await tweet_queue.put((priority, next(counter), (item, status, url, region)))

        if current_products != previous_products:
            write_current_products(file_path, current_products)

        print("Ran " + url)
    except aiohttp.ClientError as e:
        print(f"Error fetching products: {e}")


async def run_checks():
    while True:
        await asyncio.gather(
            check_for_new_products(file_path=previous_products_file_Badlands, url=url_Badlands, region="US"),
            check_for_new_products(file_path=previous_products_file_Badlands_eu, url=url_Badlands_eu, region="EU"),
            check_for_new_products(file_path=previous_products_file_Badlands_uk, url=url_Badlands_uk, region="UK"),
            check_for_new_products(file_path=previous_products_file_EU, url=url_EU, region="EU"),
            check_for_new_products(file_path=previous_products_file_UK, url=url_UK, region="UK"),
            check_for_new_products(file_path=previous_products_file_US, url=url_US, region="US"),
            check_for_new_products(file_path=previous_products_file_Global, url=url_Global, region="Global"),
        )
        await asyncio.sleep(0.5)  # Sleep for half a second


async def tweet_worker():
    while True:
        _, _, (product, status, url, region) = await tweet_queue.get()
        try:
            tweet(product, status, url, region)
            await asyncio.sleep(2)  # Regular delay
        except tweepy.TooManyRequests:
            print("Rate limit hit. Sleeping for 15 minutes.")
            await asyncio.sleep(15 * 60)
        except tweepy.TweepyException as e:
            print(f"Tweet error: {e}")
            await asyncio.sleep(10)
        finally:
            tweet_queue.task_done()


async def main():
    global container_client
    global halseyWatch

    CONNECTION_STRING = secret_client.get_secret("connection-string").value

    halseyWatch = initialise()
    container_client = initialiseBlobStorage(CONNECTION_STRING)
    asyncio.create_task(tweet_worker())
    await run_checks()


if __name__ == "__main__":
    print("🟢 Script is running directly")
    asyncio.run(main())
