import os
import sys
import logging
from datetime import datetime, time, timedelta, date
import time as sleep_time
import holidays
from kiteconnect import KiteConnect, KiteTicker
import pytz
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('banknifty_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
LOT_SIZE = 30
TARGET_PERCENT = 2.5
STOPLOSS_PERCENT = 2.5
TRAILING_PERCENT = 2.5
IST = pytz.timezone('Asia/Kolkata')
# TRADING_START_TIME = time(9, 48, tzinfo=IST)
TRADING_START_TIME = time(10, 12)
TRADING_END_TIME = time(15, 15)
CHECK_INTERVAL = 900  # 15 minutes in seconds

# Initialize Kite Connect
# api_key = os.getenv('KITE_API_KEY')
# access_token = os.getenv('KITE_ACCESS_TOKEN')


api_key = "d7fg3jqz3k1i6eio"
api_secret = "0ojki9vtqxzj6oamaf715imhse4uenp5"


def intitiate_session():
    global kws, kite, access_token, api_key, api_secret, request_token
    print('Please visit this URL to get your access token:')
    print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio')
    print('\nAfter logging in, you will be redirected to a URL. Copy the access_token from that URL.')
    print('The access_token will be in the format: access_token=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')

    while True:
        request_token = access_token = input('\nEnter the access token: ').strip()
        if not access_token:
            print("Access token cannot be empty. Please try again.")
            continue
            
        try:

            # Initialize KiteConnect
            kite = KiteConnect(api_key=api_key)
            data = kite.generate_session(request_token, api_secret=api_secret)
            # Set access token
            kite.set_access_token(data["access_token"])
            
            # Test the connection with a simple API call
            try:
                profile = kite.profile()
                print(f"Successfully connected to Kite! Logged in as: {profile.get('user_name', 'Unknown')}")

                break
                
            except Exception as e:
                print(f"Error testing connection: {str(e)}")
                print("Please check if:")
                print("1. Your access token is fresh (less than 24 hours old)")
                print("2. You have the necessary permissions in your Zerodha account")
                print("3. Your API key has the required permissions")
                continue
                
        except Exception as e:
            print(f"Error initializing KiteConnect: {str(e)}")
            print("Please check your API key and try again.")
            continue

# Global variables
trading_day_high = None
trading_day_low = None
current_price = None
straddle_bought = False
straddle_data = {}
pnl_updates = {}
order_details = {}
current_expiry = None
next_expiry = None
banknifty_future_token = None

def is_market_open_day():
    """Check if current day is a trading day (weekday + not holiday)"""
    today = datetime.now(IST).date()
    
    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        logger.info(f"Weekend detected ({today.strftime('%A')})")
        return False
    
    in_holidays = holidays.India(years=today.year)
    if today in in_holidays:
        logger.info(f"Market holiday detected: {in_holidays.get(today)}")
        return False
    
    return True

def safe_price_compare(current, high, low):
    """Safe comparison with None checks"""
    if None in (current, high, low):
        logger.warning("Cannot compare prices - missing data")
        return False
    return current > high or current < low

def initialize_price_data():
    """Initialize price data from LTP"""
    global current_price, trading_day_high, trading_day_low
    
    try:
        print('banknifty_future_token====>>>>', banknifty_future_token)
        banknifty_future_SYMBOL = 'NIFTY BANK'
        ltp_data = kite.ltp(f"NSE:{banknifty_future_SYMBOL}")
        current_price = ltp_data[f"NSE:{banknifty_future_SYMBOL}"]['last_price']
        print('current_price====>>>>', current_price)
        trading_day_high = current_price
        trading_day_low = current_price
        logger.info(f"Initialized prices: {current_price}")
    except Exception as e:
        logger.error(f"Price initialization failed: {e}")
        raise

def get_expiry_dates():
    global current_expiry, next_expiry
    
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    today = datetime.now(IST).date()
    expiries = sorted(list(set([i['expiry'] for i in banknifty_futures])))
    
    current_expiry = next_expiry = None
    
    for expiry in expiries:
        if expiry >= today:
            if current_expiry is None:
                current_expiry = expiry
            elif next_expiry is None and expiry > current_expiry:
                next_expiry = expiry
                break
    
    logger.info(f"Current expiry: {current_expiry}, Next expiry: {next_expiry}")

def is_expiry_day():
    today = datetime.now(IST).date()
    return today == current_expiry

def get_atm_strike(price):
    if price is None:
        logger.error("Cannot calculate ATM strike - price is None")
        return None
    return round(price / 100) * 100  # BankNifty strikes in 100 increments

def get_option_instruments(expiry_date, strike, option_type):
    instruments = kite.instruments("NFO")
    expected_type = 'CE' if option_type == 'CE' else 'PE'
    
    option = [
        i for i in instruments 
        if (i['name'] == 'BANKNIFTY' and
            i['instrument_type'] == expected_type and
            i['expiry'] == expiry_date and
            i['strike'] == strike)
    ]
    
    if not option:
        logger.error(f"No option found for {option_type} {strike} {expiry_date}")
        return None
    
    return option[0]

def place_order(transaction_type, instrument_token, quantity):
    try:
        order_id = f"PAPER_{int(datetime.now().timestamp())}"
        ltp = kite.ltp(f"NFO:{instrument_token}")[f"NFO:{instrument_token}"]['last_price']
        
        order_data = {
            'order_id': order_id,
            'transaction_type': transaction_type,
            'instrument_token': instrument_token,
            'quantity': quantity,
            'price': ltp,
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"Placing {transaction_type} order: {order_data}")
        
        if instrument_token not in order_details:
            order_details[instrument_token] = []
        order_details[instrument_token].append(order_data)
        
        return order_id
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return None

def on_ticks(ws, ticks):
    global current_price, trading_day_high, trading_day_low
    
    for tick in ticks:
        if tick['instrument_token'] == banknifty_future_token:
            if tick['last_price'] is not None:
                current_price = tick['last_price']
                
                # Initialize if None
                if trading_day_high is None:
                    trading_day_high = current_price
                if trading_day_low is None:
                    trading_day_low = current_price
                
                # Update high/low
                trading_day_high = max(trading_day_high, current_price)
                trading_day_low = min(trading_day_low, current_price)
                
                logger.debug(f"Tick: {current_price} | High: {trading_day_high} | Low: {trading_day_low}")

def on_connect(ws, response):
    logger.info("WebSocket connected")
    ws.subscribe([banknifty_future_token])
    ws.set_mode(ws.MODE_LTP, [banknifty_future_token])
    initialize_price_data()  # Refresh prices on reconnect

def on_close(ws, code, reason):
    logger.info(f"WebSocket closed. Code: {code}, Reason: {reason}")
    # ticker.close() 
def on_error(ws, error):
    print(f"Error: {error}")
    ws.close()  # Close on error


def initialize_trading():
    global banknifty_future_token, straddle_bought
    
    if not is_market_open_day():
        logger.info("Not a trading day - exiting")
        sys.exit(0)
        
    now = datetime.now(IST)
    if now.time() < TRADING_START_TIME or now.time() > TRADING_END_TIME:
        logger.info("Outside market hours")
        sys.exit(0)
    
    # Reset state
    straddle_bought = False
    straddle_data.clear()
    pnl_updates.clear()
    order_details.clear()
    
    # Get BankNifty future
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    today = datetime.now(IST).date()
    current_month_future = [f for f in banknifty_futures if f['expiry'].month == today.month and f['expiry'].year == today.year][0]
    banknifty_future_token = current_month_future['instrument_token']
    
    get_expiry_dates()
    initialize_price_data()
    logger.info("Trading session initialized")

def trading_strategy():
    global straddle_bought
    
    now = datetime.now(IST)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
    
    # Wait until 10 AM
    if now.time() < time(10, 0, tzinfo=IST):
        sleep_seconds = (start_time - now).total_seconds()
        logger.info(f"Waiting until 10 AM. Sleeping for {sleep_seconds:.0f} seconds...")
        sleep_time.sleep(sleep_seconds)
    
    # Main trading loop
    while now.time() <= end_time.time() and not straddle_bought:
        now = datetime.now(IST)
        
        if None in (current_price, trading_day_high, trading_day_low):
            logger.warning("Missing price data - retrying...")
            sleep_time.sleep(5)
            continue
            
        if safe_price_compare(current_price, trading_day_high, trading_day_low):
            logger.info(f"Price crossover: {current_price} vs Range({trading_day_low}-{trading_day_high})")
            buy_straddle()
        else:
            logger.info(f"No crossover: {current_price} within Range({trading_day_low}-{trading_day_high})")
            
            next_check = now + timedelta(seconds=CHECK_INTERVAL)
            if next_check.time() > end_time.time():
                break
                
            sleep_seconds = (next_check - now).total_seconds()
            logger.info(f"Next check in {sleep_seconds:.0f} seconds...")
            sleep_time.sleep(sleep_seconds)
    
    # Monitor positions until market close
    while now.time() <= TRADING_END_TIME.time() and straddle_bought and not straddle_data.get('exited', False):
        check_exit_conditions()
        sleep_time.sleep(1)
        now = datetime.now(IST)
    
    # EOD exit
    if straddle_bought and not straddle_data.get('exited', False):
        logger.info("Market closing - exiting straddle")
        exit_straddle('MARKET_CLOSE')

def main():
    global kws
    try:
        intitiate_session()
        logger.info("Starting BankNifty Options Trading Strategy")
        
        if not is_market_open_day():
            logger.info("Exiting: Not a trading day")
            sys.exit(0)
            
        now = datetime.now(IST)
        if now.time() < TRADING_START_TIME:
            market_open_time = datetime.combine(now.date(), TRADING_START_TIME)
            wait_seconds = (market_open_time - now).total_seconds()
            logger.info(f"Waiting until market opens at {TRADING_START_TIME.strftime('%I:%M:%S %p')} ({wait_seconds:.0f} seconds remaining)")
            sleep_time.sleep(wait_seconds)

        elif now.time() > TRADING_END_TIME:
            logger.info(f"Market already closed at {TRADING_END_TIME.strftime('%I:%M:%S %p')}")
            sys.exit(0)
            
        initialize_trading()
        # access_token = ''
        # kws = KiteTicker(api_key, access_token)
                        
        # Test WebSocket connection
        # access_token_1 = 'fX4wNKAqspYVVGLJnWJNVSno9oqD92J7'
        kws = KiteTicker(api_key, access_token)
        print("WebSocket connection test successful!")
        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_close = on_close
        kws.on_error = on_error

        kws.connect(threaded=True)
        
        trading_strategy()
        
        kws.disconnect()
        kws.close()
        
        # Save trade data
        trade_data = {
            'date': datetime.now(IST).date().isoformat(),
            'straddle_data': straddle_data,
            'pnl_updates': {k.strftime('%Y-%m-%d %H:%M:%S'): v for k, v in pnl_updates.items()},
            'order_details': order_details
        }
        
        with open(f"trades/trade_{datetime.now(IST).date().isoformat()}.json", 'w') as f:
            json.dump(trade_data, f, indent=2, default=str)
        
        logger.info("Script execution completed")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()