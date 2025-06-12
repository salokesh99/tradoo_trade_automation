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
TRADING_START_TIME = time(9, 15, tzinfo=IST)
TRADING_END_TIME = time(15, 15, tzinfo=IST)
CHECK_INTERVAL = 900  # 15 minutes in seconds

# Initialize Kite Connect
# api_key = os.getenv('KITE_API_KEY')
# access_token = os.getenv('KITE_ACCESS_TOKEN')

api_key = "d7fg3jqz3k1i6eio"
api_secret = "ngh8ag2owecpv05l8gbbdwe7491ikerx"
print('https://kite.zerodha.com/connect/login?api_key=d7fg3jqz3k1i6eio&v=3')

access_token = input('Enter the Input Token --\n')
# A5fatS68JPjFZBo9qMQUIva65Qx8LL22



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
banknifty_future_token = None

def is_market_open_day():
    """Check if current day is a trading day (weekday + not holiday)"""
    today = datetime.now(IST).date()
    
    # Check weekend (Saturday=5, Sunday=6)
    if today.weekday() >= 5:
        logger.info(f"Weekend detected ({today.strftime('%A')})")
        return False
    
    # Check India market holidays
    in_holidays = holidays.India(years=today.year)
    if today in in_holidays:
        logger.info(f"Market holiday detected: {in_holidays.get(today)}")
        return False
    
    return True

def get_expiry_dates():
    """Get current and next month expiry dates"""
    global current_expiry, next_expiry
    
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    today = datetime.now(IST).date()
    expiries = sorted(list(set(i['expiry'] for i in banknifty_futures)))
    
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
    if option_type == 'CE':
         expected_type = 'CE' 
    else :
        expected_type = 'PE'
    
    option = [
        i for i in instruments 
        if (i['name'] == 'BANKNIFTY' and
            i['instrument_type'] == expected_type and
            i['expiry'] == expiry_date and
            i['strike'] == strike)
    ]
    print(option)

    if not option:
        logger.error(f"No option found for {option_type} {strike} {expiry_date}")
        return None
    
    return option[0]

def place_order(transaction_type, instrument_token, quantity):
    """Place an order (paper trading - simulate order placement)"""
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
        logger.error(f"Error placing order: {e}")
        return None

