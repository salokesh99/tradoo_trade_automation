from kiteconnect import KiteConnect, KiteTicker
from datetime import datetime
import logging
import math
import time

# Configure logging
logging.basicConfig(level=logging.INFO)

# Credentials
API_KEY = "d7fg3jqz3k1i6eio"
ACCESS_TOKEN =  "ngh8ag2owecpv05l8gbbdwe7491ikerx"
# input('Enter the Input Token --\n')


kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# Constants
INDEX_SYMBOL = "NIFTY 50"
INSTRUMENTS_CACHE = []
SUBSCRIBED_TOKENS = []

# Utility: Load instrument dump
def get_instruments():
    global INSTRUMENTS_CACHE
    if not INSTRUMENTS_CACHE:
        logging.info("Downloading instrument list...")
        INSTRUMENTS_CACHE = kite.instruments("NFO")
    return INSTRUMENTS_CACHE

# Utility: Round to nearest 50
def round_to_nearest_50(x):
    return int(round(x / 50.0)) * 50

# Get current ATM strike
def get_atm_strike():
    ltp = kite.ltp("NSE:NIFTY 50")["NSE:NIFTY 50"]["last_price"]
    return round_to_nearest_50(ltp)

# Get current weekly expiry
def get_current_expiry():
    today = datetime.now().date()
    weekday = today.weekday()
    days_to_thursday = (3 - weekday + 7) % 7
    expiry = today if weekday == 3 else today + timedelta(days=days_to_thursday)
    return expiry.strftime("%d%b%Y").upper()

# Find option instrument tokens
def find_option_tokens(strike):
    expiry = get_current_expiry()
    instruments = get_instruments()
    ce_token = pe_token = None

    for ins in instruments:
        if (ins["name"] == "NIFTY"
                and ins["strike"] == strike
                and ins["expiry"].strftime("%d%b%Y").upper() == expiry
                and ins["instrument_type"] in ["CE", "PE"]):
            if ins["instrument_type"] == "CE":
                ce_token = ins["instrument_token"]
            elif ins["instrument_type"] == "PE":
                pe_token = ins["instrument_token"]

    return ce_token, pe_token

# WebSocket setup
def on_ticks(ws, ticks):
    global SUBSCRIBED_TOKENS
    prices = {tick['instrument_token']: tick['last_price'] for tick in ticks}
    ce_price = prices.get(SUBSCRIBED_TOKENS[0], 0)
    pe_price = prices.get(SUBSCRIBED_TOKENS[1], 0)
    total_straddle = ce_price + pe_price
    logging.info(f"ATM Straddle Price: CE={ce_price}, PE={pe_price}, Total={total_straddle}")

def on_connect(ws, response):
    ws.subscribe(SUBSCRIBED_TOKENS)
    ws.set_mode(ws.MODE_LTP, SUBSCRIBED_TOKENS)

def on_close(ws, code, reason):
    logging.info("WebSocket closed")

def run_websocket(ce_token, pe_token):
    global SUBSCRIBED_TOKENS
    SUBSCRIBED_TOKENS = [ce_token, pe_token]
    kws = KiteTicker(API_KEY, ACCESS_TOKEN)
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.connect(threaded=True)

    # Keep script running
    while True:
        time.sleep(1)

if __name__ == "__main__":
    try:
        strike = get_atm_strike()
        logging.info(f"ATM Strike: {strike}")
        ce_token, pe_token = find_option_tokens(strike)

        if ce_token and pe_token:
            logging.info(f"CE Token: {ce_token}, PE Token: {pe_token}")
            run_websocket(ce_token, pe_token)
        else:
            logging.error("Could not find ATM option tokens.")

    except Exception as e:
        logging.exception(f"Error: {str(e)}")
