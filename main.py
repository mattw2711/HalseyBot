import requests
import time
import tweepy
import csv
import io
import os
import json
from blobStorage import initialiseBlobStorage
from usInitialise import usInitialise
from euInitialise import euInitialise

# EU URL to fetch products
url_EU = 'https://www.halseymusicstore.eu'
previous_products_file_EU = 'previous_products.csv'

# US Twitter API credentials
url_US = 'https://www.halseymusicstore.com'
previous_products_file_US = 'previous_productsUS.csv'

global clientEU
global clientUS
global container_client

CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=halseybot9e83;AccountKey=B2DCFtCGtESjL2mycH0gK1C4NXddgPyM1lGuS9YV2fw5Tc7K7Fo1amMNM6vDInOcJt8caw8o2DHS+AStnPmKlA==;EndpointSuffix=core.windows.net"

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


def tweet(product, status, url, variantNum):
    try:
        if variantNum == 0:
            title = product['title'].title()
        else:
            title = f"{product['title'].title()} - {product['variants'][variantNum]['title']}"
        price = product['variants'][variantNum]['price']
        link = f"{url}/products/{product['handle']}"
        if url == url_EU:
            currency = "€"
            client = clientEU
        else:
            currency = "$"
            client = clientUS
        tweet_text = f"🚨 {status.upper()} 🚨\n{title} - {currency}{price}\n🔗 {link}"
        
        response = client.create_tweet(text=tweet_text)

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(json.dumps(response.data, indent=4, sort_keys=True))
        print(f"Tweeted: {tweet_text}")
    except tweepy.TweepyException as e:
        print(f"Error tweeting: {e}")

def check_for_new_products(file_path, url):
    previous_products = read_previous_products(file_path)
    try:
        r = requests.get(url + "/products.json")
        r.raise_for_status()  # Raise an HTTPError for bad responses
        data = r.json()
        
        current_products = {}
        for item in data['products']:
            title = item['title']
            for i, variant in enumerate(item['variants']):
                variant_title = f"{title} - {variant['title']}"
                current_products[variant_title] = variant['available']
        
        new_products = set(current_products.keys()) - set(previous_products.keys())
        restocked_products = {title for title in current_products if title in previous_products and not previous_products[title] and current_products[title]}
        out_of_stock_products = {title for title in previous_products if title in current_products and previous_products[title] and not current_products[title]}

        for item in data['products']:
            title = item['title']
            for i, variant in enumerate(item['variants']):
                variant_title = f"{title} - {variant['title']}"
                if variant_title in new_products and current_products[variant_title]:
                    print(f"New product added: {variant_title}")
                    tweet(item, f"NEW PRODUCT", url, i)
                elif variant_title in new_products and not current_products[variant_title]:
                    print(f"New product added but out of stock: {variant_title}")
                    tweet(item, f"NEW PRODUCT (OUT OF STOCK)", url, i)
                elif variant_title in restocked_products:
                    print(f"Product back in stock: {variant_title}")
                    tweet(item, f"BACK IN STOCK", url, i)
                elif variant_title in out_of_stock_products:
                    print(f"Product out of stock: {variant_title}")
                    tweet(item, f"OUT OF STOCK", url. i)
            
        write_current_products(file_path, current_products)
    except requests.RequestException as e:
        print(f"Error fetching products: {e}")

def main():
    global clientEU
    global clientUS
    global container_client

    clientEU = euInitialise()
    clientUS = usInitialise()
    container_client = initialiseBlobStorage(CONNECTION_STRING)
    check_for_new_products(file_path=previous_products_file_EU, url=url_EU)
    check_for_new_products(file_path=previous_products_file_US, url=url_US)

if __name__ == "__main__":
    main()