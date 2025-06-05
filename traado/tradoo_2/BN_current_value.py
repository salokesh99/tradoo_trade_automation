from kiteconnect import KiteConnect
import pandas as pd
import datetime
import os
from authentication import kite, generate_tokens





def get_bn_current_val():
    # === BANKNIFTY index symbol ===
    symbol = "NSE:NIFTY BANK"  # BANKNIFTY index

    # === Get LTP (Last Traded Price) ===
    ltp_data = kite.ltp(symbol)
    print('ltp_data   ', ltp_data)
    banknifty_price = ltp_data[symbol]["last_price"]

    print(f"📈 BANKNIFTY Current Value: {banknifty_price}")



if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    # fetch_option_chain()
    while True :
        command = input('Do you want to run ?\n')
        if command == 'y':
            get_bn_current_val()
        else :
            break