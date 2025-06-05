from kiteconnect import KiteConnect
import pandas as pd
import datetime
from authentication import kite, generate_tokens


# # === 1. API Setup ===
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# request_token = "your_daily_generated_request_token"  # From login flow

# kite = KiteConnect(api_key=api_key)
# data = kite.generate_session(request_token, api_secret=api_secret)
# kite.set_access_token(data["access_token"])



def display_BN_expiry():
    # === 2. Fetch NFO Instruments ===
    print("[+] Fetching instrument list...")
    instruments = kite.instruments("NFO")
    print('instruments', instruments)


    df = pd.DataFrame(instruments)


    # === 3. Get Next BankNIFTY Monthly Expiry ===
    def get_next_monthly_expiry(symbol_name="BANKNIFTY"):
        today = datetime.date.today()
        print('Toeay - ', today)

        month_end_expiries = sorted({
            i["expiry"]
            for i in instruments
            if i["name"] == symbol_name and ( i["instrument_type"] == "CE" or i["instrument_type"] == "PE" ) and i["segment"]=="NFO-OPT"
        })
        for expiry in month_end_expiries:
            if expiry > today and expiry.strftime('%A') == "Thursday" and expiry.day > 25:
                return expiry
        return month_end_expiries[0] if month_end_expiries else None

    symbol = "BANKNIFTY"
    expiry_date = get_next_monthly_expiry(symbol)
    print(f"[✓] Next monthly expiry for {symbol}: {expiry_date}")

    # === 4. Filter for Monthly Options Around ATM ===
    strike_min = 55000
    strike_max = 56000

    options = df[
        (df["name"] == symbol) &
        (df["segment"] == "NFO-OPT") &
        (df["expiry"] == pd.to_datetime(expiry_date)) &
        (df["strike"] >= strike_min) &
        (df["strike"] <= strike_max)
    ].copy()

    options["symbol"] = "NFO:" + options["tradingsymbol"]

    # === 5. Safe LTP Fetch ===
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

    print("[+] Fetching LTPs...")
    quotes = safe_ltp_fetch(options["symbol"].tolist())
    options["ltp"] = options["symbol"].apply(lambda x: quotes.get(x, {}).get("last_price", None))

    # === 6. Merge CE and PE into Option Chain Table ===
    ce = options[options["instrument_type"] == "CE"][["strike", "ltp"]].rename(columns={"ltp": "CE_LTP"})
    pe = options[options["instrument_type"] == "PE"][["strike", "ltp"]].rename(columns={"ltp": "PE_LTP"})

    merged = pd.merge(ce, pe, on="strike", how="outer").sort_values("strike")
    merged = merged.dropna(subset=["CE_LTP", "PE_LTP"])  # Optional: drop incomplete rows

    # # === 7. Display ===
    # pd.set_option('display.max_rows', None)
    # print(f"\n📊 BANKNIFTY Monthly Option Chain — Expiry: {expiry_date}\n")
    # print(merged.to_string(index=False, formatters={
    #     "strike": '{:.0f}'.format,
    #     "CE_LTP": '{:.2f}'.format,
    #     "PE_LTP": '{:.2f}'.format,
    # }))
    # pd.reset_option('display.max_rows')



    # === Optional: Sort & Clean Display ===
    df = df.sort_values(["name", "expiry", "strike", "instrument_type"])

    # === Save to Log File ===
    log_file = "nfo_instruments_log.txt"

    import os

    # If the file exists, remove it
    if os.path.exists(log_file):
        os.remove(log_file)

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"Total instruments: {len(df)}\n\n")
        f.write(df.to_string(index=False))

    print(f"[✓] Instruments logged to: {log_file}")




if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    # fetch_option_chain()
    while True :
        command = input('Do you want to run ?\n')
        if command == 'y':
            display_BN_expiry()
        else :
            break
