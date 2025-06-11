import os
import time
import datetime
import logging
import json
import requests
import threading
import pytz
from kiteconnect import KiteConnect, KiteTicker
from typing import Optional, Dict, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nifty_straddle_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
NIFTY_SYMBOL = "NIFTY 50"
LOT_SIZE = 75
STRIKE_MULTIPLE = 50  # Nifty strikes are in multiples of 50
TRADING_START_TIME = datetime.time(9, 15)  # 9:15 AM
TRADING_END_TIME = datetime.time(15, 15)    # 3:15 PM
TZ = pytz.timezone('Asia/Kolkata')
INITIAL_TARGET_PCT = 2.5
INITIAL_SL_PCT = 2.5
TRAILING_SL_PCT = 1.0
TRAILING_PROFIT_STEP_PCT = 1.5

# Zerodha API configuration
API_KEY = os.getenv("ZERODHA_API_KEY")
API_SECRET = os.getenv("ZERODHA_API_SECRET")
ACCESS_TOKEN = os.getenv("ZERODHA_ACCESS_TOKEN")

class NiftyStraddleBot:
    def __init__(self):
        self.current_price = 0.0
        self.days_high = 0.0
        self.days_low = float('inf')
        self.last_15min_high = 0.0
        self.last_15min_low = float('inf')
        self.straddle_bought = False
        self.straddle_price = 0.0
        self.ce_leg = None
        self.pe_leg = None
        self.initial_sl = 0.0
        self.initial_target = 0.0
        self.trailing_sl = 0.0
        self.current_pnl = 0.0
        self.kite = None
        self.kws = None
        self.is_expiry_day = self.check_if_expiry_day()
        self.expiry_date = self.get_expiry_date()
        self.running = True
        self.instruments = None
        self.nifty_token = None
        self.last_15min_check = None
        
        # Initialize Kite Connect
        self.initialize_kite()
        
    def initialize_kite(self):
        """Initialize Zerodha Kite Connect and Kite Ticker"""
        try:
            self.kite = KiteConnect(api_key=API_KEY)
            if ACCESS_TOKEN:
                self.kite.set_access_token(ACCESS_TOKEN)
            
            # Fetch instruments and get Nifty token
            self.instruments = self.kite.instruments("NFO")
            self.nifty_token = self.get_nifty_token()
            
            # Initialize WebSocket
            self.kws = KiteTicker(API_KEY, ACCESS_TOKEN)
            
            logger.info("Zerodha API initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Zerodha API: {str(e)}")
            raise
    
    def get_nifty_token(self) -> int:
        """Get Nifty index token for subscription"""
        equity_instruments = self.kite.instruments("NSE")
        for instrument in equity_instruments:
            if instrument['tradingsymbol'] == NIFTY_SYMBOL:
                return instrument['instrument_token']
        raise ValueError("Nifty instrument not found")
    
    def check_if_expiry_day(self) -> bool:
        """Check if today is Nifty weekly expiry day (Thursday)"""
        today = datetime.datetime.now(TZ).date()
        return today.weekday() == 3  # Thursday
    
    def get_expiry_date(self) -> str:
        """Get current or next week's expiry date in format YYYY-MM-DD"""
        today = datetime.datetime.now(TZ)
        
        if not self.is_expiry_day:
            # Current week expiry (Thursday)
            expiry = today + datetime.timedelta((3 - today.weekday()) % 7)
        else:
            # Next week expiry
            expiry = today + datetime.timedelta((3 - today.weekday()) % 7 + 7)
            
        return expiry.strftime("%Y-%m-%d")
    
    def get_atm_strike(self) -> int:
        """Get ATM strike price based on current Nifty price"""
        return round(self.current_price / STRIKE_MULTIPLE) * STRIKE_MULTIPLE
    
    def get_option_symbol(self, option_type: str, strike: int) -> Dict:
        """Find option instrument details based on strike and type"""
        expiry_str = datetime.datetime.strptime(self.expiry_date, "%Y-%m-%d").strftime("%d%b%y").upper()
        symbol = f"{NIFTY_SYMBOL.replace(' ', '')}{expiry_str}{strike}{option_type}"
        
        for instrument in self.instruments:
            if (instrument['name'] == NIFTY_SYMBOL and 
                instrument['expiry'] == self.expiry_date and
                instrument['strike'] == strike and
                instrument['instrument_type'] == option_type):
                return {
                    'instrument_token': instrument['instrument_token'],
                    'tradingsymbol': instrument['tradingsymbol']
                }
        raise ValueError(f"Option instrument not found: {symbol}")
    
    def place_order(self, tradingsymbol: str, quantity: int, is_buy: bool) -> Optional[Dict]:
        """Place order through Zerodha Kite API"""
        try:
            transaction_type = KiteConnect.TRANSACTION_TYPE_BUY if is_buy else KiteConnect.TRANSACTION_TYPE_SELL
            order_type = KiteConnect.ORDER_TYPE_MARKET
            product = KiteConnect.PRODUCT_MIS
            
            # Retry logic (3 attempts)
            for attempt in range(3):
                try:
                    order_id = self.kite.place_order(
                        variety=KiteConnect.VARIETY_REGULAR,
                        exchange=KiteConnect.EXCHANGE_NFO,
                        tradingsymbol=tradingsymbol,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        product=product,
                        order_type=order_type
                    )
                    
                    logger.info(f"Order placed successfully. ID: {order_id}")
                    return order_id
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise
                    logger.warning(f"Order placement failed (attempt {attempt+1}). Retrying...")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return None
    
    def buy_straddle(self) -> bool:
        """Buy ATM straddle (CE and PE at same strike)"""
        if self.straddle_bought:
            logger.info("Straddle already bought today")
            return False
            
        atm_strike = self.get_atm_strike()
        
        try:
            ce_instrument = self.get_option_symbol("CE", atm_strike)
            pe_instrument = self.get_option_symbol("PE", atm_strike)
            
            # Get current LTP for both options
            ce_ltp = self.kite.ltp([f"NFO:{ce_instrument['tradingsymbol']}"])[f"NFO:{ce_instrument['tradingsymbol']}"]['last_price']
            pe_ltp = self.kite.ltp([f"NFO:{pe_instrument['tradingsymbol']}"])[f"NFO:{pe_instrument['tradingsymbol']}"]['last_price']
            
            # Place CE order
            ce_order_id = self.place_order(ce_instrument['tradingsymbol'], LOT_SIZE, True)
            if not ce_order_id:
                logger.error("Failed to place CE order")
                return False
            
            # Place PE order
            pe_order_id = self.place_order(pe_instrument['tradingsymbol'], LOT_SIZE, True)
            if not pe_order_id:
                logger.error("Failed to place PE order")
                # Attempt to cancel CE order if PE failed
                self.place_order(ce_instrument['tradingsymbol'], LOT_SIZE, False)
                return False
            
            self.ce_leg = {
                'tradingsymbol': ce_instrument['tradingsymbol'],
                'instrument_token': ce_instrument['instrument_token'],
                'price': ce_ltp,
                'quantity': LOT_SIZE,
                'order_id': ce_order_id
            }
            
            self.pe_leg = {
                'tradingsymbol': pe_instrument['tradingsymbol'],
                'instrument_token': pe_instrument['instrument_token'],
                'price': pe_ltp,
                'quantity': LOT_SIZE,
                'order_id': pe_order_id
            }
            
            self.straddle_price = ce_ltp + pe_ltp
            self.straddle_bought = True
            self.initial_sl = self.straddle_price * (1 - INITIAL_SL_PCT/100)
            self.initial_target = self.straddle_price * (1 + INITIAL_TARGET_PCT/100)
            self.trailing_sl = self.straddle_price * (1 + TRAILING_SL_PCT/100)
            
            logger.info(f"Straddle bought at strike {atm_strike}. CE: {ce_ltp}, PE: {pe_ltp}")
            logger.info(f"Initial SL: {self.initial_sl}, Initial Target: {self.initial_target}")
            
            # Subscribe to option ticks for exit conditions
            tokens = [self.ce_leg['instrument_token'], self.pe_leg['instrument_token']]
            self.kws.subscribe(tokens)
            self.kws.set_mode(self.kws.MODE_QUOTE, tokens)
            
            return True
            
        except Exception as e:
            logger.error(f"Error buying straddle: {str(e)}")
            return False
    
    def exit_leg(self, leg: Dict, reason: str) -> bool:
        """Exit a single leg of the straddle"""
        try:
            logger.info(f"Exiting {leg['tradingsymbol']} {reason}")
            exit_order_id = self.place_order(leg['tradingsymbol'], leg['quantity'], False)
            
            if exit_order_id:
                logger.info(f"Successfully exited {leg['tradingsymbol']}")
                return True
            else:
                logger.error(f"Failed to exit {leg['tradingsymbol']}")
                return False
        except Exception as e:
            logger.error(f"Error exiting leg: {str(e)}")
            return False
    
    def exit_straddle(self, reason: str) -> bool:
        """Exit both legs of the straddle"""
        success = True
        
        if self.ce_leg:
            if not self.exit_leg(self.ce_leg, reason):
                success = False
                
        if self.pe_leg:
            if not self.exit_leg(self.pe_leg, reason):
                success = False
                
        if success:
            self.straddle_bought = False
            self.ce_leg = None
            self.pe_leg = None
            logger.info("Straddle exited successfully")
            
        return success
    
    def calculate_current_pnl(self) -> float:
        """Calculate current PnL based on current prices"""
        if not self.straddle_bought:
            return 0.0
            
        try:
            # Get current LTP for both options
            ce_ltp = self.kite.ltp([f"NFO:{self.ce_leg['tradingsymbol']}"])[f"NFO:{self.ce_leg['tradingsymbol']}"]['last_price']
            pe_ltp = self.kite.ltp([f"NFO:{self.pe_leg['tradingsymbol']}"])[f"NFO:{self.pe_leg['tradingsymbol']}"]['last_price']
            
            ce_pnl = (ce_ltp - self.ce_leg['price']) * LOT_SIZE
            pe_pnl = (pe_ltp - self.pe_leg['price']) * LOT_SIZE
            total_pnl = ce_pnl + pe_pnl
            
            self.current_pnl = total_pnl
            return total_pnl
        except Exception as e:
            logger.error(f"Error calculating PnL: {str(e)}")
            return 0.0
    
    def check_exit_conditions(self) -> bool:
        """Check if exit conditions are met"""
        if not self.straddle_bought:
            return False
            
        total_pnl = self.calculate_current_pnl()
        total_value = self.straddle_price * LOT_SIZE * 2  # Both legs
        
        # Check initial SL
        if total_pnl <= -abs(total_value * INITIAL_SL_PCT / 100):
            logger.info(f"Initial SL hit. PnL: {total_pnl}")
            self.exit_straddle("Initial SL hit")
            return True
            
        # Check initial target
        if total_pnl >= total_value * INITIAL_TARGET_PCT / 100:
            logger.info(f"Initial target hit. PnL: {total_pnl}")
            
            # Exit the losing leg or least profitable leg
            ce_pnl = (self.kite.ltp([f"NFO:{self.ce_leg['tradingsymbol']}"])[f"NFO:{self.ce_leg['tradingsymbol']}"]['last_price'] - self.ce_leg['price']) * LOT_SIZE
            pe_pnl = (self.kite.ltp([f"NFO:{self.pe_leg['tradingsymbol']}"])[f"NFO:{self.pe_leg['tradingsymbol']}"]['last_price'] - self.pe_leg['price']) * LOT_SIZE
            
            if ce_pnl < pe_pnl:
                # Exit CE leg
                self.exit_leg(self.ce_leg, "Initial target hit - exiting weaker leg")
                self.ce_leg = None
                # Unsubscribe from CE ticks
                self.kws.unsubscribe([self.ce_leg['instrument_token']])
            else:
                # Exit PE leg
                self.exit_leg(self.pe_leg, "Initial target hit - exiting weaker leg")
                self.pe_leg = None
                # Unsubscribe from PE ticks
                self.kws.unsubscribe([self.pe_leg['instrument_token']])
                
            # Update trailing SL
            self.trailing_sl = self.straddle_price * (1 + TRAILING_SL_PCT/100)
            return False
            
        # Check trailing SL if only one leg remains
        if (self.ce_leg is None or self.pe_leg is None) and total_pnl >= total_value * TRAILING_SL_PCT / 100:
            # Trail the profit
            if total_pnl >= self.current_pnl + total_value * TRAILING_PROFIT_STEP_PCT / 100:
                self.trailing_sl = total_pnl - total_value * TRAILING_PROFIT_STEP_PCT / 100
                logger.info(f"Trailing SL updated to {self.trailing_sl}")
                
            if total_pnl <= self.trailing_sl:
                logger.info(f"Trailing SL hit. PnL: {total_pnl}")
                self.exit_straddle("Trailing SL hit")
                return True
                
        return False
    
    def on_ticks(self, ws, ticks):
        """Callback for WebSocket ticks"""
        for tick in ticks:
            # Update Nifty price
            if tick['instrument_token'] == self.nifty_token:
                self.current_price = tick['last_price']
                
                # Update day's high/low
                if 'ohlc' in tick:
                    if tick['ohlc']['high'] > self.days_high:
                        self.days_high = tick['ohlc']['high']
                    if tick['ohlc']['low'] < self.days_low:
                        self.days_low = tick['ohlc']['low']
                
                # Update last 15min high/low
                if self.current_price > self.last_15min_high:
                    self.last_15min_high = self.current_price
                if self.current_price < self.last_15min_low:
                    self.last_15min_low = self.current_price
            
            # Update option prices if straddle is active
            if self.straddle_bought:
                if self.ce_leg and tick['instrument_token'] == self.ce_leg['instrument_token']:
                    self.ce_leg['last_price'] = tick['last_price']
                if self.pe_leg and tick['instrument_token'] == self.pe_leg['instrument_token']:
                    self.pe_leg['last_price'] = tick['last_price']
    
    def on_connect(self, ws, response):
        """Callback when WebSocket connects"""
        logger.info("WebSocket connected")
        # Subscribe to Nifty index
        self.kws.subscribe([self.nifty_token])
        self.kws.set_mode(self.kws.MODE_QUOTE, [self.nifty_token])
    
    def on_close(self, ws, code, reason):
        """Callback when WebSocket closes"""
        logger.warning(f"WebSocket closed: {reason}")
        # Attempt to reconnect
        self.connect_websocket()
    
    def connect_websocket(self):
        """Connect to Zerodha WebSocket"""
        try:
            # Assign callbacks
            self.kws.on_ticks = self.on_ticks
            self.kws.on_connect = self.on_connect
            self.kws.on_close = self.on_close
            
            # Start WebSocket connection
            self.kws.connect(threaded=True)
            logger.info("WebSocket connection started")
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}")
            return False
    
    def check_entry_condition(self):
        """Check if entry condition is met (price breaks 15min high/low)"""
        now = datetime.datetime.now(TZ)
        current_time = now.time()
        
        # Only check between 9:15 AM and 3:15 PM
        if current_time < TRADING_START_TIME or current_time > TRADING_END_TIME:
            return False
            
        # Check every 15 minutes
        if self.last_15min_check and (now - self.last_15min_check).total_seconds() < 900:
            return False
            
        # Check if price breaks 15min high/low
        if self.current_price > self.last_15min_high or self.current_price < self.last_15min_low:
            logger.info(f"Entry condition met. Price: {self.current_price}, 15min High: {self.last_15min_high}, 15min Low: {self.last_15min_low}")
            self.last_15min_check = now
            return self.buy_straddle()
            
        # Reset 15min high/low for next interval
        self.last_15min_high = self.current_price
        self.last_15min_low = self.current_price
        self.last_15min_check = now
        return False
    
    def run(self):
        """Main trading loop"""
        logger.info("Starting Nifty Straddle Bot")
        logger.info(f"Is Expiry Day: {self.is_expiry_day}, Expiry Date: {self.expiry_date}")
        
        # Connect to WebSocket
        if not self.connect_websocket():
            logger.error("Failed to connect to WebSocket. Exiting.")
            return
            
        try:
            while self.running:
                now = datetime.datetime.now(TZ)
                current_time = now.time()
                
                # Check if we should stop trading for the day
                if current_time > TRADING_END_TIME:
                    if self.straddle_bought:
                        logger.info("Market closing time reached. Exiting straddle.")
                        self.exit_straddle("Market closing")
                    logger.info("Trading session ended.")
                    self.running = False
                    break
                
                # Check entry conditions if straddle not bought yet
                if not self.straddle_bought and current_time >= TRADING_START_TIME:
                    self.check_entry_condition()
                
                # Check exit conditions if straddle is active
                if self.straddle_bought:
                    self.check_exit_conditions()
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
        finally:
            self.running = False
            if self.kws:
                self.kws.close()
            logger.info("Nifty Straddle Bot stopped")

if __name__ == "__main__":
    bot = NiftyStraddleBot()
    bot.run()