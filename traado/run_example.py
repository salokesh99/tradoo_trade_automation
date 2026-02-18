#!/usr/bin/env python3
"""
Example script showing how to use the BankNifty Historical Data Fetcher
with configuration file and custom settings.
"""

import os
import sys
from banknifty_historical_data import BankNiftyHistoricalDataFetcher

def load_config():
    """Load configuration from config.py or environment variables"""
    try:
        # Try to import config
        from config import KITE_API_KEY, KITE_API_SECRET, DATA_INTERVAL, DAYS_BACK
        print("Configuration loaded from config.py")
        return KITE_API_KEY, KITE_API_SECRET, DATA_INTERVAL, DAYS_BACK
    except ImportError:
        # Fall back to environment variables
        api_key = os.getenv('KITE_API_KEY')
        api_secret = os.getenv('KITE_API_SECRET')
        data_interval = os.getenv('DATA_INTERVAL', 'day')
        days_back = int(os.getenv('DAYS_BACK', '365'))
        
        if api_key and api_secret:
            print("Configuration loaded from environment variables")
            return api_key, api_secret, data_interval, days_back
        else:
            print("Configuration not found!")
            print("Please either:")
            print("1. Set KITE_API_KEY and KITE_API_SECRET environment variables")
            print("2. Create a config.py file with your credentials")
            return None, None, None, None

def main():
    """Main function with custom configuration"""
    print("=" * 60)
    print("BankNifty Historical Data Fetcher - Example Usage")
    print("=" * 60)
    
    # Load configuration
    api_key, api_secret, data_interval, days_back = load_config()
    
    if not api_key or not api_secret:
        sys.exit(1)
    
    print(f"API Key: {api_key[:8]}...")
    print(f"Data Interval: {data_interval}")
    print(f"Days Back: {days_back}")
    print()
    
    # Initialize fetcher
    fetcher = BankNiftyHistoricalDataFetcher(api_key, api_secret)
    
    # Customize settings
    fetcher.DATA_INTERVAL = data_interval
    
    try:
        # Authenticate
        print("Starting authentication...")
        if not fetcher.authenticate():
            print("Authentication failed!")
            sys.exit(1)
        
        print("Authentication successful!")
        print()
        
        # Fetch data with custom settings
        print(f"Fetching {days_back} days of {data_interval} data...")
        if fetcher.fetch_all_data(days_back=days_back):
            print("Data collection completed successfully!")
        else:
            print("Data collection failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 