# Configuration file for BankNifty Historical Data Fetcher
# You can either set these values directly or use environment variables

# Zerodha API Credentials
KITE_API_KEY = "your_api_key_here"
KITE_API_SECRET = "your_api_secret_here"

# Data Collection Settings
DATA_INTERVAL = "day"  # Options: "minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute", "day"
DAYS_BACK = 365  # Number of days to fetch historical data

# Output Settings
OUTPUT_DIR = "historical_data"
CSV_ENCODING = "utf-8"

# Rate Limiting
API_DELAY = 0.1  # Delay between API calls in seconds

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "banknifty_historical_data.log"

# Market Settings
TIMEZONE = "Asia/Kolkata"
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:30" 