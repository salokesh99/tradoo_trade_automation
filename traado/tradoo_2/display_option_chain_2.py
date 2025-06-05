from kiteconnect import KiteConnect
import pandas as pd
from authentication import kite, generate_tokens


# # === 1. Setup Credentials ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_daily_generated_request_token"

# # === 2. Login ===
# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])

pd.set_option('display.max_rows', None)        # Show all rows
pd.set_option('display.max_columns', None)     # Show all columns
pd.set_option('display.width', None)           # Don't break lines
pd.set_option('display.max_colwidth', None)    # Show full column content

def display_option_chain():

    # === 3. Load Instrument List ===
    instruments = kite.instruments("NFO")
    df = pd.DataFrame(instruments)


    # === 4. Filter for NIFTY Options ===
    symbol = "NIFTY"
    expiry_date = "2025-06-12"  # Adjust to next expiry
    strike_min = 24000
    strike_max = 25000

    options = df[
        (df["name"] == symbol) &
        (df["segment"] == "NFO-OPT") &
        (df["expiry"] == pd.to_datetime(expiry_date)) &
        (df["strike"] >= strike_min) &
        (df["strike"] <= strike_max)
    ].copy()

    # Add full symbol name
    options["symbol"] = "NFO:" + options["tradingsymbol"]

    # === 5. Safe LTP Fetching ===
    def safe_ltp_fetch(symbols):
        quotes = {}
        chunk_size = 25
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i + chunk_size]
            try:
                quotes.update(kite.ltp(chunk))
            except Exception as e:
                print(f"[!] Error fetching LTP for {chunk}: {e}")
        return quotes

    symbols_list = options["symbol"].tolist()
    print(f"\n[+] Fetching LTPs for {len(symbols_list)} option symbols...")
    quotes = safe_ltp_fetch(symbols_list)

    options["ltp"] = options["symbol"].apply(lambda x: quotes.get(x, {}).get("last_price", None))

    # === 6. Build Option Chain Table ===
    ce = options[options["instrument_type"] == "CE"].copy()
    pe = options[options["instrument_type"] == "PE"].copy()

    merged = pd.merge(
        ce[["strike", "ltp"]].rename(columns={"ltp": "CE_LTP"}),
        pe[["strike", "ltp"]].rename(columns={"ltp": "PE_LTP"}),
        on="strike",
        how="outer"
    ).sort_values(by="strike")

    # Optional: Remove rows with missing prices
    merged = merged.dropna(subset=["CE_LTP", "PE_LTP"])

    print(merged)


    # === 7. Display Option Chain ===
    print(f"\n📊 OPTION CHAIN — {symbol} — Expiry: {expiry_date}\n")
    print(merged.to_string(index=False, formatters={
        "CE_LTP": '{:.2f}'.format,
        "PE_LTP": '{:.2f}'.format,
        "strike": '{:.0f}'.format
    }))


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