def buy_straddle():
    """Buy ATM straddle (CE and PE at same strike)"""
    global straddle_bought, straddle_data
    
    if straddle_bought:
        logger.info("Straddle already bought today. Skipping.")
        return False
    
    expiry_date = next_expiry if is_expiry_day() else current_expiry
    atm_strike = get_atm_strike(current_price)
    logger.info(f"Current price: {current_price}, ATM strike: {atm_strike}")
    
    ce_instrument = get_option_instruments(expiry_date, atm_strike, 'CE')
    pe_instrument = get_option_instruments(expiry_date, atm_strike, 'PE')
    
    if not ce_instrument or not pe_instrument:
        logger.error("Could not get option instruments for straddle")
        return False
    
    ce_order_id = place_order('BUY', ce_instrument['instrument_token'], LOT_SIZE)
    pe_order_id = place_order('BUY', pe_instrument['instrument_token'], LOT_SIZE)
    
    if not ce_order_id or not pe_order_id:
        logger.error("Failed to place straddle orders")
        return False
    
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
    
    ce_price = kite.ltp(f"NFO:{straddle_data['ce_instrument']['instrument_token']}")[f"NFO:{straddle_data['ce_instrument']['instrument_token']}"]['last_price']
    pe_price = kite.ltp(f"NFO:{straddle_data['pe_instrument']['instrument_token']}")[f"NFO:{straddle_data['pe_instrument']['instrument_token']}"]['last_price']
    
    current_value = (ce_price + pe_price) * LOT_SIZE
    current_pnl = current_value - straddle_data['straddle_entry_value']
    pnl_percent = (current_pnl / straddle_data['straddle_entry_value']) * 100
    
    if current_pnl > straddle_data['max_pnl']:
        straddle_data['max_pnl'] = current_pnl
    
    straddle_data['current_pnl'] = current_pnl
    pnl_updates[datetime.now(IST)] = current_pnl
    
    logger.info(f"Current PNL: {current_pnl:.2f} ({pnl_percent:.2f}%) | Max PNL: {straddle_data['max_pnl']:.2f}")
    
    if current_value <= straddle_data['stoploss_pnl']:
        logger.info(f"Stoploss hit. Current value: {current_value}, Stoploss: {straddle_data['stoploss_pnl']}")
        exit_straddle('STOPLOSS')
        return
    
    if not straddle_data['partial_exit_done'] and current_value >= straddle_data['target_pnl']:
        logger.info(f"Initial target hit. Current value: {current_value}, Target: {straddle_data['target_pnl']}")
        
        ce_pnl = (ce_price - straddle_data['ce_entry_price']) * LOT_SIZE
        pe_pnl = (pe_price - straddle_data['pe_entry_price']) * LOT_SIZE
        
        if ce_pnl < 0 or pe_pnl < 0:
            if ce_pnl < pe_pnl:
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'PE'
                straddle_data['trailing_leg_price'] = pe_price
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'CE'
                straddle_data['trailing_leg_price'] = ce_price
        else:
            if ce_pnl < pe_pnl:
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'PE'
                straddle_data['trailing_leg_price'] = pe_price
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TARGET_PARTIAL')
                straddle_data['trailing_leg'] = 'CE'
                straddle_data['trailing_leg_price'] = ce_price
        
        straddle_data['partial_exit_done'] = True
        straddle_data['trailing_active'] = True
        straddle_data['trailing_start_value'] = current_value
        straddle_data['trailing_sl_price'] = straddle_data['trailing_leg_price'] * (1 - STOPLOSS_PERCENT/100)
        logger.info(f"Partial exit complete. Trailing active on {straddle_data['trailing_leg']}. Current price: {straddle_data['trailing_leg_price']:.2f}, Trailing SL: {straddle_data['trailing_sl_price']:.2f}")
        return
    
    if straddle_data.get('trailing_active', False):
        current_leg_price = ce_price if straddle_data['trailing_leg'] == 'CE' else pe_price
        
        if current_leg_price > straddle_data['trailing_leg_price']:
            straddle_data['trailing_leg_price'] = current_leg_price
            new_sl = current_leg_price * (1 - STOPLOSS_PERCENT/100)
            if new_sl > straddle_data['trailing_sl_price']:
                straddle_data['trailing_sl_price'] = new_sl
                logger.info(f"Updated trailing SL for {straddle_data['trailing_leg']} to {new_sl:.2f}")
        
        if current_leg_price <= straddle_data['trailing_sl_price']:
            logger.info(f"Trailing SL hit for {straddle_data['trailing_leg']}. Current price: {current_leg_price:.2f}, SL: {straddle_data['trailing_sl_price']:.2f}")
            
            if straddle_data['trailing_leg'] == 'CE':
                exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', 'TRAILING_SL')
            else:
                exit_leg(straddle_data['pe_instrument']['instrument_token'], 'PE', 'TRAILING_SL')
            
            straddle_data['exited'] = True
            logger.info(f"Straddle completely exited via trailing SL. Final PNL: {current_pnl:.2f}")

def exit_leg(instrument_token, leg_type, reason):
    """Exit one leg of the straddle"""
    order_id = place_order('SELL', instrument_token, LOT_SIZE)
    
    if not order_id:
        logger.error(f"Failed to exit {leg_type} leg")
        return False
    
    logger.info(f"Exited {leg_type} leg due to {reason}")
    return True

