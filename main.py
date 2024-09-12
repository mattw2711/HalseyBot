import requests
import time
from requests_oauthlib import OAuth1Session
import os
import json

# URL to fetch products
url = 'https://www.halseymusicstore.eu/products.json'
previous_products = set()

def twitter_auth():
    consumer_key = '5xRUBnLbsL69owtta4WeFQdFx'
    consumer_secret = '5wRguMrjCewzcKIw2fXLez9FgT0Ljb4IgOpknhNjCr9a72Fz2p'

    request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
    oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)

    try:
        fetch_response = oauth.fetch_request_token(request_token_url)
    except ValueError:
        print("There may have been an issue with the consumer_key or consumer_secret you entered.")
        return None

    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")
    print("Got OAuth token: %s" % resource_owner_key)

    # Get authorization
    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    print("Please go here and authorize: %s" % authorization_url)
    verifier = input("Paste the PIN here: ")

    # Get the access token
    access_token_url = "https://api.twitter.com/oauth/access_token"
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    oauth_tokens = oauth.fetch_access_token(access_token_url)

    access_token = oauth_tokens["oauth_token"]
    access_token_secret = oauth_tokens["oauth_token_secret"]

    # Return the authenticated session
    return OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )

def tweet(oauth, product):
    payload = {"text": "New Product Added: " + product}

    # Making the request
    response = oauth.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
    )

    if response.status_code != 201:
        raise Exception(
            "Request returned an error: {} {}".format(response.status_code, response.text)
        )

    print("Response code: {}".format(response.status_code))

    # Saving the response as JSON
    json_response = response.json()
    print(json.dumps(json_response, indent=4, sort_keys=True))

def check_for_new_products(oauth):
    global previous_products
    try:
        r = requests.get(url)
        r.raise_for_status()  # Raise an HTTPError for bad responses
        data = r.json()
        
        current_products = set(item['title'] for item in data['products'])
        
        new_products = current_products - previous_products
        for product in new_products:
            print(f"New product added: {product}")
            tweet(oauth, product)
            break
        
        previous_products = current_products
    except requests.RequestException as e:
        print(f"Error fetching products: {e}")

def start_monitoring(interval=60):
    oauth = twitter_auth()
    if oauth is None:
        return

    while True:
        check_for_new_products(oauth)
        time.sleep(interval)

# Call the start_monitoring function to begin monitoring every minute
start_monitoring()