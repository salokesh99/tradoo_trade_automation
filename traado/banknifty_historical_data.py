import os
import sys
import logging
import csv
import time
from datetime import datetime, timedelta, date
import pytz
import json
from kiteconnect import KiteConnect
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('banknifty_historical_data.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
IST = pytz.timezone('Asia/Kolkata')
DATA_INTERVAL = 'day'  # 'day' for daily data, '15minute' for intraday
OUTPUT_DIR = 'historical_data'
CSV_HEADERS = ['date', 'open', 'high', 'low', 'close', 'volume', 'instrument_token', 'strike', 'option_type', 'expiry']

class BankNiftyHistoricalDataFetcher:
    def __init__(self, api_key, api_secret):
        """Initialize the BankNifty Historical Data Fetcher"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = None
        self.access_token = None
        self.instruments_data = None
        
    def authenticate(self):
        """Authenticate with Zerodha using OAuth flow"""
        try:
            logger.info("Starting authentication process...")
            
            # Initialize KiteConnect
            self.kite = KiteConnect(api_key=self.api_key)
            
            # Generate login URL
            login_url = self.kite.login_url()
            print(f"\nPlease visit this URL to login: {login_url}")
            print("After successful login, you will be redirected to a URL.")
            print("Copy the 'request_token' parameter from that URL.\n")
            
            while True:
                request_token = input("Enter the request token: ").strip()
                if not request_token:
                    print("Request token cannot be empty. Please try again.")
                    continue
                
                try:
                    # Generate session
                    data = self.kite.generate_session(request_token, api_secret=self.api_secret)
                    self.access_token = data["access_token"]
                    
                    # Set access token
                    self.kite.set_access_token(self.access_token)
                    
                    # Test connection
                    profile = self.kite.profile()
                    logger.info(f"Successfully authenticated! Logged in as: {profile.get('user_name', 'Unknown')}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Authentication failed: {str(e)}")
                    print("Please check if:")
                    print("1. Your request token is correct and fresh")
                    print("2. You have the necessary permissions in your Zerodha account")
                    print("3. Your API key has the required permissions")
                    continue
                    
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def get_instruments(self):
        """Fetch all NFO instruments and filter BankNifty options"""
        try:
            logger.info("Fetching NFO instruments...")
            instruments = self.kite.instruments("NFO")
            
            # Filter BankNifty options
            banknifty_options = [
                i for i in instruments 
                if (i['name'] == 'BANKNIFTY' and 
                    i['instrument_type'] in ['CE', 'PE'] and
                    i['expiry'] is not None)
            ]
            
            logger.info(f"Found {len(banknifty_options)} BankNifty option instruments")
            self.instruments_data = banknifty_options
            return True
            
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {str(e)}")
            return False
    
    def get_available_expiries(self):
        """Get all available expiry dates for BankNifty options"""
        if not self.instruments_data:
            logger.error("Instruments data not available")
            return []
        
        expiries = sorted(list(set([i['expiry'] for i in self.instruments_data])))
        logger.info(f"Available expiries: {[e.strftime('%Y-%m-%d') for e in expiries]}")
        return expiries
    
    def get_strikes_for_expiry(self, expiry_date):
        """Get all available strikes for a specific expiry date"""
        if not self.instruments_data:
            return []
        
        strikes = sorted(list(set([
            i['strike'] for i in self.instruments_data 
            if i['expiry'] == expiry_date
        ])))
        return strikes
    
    def calculate_date_range(self, days_back=365):
        """Calculate the date range for historical data"""
        end_date = datetime.now(IST).date()
        start_date = end_date - timedelta(days=days_back)
        
        # Adjust for market holidays (simplified - you might want to add proper holiday calendar)
        # Skip weekends
        while start_date.weekday() >= 5:  # Saturday=5, Sunday=6
            start_date += timedelta(days=1)
        
        logger.info(f"Date range: {start_date} to {end_date}")
        return start_date, end_date
    
    def fetch_historical_data(self, instrument_token, from_date, to_date):
        """Fetch historical data for a specific instrument"""
        try:
            # Add delay to respect rate limits
            time.sleep(0.1)
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=self.DATA_INTERVAL
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch data for token {instrument_token}: {str(e)}")
            return []
    
    def process_historical_data(self, raw_data, instrument_info):
        """Process raw historical data and add instrument details"""
        processed_data = []
        
        for candle in raw_data:
            processed_candle = {
                'date': candle['date'].strftime('%Y-%m-%d'),
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'volume': candle['volume'],
                'instrument_token': instrument_info['instrument_token'],
                'strike': instrument_info['strike'],
                'option_type': instrument_info['instrument_type'],
                'expiry': instrument_info['expiry'].strftime('%Y-%m-%d')
            }
            processed_data.append(processed_candle)
        
        return processed_data
    
    def save_to_csv(self, data, filename):
        """Save data to CSV file"""
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Data saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save CSV: {str(e)}")
            return False
    
    def fetch_all_data(self, days_back=365):
        """Main method to fetch all BankNifty option historical data"""
        try:
            logger.info("Starting data fetch process...")
            
            # Calculate date range
            start_date, end_date = self.calculate_date_range(days_back)
            
            # Get all instruments
            if not self.get_instruments():
                return False
            
            # Get available expiries
            expiries = self.get_available_expiries()
            if not expiries:
                logger.error("No expiry dates found")
                return False
            
            all_data = []
            total_instruments = len(self.instruments_data)
            
            logger.info(f"Processing {total_instruments} instruments...")
            
            for idx, instrument in enumerate(self.instruments_data, 1):
                try:
                    logger.info(f"Processing instrument {idx}/{total_instruments}: {instrument['instrument_type']} {instrument['strike']} {instrument['expiry']}")
                    
                    # Fetch historical data
                    raw_data = self.fetch_historical_data(
                        instrument['instrument_token'],
                        start_date,
                        end_date
                    )
                    
                    if raw_data:
                        # Process and add to all data
                        processed_data = self.process_historical_data(raw_data, instrument)
                        all_data.extend(processed_data)
                        
                        logger.info(f"Fetched {len(processed_data)} data points for {instrument['instrument_type']} {instrument['strike']}")
                    else:
                        logger.warning(f"No data found for {instrument['instrument_type']} {instrument['strike']}")
                    
                except Exception as e:
                    logger.error(f"Error processing instrument {instrument['instrument_token']}: {str(e)}")
                    continue
            
            if all_data:
                # Save all data to CSV
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"banknifty_options_historical_{timestamp}.csv"
                
                if self.save_to_csv(all_data, filename):
                    logger.info(f"Successfully saved {len(all_data)} data points to {filename}")
                    
                    # Also save summary
                    self.save_summary(all_data, timestamp)
                    return True
                else:
                    logger.error("Failed to save data")
                    return False
            else:
                logger.error("No data collected")
                return False
                
        except Exception as e:
            logger.error(f"Error in fetch_all_data: {str(e)}")
            return False
    
    def save_summary(self, data, timestamp):
        """Save a summary of the collected data"""
        try:
            # Convert to DataFrame for analysis
            df = pd.DataFrame(data)
            
            # Create summary
            summary = {
                'total_records': len(data),
                'unique_dates': df['date'].nunique(),
                'unique_strikes': df['strike'].nunique(),
                'unique_expiries': df['expiry'].nunique(),
                'date_range': f"{df['date'].min()} to {df['date'].max()}",
                'option_types': df['option_type'].value_counts().to_dict(),
                'fetch_timestamp': timestamp
            }
            
            # Save summary
            summary_file = os.path.join(OUTPUT_DIR, f"summary_{timestamp}.json")
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            logger.info(f"Summary saved to {summary_file}")
            
            # Print summary
            print("\n" + "="*50)
            print("DATA COLLECTION SUMMARY")
            print("="*50)
            print(f"Total Records: {summary['total_records']}")
            print(f"Date Range: {summary['date_range']}")
            print(f"Unique Dates: {summary['unique_dates']}")
            print(f"Unique Strikes: {summary['unique_strikes']}")
            print(f"Unique Expiries: {summary['unique_expiries']}")
            print(f"Option Types: {summary['option_types']}")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Failed to save summary: {str(e)}")

def main():
    """Main function"""
    try:
        # Load credentials from environment variables or config
        api_key = os.getenv('KITE_API_KEY')
        api_secret = os.getenv('KITE_API_SECRET')
        
        if not api_key or not api_secret:
            print("Please set KITE_API_KEY and KITE_API_SECRET environment variables")
            print("Or modify the script to include your credentials directly")
            sys.exit(1)
        
        # Initialize fetcher
        fetcher = BankNiftyHistoricalDataFetcher(api_key, api_secret)
        
        # Authenticate
        if not fetcher.authenticate():
            logger.error("Authentication failed")
            sys.exit(1)
        
        # Fetch all data
        if fetcher.fetch_all_data(days_back=365):
            logger.info("Data collection completed successfully!")
        else:
            logger.error("Data collection failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 