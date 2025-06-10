from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
import logging
import pytz

# Setup logging
logging.basicConfig(
    filename='nifty_otm_straddle.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
IS_INTRADAY = True  # Set to False for NRML positional trades
PRODUCT_TYPE = "MIS" if IS_INTRADAY else "NRML"


api_key = "d7fg3jqz3k1i6eio"
api_secret = "ngh8ag2owecpv05l8gbbdwe7491ikerx"
print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio&v=3')

request_token = input('Enter the Input Token --\n')

 

logging.info("Initializing KiteConnect session")
kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])
logging.info("Session established and access token set")

EXCHANGE = "NFO"
SYMBOL = "NIFTY"
SPOT_SYMBOL = "NIFTY 50"
LOT_SIZE = 75

ABSOLUTE_TRAIL_INTERVAL = 3  # % gain
ABSOLUTE_TRAIL_STEP = 2      # % tighter SL step
INITIAL_TARGET = 3           # Initial target in %
LOCKED_PROFIT = 1.0          # Lock this much profit once initial target hits
EXIT_TIME = datetime.time(15, 15)  # Exit at 03:15 PM IST
REENTRY_DELAY_MINUTES = 5


def get_spot_token():
    logging.info("Fetching spot token")
    instruments = kite.instruments("NSE")
    for ins in instruments:
        if ins["tradingsymbol"] == SPOT_SYMBOL and ins["exchange"] == "NSE":
            logging.info(f"Found spot token: {ins['instrument_token']}")
            return ins["instrument_token"]
    raise Exception(f"Token for {SPOT_SYMBOL} not found.")

def round_strike(price):
    strike = int(round(price / 50) * 50)
    logging.info(f"Rounded strike price: {strike}")
    return strike

def get_expiry():
    logging.info("Fetching expiry date")
    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])
    today = datetime.date.today()
    df = df[df["expiry"].dt.date >= today]
    expiries = sorted(df["expiry"].unique())

    if datetime.datetime.now().date() == pd.to_datetime(expiries[0]).date():
        logging.info(f"Today is expiry. Picking next expiry: {expiries[1]}")
        return expiries[1]
    else:
        logging.info(f"Next expiry selected: {expiries[0]}")
        return expiries[0]

def get_otm_straddle():
    logging.info("Getting OTM straddle symbols")
    expiry = get_expiry()
    spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_ltp)
    ce_strike = atm_strike + 200
    pe_strike = atm_strike - 200
    logging.info(f"Spot LTP: {spot_ltp}, ATM: {atm_strike}, CE: {ce_strike}, PE: {pe_strike}")

    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df["expiry"] = pd.to_datetime(df["expiry"])
    df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    ce = df[(df["strike"] == ce_strike) & (df["instrument_type"] == "CE")].iloc[0]
    pe = df[(df["strike"] == pe_strike) & (df["instrument_type"] == "PE")].iloc[0]

    logging.info(f"Selected CE: {ce['tradingsymbol']}, PE: {pe['tradingsymbol']}")
    return ce["tradingsymbol"], pe["tradingsymbol"]

def place_order(tradingsymbol, transaction_type):
    logging.info(f"Placing {transaction_type} order for {tradingsymbol} with product {PRODUCT_TYPE}")
    return kite.place_order(
        tradingsymbol=tradingsymbol,
        exchange=EXCHANGE,
        transaction_type=transaction_type,
        quantity=LOT_SIZE,
        order_type="MARKET",
        product=PRODUCT_TYPE,
        variety="regular"
    )

def square_off(symbol):
    logging.info(f"Attempting to square off position: {symbol}")
    positions = kite.positions()["net"]
    for pos in positions:
        if pos["tradingsymbol"] == symbol and pos["product"] == PRODUCT_TYPE and pos["quantity"] != 0:
            txn = "SELL" if pos["quantity"] > 0 else "BUY"
            kite.place_order(
                tradingsymbol=symbol,
                exchange=EXCHANGE,
                transaction_type=txn,
                quantity=abs(pos["quantity"]),
                order_type="MARKET",
                product=PRODUCT_TYPE,
                variety="regular"
            )
            logging.info(f"Squared off {symbol}")

