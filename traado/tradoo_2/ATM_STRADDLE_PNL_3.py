from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import datetime
import time
import threading
import logging

# Setup logging
logging.basicConfig(
    filename='nifty_strategy.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

api_key = "d7fg3jqz3k1i6eio"
api_secret = "ngh8ag2owecpv05l8gbbdwe7491ikerx"
print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio&v=3')

request_token = input('Enter the Input Token --\n')

kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])

EXCHANGE = "NFO"
SYMBOL = "NIFTY"  # Used for instrument filtering
SPOT_SYMBOL = "NIFTY 50"  # Used for LTP of spot index
LOT_SIZE = 1

spot_token = None
ce_sym = None
pe_sym = None
ce_token = None
pe_token = None

positions_data = {}
bought = False
profit_locked = 0
trail_trigger = 0

spot_high = float('-inf')
spot_low = float('inf')
high_low_captured = False
entry_triggered = False

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

def get_atm_options():
    expiry = get_nearest_expiry()
    spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_ltp)

    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])  # Convert before filtering

    df = df[df["expiry"] == expiry]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    if df.empty:
        logging.error(f"No instruments found for expiry {expiry}")
        raise ValueError(f"No instruments found for expiry {expiry}")

    ce = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "CE")]
    pe = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "PE")]

    if ce.empty or pe.empty:
        logging.error(f"No CE or PE found at ATM strike {atm_strike} for expiry {expiry}")
        raise ValueError("ATM option not found")

    return ce.iloc[0]["tradingsymbol"], pe.iloc[0]["tradingsymbol"], ce.iloc[0]["instrument_token"], pe.iloc[0]["instrument_token"]


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

def square_off_all():
    for pos in kite.positions()["net"]:
        if pos["product"] == "MIS" and pos["quantity"] != 0:
            txn = "SELL" if pos["quantity"] > 0 else "BUY"
            kite.place_order(
                tradingsymbol=pos["tradingsymbol"],
                exchange=EXCHANGE,
                transaction_type=txn,
                quantity=abs(pos["quantity"]),
                order_type="MARKET",
                product="MIS",
                variety="regular"
            )
            logging.info(f"Auto-exit: Squared off {pos['tradingsymbol']}")

def try_enter_trade(spot_price):
    global bought, positions_data, profit_locked, trail_trigger, ce_sym, pe_sym, ce_token, pe_token, entry_triggered
    if entry_triggered:
        return

    if spot_price > spot_high or spot_price < spot_low:
        ce_sym, pe_sym, ce_token, pe_token = get_atm_options()
        ce_price = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
        pe_price = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]

        place_order(ce_sym, "BUY")
        place_order(pe_sym, "BUY")
        bought = True
        entry_triggered = True

        positions_data[ce_token] = {"symbol": ce_sym, "entry": ce_price, "ltp": ce_price, "active": True}
        positions_data[pe_token] = {"symbol": pe_sym, "entry": pe_price, "ltp": pe_price, "active": True}

        logging.info("Trade Entered Based on High/Low Break")

def on_ticks(ws, ticks):
    global spot_high, spot_low, high_low_captured
    current_time = datetime.datetime.now().time()

    if current_time >= datetime.time(12, 0):
        square_off_all()
        ws.close()
        logging.info("Auto-exit at 12:00 PM")
        return

    for tick in ticks:
        token = tick["instrument_token"]
        ltp = tick["last_price"]

        if token == spot_token:
            if current_time < datetime.time(9, 45):
                spot_high = max(spot_high, ltp)
                spot_low = min(spot_low, ltp)
            elif not high_low_captured:
                logging.info(f"Captured High/Low @ 09:45 => High: {spot_high}, Low: {spot_low}")
                high_low_captured = True
            elif not bought:
                try_enter_trade(ltp)

        if token in positions_data:
            positions_data[token]["ltp"] = ltp

    if bought:
        ce_pos = positions_data[ce_token]
        pe_pos = positions_data[pe_token]

        ce_pnl = (ce_pos["ltp"] - ce_pos["entry"])
        pe_pnl = (pe_pos["ltp"] - pe_pos["entry"])
        combined_pnl = (ce_pnl + pe_pnl) * LOT_SIZE
        total_cost = (ce_pos["entry"] + pe_pos["entry"]) * LOT_SIZE
        pnl_percent = (combined_pnl / total_cost) * 100

        logging.info(f"Combined PnL: {pnl_percent:.2f}%")

        if ce_pos["active"] and pe_pos["active"] and pnl_percent >= 5:
            if ce_pnl < pe_pnl:
                square_off(ce_sym)
                ce_pos["active"] = False
            else:
                square_off(pe_sym)
                pe_pos["active"] = False

            profit_locked = combined_pnl * (2/3)
            trail_trigger = combined_pnl + (combined_pnl / 3)
            logging.info(f"Locked profit: {profit_locked}, Next trail at: {trail_trigger}")

        if (ce_pos["active"] ^ pe_pos["active"]):
            active = ce_pos if ce_pos["active"] else pe_pos
            active_pnl = (active["ltp"] - active["entry"]) * LOT_SIZE

            if active_pnl <= profit_locked:
                square_off(ce_sym if ce_pos["active"] else pe_sym)
                active["active"] = False
                logging.info("Trailing SL hit, exited remaining position")
                ws.close()
            elif active_pnl >= trail_trigger:
                profit_locked += (active_pnl - profit_locked) / 3
                trail_trigger = active_pnl + (active_pnl - profit_locked)
                logging.info(f"Trail updated: Locked={profit_locked}, Next={trail_trigger}")

def on_connect(ws, response):
    logging.info("Websocket connected")
    ws.subscribe([spot_token])
    ws.set_mode(ws.MODE_LTP, [spot_token])

def main():
    global spot_token

    spot_token = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["instrument_token"]

    kws = KiteTicker(api_key, kite.access_token)
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.connect()

if __name__ == "__main__":
    main()
