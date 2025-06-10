import datetime
import pytz
import time
from kiteconnect import KiteConnect, KiteTicker

# Setup timezone
IST = pytz.timezone("Asia/Kolkata")

# Zerodha credentials (configure securely)
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
ACCESS_TOKEN = "your_access_token"

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# Constants
LOT_SIZE = 75
SYMBOL = "NIFTY"
TRADED = False

def is_expiry_day():
    today = datetime.datetime.now(IST).date()
    return today.weekday() == 3  # Thursday

def get_expiry_date():
    today = datetime.datetime.now(IST).date()
    if is_expiry_day():
        # Next week's Thursday
        expiry = today + datetime.timedelta(days=7)
        while expiry.weekday() != 3:
            expiry += datetime.timedelta(days=1)
    else:
        # This week's Thursday
        expiry = today
        while expiry.weekday() != 3:
            expiry += datetime.timedelta(days=1)
    return expiry

def get_historical_data(instrument_token, from_time, to_time, interval="5minute"):
    data = kite.historical_data(
        instrument_token,
        from_time,
        to_time,
        interval
    )
    return data

def get_ltp(symbol):
    return kite.ltp([symbol])[symbol]["last_price"]

def get_instrument_token(symbol):
    # Add token cache or static token for efficiency
    instruments = kite.instruments("NSE")
    for instrument in instruments:
        if instrument["tradingsymbol"] == symbol:
            return instrument["instrument_token"]
    return None

def get_day_high_low(symbol, till_time):
    token = get_instrument_token(symbol)
    start_time = datetime.datetime.combine(till_time.date(), datetime.time(9, 15)).astimezone(IST)
    end_time = (till_time - datetime.timedelta(minutes=15)).astimezone(IST)

    candles = get_historical_data(token, start_time, end_time)
    highs = [candle['high'] for candle in candles]
    lows = [candle['low'] for candle in candles]

    return max(highs), min(lows)

def get_atm_strike(price):
    return round(price / 50) * 50

def place_straddle(symbol, expiry, strike):
    global TRADED

    ce_symbol = f"{symbol}{expiry.strftime('%y%b').upper()}{strike}CE"
    pe_symbol = f"{symbol}{expiry.strftime('%y%b').upper()}{strike}PE"

    try:
        kite.place_order(
            tradingsymbol=ce_symbol,
            exchange="NFO",
            transaction_type="BUY",
            quantity=LOT_SIZE,
            order_type="MARKET",
            product="MIS",
            variety="regular"
        )

        kite.place_order(
            tradingsymbol=pe_symbol,
            exchange="NFO",
            transaction_type="BUY",
            quantity=LOT_SIZE,
            order_type="MARKET",
            product="MIS",
            variety="regular"
        )
        print(f"Straddle placed for {ce_symbol} and {pe_symbol}")
        TRADED = True
    except Exception as e:
        print("Order placement failed:", e)

def monitor_market():
    global TRADED
    if TRADED:
        return

    now = datetime.datetime.now(IST)
    if now.hour < 10 or now.hour >= 15:
        return

    ltp = get_ltp("NSE:NIFTY 50")
    high, low = get_day_high_low("NSE:NIFTY 50", now)

    if ltp > high or ltp < low:
        strike = get_atm_strike(ltp)
        expiry = get_expiry_date()
        place_straddle("NIFTY", expiry, strike)
    else:
        print(f"[{now.strftime('%H:%M')}] No breakout yet: LTP={ltp}, High={high}, Low={low}")

def main():
    while True:
        now = datetime.datetime.now(IST)
        if now.time() > datetime.time(15, 0):
            break
        monitor_market()
        time.sleep(900)  # wait for 15 mins

if __name__ == "__main__":
    main()
