import logging
from kiteconnect import KiteConnect
from keys import *

logging.basicConfig(level=logging.DEBUG)

kite = KiteConnect(api_key=API_KEY)

session_token = kite.login_url()
print(session_token)
print('\n \n')

REQUEST_TOKEN = input('Enter the token ---')

data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
kite.set_access_token(data["access_token"])

profile = kite.profile()
print(profile)