def exit_straddle(reason):
    """Exit both legs of the straddle"""
    global straddle_data
    
    if 'ce_instrument' in straddle_data and not straddle_data.get('ce_exited', False):
        exit_leg(straddle_data['ce_instrument']['instrument_token'], 'CE', reason)
        straddle_data['ce_exited'] = True
    
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
        if tick['instrument_token'] == banknifty_future_token:
            print('tick', tick)
            current_price = tick['last_price']
            
            if trading_day_high is None or tick['last_price'] > trading_day_high:
                trading_day_high = tick['last_price']
            if trading_day_low is None or tick['last_price'] < trading_day_low:
                trading_day_low = tick['last_price']
    
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
    
    if not is_market_open_day():
        logger.info("Not a trading day - exiting")
        sys.exit(0)
        
    now = datetime.now(IST)
    if now.time() < TRADING_START_TIME or now.time() > TRADING_END_TIME:
        logger.info(f"Outside market hours (9:15 AM - 3:15 PM IST)")
        sys.exit(0)
    
    trading_day_high = None
    trading_day_low = None
    straddle_bought = False
    straddle_data.clear()
    pnl_updates.clear()
    order_details.clear()
    
    instruments = kite.instruments("NFO")
    banknifty_futures = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    today = datetime.now(IST).date()
    current_month_future = [f for f in banknifty_futures if f['expiry'].month == today.month and f['expiry'].year == today.year][0]
    print('current month future', current_month_future)
    banknifty_future_token = current_month_future['instrument_token']
    print('banknifty_future_token', banknifty_future_token)
    
    get_expiry_dates()
    logger.info("Trading session initialized")

def trading_strategy():
    global straddle_bought, current_price, trading_day_high, trading_day_low
    
    # Initialize price variables if None
    if current_price is None or trading_day_high is None or trading_day_low is None:
        logger.error("Price data not initialized properly")
        return
    
    now = datetime.now(IST)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
    
    if now.time() < time(10, 0, tzinfo=IST):
        sleep_seconds = (start_time - now).total_seconds()
        logger.info(f"Waiting until 10 AM. Sleeping for {sleep_seconds:.0f} seconds...")
        sleep_time.sleep(sleep_seconds)
    
    while now.time() <= end_time.time() and not straddle_bought:
        now = datetime.now(IST)
        
        if current_price > trading_day_high or current_price < trading_day_low:
            logger.info(f"Price crossed day's range. High: {trading_day_high}, Low: {trading_day_low}, Current: {current_price}")
            buy_straddle()
        else:
            logger.info(f"No crossover yet. High: {trading_day_high}, Low: {trading_day_low}, Current: {current_price}")
            
            next_check = now + timedelta(seconds=CHECK_INTERVAL)
            if next_check.time() > end_time.time():
                break
                
            sleep_seconds = (next_check - now).total_seconds()
            logger.info(f"Waiting for next check at {next_check.time()}. Sleeping for {sleep_seconds:.0f} seconds...")
            sleep_time.sleep(sleep_seconds)
    
    while now.time() <= TRADING_END_TIME.time() and straddle_bought and not straddle_data.get('exited', False):
        check_exit_conditions()
        sleep_time.sleep(1)
        now = datetime.now(IST)
    
    if straddle_bought and not straddle_data.get('exited', False):
        logger.info("Market closing. Exiting straddle...")
        exit_straddle('MARKET_CLOSE')
    
    logger.info("Trading session completed")

def main():
    try:
        logger.info("Starting BankNifty Options Trading Strategy")
        
        if not is_market_open_day():
            logger.info("Exiting: Not a trading day")
            sys.exit(0)
            
        now = datetime.now(IST)
        if now.time() < TRADING_START_TIME:
            logger.info(f"Waiting until market opens at {TRADING_START_TIME}")
            sleep_time.sleep((datetime.combine(now.date(), TRADING_START_TIME) - now).total_seconds())
        elif now.time() > TRADING_END_TIME:
            logger.info(f"Market already closed at {TRADING_END_TIME}")
            sys.exit(0)
            
        initialize_trading()
        
        kws = KiteTicker(api_key, access_token)
        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_close = on_close
        kws.connect(threaded=True)
        
        trading_strategy()
        kws.disconnect()
        
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