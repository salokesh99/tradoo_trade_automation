from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
import logging

# Setup logging
logging.basicConfig(
    filename='nifty_otm_straddle.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

def round_strike(price):
    return int(round(price / 50) * 50)

def get_nearest_expiry():
    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])
    today = datetime.date.today()
    future_expiries = sorted(df[df["expiry"].dt.date >= today]["expiry"].unique())
    return future_expiries[0]

def get_otm_straddle():
    expiry = get_nearest_expiry()
    spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_ltp)
    otm_ce_strike = atm_strike + 500
    otm_pe_strike = atm_strike - 500

    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df["expiry"] = pd.to_datetime(df["expiry"])
    df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    ce = df[(df["strike"] == otm_ce_strike) & (df["instrument_type"] == "CE")].iloc[0]
    pe = df[(df["strike"] == otm_pe_strike) & (df["instrument_type"] == "PE")].iloc[0]

    return ce["tradingsymbol"], pe["tradingsymbol"]

def place_order(tradingsymbol, transaction_type):
    logging.info(f"Placing {transaction_type} order for {tradingsymbol}")
    return kite.place_order(
        tradingsymbol=tradingsymbol,
        exchange=EXCHANGE,
        transaction_type=transaction_type,
        quantity=LOT_SIZE,
        order_type="MARKET",
        product="MIS",
        variety="regular"
    )

def square_off(symbol):
    positions = kite.positions()["net"]
    for pos in positions:
        if pos["tradingsymbol"] == symbol and pos["product"] == "MIS" and pos["quantity"] != 0:
            txn = "SELL" if pos["quantity"] > 0 else "BUY"
            kite.place_order(
                tradingsymbol=symbol,
                exchange=EXCHANGE,
                transaction_type=txn,
                quantity=abs(pos["quantity"]),
                order_type="MARKET",
                product="MIS",
                variety="regular"
            )
            logging.info(f"Squared off {symbol}")

def main():
    entry_time = datetime.time(13, 0)
    exit_time = datetime.time(14, 0)

    logging.info("Waiting for entry time...")
    while datetime.datetime.now().time() < entry_time:
        time.sleep(1)

    logging.info("Entry time reached, placing OTM straddle")
    ce_sym, pe_sym = get_otm_straddle()

    ce_price = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
    pe_price = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]
    total_cost = (ce_price + pe_price) * LOT_SIZE

    place_order(ce_sym, "BUY")
    place_order(pe_sym, "BUY")

    logging.info(f"Bought CE: {ce_sym} at {ce_price}, PE: {pe_sym} at {pe_price}, Total Cost: {total_cost}")

    max_pnl_percent = 0
    trail_sl_percent = 2.5

    while True:
        time.sleep(5)
        current_time = datetime.datetime.now().time()
        if current_time >= exit_time:
            logging.info("Exit time reached. Exiting positions.")
            square_off(ce_sym)
            square_off(pe_sym)
            break

        ltp = kite.ltp([f"{EXCHANGE}:{ce_sym}", f"{EXCHANGE}:{pe_sym}"])
        ce_ltp = ltp[f"{EXCHANGE}:{ce_sym}"]["last_price"]
        pe_ltp = ltp[f"{EXCHANGE}:{pe_sym}"]["last_price"]
        combined_value = (ce_ltp + pe_ltp) * LOT_SIZE
        pnl_percent = ((combined_value - total_cost) / total_cost) * 100

        logging.info(f"CE LTP: {ce_ltp}, PE LTP: {pe_ltp}, PnL: {pnl_percent:.2f}%")

        if pnl_percent > max_pnl_percent:
            max_pnl_percent = pnl_percent

        expected_trail = 2.5 + ((max_pnl_percent // 3) * 1)
        if expected_trail > trail_sl_percent:
            trail_sl_percent = expected_trail
            logging.info(f"Trailing SL updated to {trail_sl_percent:.2f}%")

        if pnl_percent <= -trail_sl_percent:
            logging.info(f"Trailing SL hit ({trail_sl_percent}%). Exiting...")
            square_off(ce_sym)
            square_off(pe_sym)
            break
        elif pnl_percent >= 5:
            logging.info("Target hit. Exiting...")
            square_off(ce_sym)
            square_off(pe_sym)
            break

if __name__ == "__main__":
    main()
