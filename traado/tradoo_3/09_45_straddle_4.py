import os
import logging
from datetime import datetime, time, timedelta
import time as sleep_time
import pandas as pd
from kiteconnect import KiteConnect, KiteTicker
import pytz
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('banknifty_options_trading.log'),
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
TRADING_START_TIME = time(9, 15, tzinfo=IST)
TRADING_END_TIME = time(15, 15, tzinfo=IST)  # 3:15 PM
CHECK_INTERVAL = 900  # 15 minutes in seconds

# Initialize Kite Connect
api_key = os.getenv('KITE_API_KEY')
access_token = os.getenv('KITE_ACCESS_TOKEN')
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

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


def get_expiry_dates():
    """Get current and next month expiry dates"""
    global current_expiry, next_expiry
    
    # Get all Bank Nifty futures
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    # Get current month and next month expiry
    today = datetime.now(IST).date()
    expiries = sorted(list(set([i['expiry'] for i in banknifty_futures])))
    
    current_expiry = None
    next_expiry = None
    
    for expiry in expiries:
        if expiry >= today:
            if current_expiry is None:
                current_expiry = expiry
            elif next_expiry is None and expiry > current_expiry:
                next_expiry = expiry
                break
    
    logger.info(f"Current expiry: {current_expiry}, Next expiry: {next_expiry}")


def is_expiry_day():
    """Check if today is expiry day"""
    today = datetime.now(IST).date()
    return today == current_expiry


def get_atm_strike(price):
    """Get ATM strike price based on current price"""
    strike_step = 100  # Bank Nifty strike interval
    return round(price / strike_step) * strike_step


def get_option_instruments(expiry_date, strike, option_type):
    """Get option instrument token for given parameters"""
    instruments = kite.instruments("NFO")
    option = [i for i in instruments if 
              i['name'] == 'BANKNIFTY' and 
              i['instrument_type'] == 'CE' if option_type == 'CE' else 'PE' and 
              i['expiry'] == expiry_date and 
              i['strike'] == strike]
    
    if not option:
        logger.error(f"No option found for {option_type} {strike} {expiry_date}")
        return None
    
    return option[0]


def place_order(transaction_type, instrument_token, quantity):
    """Place an order (paper trading - simulate order placement)"""
    try:
        # In paper trading, we'll simulate order placement
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
        
        # Store order details
        if instrument_token not in order_details:
            order_details[instrument_token] = []
        order_details[instrument_token].append(order_data)
        
        return order_id
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return None


def buy_straddle():
    """Buy ATM straddle (CE and PE at same strike)"""
    global straddle_bought, straddle_data
    
    if straddle_bought:
        logger.info("Straddle already bought today. Skipping.")
        return False
    
    # Determine which expiry to use
    expiry_date = next_expiry if is_expiry_day() else current_expiry
    
    # Get ATM strike
    atm_strike = get_atm_strike(current_price)
    logger.info(f"Current price: {current_price}, ATM strike: {atm_strike}")
    
    # Get CE and PE instruments
    ce_instrument = get_option_instruments(expiry_date, atm_strike, 'CE')
    pe_instrument = get_option_instruments(expiry_date, atm_strike, 'PE')
    
    if not ce_instrument or not pe_instrument:
        logger.error("Could not get option instruments for straddle")
        return False
    
    # Place buy orders (simulated in paper trading)
    ce_order_id = place_order('BUY', ce_instrument['instrument_token'], LOT_SIZE)
    pe_order_id = place_order('BUY', pe_instrument['instrument_token'], LOT_SIZE)
    
    if not ce_order_id or not pe_order_id:
        logger.error("Failed to place straddle orders")
        return False
    
    # Record straddle details
    straddle_data = {
        'entry_time': datetime.now(IST),
        'ce_instrument': ce_instrument,
        'pe_instrument': pe_instrument,
        'ce_order_id': ce_order_id,
        'pe_order_id': pe_order_id,
        'ce_entry_price': kite.ltp(f"NFO:{ce_instrument['instrument_token']}")[f"NFO:{ce_instrument['instrument_token']}"]['last_price'],
        'pe_entry_price': kite.ltp(f"NFO:{pe_instrument['instrument_token']}")[f"NFO:{pe_instrument['instrument_token']}"]['last_price'],
        'straddle_entry_value': None,
        'current_pnl': 0,
        'max_pnl': 0,
        'target_pnl': None,
        'stoploss_pnl': None,
        'exit_condition': None,
        'exited': False,
        'partial_exit_done': False,
        'trailing_active': False,
        'trailing_levels': []
    }
    
    straddle_data['straddle_entry_value'] = (straddle_data['ce_entry_price'] + straddle_data['pe_entry_price']) * LOT_SIZE
    straddle_data['target_pnl'] = straddle_data['straddle_entry_value'] * (1 + TARGET_PERCENT/100)
    straddle_data['stoploss_pnl'] = straddle_data['straddle_entry_value'] * (1 - STOPLOSS_PERCENT/100)
    
    logger.info(f"Straddle bought. CE: {straddle_data['ce_entry_price']}, PE: {straddle_data['pe_entry_price']}")
    logger.info(f"Total straddle value: {straddle_data['straddle_entry_value']}")
    logger.info(f"Target: {straddle_data['target_pnl']}, Stoploss: {straddle_data['stoploss_pnl']}")
    
    straddle_bought = True
    return True


