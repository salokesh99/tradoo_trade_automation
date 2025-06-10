from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import datetime
import time
import logging

# === Setup Logging ===
logging.basicConfig(
    filename="atm_straddle.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === Configuration ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_request_token"


api_key = "d7fg3jqz3k1i6eio"
api_secret = "ngh8ag2owecpv05l8gbbdwe7491ikerx"
print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio&v=3')

request_token = input('Enter the Input Token --\n')




SPOT_SYMBOL = "NIFTY 50"
SYMBOL = "NIFTY"
EXCHANGE = "NFO"
LOT_SIZE = 75






kite = KiteConnect(api_key=api_key)
try:
    data = kite.generate_session(request_token, api_secret=api_secret)
    kite.set_access_token(data["access_token"])
    logging.info("Successfully authenticated with Kite API.")
except Exception as e:
    logging.error(f"Authentication failed: {e}")
    raise

# === Globals ===
ce_sym = pe_sym = None
ce_token = pe_token = spot_token = None
positions_data = {}
entered_trade = False

# === Utilities ===

def round_strike(price):
    return int(round(price / 50) * 50)

def get_nearest_expiry():
    try:
        df = pd.DataFrame(kite.instruments(EXCHANGE))
        df = df[df["name"] == SYMBOL]
        df["expiry"] = pd.to_datetime(df["expiry"])
        today = datetime.date.today()
        nearest_expiry = sorted(df[df["expiry"].dt.date >= today]["expiry"].unique())[0]
        logging.info(f"Nearest expiry selected: {nearest_expiry}")
        return nearest_expiry
    except Exception as e:
        logging.error(f"Error fetching expiry: {e}")
        raise

def get_atm_options():
    try:
        expiry = get_nearest_expiry()
        spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
        atm_strike = round_strike(spot_ltp)
        logging.info(f"Spot LTP: {spot_ltp}, ATM Strike: {atm_strike}")

        df = pd.DataFrame(kite.instruments(EXCHANGE))

        df["expiry"] = pd.to_datetime(df["expiry"])  # Convert before filtering

        df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]
        df = df[df["instrument_type"].isin(["CE", "PE"])]

        ce = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "CE")].iloc[0]
        pe = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "PE")].iloc[0]

        return ce["tradingsymbol"], pe["tradingsymbol"], ce["instrument_token"], pe["instrument_token"]
    except Exception as e:
        logging.error(f"Error fetching ATM options: {e}")
        raise

def place_order(symbol, txn):
    try:
        logging.info(f"Placing {txn} order for {symbol}")
        return kite.place_order(
            tradingsymbol=symbol,
            exchange=EXCHANGE,
            transaction_type=txn,
            quantity=LOT_SIZE,
            order_type="MARKET",
            product="MIS",
            variety="regular"
        )
    except Exception as e:
        logging.error(f"Failed to place order for {symbol}: {e}")
        raise

def square_off(symbol):
    try:
        for p in kite.positions()["net"]:
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
    except Exception as e:
        logging.error(f"Failed to square off {symbol}: {e}")

def square_off_all():
    try:
        for p in kite.positions()["net"]:
            if p["product"] == "MIS" and p["quantity"] != 0:
                txn = "SELL" if p["quantity"] > 0 else "BUY"
                kite.place_order(
                    tradingsymbol=p["tradingsymbol"],
                    exchange=EXCHANGE,
                    transaction_type=txn,
                    quantity=abs(p["quantity"]),
                    order_type="MARKET",
                    product="MIS",
                    variety="regular"
                )
                logging.info(f"Squared off {p['tradingsymbol']}")
    except Exception as e:
        logging.error(f"Error during square off all: {e}")

# === Trading Logic ===

def on_ticks(ws, ticks):
    global entered_trade
    now = datetime.datetime.now().time()

    if now >= datetime.time(14, 0):
        logging.info("2:00 PM reached - exiting all positions")
        square_off_all()
        ws.close()
        return

    for tick in ticks:
        token = tick["instrument_token"]
        ltp = tick["last_price"]
        if token in positions_data:
            positions_data[token]["ltp"] = ltp

    if entered_trade:
        ce = positions_data[ce_token]
        pe = positions_data[pe_token]
        pnl = ((ce["ltp"] - ce["entry"]) + (pe["ltp"] - pe["entry"])) * LOT_SIZE
        cost = (ce["entry"] + pe["entry"]) * LOT_SIZE
        pnl_pct = (pnl / cost) * 100

        logging.info(f"Live PnL: ₹{pnl:.2f} ({pnl_pct:.2f}%)")

        if pnl_pct <= -2.5 or pnl_pct >= 5:
            logging.info("Target or Stoploss hit - exiting")
            square_off_all()
            ws.close()

def on_connect(ws, response):
    logging.info("WebSocket connected")
    ws.subscribe([spot_token])
    ws.set_mode(ws.MODE_LTP, [spot_token])
    logging.info("WebSocket subscribed to spot")

def start_websocket():
    kws = KiteTicker(api_key, kite.access_token)
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    print('Socket Started!!!')
    try:
        kws.connect(threaded=True)
        print('Socket Started!!!- 2')
    except Exception as e:
        logging.error(f"WebSocket connection failed: {e}")

# === Entry Logic ===

def run_strategy():
    global ce_sym, pe_sym, ce_token, pe_token, spot_token, positions_data, entered_trade

    ce_sym, pe_sym, ce_token, pe_token = get_atm_options()
    spot_token = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["instrument_token"]

    ce_ltp = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
    pe_ltp = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]

    place_order(ce_sym, "BUY")
    place_order(pe_sym, "BUY")

    positions_data[ce_token] = {"symbol": ce_sym, "entry": ce_ltp, "ltp": ce_ltp}
    positions_data[pe_token] = {"symbol": pe_sym, "entry": pe_ltp, "ltp": pe_ltp}
    entered_trade = True

    logging.info(f"Entered ATM Straddle at 1:00 PM: {ce_sym} @ ₹{ce_ltp}, {pe_sym} @ ₹{pe_ltp}")
    print('Touch Point 1 received!!!!')
    start_websocket()

# === Scheduler ===

def wait_until_1pm():
    logging.info("Waiting for 1:00 PM to start trade...")
    while datetime.datetime.now().time() < datetime.time(13, 0):
        time.sleep(10)
    run_strategy()

if __name__ == "__main__":
    logging.info("Starting ATM Straddle Strategy Script")
    try:
        wait_until_1pm()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
