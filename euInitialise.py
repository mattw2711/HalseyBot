import tweepy

def euInitialise():
    # EU Twitter API credentials
    API_KEY = 'dLJWJ0dWT2mgMWaXjME8dpFVs'
    API_SECRET_KEY = 'z0zJhhwXuik6Zm7yHhBNMrhglhkosfU9L3XkLjZzhNv6oxwWQh'
    ACCESS_TOKEN = '1834273643955732480-UG8VZaBsDrpBaOFx6hS1xVEWhHohVD'
    ACCESS_TOKEN_SECRET = 'JmvFjvNVR7bge44QZsiiHXyLIjFdCZ0tYc5ilTwZPUMCz'
    BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAAVwvwEAAAAAdQ9g4SyfyGWUgrw8UqBYsj7Q0VE%3D0J2fZ2zMEhLbScoWhbIlHy7vgk0Y6wwZ1DqLd1kRNx2srQXMwS'
    CLIENT_ID = 'dVltRU5SZ1pHNndqVWwtSmtMekU6MTpjaQ'
    CLIENT_SECRET = 'WtPk6ayBLUDPxpQUn_dHiHE3a8hpfvdSdAiqDCtifJiizL_pGX'

    # Set up tweepy client for OAuth 2.0 User Context
    client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True)
    auth = tweepy.OAuth2BearerHandler(BEARER_TOKEN)
    api = tweepy.API(auth, wait_on_rate_limit=True)

    return client