def check_exit_conditions():
    """Check if exit conditions are met for the straddle"""
    global straddle_data
    
    if not straddle_bought or straddle_data.get('exited', True):
        return
    
    # Get current prices
    ce_price = kite.ltp(f"NFO:{straddle_data['ce_instrument']['instrument_token']}")[f"NFO:{straddle_data['ce_instrument']['instrument_token']}"]['last_price']
    pe_price = kite.ltp(f"NFO:{straddle_data['pe_instrument']['instrument_token']}")[f"NFO:{straddle_data['pe_instrument']['instrument_token']}"]['last_price']
    
    current_value = (ce_price + pe_price) * LOT_SIZE
    current_pnl = current_value - straddle_data['straddle_entry_value']
    pnl_percent = (current_pnl / straddle_data['straddle_entry_value']) * 100
    
    # Update max PNL
    if current_pnl > straddle_data['max_pnl']:
        straddle_data['max_pnl'] = current_pnl
    
    straddle_data['current_pnl'] = current_pnl
    pnl_updates[datetime.now(IST)] = current_pnl
    
    # Log PNL every second
    logger.info(f"Current PNL: {current_pnl:.2f} ({pnl_percent:.2f}%) | Max PNL: {straddle_data['max_pnl']:.2f}")
    
    # Check stoploss
    if current_value <= straddle_data['stoploss_pnl']:
        logger.info(f"Stoploss hit. Current value: {current_value}, Stoploss: {straddle_data['stoploss_pnl']}")
        exit_straddle('STOPLOSS')
        return
    
    # Check for partial exit condition (initial target)
    if not straddle_data['partial_exit_done'] and current_value >= straddle_data['target_pnl']:
        logger.info(f"Initial target hit. Current value: {current_value}, Target: {straddle_data['target_pnl']}")
        
        # Calculate individual leg PNLs
        ce_pnl = (ce_price - straddle_data['ce_entry_price']) * LOT_SIZE
        pe_pnl = (pe_price - straddle_data['pe_entry_price']) * LOT_SIZE
        
        # Exit the losing leg or the leg with minimum profit
        if ce_pnl < 0 or pe_pnl < 0:
            # Exit the losing leg
            if ce_pnl < pe_pnl:
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'PE'
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'CE'
        else:
            # Both legs in profit, exit the one with less profit
            if ce_pnl < pe_pnl:
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'PE'
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'CE'
        
        straddle_data['partial_exit_done'] = True
        straddle_data['trailing_active'] = True
        straddle_data['trailing_start_value'] = current_value
        straddle_data['next_trailing_level'] = current_value * (1 + TRAILING_PERCENT/100)
        logger.info(f"Partial exit complete. Trailing active on {straddle_data['trailing_leg']}. Next level: {straddle_data['next_trailing_level']:.2f}")
        return
    
    # Check trailing stop for remaining leg
    if straddle_data.get('trailing_active', False):
        if current_value >= straddle_data['next_trailing_level']:
            logger.info(f"Trailing level hit. Current value: {current_value}, Next level: {straddle_data['next_trailing_level']}")
            straddle_data['trailing_levels'].append(current_value)
            
            # Exit the remaining leg
            if straddle_data['trailing_leg'] == 'CE':
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TRAILING_TARGET')
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TRAILING_TARGET')
            
            straddle_data['exited'] = True
            logger.info(f"Straddle completely exited via trailing. Final PNL: {current_pnl:.2f}")


def exit_leg(instrument_token, leg_type, reason):
    """Exit one leg of the straddle"""
    # Simulate order placement
    order_id = place_order('SELL', instrument_token, LOT_SIZE)
    
    if not order_id:
        logger.error(f"Failed to exit {leg_type} leg")
        return False
    
    logger.info(f"Exited {leg_type} leg due to {reason}")
    return True


