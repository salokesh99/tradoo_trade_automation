# Nifty Straddle Trading Bot with WebSocket Streaming
import datetime
import time
import pytz
from kiteconnect import KiteConnect, KiteTicker
import logging

# Constants
LOTSIZE = 75
PERCENT_TARGET = 2.5
PERCENT_INITIAL_SL = -2.5
PERCENT_REVISED_SL = 1.0
PERCENT_TRAIL_INTERVAL = 1.5
IST = pytz.timezone('Asia/Kolkata')

# Setup logging
logging.basicConfig(filename="nifty_straddle_bot.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

kite = KiteConnect(api_key="your_api_key")
kite.set_access_token("your_access_token")
kws = KiteTicker("your_api_key", "your_access_token")

# Global variables
entry_price_ce = None
entry_price_pe = None
order_placed = False
straddle_exit = False
ltp_map = {}
active_tokens = []

# Utility functions
def get_instrument_token(symbol):
    # Replace with logic to fetch token from instrument list
    return 0

def get_day_high_low(symbol, from_time, to_time):
    try:
        instrument_token = get_instrument_token(symbol)
        data = kite.historical_data(instrument_token=instrument_token, interval="5minute",
                                    from_date=from_time, to_date=to_time)
        highs = [x['high'] for x in data]
        lows = [x['low'] for x in data]
        return max(highs), min(lows)
    except Exception as e:
        logging.error(f"Error fetching historical data: {e}")
        return None, None

def place_straddle_orders(atm_strike, expiry):
    global entry_price_ce, entry_price_pe
    ce_symbol = f"NIFTY{expiry}{atm_strike}CE"
    pe_symbol = f"NIFTY{expiry}{atm_strike}PE"

    try:
        ce_order = kite.place_order(variety=kite.VARIETY_REGULAR,
                                    exchange=kite.EXCHANGE_NFO,
                                    tradingsymbol=ce_symbol,
                                    transaction_type=kite.TRANSACTION_TYPE_BUY,
                                    quantity=LOTSIZE,
                                    order_type=kite.ORDER_TYPE_MARKET,
                                    product=kite.PRODUCT_MIS)

        pe_order = kite.place_order(variety=kite.VARIETY_REGULAR,
                                    exchange=kite.EXCHANGE_NFO,
                                    tradingsymbol=pe_symbol,
                                    transaction_type=kite.TRANSACTION_TYPE_BUY,
                                    quantity=LOTSIZE,
                                    order_type=kite.ORDER_TYPE_MARKET,
                                    product=kite.PRODUCT_MIS)

        time.sleep(2)
        entry_price_ce = ltp_map.get(ce_symbol, 0)
        entry_price_pe = ltp_map.get(pe_symbol, 0)

        active_tokens.extend([get_instrument_token(ce_symbol), get_instrument_token(pe_symbol)])

        logging.info(f"Straddle Buy Orders Placed - CE: {ce_symbol} @ {entry_price_ce}, PE: {pe_symbol} @ {entry_price_pe}")
        return ce_symbol, pe_symbol
    except Exception as e:
        logging.error(f"Error placing straddle orders: {e}")
        return None, None

def exit_positions(symbols):
    for symbol in symbols:
        try:
            kite.place_order(variety=kite.VARIETY_REGULAR,
                             exchange=kite.EXCHANGE_NFO,
                             tradingsymbol=symbol,
                             transaction_type=kite.TRANSACTION_TYPE_SELL,
                             quantity=LOTSIZE,
                             order_type=kite.ORDER_TYPE_MARKET,
                             product=kite.PRODUCT_MIS)
            logging.info(f"Exit Order Placed for {symbol}")
        except Exception as e:
            logging.error(f"Failed to exit {symbol}: {e}")

def on_ticks(ws, ticks):
    global straddle_exit, order_placed, entry_price_ce, entry_price_pe
    for tick in ticks:
        token = tick['instrument_token']
        ltp = tick['last_price']
        symbol = next((k for k, v in token_map.items() if v == token), None)
        if symbol:
            ltp_map[symbol] = ltp

    if order_placed and not straddle_exit:
        ce_symbol = next(k for k in ltp_map if 'CE' in k)
        pe_symbol = next(k for k in ltp_map if 'PE' in k)
        ce_price = ltp_map.get(ce_symbol, 0)
        pe_price = ltp_map.get(pe_symbol, 0)
        total_buy_price = entry_price_ce + entry_price_pe
        total_ltp = ce_price + pe_price
        pnl = ((total_ltp - total_buy_price) / total_buy_price) * 100

        logging.info(f"Tick Update - CE={ce_price}, PE={pe_price}, PNL={pnl:.2f}%")

        if pnl <= PERCENT_INITIAL_SL:
            logging.info("SL Hit. Exiting both legs.")
            exit_positions([ce_symbol, pe_symbol])
            straddle_exit = True
        elif pnl >= PERCENT_TARGET:
            if ce_price - entry_price_ce < pe_price - entry_price_pe:
                exit_positions([ce_symbol])
                trail_logic(pe_symbol, total_buy_price, pnl)
            else:
                exit_positions([pe_symbol])
                trail_logic(ce_symbol, total_buy_price, pnl)

def trail_logic(symbol, buy_price, max_pnl):
    global straddle_exit
    revised_sl = buy_price * (1 + PERCENT_REVISED_SL / 100)
    while not straddle_exit:
        current_ltp = ltp_map.get(symbol, 0)
        current_total = current_ltp
        pnl = ((current_total - buy_price) / buy_price) * 100

        if pnl >= max_pnl + PERCENT_TRAIL_INTERVAL:
            max_pnl = pnl
            revised_sl = max(revised_sl, buy_price * (1 + (pnl - PERCENT_TRAIL_INTERVAL) / 100))
            logging.info(f"Trail SL updated: {revised_sl:.2f}")

        elif current_total < revised_sl:
            logging.info("Trailing SL hit. Exiting remaining leg.")
            exit_positions([symbol])
            straddle_exit = True
            break
        time.sleep(5)

def on_connect(ws, response):
    ws.subscribe(active_tokens)
    ws.set_mode(ws.MODE_LTP, active_tokens)

# Main logic
def main():
    global order_placed
    while datetime.datetime.now(IST).time() < datetime.time(15, 0):
        now = datetime.datetime.now(IST)
        if now.time() < datetime.time(10, 0):
            time.sleep(60)
            continue

        if order_placed:
            break

        from_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        to_time = now - datetime.timedelta(minutes=15)

        high, low = get_day_high_low("NIFTY", from_time, to_time)
        current_price = kite.ltp(["NSE:NIFTY 50"])["NSE:NIFTY 50"]["last_price"]

        logging.info(f"Checking breakout - Time: {now.time()}, Price: {current_price}, High: {high}, Low: {low}")

        if current_price and high and low:
            if current_price > high or current_price < low:
                expiry = get_expiry_string()
                atm_strike = round(current_price / 50) * 50
                ce_symbol, pe_symbol = place_straddle_orders(atm_strike, expiry)
                if ce_symbol and pe_symbol:
                    order_placed = True
                    token_map[ce_symbol] = get_instrument_token(ce_symbol)
                    token_map[pe_symbol] = get_instrument_token(pe_symbol)
        time.sleep(900)

if __name__ == "__main__":
    token_map = {}
    main()
    if order_placed:
        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.connect(threaded=True)
