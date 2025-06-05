from kiteconnect import KiteConnect
import pandas as pd
import datetime
import time
from authentication import kite, generate_tokens

# # === API credentials ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_request_token"  # Get this daily via login flow

# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])


#24 hour format
entry_time = "09:25"
exit_time = "09:45"

spot_symbol = "NSE:NIFTY 50"
SYMBOL = "NIFTY"
EXCHANGE = "NFO"
LOT_SIZE = 75  # Confirm your lot size from Zerodha


# spot_symbol = "NSE:NIFTY BANK"
# SYMBOL = "BANKNIFTY"
# EXCHANGE = "NFO"
# LOT_SIZE = 30

def round_strike(price):
    return int(round(price / 100) * 100)

def get_atm_option_symbols():
    instruments = kite.instruments(EXCHANGE)
    df = pd.DataFrame(instruments)
    df = df[df["name"] == SYMBOL]
    df["expiry"] = pd.to_datetime(df["expiry"])
    # df = df[df["segment"] == "NFO-OPT"]
    df = df[df["instrument_type"].isin(["CE", "PE"])]

    today = datetime.date.today()
    future_expiries = sorted(df[df["expiry"].dt.date >= today]["expiry"].unique())
    nearest_expiry = future_expiries[0]


    ltp = kite.ltp([spot_symbol])[spot_symbol]["last_price"]
    atm_strike = round_strike(ltp)

    ce_option = df[
        (df["strike"] == atm_strike) &
        (df["expiry"] == nearest_expiry) &
        (df["instrument_type"] == "CE")
    ].iloc[0]

    pe_option = df[
        (df["strike"] == atm_strike) &
        (df["expiry"] == nearest_expiry) &
        (df["instrument_type"] == "PE")
    ].iloc[0]

    return ce_option["tradingsymbol"], pe_option["tradingsymbol"], ce_option["expiry"].date()

def place_order(symbol, transaction_type):
    print(f"Placing {transaction_type} order for {symbol}")
    return kite.place_order(
        tradingsymbol=symbol,
        exchange=EXCHANGE,
        transaction_type=transaction_type,
        quantity=LOT_SIZE,
        order_type="MARKET",
        product="MIS",
        variety="regular"
    )

def get_open_positions():
    return kite.positions()["net"]

def square_off_positions():
    for pos in get_open_positions():
        if SYMBOL in pos["tradingsymbol"] and pos["product"] == "MIS" and pos["quantity"] != 0:
            txn_type = "SELL" if pos["quantity"] > 0 else "BUY"
            print(f"Squaring off {pos['tradingsymbol']} with {txn_type}")
            kite.place_order(
                tradingsymbol=pos["tradingsymbol"],
                exchange=EXCHANGE,
                transaction_type=txn_type,
                quantity=abs(pos["quantity"]),
                order_type="MARKET",
                product="MIS",
                variety="regular"
            )

def wait_until(time_str):
    target = datetime.datetime.strptime(time_str, "%H:%M").time()
    while datetime.datetime.now().time() < target:
        time.sleep(1)

def main():
    print("Script started.")
    print("Waiting until {} to buy ATM BankNifty options...".format(entry_time))
    wait_until(entry_time)
    ce, pe, expiry = get_atm_option_symbols()
    print(f"ATM options for {SYMBOL} expiry {expiry}: CE={ce}, PE={pe}")

    place_order(ce, "BUY")
    place_order(pe, "BUY")

    print("Waiting until 09:45 to exit positions...")
    wait_until("09:45")
    square_off_positions()
    print("All positions exited. Script finished.")



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

