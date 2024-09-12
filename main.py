import requests
import time
import tweepy
import json

# URL to fetch products
url = 'https://www.halseymusicstore.eu/products.json'
previous_products = set()

# Twitter API credentials
API_KEY = '5xRUBnLbsL69owtta4WeFQdFx'
API_SECRET_KEY = '5wRguMrjCewzcKIw2fXLez9FgT0Ljb4IgOpknhNjCr9a72Fz2p'
ACCESS_TOKEN = '1834273643955732480-PzuN7oQWNOOEKkEwXJZMnjOmBrQejm'
ACCESS_TOKEN_SECRET = 'QQRtYN4ULXxxdwqVVw9HpSPGmgRqu69nXUGMlWHY6lVdh'
BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAAVwvwEAAAAAtaLP8Hxyk2yd096YrUXSxfAUb9M%3Dz1bY7dweFgrbLeaoTlQiaMLiHd8UxJmaSfFGR43K5tisfgA0Qs'
CLIENT_ID = 'dVltRU5SZ1pHNndqVWwtSmtMekU6MTpjaQ'
CLIENT_SECRET = 'UgmtU5SQMxBe8-10zlGycw7Hbqy5KHgJrov7gWpNSfZYgf_Qor'

# Set up tweepy client for OAuth 2.0 User Context
client = tweepy.Client(BEARER_TOKEN, API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

def tweet(product):
    try:
        title = product['title'].title()
        price = product['variants'][0]['price']
        link = f"https://www.halseymusicstore.eu/products/{product['handle']}"
        tweet_text = f"🚨 NEW PRODUCT ALERT 🚨\n{title} - €{price}\n {link}"
        
        response = client.create_tweet(text=tweet_text)

        if response.errors:
            raise Exception(f"Request returned an error: {response.errors}")

        print(f"Tweeted: {tweet_text}")
        print(json.dumps(response.data, indent=4, sort_keys=True))
    except Exception as e:
        print(f"Error tweeting: {e}")

def check_for_new_products():
    global previous_products
    try:
        r = requests.get(url)
        r.raise_for_status()  # Raise an HTTPError for bad responses
        data = r.json()
        
        current_products = set(item['title'] for item in data['products'])
        
        new_products = current_products - previous_products
        for product in data['products']:
            if product['title'] in new_products:
                print(f"New product added: {product['title']}")
                tweet(product)
                break  # Exit the loop after the first iteration
        
        previous_products = current_products
    except requests.RequestException as e:
        print(f"Error fetching products: {e}")

def start_monitoring(interval=60):
    while True:
        check_for_new_products()
        time.sleep(interval)

# Call the start_monitoring function to begin monitoring every minute
start_monitoring()