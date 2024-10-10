import requests
import time
import tweepy
import csv
import io
import os
import json
import asyncio
import aiohttp
from blobStorage import initialiseBlobStorage
from ukInitialise import ukInitialise
from usInitialise import usInitialise
from euInitialise import euInitialise

# EU URL to fetch products
url_EU = 'https://www.halseymusicstore.eu'
previous_products_file_EU = 'previous_productsEU.csv'

# US Twitter API credentials
url_US = 'https://www.halseymusicstore.com'
previous_products_file_US = 'previous_productsUS.csv'

# UK Twitter API credentials
url_UK = 'https://www.halseymusicstore.co.uk'
previous_products_file_UK = 'previous_productsUK.csv'

global clientEU
global clientUS
global clientUK
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
            client = clientEU
        elif url == url_UK:
            currency = "£"
            client = clientUK
        else:
            currency = "$"
            client = clientUS

        tweet_text = f"🚨 {status.upper()} 🚨\n{title} - {currency}{price}\n{link}"
        
        response = client.create_tweet(text=tweet_text)

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(json.dumps(response.data, indent=4, sort_keys=True))
        print(f"Tweeted: {tweet_text}")
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
            current_products[title] = item['variants'][0]['available']
        
        current_products = {}
        for item in data['products']:
            title = item['title']
            current_products[title] = item['variants'][0]['available']
        
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

            if status != 'UNCHANGED':
                tweet(item, status, url)
            
        if current_products != previous_products:
            write_current_products(file_path, current_products)

        print("ran" + url)
    except aiohttp.ClientError as e:
        print(f"Error fetching products: {e}")

async def run_checks():
    start_time = asyncio.get_event_loop().time()
    while True:
        await asyncio.gather(
            check_for_new_products(file_path=previous_products_file_US, url=url_US),
            check_for_new_products(file_path=previous_products_file_UK, url=url_UK),
            check_for_new_products(file_path=previous_products_file_EU, url=url_EU)
        )
        await asyncio.sleep(0.5)
        # Check if a minute has passed
        if asyncio.get_event_loop().time() - start_time > 59:
            break 

def main():
    global clientEU
    global clientUS
    global clientUK
    global container_client

    clientEU = euInitialise()
    clientUS = usInitialise()
    clientUK = ukInitialise()
    container_client = initialiseBlobStorage(CONNECTION_STRING)

    asyncio.run(run_checks())

if __name__ == "__main__":
    main()