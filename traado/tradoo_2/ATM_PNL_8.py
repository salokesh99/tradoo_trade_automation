from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
import logging

# Setup logging
logging.basicConfig(
    filename='nifty_atm_straddle_2.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
IS_INTRADAY = True  # Set to False for NRML positional trades
PRODUCT_TYPE = "MIS" if IS_INTRADAY else "NRML"

# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_request_token"


api_key = "d7fg3jqz3k1i6eio"
api_secret = "ngh8ag2owecpv05l8gbbdwe7491ikerx"
print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio&v=3')

request_token = input('Enter the Input Token --\n')



kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])

EXCHANGE = "NFO"
SYMBOL = "NIFTY"
SPOT_SYMBOL = "NIFTY 50"
LOT_SIZE = 75

ABSOLUTE_TRAIL_INTERVAL = 3  # % gain
ABSOLUTE_TRAIL_STEP = 2      # % tighter SL step
INITIAL_LOCK_PROFIT = 1.0    # Lock profit after first target in %


def get_spot_token():
    instruments = kite.instruments("NSE")
    for ins in instruments:
        if ins["tradingsymbol"] == SPOT_SYMBOL and ins["segment"] == "NSE":
            return ins["instrument_token"]
    raise Exception(f"Token for {SPOT_SYMBOL} not found.")

def round_strike(price):
    return int(round(price / 50) * 50)

def get_expiry():
    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])
    today = datetime.date.today()
    df = df[df["expiry"].dt.date >= today]
    expiries = sorted(df["expiry"].unique())

    if datetime.datetime.now().date() == pd.to_datetime(expiries[0]).date():
        return expiries[1]
    else:
        return expiries[0]

def get_atm_straddle():
    expiry = get_expiry()
    spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_ltp)

    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df["expiry"] = pd.to_datetime(df["expiry"])
    df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    ce = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "CE")].iloc[0]
    pe = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "PE")].iloc[0]

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
    logging.info("Waiting for 09:45 AM to check crossover...")
    target_time = datetime.time(9, 45)
    while datetime.datetime.now().time() < target_time:
        time.sleep(1)

    candles = kite.historical_data(
        instrument_token=get_spot_token(),
        from_date=datetime.datetime.now().replace(hour=9, minute=15, second=0, microsecond=0),
        to_date=datetime.datetime.now().replace(hour=9, minute=45, second=0, microsecond=0),
        interval="5minute"
    )
    highs = [candle["high"] for candle in candles]
    lows = [candle["low"] for candle in candles]
    day_high = max(highs)
    day_low = min(lows)

    logging.info(f"Day High: {day_high}, Day Low: {day_low}")

    while True:
        spot_price = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
        if spot_price > day_high or spot_price < day_low:
            logging.info(f"Crossover detected at price {spot_price}")
            return
        time.sleep(1)

def wait_until_time(target_time):
    while datetime.datetime.now().time() < target_time:
        time.sleep(1)

def trade_straddle():
    ce_sym, pe_sym = get_atm_straddle()

    ce_price = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
    pe_price = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]
    total_cost = (ce_price + pe_price) * LOT_SIZE

    place_order(ce_sym, "BUY")
    place_order(pe_sym, "BUY")

    logging.info(f"Bought CE: {ce_sym} at {ce_price}, PE: {pe_sym} at {pe_price}, Total Cost: {total_cost}")

    max_pnl_percent = 0
    trail_sl_triggered = False
    trail_sl_percent = 0

    while True:
        time.sleep(5)
        current_time = datetime.datetime.now().time()
        if current_time >= datetime.time(15, 15):
            logging.info("Exit time reached. Exiting positions.")
            square_off(ce_sym)
            square_off(pe_sym)
            return

        ltp = kite.ltp([f"{EXCHANGE}:{ce_sym}", f"{EXCHANGE}:{pe_sym}"])
        ce_ltp = ltp[f"{EXCHANGE}:{ce_sym}"]["last_price"]
        pe_ltp = ltp[f"{EXCHANGE}:{pe_sym}"]["last_price"]
        combined_value = (ce_ltp + pe_ltp) * LOT_SIZE
        pnl_percent = ((combined_value - total_cost) / total_cost) * 100

        logging.info(f"CE LTP: {ce_ltp}, PE LTP: {pe_ltp}, Combined PnL: {pnl_percent:.2f}%")

        if pnl_percent > max_pnl_percent:
            max_pnl_percent = pnl_percent
            if max_pnl_percent >= 3:
                trail_sl_triggered = True
                trail_sl_percent = max_pnl_percent - 1
                logging.info(f"Trailing SL activated. Max PnL: {max_pnl_percent:.2f}%, SL set at {trail_sl_percent:.2f}%")

        if trail_sl_triggered and pnl_percent <= trail_sl_percent:
            logging.info(f"Trailing SL hit. Exiting both legs. Current PnL: {pnl_percent:.2f}%, SL: {trail_sl_percent:.2f}%")
            square_off(ce_sym)
            square_off(pe_sym)
            return

        if pnl_percent <= -2.5:
            logging.info(f"Hard SL hit. Exiting both legs. Current PnL: {pnl_percent:.2f}%")
            square_off(ce_sym)
            square_off(pe_sym)
            return

def main():
    wait_for_crossover()

    if datetime.datetime.now().time() < datetime.time(10, 0):
        logging.info("Crossover occurred before 10:00 AM. Waiting until 10:00 AM to place orders.")
        wait_until_time(datetime.time(10, 0))

    trade_straddle()

if __name__ == "__main__":
    main()