def wait_for_crossover():
    logging.info("Waiting until 10:30 AM IST to check crossover...")
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(pytz.utc).astimezone(ist)
    target_time_ist = now_ist.replace(hour=10, minute=30, second=0, microsecond=0)

    while now_ist < target_time_ist:
        time.sleep(5)
        now_ist = datetime.datetime.now(pytz.utc).astimezone(ist)

    logging.info("Reached 10:30 AM IST. Fetching historical candles for crossover check")
    from_date_ist = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    to_date_ist = now_ist.replace(hour=10, minute=30, second=0, microsecond=0)

    # from_date_utc = from_date_ist.astimezone(pytz.utc)
    # to_date_utc = to_date_ist.astimezone(pytz.utc)
    # print('from_date_utc', from_date_utc)
    # print('to_date_utc', to_date_utc)

    # candles = kite.historical_data(
    #     instrument_token=get_spot_token(),
    #     from_date=from_date_utc,
    #     to_date=to_date_utc,
    #     interval="5minute"
    # )
    from_date_ist = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    to_date_ist = now_ist.replace(hour=10, minute=30, second=0, microsecond=0)
    print('from_date_utc', from_date_ist)
    print('to_date_utc', to_date_ist)

    # ⚠️ REMOVE the timezone conversion:
    # from_date_utc = from_date_ist.astimezone(pytz.utc)
    # to_date_utc = to_date_ist.astimezone(pytz.utc)

    candles = kite.historical_data(
        instrument_token=get_spot_token(),
        from_date=from_date_ist.replace(tzinfo=None),
        to_date=to_date_ist.replace(tzinfo=None),
        interval="5minute"
    )




    print('candles', candles)
    highs = [candle["high"] for candle in candles]
    lows = [candle["low"] for candle in candles]
    day_high = max(highs)
    day_low = min(lows)

    logging.info(f"Day High at 10:30 AM: {day_high}, Day Low: {day_low}")

    logging.info("Monitoring crossover after 10:30 AM")
    while True:
        spot_price = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
        logging.debug(f"Current Spot Price: {spot_price}")
        if spot_price > day_high or spot_price < day_low:
            logging.info(f"Crossover detected at price {spot_price}")
            return
        time.sleep(1)

def monitor_trailing_sl(entry_price):
    target_hit = False
    trail_sl = entry_price * (1 - (INITIAL_TARGET - LOCKED_PROFIT)/100)
    logging.info(f"Initial trailing SL set to {trail_sl}")

    while True:
        ce_symbol, pe_symbol = get_otm_straddle()
        ce_ltp = kite.ltp([f"{EXCHANGE}:{ce_symbol}"])[f"{EXCHANGE}:{ce_symbol}"]["last_price"]
        pe_ltp = kite.ltp([f"{EXCHANGE}:{pe_symbol}"])[f"{EXCHANGE}:{pe_symbol}"]["last_price"]
        total_ltp = ce_ltp + pe_ltp
        pnl_percent = ((total_ltp - entry_price) / entry_price) * 100

        now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Kolkata"))
        if now.time() >= EXIT_TIME:
            logging.info("Exit time reached. Exiting position.")
            square_off(ce_symbol)
            square_off(pe_symbol)
            return False

        if not target_hit and pnl_percent >= INITIAL_TARGET:
            trail_sl = entry_price * (1 + LOCKED_PROFIT / 100)
            target_hit = True
            logging.info(f"Initial target hit. Locked profit SL set to {trail_sl}")
        elif target_hit and pnl_percent >= (INITIAL_TARGET + ABSOLUTE_TRAIL_INTERVAL):
            trail_sl = total_ltp * (1 - ABSOLUTE_TRAIL_STEP / 100)
            logging.info(f"Trailing SL moved to {trail_sl}")

        if total_ltp <= trail_sl:
            logging.info(f"Trailing SL hit. Premium: {total_ltp}, SL: {trail_sl}. Exiting...")
            square_off(ce_symbol)
            square_off(pe_symbol)
            return True

        time.sleep(5)

def trade_straddle():
    logging.info("Starting straddle trade after crossover detection")
    while True:
        ce_symbol, pe_symbol = get_otm_straddle()
        place_order(ce_symbol, "BUY")
        place_order(pe_symbol, "BUY")
        ce_entry = kite.ltp([f"{EXCHANGE}:{ce_symbol}"])[f"{EXCHANGE}:{ce_symbol}"]["last_price"]
        pe_entry = kite.ltp([f"{EXCHANGE}:{pe_symbol}"])[f"{EXCHANGE}:{pe_symbol}"]["last_price"]
        entry_premium = ce_entry + pe_entry
        logging.info(f"Straddle entered. Entry premium: {entry_premium}")

        sl_hit = monitor_trailing_sl(entry_premium)
        if not sl_hit:
            logging.info("End of day exit or SL not hit. Ending trade.")
            break

        logging.info(f"Waiting {REENTRY_DELAY_MINUTES} minutes before re-entry")
        time.sleep(REENTRY_DELAY_MINUTES * 60)

def main():
    logging.info("Script started")
    wait_for_crossover()
    trade_straddle()

if __name__ == "__main__":
    main()
