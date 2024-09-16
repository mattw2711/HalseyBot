import tweepy

def usInitialise():
    # US Twitter API credentials
    API_KEY = '6a0QlOiSUGsMlVDi75W3HWH2M'
    API_SECRET_KEY = 'hqAHoYz49xjjQhoKFaazs5kX7Nmph8SC2H1p0NP9oR49lGPsDJ'
    ACCESS_TOKEN = '1834716671203737600-F6MwqGtxFHXtltf0RHdNVYrtGrUwe1'
    ACCESS_TOKEN_SECRET = 'NqzxDbkkuhqTPWQfyLacsjJya87KcCNj0SnlYoqxX75BT'
    BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAICMvwEAAAAAHiJA3scm1WvEHEklsabV2AX2XAE%3DxN3UeToHNvqzVGRjALEeFGKMjWhEft8fyWjIG6coF6hODKz2OR'
    CLIENT_ID = 'V1BjT3pTam5uclp3QjN2c3dpTk86MTpjaQ'
    CLIENT_SECRET = 'rPGQ8G76zi8uuM8klZleHMZRG2d4FESKw65Yk4t-7q43aFuofH'

    # Set up tweepy client for OAuth 2.0 User Context
    client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True)
    auth = tweepy.OAuth2BearerHandler(BEARER_TOKEN)
    api = tweepy.API(auth, wait_on_rate_limit=True)

    return client