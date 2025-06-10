from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
import logging

# --- Setup logging ---
logging.basicConfig(filename="nifty_otm_straddle.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# --- Kite credentials ---
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

# --- Constants ---
EXCHANGE = "NFO"
SYMBOL = "NIFTY"
SPOT_SYMBOL = "NIFTY 50"
LOT_SIZE = 75
OTM_DISTANCE = 500  # total 1000 points wide straddle

# --- Helper functions ---
def round_strike(price):
    return int(round(price / 50) * 50)

def get_nearest_expiry():
    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df["expiry"] = pd.to_datetime(df["expiry"])
    df = df[df["name"] == SYMBOL]
    future_expiries = sorted(df[df["expiry"].dt.date >= datetime.date.today()]["expiry"].unique())
    return future_expiries[0]

def get_otm_straddle_tokens():
    expiry = get_nearest_expiry()
    instruments = pd.DataFrame(kite.instruments(EXCHANGE))
    instruments["expiry"] = pd.to_datetime(instruments["expiry"])

    instruments = instruments[(instruments["name"] == SYMBOL) & 
                              (instruments["expiry"] == expiry) &
                              (instruments["instrument_type"].isin(["CE", "PE"]))]

    spot_price = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_price)

    ce_strike = atm_strike + OTM_DISTANCE // 2
    pe_strike = atm_strike - OTM_DISTANCE // 2

    ce_row = instruments[(instruments["strike"] == ce_strike) & (instruments["instrument_type"] == "CE")].iloc[0]
    pe_row = instruments[(instruments["strike"] == pe_strike) & (instruments["instrument_type"] == "PE")].iloc[0]

    return ce_row["tradingsymbol"], pe_row["tradingsymbol"], ce_row["instrument_token"], pe_row["instrument_token"]

def place_market_order(symbol):
    kite.place_order(
        tradingsymbol=symbol,
        exchange=EXCHANGE,
        transaction_type="BUY",
        quantity=LOT_SIZE,
        order_type="MARKET",
        product="MIS",
        variety="regular"
    )
    logging.info(f"Placed BUY order for {symbol}")

# --- Main Logic ---
def main():
    ce_symbol, pe_symbol, ce_token, pe_token = get_otm_straddle_tokens()

    # Get entry prices
    prices = kite.ltp([f"{EXCHANGE}:{ce_symbol}", f"{EXCHANGE}:{pe_symbol}"])
    ce_price = prices[f"{EXCHANGE}:{ce_symbol}"]["last_price"]
    pe_price = prices[f"{EXCHANGE}:{pe_symbol}"]["last_price"]
    total_cost = (ce_price + pe_price) * LOT_SIZE

    logging.info(f"Entry CE: {ce_symbol} @ {ce_price}, PE: {pe_symbol} @ {pe_price}, Total cost: {total_cost}")

    place_market_order(ce_symbol)
    place_market_order(pe_symbol)

    SL = total_cost * 0.975
    TARGET = total_cost * 1.05

    logging.info(f"SL: {SL}, Target: {TARGET}")

    # Monitor position
    while True:
        time.sleep(5)
        prices = kite.ltp([f"{EXCHANGE}:{ce_symbol}", f"{EXCHANGE}:{pe_symbol}"])
        ce_ltp = prices[f"{EXCHANGE}:{ce_symbol}"]["last_price"]
        pe_ltp = prices[f"{EXCHANGE}:{pe_symbol}"]["last_price"]
        combined_value = (ce_ltp + pe_ltp) * LOT_SIZE

        logging.info(f"Live CE: {ce_ltp}, PE: {pe_ltp}, Combined: {combined_value}")

        if combined_value <= SL:
            logging.info("SL HIT — Exiting positions")
            square_off(ce_symbol)
            square_off(pe_symbol)
            break
        elif combined_value >= TARGET:
            logging.info("TARGET HIT — Exiting positions")
            square_off(ce_symbol)
            square_off(pe_symbol)
            break

def square_off(symbol):
    pos = kite.positions()["net"]
    for p in pos:
        if p["tradingsymbol"] == symbol and p["quantity"] != 0:
            txn = "SELL" if p["quantity"] > 0 else "BUY"
            kite.place_order(
                tradingsymbol=symbol,
                exchange=EXCHANGE,
                transaction_type=txn,
                quantity=abs(p["quantity"]),
                order_type="MARKET",
                product="MIS",
                variety="regular"
            )
            logging.info(f"Squared off {symbol}")

if __name__ == "__main__":
    main()
