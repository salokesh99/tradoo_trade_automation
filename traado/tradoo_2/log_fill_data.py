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



def fetch_all():
    # === Fetch NFO Instruments ===
    print("[+] Fetching NFO instrument list...")
    instruments = kite.instruments()
    df = pd.DataFrame(instruments)

    # === Optional: Sort & Clean Display ===
    df = df.sort_values(["name", "expiry", "strike", "instrument_type"])

    # === Save to Log File ===
    log_file = "nfo_instruments_log_1.txt"

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
            fetch_all()
        else :
            break