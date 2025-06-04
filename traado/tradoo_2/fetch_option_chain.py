import pandas as pd
from authentication import kite, generate_tokens



def fetch_option_chain():
    # Fetch the list of instruments
    instruments = kite.instruments("NSE")  # You can also fetch from "NFO" for derivatives
    df = pd.DataFrame(instruments)

    # Filter for options of a particular underlying (e.g., NIFTY)
    nifty_options = df[
        (df["segment"] == "NFO-OPT") &
        (df["name"] == "NIFTY")  # Use "BANKNIFTY" or stock names for others
    ]
    print("nifty_options", nifty_options.all())

    # Further filter by expiry and strike price range
    expiry_date = '2025-06-12'  # Format: YYYY-MM-DD
    strike_range = (24000, 2500)

    option_chain = nifty_options[
        (nifty_options["expiry"] == expiry_date) &
        (nifty_options["strike"] >= strike_range[0]) &
        (nifty_options["strike"] <= strike_range[1])
    ]

    print(option_chain[["tradingsymbol", "strike", "instrument_type", "expiry"]])





if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()

    fetch_option_chain()

