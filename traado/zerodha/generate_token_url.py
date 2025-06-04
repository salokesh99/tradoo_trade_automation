import logging
from kiteconnect import KiteConnect
from keys import *

logging.basicConfig(level=logging.DEBUG)

kite = KiteConnect(api_key=API_KEY)

session_token = kite.login_url()
print(session_token)
print('\n \n')


# data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
# kite.set_access_token(data["access_token"])







# Redirect the user to the login url obtained
# from kite.login_url(), and receive the request_token
# from the registered redirect url after the login flow.
# Once you have the request_token, obtain the access_token
# as follows.

# data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
# kite.set_access_token(data["access_token"])

# # Place an order
# try:
#     order_id = kite.place_order(tradingsymbol="INFY",
#                                 exchange=kite.EXCHANGE_NSE,
#                                 transaction_type=kite.TRANSACTION_TYPE_BUY,
#                                 quantity=1,
#                                 variety=kite.VARIETY_AMO,
#                                 order_type=kite.ORDER_TYPE_MARKET,
#                                 product=kite.PRODUCT_CNC,
#                                 validity=kite.VALIDITY_DAY)

#     logging.info("Order placed. ID is: {}".format(order_id))
# except Exception as e:
#     logging.info("Order placement failed: {}".format(e.message))

# Fetch all orders
# kite.orders()

# Get instruments
# kite.instruments()

# Place an mutual fund order
# kite.place_mf_order(
#     tradingsymbol="INF090I01239",
#     transaction_type=kite.TRANSACTION_TYPE_BUY,
#     amount=5000,
#     tag="mytag"
# )

# Cancel a mutual fund order
# kite.cancel_mf_order(order_id="order_id")

# Get mutual fund instruments
# kite.mf_instruments()


# profile = kite.profile()
# print(profile)