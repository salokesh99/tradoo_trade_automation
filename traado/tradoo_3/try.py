# from datetime import datetime, time
# import time as sleep_time
# import pytz

# IST = pytz.timezone('Asia/Kolkata')

# # now = datetime.now( tzinfo=IST)
# now = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S+%z')

# # TRADING_START_TIME = time(9, 15, 0)

# TRADING_START_TIME = time(9, 38, 0, tzinfo=IST)
# TRADING_END_TIME = time(15, 15, tzinfo=IST)

# print((now - datetime.combine(now.date(), TRADING_START_TIME) ).total_seconds())

# print(now.time())
# print(TRADING_START_TIME)
# print(TRADING_END_TIME)

# print(now.time() < TRADING_START_TIME)
# print(now.time() > TRADING_END_TIME)




# now = datetime.now(IST)
# print('now', now)
# # while True:
# if now.time() < TRADING_START_TIME:
#     print(f"Waiting until market opens at {TRADING_START_TIME}")
#     print('dates', datetime.combine(now.date(), TRADING_START_TIME))
#     print('sec--->>>', (now - datetime.combine(now.date(), TRADING_START_TIME)).total_seconds())
#     sleep_time.sleep((now - datetime.combine(now.date(), TRADING_START_TIME)).total_seconds())
# elif now.time() > TRADING_END_TIME:
#     print(f"Market already closed at {TRADING_END_TIME}")



# from kiteconnect import KiteTicker
from kiteconnect import KiteConnect, KiteTicker



api_key = "d7fg3jqz3k1i6eio"
access_token = "PF4sH02vaKYrPrNB17vr1A8o9qf5z7eO"


kite_ticker = KiteTicker(
    api_key=api_key,
    access_token=access_token
)

def on_connect(ws, response):
    print("Connected!")
    ws.subscribe(["NSE:NIFTY BANK"])
    ws.set_mode(ws.MODE_LTP, ["NSE:NIFTY BANK"])

def on_error(ws, error):
    print(f"Error: {error}")

kite_ticker.on_connect = on_connect
kite_ticker.on_error = on_error
kite_ticker.connect()