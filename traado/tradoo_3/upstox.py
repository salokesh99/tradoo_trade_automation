
from upstox_api.api import Upstox, LiveFeedType, WebSocket




# Replace these with your credentials
api_key = 'e2e98fe3-c132-4092-be92-eb6f7d27bdf4'
api_secret = '1euebh7gds'
redirect_uri = 'https://account.upstox.com/'
access_token = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBTTkwODAiLCJqdGkiOiI2ODUxMzkwZjMyNjJlMDZkNWU0YTI5Y2UiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzUwMTUzNDg3LCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NTI3MDMyMDB9.FQjmBFVQQoEF3w8_DKidQMU3xkykIUBIyCLQA_o3aRE'

# Step 1: Initialize Upstox instance
u = Upstox(api_key, access_token)

# Step 2: Wait for master contract to load
u.get_master_contract('NSE_EQ')  # or 'NSE_INDEX', 'NFO', etc.

# Step 3: Get instrument for subscription
nifty = u.get_instrument_by_symbol('NSE_INDEX', 'NIFTY 50')

# Step 4: Define WebSocket callback functions
def on_tick(tick_data):
    print("Tick received:", tick_data)

def on_open(ws):
    print("WebSocket opened")
    ws.subscribe(nifty, LiveFeedType.LTP)

def on_close(ws):
    print("WebSocket closed")

def on_error(ws, error):
    print("Error:", error)

# Step 5: Start WebSocket connection
ws = WebSocket(u)
ws.on_tick = on_tick
ws.on_open = on_open
ws.on_close = on_close
ws.on_error = on_error

print("Connecting to Upstox WebSocket...")
ws.connect()
