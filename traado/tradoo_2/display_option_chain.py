from kiteconnect import KiteConnect
import pandas as pd
from authentication import kite, generate_tokens


# # === Step 1: Setup your credentials ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_daily_generated_request_token"

# # === Step 2: Initialize Kite session ===
# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])


def display_option_chain():
    # === Step 3: Download instrument list ===
    instruments = kite.instruments("NFO")
    df = pd.DataFrame(instruments)

    # === Step 4: Filter for NIFTY options ===
    expiry_date = '2025-06-12'  # <-- Adjust as needed
    strike_min = 24000
    strike_max = 25000

    options = df[
        (df["name"] == "NIFTY") &
        (df["segment"] == "NFO-OPT") &
        (df["expiry"] == pd.to_datetime(expiry_date)) &
        (df["strike"] >= strike_min) &
        (df["strike"] <= strike_max)
    ].copy()

    # === Step 5: Fetch live prices ===
    options["symbol"] = "NFO:" + options["tradingsymbol"]
    quotes = kite.ltp(options["symbol"].tolist())

    # Add last traded price (LTP) to the DataFrame
    options["ltp"] = options["symbol"].map(lambda x: quotes[x]["last_price"])

    # === Step 6: Create pivoted option chain table ===
    ce = options[options["instrument_type"] == "CE"].copy()
    pe = options[options["instrument_type"] == "PE"].copy()

    # Merge CE and PE on strike price
    merged = pd.merge(
        ce[["strike", "ltp"]].rename(columns={"ltp": "CE_LTP"}),
        pe[["strike", "ltp"]].rename(columns={"ltp": "PE_LTP"}),
        on="strike",
        how="outer"
    ).sort_values(by="strike")

    # === Step 7: Display option chain ===
    print("\nOPTION CHAIN (NIFTY)")
    print(merged.to_string(index=False))





if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    # fetch_option_chain()
    while True :
        command = input('Do you want to run again?')
        if command == 'y':
            display_option_chain()
        else :
            break
