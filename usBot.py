import requests
import time
import tweepy
import csv
import os
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import json

# URL to fetch products
url = 'https://www.halseymusicstore.com/products.json'
previous_products_fileUS = 'previous_productsUS.csv'

API_KEY = '6a0QlOiSUGsMlVDi75W3HWH2M'
API_SECRET_KEY = 'hqAHoYz49xjjQhoKFaazs5kX7Nmph8SC2H1p0NP9oR49lGPsDJ'
ACCESS_TOKEN = '1834716671203737600-F6MwqGtxFHXtltf0RHdNVYrtGrUwe1'
ACCESS_TOKEN_SECRET = 'NqzxDbkkuhqTPWQfyLacsjJya87KcCNj0SnlYoqxX75BT'
BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAICMvwEAAAAAHiJA3scm1WvEHEklsabV2AX2XAE%3DxN3UeToHNvqzVGRjALEeFGKMjWhEft8fyWjIG6coF6hODKz2OR'
CLIENT_ID = 'V1BjT3pTam5uclp3QjN2c3dpTk86MTpjaQ'
CLIENT_SECRET = 'rPGQ8G76zi8uuM8klZleHMZRG2d4FESKw65Yk4t-7q43aFuofH'

CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=halseybot9e83;AccountKey=B2DCFtCGtESjL2mycH0gK1C4NXddgPyM1lGuS9YV2fw5Tc7K7Fo1amMNM6vDInOcJt8caw8o2DHS+AStnPmKlA==;EndpointSuffix=core.windows.net"

# Create the BlobServiceClient object
blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
container_client = blob_service_client.get_container_client('merchbotproducts')

# Set up tweepy client for OAuth 2.0 User Context
client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True)
auth = tweepy.OAuth2BearerHandler(BEARER_TOKEN)
api = tweepy.API(auth, wait_on_rate_limit=True)


def read_previous_productsUS(file_path):
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

def write_current_productsUS(file_path, products):
    # Write products to a CSV file
    with open(file_path, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        for title, available in products.items():
            writer.writerow([title, available])

    # Upload the file to Azure Blob Storage
    blob_client = container_client.get_blob_client(os.path.basename(file_path))
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    print(f"{file_path} uploaded to Azure Blob Storage.")


def tweetUS(product, status):
    try:
        title = product['title'].title()
        price = product['variants'][0]['price']
        link = f"https://www.halseymusicstore.com/products/{product['handle']}"
        tweet_text = f"🚨 {status.upper()} 🚨\n{title} - €{price}\n🔗 {link}"
        
        response = client.create_tweet(text=tweet_text)

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(f"Tweeted: {tweet_text}")
        print(json.dumps(response.data, indent=4, sort_keys=True))
    except tweepy.TweepyException as e:
        print(f"Error tweeting: {e}")

def check_for_new_productsUS():
    previous_products = read_previous_productsUS(previous_products_fileUS)
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
                tweetUS(product, "NEW PRODUCT")
            elif title in new_products and not product['variants'][0]['available']:
                print(f"New product added but out of stock: {title}")
                tweetUS(product, "NEW PRODUCT (OUT OF STOCK)")
            elif title in restocked_products:
                print(f"Product back in stock: {title}")
                tweetUS(product, "BACK IN STOCK")
            elif title in out_of_stock_products:
                print(f"Product out of stock: {title}")
                tweetUS(product, "OUT OF STOCK")
            
        write_current_productsUS(previous_products_fileUS, current_products)
    except requests.RequestException as e:
        print(f"Error fetching products: {e}")

if __name__ == '__main__':
    check_for_new_productsUS()