def exit_straddle(reason):
    """Exit both legs of the straddle"""
    global straddle_data
    
    # Exit CE leg if not already exited
    if 'ce_instrument' in straddle_data and not straddle_data.get('ce_exited', False):
        exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', reason)
        straddle_data['ce_exited'] = True
    
    # Exit PE leg if not already exited
    if 'pe_instrument' in straddle_data and not straddle_data.get('pe_exited', False):
        exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', reason)
        straddle_data['pe_exited'] = True
    
    straddle_data['exited'] = True
    straddle_data['exit_time'] = datetime.now(IST)
    straddle_data['exit_condition'] = reason
    straddle_data['final_pnl'] = straddle_data['current_pnl']
    
    logger.info(f"Straddle completely exited due to {reason}")
    logger.info(f"Final PNL: {straddle_data['current_pnl']:.2f}")
    logger.info(f"Maximum PNL achieved: {straddle_data['max_pnl']:.2f}")
    logger.info(f"Trailing levels hit: {len(straddle_data['trailing_levels'])}")


def on_ticks(ws, ticks):
    """Handle incoming ticks from WebSocket"""
    global current_price, trading_day_high, trading_day_low
    
    for tick in ticks:
        # Update current price (assuming Bank Nifty future tick)
        if tick['instrument_token'] == banknifty_future_token:
            current_price = tick['last_price']
            
            # Update day's high/low
            if trading_day_high is None or tick['last_price'] > trading_day_high:
                trading_day_high = tick['last_price']
            if trading_day_low is None or tick['last_price'] < trading_day_low:
                trading_day_low = tick['last_price']
    
    # Check exit conditions if straddle is active
    check_exit_conditions()


def on_connect(ws, response):
    """Callback when WebSocket is connected"""
    ws.subscribe([banknifty_future_token])
    ws.set_mode(ws.MODE_LTP, [banknifty_future_token])
    logger.info("WebSocket connected and subscribed to Bank Nifty")


def on_close(ws, code, reason):
    """Callback when WebSocket is closed"""
    logger.info(f"WebSocket closed. Code: {code}, Reason: {reason}")


def initialize_trading():
    """Initialize trading session"""
    global banknifty_future_token, trading_day_high, trading_day_low, straddle_bought
    
    # Reset for new day
    trading_day_high = None
    trading_day_low = None
    straddle_bought = False
    straddle_data.clear()
    pnl_updates.clear()
    order_details.clear()
    
    # Get Bank Nifty future instrument
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    # Get current month future
    today = datetime.now(IST).date()
    current_month_future = [f for f in banknifty_futures if f['expiry'].month == today.month and f['expiry'].year == today.year][0]
    banknifty_future_token = current_month_future['instrument_token']
    
    # Get expiry dates
    get_expiry_dates()
    
    logger.info("Trading session initialized")


def trading_strategy():
    """Main trading strategy logic"""
    global straddle_bought
    
    now = datetime.now(IST)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
    
    # Wait until 10 AM to start checking
    if now.time() < time(10, 0, tzinfo=IST):
        sleep_seconds = (start_time - now).total_seconds()
        logger.info(f"Waiting until 10 AM. Sleeping for {sleep_seconds:.0f} seconds...")
        sleep_time.sleep(sleep_seconds)
    
    # Main trading loop
    while now.time() <= end_time.time() and not straddle_bought:
        now = datetime.now(IST)
        
        # Check if price crossed day's high/low
        if current_price > trading_day_high or current_price < trading_day_low:
            logger.info(f"Price crossed day's range. High: {trading_day_high}, Low: {trading_day_low}, Current: {current_price}")
            buy_straddle()
        else:
            logger.info(f"No crossover yet. High: {trading_day_high}, Low: {trading_day_low}, Current: {current_price}")
            
            # Wait for next 15-minute interval
            next_check = now + timedelta(seconds=CHECK_INTERVAL)
            if next_check.time() > end_time.time():
                break
                
            sleep_seconds = (next_check - now).total_seconds()
            logger.info(f"Waiting for next check at {next_check.time()}. Sleeping for {sleep_seconds:.0f} seconds...")
            sleep_time.sleep(sleep_seconds)
    
    # If straddle was bought, keep checking exit conditions until market closes
    while now.time() <= TRADING_END_TIME.time() and straddle_bought and not straddle_data.get('exited', False):
        check_exit_conditions()
        sleep_time.sleep(1)  # Check every second
        now = datetime.now(IST)
    
    # Exit any remaining positions at market close
    if straddle_bought and not straddle_data.get('exited', False):
        logger.info("Market closing. Exiting straddle...")
        exit_straddle('MARKET_CLOSE')
    
    logger.info("Trading session completed")


def main():
    """Main function"""
    try:
        logger.info("Starting Bank Nifty Options Trading Script")
        
        # Initialize trading session
        initialize_trading()
        
        # Connect to WebSocket
        kws = KiteTicker(api_key, access_token)
        
        # Assign callbacks
        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_close = on_close
        
        # Start WebSocket in a separate thread
        kws.connect(threaded=True)
        
        # Run trading strategy
        trading_strategy()
        
        # Disconnect WebSocket
        kws.disconnect()
        
        # Save trade data to file
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
        logger.error(f"Error in main execution: {e}", exc_info=True)


if __name__ == "__main__":
    main()