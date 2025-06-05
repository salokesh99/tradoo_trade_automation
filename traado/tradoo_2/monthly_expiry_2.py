from kiteconnect import KiteConnect
import pandas as pd
import datetime
import os
from authentication import kite, generate_tokens


# # === Zerodha API Setup ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_request_token"

# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])





def get_bn_current_val():
    # === BANKNIFTY index symbol ===
    symbol = "NSE:NIFTY BANK"  # BANKNIFTY index

    # === Get LTP (Last Traded Price) ===
    ltp_data = kite.ltp(symbol)
    banknifty_price = ltp_data[symbol]["last_price"]

    print(f"📈 BANKNIFTY Current Value: {banknifty_price}")

    return banknifty_price


def fetch_data():
    # === Fetch NFO Instruments ===
    print("[+] Fetching NFO instruments...")
    instruments = kite.instruments("NFO")
    df = pd.DataFrame(instruments)
    df["expiry"] = pd.to_datetime(df["expiry"])

    # === Filter for BANKNIFTY Monthly Options for This Month ===
    today = datetime.date.today()
    this_month = today.month
    this_year = today.year


    banknifty_price = get_bn_current_val()


    # === 4. Filter for Monthly Options Around ATM ===
    strike_min = banknifty_price - 1000
    strike_max = banknifty_price + 1000



    # Filter to BANKNIFTY options only
    banknifty_options = df[
        (df["name"] == "BANKNIFTY") &
        ((df["instrument_type"] == "PE") | ( df["instrument_type"] == "CE" ) ) &
        (df["segment"] == "NFO-OPT") &
         (df["strike"] >= strike_min) &
        (df["strike"] <= strike_max)
    ]

    # Monthly expiry usually has Thursday expiry after 4th Thursday
    # We'll pick the last Thursday of the current month
    def is_last_thursday(date):
        next_week = date + datetime.timedelta(days=7)
        return date.weekday() == 3 and next_week.month != date.month

    monthly_expiries = sorted(set(banknifty_options["expiry"].dt.date))
    this_month_expiry = next((d for d in monthly_expiries if d.month == this_month and is_last_thursday(d)), None)

    if not this_month_expiry:
        print("[!] No monthly expiry found for current month.")
        exit()

    print(f"[✓] Monthly Expiry Date for BANKNIFTY: {this_month_expiry}")

    # Filter instruments with this expiry
    monthly_df = banknifty_options[banknifty_options["expiry"].dt.date == this_month_expiry]
    monthly_df = monthly_df.sort_values(["strike", "instrument_type"])

    # === Log to File ===
    log_filename = f"banknifty_monthly_expiry_{this_month_expiry}.log"

    with open(log_filename, "w", encoding="utf-8") as f:
        f.write(f"BANKNIFTY Monthly Expiry Instruments for {this_month_expiry} — Total: {len(monthly_df)}\n\n")
        f.write(monthly_df.to_string(index=False))

    print(f"[✓] Logged to: {log_filename}")



if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    # fetch_option_chain()
    while True :
        command = input('Do you want to run ?\n')
        if command == 'y':
            fetch_data()
        else :
            break