import tweepy
import csv
import io
import os
import asyncio
import aiohttp
import tweepy
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load environment variables from .env file for local development
#load_dotenv()


def initialiseBlobStorage(connection_string):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client('merchbotproducts')

    return container_client

def initialise():
    # Halsey Watch Twitter API credentials
    API_KEY = os.getenv("api-key")
    API_SECRET_KEY = os.getenv("api-key-secret")
    ACCESS_TOKEN = os.getenv("access-token")
    ACCESS_TOKEN_SECRET = os.getenv("access-token-secret")
    BEARER_TOKEN = os.getenv("bearer-token")


    # Set up tweepy client for OAuth 2.0 User Context
    client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True)

    return client

# EU URL
url_EU = 'https://www.halseymusicstore.eu'
previous_products_file_EU = 'previous_productsEU.csv'

# US URL
url_US = 'https://www.halseymusicstore.com'
previous_products_file_US = 'previous_productsUS.csv'

# UK URL 
url_UK = 'https://www.halseymusicstore.co.uk'
previous_products_file_UK = 'previous_productsUK.csv'

global container_client
global halseyWatch



def read_previous_products(file_path):
    blob_client = container_client.get_blob_client(os.path.basename(file_path))
    if blob_client.exists():
        try:
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            reader = csv.reader(content.splitlines())
            return {rows[0]: rows[1] == 'True' for rows in reader}
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


def tweet(product, status, url):
    try:
        title = product['title'].title()
        handle = product['handle']

        price = product['variants'][0]['price']

        if status == 'OUT OF STOCK':
            link = ''
        elif 'Signed' in title:
            link = f"🔗 Instant Checkout \n {url}/cart/{product['variants'][0]['id']}:1"
        else:
            link = f"🔗 {url}/products/{handle}"

        if url == url_EU:
            currency = "€"
            flag = "🇪🇺"

        elif url == url_UK:
            currency = "£"
            flag = "🇬🇧"
        else:
            currency = "$"
            flag = "🇺🇸"

        tweet_text = f"{flag} {status.upper()} {flag}\n{title} - {currency}{price}\n{link}"
        test_text = f"🛠️ TESTING 🛠️\n{title} - {currency}{price}\n{link}"

        response = halseyWatch.create_tweet(text=tweet_text)
        

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(f"Tweeted: {test_text}")
    except tweepy.TweepyException as e:
        print(f"Error tweeting: {e}")

async def fetch_products(session, url):
    async with session.get(url + "/products.json") as response:
        response.raise_for_status()
        return await response.json()

async def check_for_new_products(file_path, url):
    previous_products = read_previous_products(file_path)
    try:
        async with aiohttp.ClientSession() as session:
            data = await fetch_products(session, url)
        
        current_products = {}
        for item in data['products']:
            title = item['title']
            current_products[title] = any(variant['available'] for variant in item['variants'])
        
        current_products = {}
        for item in data['products']:
            title = item['title']
            current_products[title] = any(variant['available'] for variant in item['variants'])
        
        new_products = set(current_products.keys()) - set(previous_products.keys())
        restocked_products = {title for title in current_products if title in previous_products and not previous_products[title] and current_products[title]}
        out_of_stock_products = {title for title in previous_products if title in current_products and previous_products[title] and not current_products[title]}
        unchanged_products = {title for title in current_products if title in previous_products and previous_products[title] == current_products[title]}


        for item in data['products']:
            title = item['title']
            status = "" 
            if title in unchanged_products:
                #print(f"Product unchanged: {title}")
                status = "UNCHANGED"
            elif title in new_products and current_products[title]:
                #print(f"New product added: {title}")
                status = "NEW PRODUCT"
            elif title in new_products and not current_products[title]:
                #print(f"New product added but out of stock: {title}")
                status = "NEW PRODUCT (OUT OF STOCK)"
            elif title in restocked_products:
                #print(f"Product back in stock: {title}")
                status = "BACK IN STOCK"
            elif title in out_of_stock_products:
                #print(f"Product out of stock: {title}")
                status = "OUT OF STOCK"

            print(status)

            if status != "UNCHANGED":
               tweet(item, status, url)
            
        if current_products != previous_products:
            write_current_products(file_path, current_products)

        print("ran" + url)
    except aiohttp.ClientError as e:
        print(f"Error fetching products: {e}")

async def run_checks():
    while True:
        await asyncio.gather(
            check_for_new_products(file_path=previous_products_file_US, url=url_US),
            check_for_new_products(file_path=previous_products_file_UK, url=url_UK),
            check_for_new_products(file_path=previous_products_file_EU, url=url_EU)
        )
        await asyncio.sleep(0.5)  # Sleep for half a second

async def main():
    global container_client
    global halseyWatch
    
    CONNECTION_STRING = os.getenv("connection-string")

    if not CONNECTION_STRING:
        raise ValueError("Connection string is missing!")

    halseyWatch = initialise()
    container_client = initialiseBlobStorage(CONNECTION_STRING)
    await run_checks()

if __name__ == "__main__":
    print("🟢 Script is running directly")
    asyncio.run(main())