from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
import logging

# Setup logging
logging.basicConfig(
    filename='nifty_atm_straddle.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

api_key = "your_api_key"
api_secret = "your_api_secret"
request_token = "your_request_token"

kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])

EXCHANGE = "NFO"
SYMBOL = "NIFTY"
SPOT_SYMBOL = "NIFTY 50"
LOT_SIZE = 75

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

def main():
    exit_time = datetime.time(15, 15)

    wait_for_crossover()

    ce_sym, pe_sym = get_atm_straddle()

    ce_price = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
    pe_price = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]
    total_cost = (ce_price + pe_price) * LOT_SIZE

    place_order(ce_sym, "BUY")
    place_order(pe_sym, "BUY")

    logging.info(f"Bought CE: {ce_sym} at {ce_price}, PE: {pe_sym} at {pe_price}, Total Cost: {total_cost}")

    leg_exited = False
    leg_held = None
    initial_price_held_leg = 0
    max_leg_pnl = 0
    leg_trail_sl = 0
    locked_profit_percent = 0  # To track locked profit at initial target

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

        ce_pnl = ((ce_ltp - ce_price) / ce_price) * 100
        pe_pnl = ((pe_ltp - pe_price) / pe_price) * 100

        logging.info(f"CE LTP: {ce_ltp}, PE LTP: {pe_ltp}, Combined PnL: {pnl_percent:.2f}%")

        if not leg_exited:
            if pnl_percent >= 3:
                locked_profit_percent = 1.0  # Lock profit at 1% when 3% target hit

                if ce_pnl < pe_pnl:
                    square_off(ce_sym)
                    leg_held = pe_sym
                    initial_price_held_leg = pe_price
                    logging.info(f"Initial target reached. Exiting CE with PnL {ce_pnl:.2f}%. Locked profit at {locked_profit_percent}%.")
                else:
                    square_off(pe_sym)
                    leg_held = ce_sym
                    initial_price_held_leg = ce_price
                    logging.info(f"Initial target reached. Exiting PE with PnL {pe_pnl:.2f}%. Locked profit at {locked_profit_percent}%.")

                leg_exited = True
                leg_trail_sl = locked_profit_percent
        else:
            held_ltp = ce_ltp if leg_held == ce_sym else pe_ltp
            leg_pnl = ((held_ltp - initial_price_held_leg) / initial_price_held_leg) * 100

            if leg_pnl > max_leg_pnl:
                max_leg_pnl = leg_pnl

            # Trail SL: increase by 2% for every 3% increase in max_leg_pnl beyond locked profit
            expected_trail = locked_profit_percent + ((max_leg_pnl // 3) * 2)
            if expected_trail > leg_trail_sl:
                leg_trail_sl = expected_trail
                logging.info(f"Trailing SL on held leg updated to {leg_trail_sl:.2f}%")

            if leg_pnl <= leg_trail_sl:
                logging.info(f"Held leg trailing SL hit ({leg_trail_sl}%). Exiting {leg_held} with PnL {leg_pnl:.2f}%.")
                square_off(leg_held)
                break

        if pnl_percent <= -2.5:
            logging.info(f"SL hit ({pnl_percent:.2f}%). Exiting both positions.")
            square_off(ce_sym)
            square_off(pe_sym)
            break

if __name__ == "__main__":
    main()
