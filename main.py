import requests
import time
import tweepy
import csv
import os
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
import json

# URL to fetch products
url = 'https://www.halseymusicstore.eu/products.json'
previous_products_file = 'previous_products.csv'

# Twitter API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET_KEY = os.getenv('API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')

account_url = "https://halseybot9e83.blob.core.windows.net"
default_credential = DefaultAzureCredential()

# Create the BlobServiceClient object
blob_service_client = BlobServiceClient(account_url, credential=default_credential)
container_client = blob_service_client.get_container_client('merchbotproducts')

# Set up tweepy client for OAuth 2.0 User Context
client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)


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
    blob_client = container_client.get_blob_client(os.path.basename(file_path))
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    print(f"{file_path} uploaded to Azure Blob Storage.")


def tweet(product, status):
    try:
        title = product['title'].title()
        price = product['variants'][0]['price']
        link = f"https://www.halseymusicstore.eu/products/{product['handle']}"
        tweet_text = f"🚨 {status.upper()} 🚨\n{title} - €{price}\n🔗 {link}"
        
        response = client.create_tweet(text=tweet_text)

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(f"Tweeted: {tweet_text}")
        print(json.dumps(response.data, indent=4, sort_keys=True))
    except Exception as e:
        print(f"Error tweeting: {e}")

def check_for_new_products():
    previous_products = read_previous_products(previous_products_file)
    try:
        r = requests.get(url)
        r.raise_for_status()  # Raise an HTTPError for bad responses
        data = r.json()
        
        current_products = {item['title']: item['variants'][0]['available'] for item in data['products']}
        
        new_products = set(current_products.keys()) - set(previous_products.keys())
        restocked_products = {title for title in current_products if title in previous_products and not previous_products[title] and current_products[title]}
        out_of_stock_products = {title for title in previous_products if title in current_products and previous_products[title] and not current_products[title]}
        
        for product in data['products']:
            title = product['title']
            if title in new_products and product['variants'][0]['available']:
                print(f"New product added: {title}")
                #tweet(product, "NEW PRODUCT")
            elif title in new_products and not product['variants'][0]['available']:
                print(f"New product added but out of stock: {title}")
                #tweet(product, "NEW PRODUCT (OUT OF STOCK)")
            elif title in restocked_products:
                print(f"Product back in stock: {title}")
                #tweet(product, "BACK IN STOCK")
            elif title in out_of_stock_products:
                print(f"Product out of stock: {title}")
                #tweet(product, "OUT OF STOCK")
        
        write_current_products(previous_products_file, current_products)
    except requests.RequestException as e:
        print(f"Error fetching products: {e}")

if __name__ == '__main__':
    check_for_new_products()