from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import datetime
import time
import logging

# # === Configuration ===
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
data = kite.generate_session(request_token, api_secret=api_secret)
kite.set_access_token(data["access_token"])

logging.basicConfig(
    filename="atm_straddle.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === Globals ===
ce_sym = pe_sym = None
ce_token = pe_token = spot_token = None
positions_data = {}
entered_trade = False

# === Utilities ===

def round_strike(price):
    return int(round(price / 50) * 50)

def get_nearest_expiry():
    df = pd.DataFrame(kite.instruments(EXCHANGE))
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])
    today = datetime.date.today()
    return sorted(df[df["expiry"].dt.date >= today]["expiry"].unique())[0]

def get_atm_options():
    expiry = get_nearest_expiry()
    spot_ltp = kite.ltp([f"NSE:{SPOT_SYMBOL}"])[f"NSE:{SPOT_SYMBOL}"]["last_price"]
    atm_strike = round_strike(spot_ltp)



    df = pd.DataFrame(kite.instruments(EXCHANGE))
    df["expiry"] = pd.to_datetime(df["expiry"])  # Convert before filtering
    df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    ce = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "CE")].iloc[0]
    pe = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "PE")].iloc[0]

    return ce["tradingsymbol"], pe["tradingsymbol"], ce["instrument_token"], pe["instrument_token"]

def place_order(symbol, txn):
    logging.info(f"{txn} order placed for {symbol}")
    return kite.place_order(
        tradingsymbol=symbol,
        exchange=EXCHANGE,
        transaction_type=txn,
        quantity=LOT_SIZE,
        order_type="MARKET",
        product="MIS",
        variety="regular"
    )

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

def square_off_all():
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

# === Trading Logic ===

def on_ticks(ws, ticks):
    global entered_trade

    now = datetime.datetime.now().time()

    if now >= datetime.time(14, 0):
        square_off_all()
        ws.close()
        logging.info("Auto exit at 2:00 PM")
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

        logging.info(f"PnL: {pnl:.2f}, PnL%: {pnl_pct:.2f}")

        if pnl_pct <= -2.5 or pnl_pct >= 5:
            logging.info("Target/SL hit, exiting")
            square_off_all()
            ws.close()

def on_connect(ws, response):
    global spot_token
    ws.subscribe([spot_token])
    ws.set_mode(ws.MODE_LTP, [spot_token])
    logging.info("WebSocket connected and subscribed.")

def start_websocket():
    kws = KiteTicker(api_key, kite.access_token)
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.connect(threaded=True)

# === Entry ===

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
    logging.info("Entered ATM Straddle at 1:00 PM")

    start_websocket()

# === Main Scheduler ===

def wait_until_1pm():
    while datetime.datetime.now().time() < datetime.time(13, 0):
        print("Waiting for 1:00 PM...")
        time.sleep(10)
    run_strategy()

if __name__ == "__main__":
    wait_until_1pm()
