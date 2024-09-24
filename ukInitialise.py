import tweepy

def ukInitialise():
    # EU Twitter API credentials
    API_KEY = 'tDGdM8cug2dxmhfMAqkZMqITO'
    API_SECRET_KEY = 'oPjEKyodDxlM0V7qD4V464QuGndIG300FzBePLFbWUF3nmK0yS'
    ACCESS_TOKEN = '1836747146025967616-fOZQ1GQoLLGu0kHVhYNNU4Uja7xcLW'
    ACCESS_TOKEN_SECRET = 'O7YhLi26PeTzoE7Dn7tHGWZhPsiMZPqQq3A3qQMfQElon'
    BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAMDgvwEAAAAA%2FQriCAAStTFREu7M%2F4vvhSG4GaQ%3Dvd5EcbN2SR1C7o5WZd3k0uYtpsssw6YwoyraAHDxfDfAYUJP66'
    CLIENT_ID = 'bjJvQks0YTlyS3RiS0hTZUZjeE46MTpjaQ'
    CLIENT_SECRET = '2PsdrGwCDISpWgbWg-mamYp2G9kX8bmkEG0hdrdBC3pN6J_QAs'

    # Set up tweepy client for OAuth 2.0 User Context
    client = tweepy.Client(bearer_token=BEARER_TOKEN, consumer_key=API_KEY, consumer_secret=API_SECRET_KEY, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True)
    auth = tweepy.OAuth2BearerHandler(BEARER_TOKEN)
    api = tweepy.API(auth, wait_on_rate_limit=True)

    return client