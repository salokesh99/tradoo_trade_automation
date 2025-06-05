from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import datetime
import time
import threading
from authentication import kite, generate_tokens


# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_request_token"

# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])

SPOT_SYMBOL = "NIFTY 50"  # Used for LTP of spot index


spot_symbol = "NSE:NIFTY 50"
EXCHANGE = "NFO"
SYMBOL = "NIFTY"
LOT_SIZE = 75  # Confirm your lot size from Zerodha

spot_token = None
ce_sym = None
pe_sym = None
ce_token = None
pe_token = None

positions_data = {}
bought = False
profit_locked = 0
trail_trigger = 0


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




    # expiry = '2025-06-05'
    # spot_ltp = kite.ltp([f"NSE:{SYMBOL}"])[f"NSE:{SYMBOL}"]["last_price"]
    # spot_ltp = kite.ltp([spot_symbol])[spot_symbol]["last_price"]

    # atm_strike = round_strike(spot_ltp)
    print('atm_strike===>>>', atm_strike)
    print('expiry===>>>', expiry)



    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    print('DFe1======>>>>', df)

    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])  # Convert before filtering

    df = df[df["expiry"] == expiry]
    print('DFe2======>>>>', df)
    df = df[df["instrument_type"].isin(["CE", "PE"])]
    print('DFe3======>>>>', df)

    if df.empty:
        print(f"No instruments found for expiry {expiry}")
        raise ValueError(f"No instruments found for expiry {expiry}")


    # df = df[(df["name"] == SYMBOL) & (df["expiry"] == expiry)]

    # df = df[df["instrument_type"].isin(["CE", "PE"])]



    ce = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "CE")].iloc[0]
    print('ce======>>>>', ce)

    pe = df[(df["strike"] == atm_strike) & (df["instrument_type"] == "PE")].iloc[0] 
    print('ce======>>>>', pe)


    return ce["tradingsymbol"], pe["tradingsymbol"], ce["instrument_token"], pe["instrument_token"]

def place_order(tradingsymbol, transaction_type):
    print(f"Placing {transaction_type} order for {tradingsymbol}")
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
            print(f"Squared off {symbol}")

def on_ticks(ws, ticks):
    global bought, positions_data, profit_locked, trail_trigger

    for tick in ticks:
        token = tick["instrument_token"]
        ltp = tick["last_price"]

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

        print(f"Combined PnL: {pnl_percent:.2f}%")

        if ce_pos["active"] and pe_pos["active"] and pnl_percent >= 5:
            if ce_pnl < pe_pnl:
                square_off(ce_sym)
                ce_pos["active"] = False
            else:
                square_off(pe_sym)
                pe_pos["active"] = False

            profit_locked = combined_pnl * (2/3)
            trail_trigger = combined_pnl + (combined_pnl / 3)
            print(f"Locked profit: {profit_locked}, Next trail at: {trail_trigger}")

        if (ce_pos["active"] ^ pe_pos["active"]):
            active = ce_pos if ce_pos["active"] else pe_pos
            active_pnl = (active["ltp"] - active["entry"]) * LOT_SIZE

            if active_pnl <= profit_locked:
                square_off(ce_sym if ce_pos["active"] else pe_sym)
                active["active"] = False
                ws.close()
            elif active_pnl >= trail_trigger:
                profit_locked += (active_pnl - profit_locked) / 3
                trail_trigger = active_pnl + (active_pnl - profit_locked)
                print(f"Trail updated: Locked={profit_locked}, Next={trail_trigger}")

def on_connect(ws, response):
    print("Websocket connected")
    ws.subscribe([spot_token, ce_token, pe_token])
    ws.set_mode(ws.MODE_LTP, [ce_token, pe_token])

def main():
    global spot_token, ce_sym, pe_sym, ce_token, pe_token, positions_data, bought

    ce_sym, pe_sym, ce_token, pe_token = get_atm_options()

    # spot_token = kite.ltp([f"NSE:{SYMBOL}"])[f"NSE:{SYMBOL}"]["instrument_token"]
    spot_token = kite.ltp([spot_symbol])[spot_symbol]["instrument_token"]


    ce_price = kite.ltp([f"{EXCHANGE}:{ce_sym}"])[f"{EXCHANGE}:{ce_sym}"]["last_price"]
    pe_price = kite.ltp([f"{EXCHANGE}:{pe_sym}"])[f"{EXCHANGE}:{pe_sym}"]["last_price"]
    print('ce_price', ce_price)
    print('pe_price', pe_price)

    # place_order(ce_sym, "BUY")
    # place_order(pe_sym, "BUY")
    # bought = True

    # positions_data[ce_token] = {"symbol": ce_sym, "entry": ce_price, "ltp": ce_price, "active": True}
    # positions_data[pe_token] = {"symbol": pe_sym, "entry": pe_price, "ltp": pe_price, "active": True}

    # kws = KiteTicker(api_key, kite.access_token)
    # kws.on_ticks = on_ticks
    # kws.on_connect = on_connect
    # kws.connect()

if __name__ == "__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    # fetch_option_chain()
    while True :
        command = input('Do you want to run ?\n')
        if command == 'y':
            main()
        else :
            break
