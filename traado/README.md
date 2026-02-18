# BankNifty Options Historical Data Fetcher

This Python script fetches BankNifty option chart historical data for the past 1 year using Kite Connect from Zerodha and stores it in CSV format.

## Features

- **Complete Authentication**: OAuth-based authentication with Zerodha
- **Comprehensive Data**: Fetches all available BankNifty option instruments (CE/PE)
- **Flexible Timeframes**: Configurable data intervals (daily, intraday)
- **CSV Export**: Data saved in structured CSV format
- **Rate Limiting**: Respects Zerodha API rate limits
- **Error Handling**: Robust error handling and logging
- **Progress Tracking**: Real-time progress monitoring
- **Data Summary**: Generates comprehensive data summary

## Prerequisites

1. **Zerodha Account**: Active Zerodha trading account
2. **API Access**: API key and secret from Zerodha
3. **Python 3.7+**: Python 3.7 or higher installed
4. **Required Packages**: See requirements.txt

## Installation

1. **Clone or download the script files**
2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up API credentials**:
   - Option 1: Set environment variables
     ```bash
     export KITE_API_KEY="your_api_key"
     export KITE_API_SECRET="your_api_secret"
     ```
   - Option 2: Modify `config.py` file directly

## Configuration

### API Credentials
- **KITE_API_KEY**: Your Zerodha API key
- **KITE_API_SECRET**: Your Zerodha API secret

### Data Settings
- **DATA_INTERVAL**: Data frequency ("day", "15minute", etc.)
- **DAYS_BACK**: Number of days to fetch (default: 365)

### Output Settings
- **OUTPUT_DIR**: Directory to save CSV files
- **CSV_ENCODING**: File encoding (default: utf-8)

## Usage

### Basic Usage
```bash
python banknifty_historical_data.py
```

### Step-by-Step Process

1. **Run the script**
2. **Authentication**:
   - Visit the generated login URL
   - Login with your Zerodha credentials
   - Copy the request token from the redirected URL
   - Enter the token in the script

3. **Data Collection**:
   - Script automatically fetches all BankNifty options
   - Processes each instrument individually
   - Respects API rate limits
   - Shows real-time progress

4. **Output**:
   - CSV file with timestamp in filename
   - Summary report in JSON format
   - Comprehensive logging

## Output Files

### CSV Data File
- **Filename**: `banknifty_options_historical_YYYYMMDD_HHMMSS.csv`
- **Columns**:
  - `date`: Trading date
  - `open`, `high`, `low`, `close`: OHLC prices
  - `volume`: Trading volume
  - `instrument_token`: Zerodha instrument token
  - `strike`: Option strike price
  - `option_type`: CE (Call) or PE (Put)
  - `expiry`: Option expiry date

### Summary File
- **Filename**: `summary_YYYYMMDD_HHMMSS.json`
- **Content**: Data collection statistics and metadata

### Log File
- **Filename**: `banknifty_historical_data.log`
- **Content**: Detailed execution logs and error tracking

## Data Intervals

Available data intervals for historical data:
- `minute`: 1-minute data
- `3minute`: 3-minute data
- `5minute`: 5-minute data
- `10minute`: 10-minute data
- `15minute`: 15-minute data
- `30minute`: 30-minute data
- `60minute`: 1-hour data
- `day`: Daily data

## Rate Limiting

The script includes built-in rate limiting:
- Default delay: 0.1 seconds between API calls
- Configurable via `API_DELAY` in config
- Respects Zerodha's API limits

## Error Handling

The script handles various error scenarios:
- **Authentication failures**: Retry mechanism for login
- **API errors**: Graceful handling of API failures
- **Network issues**: Retry logic for connectivity problems
- **Data validation**: Checks for data completeness

## Troubleshooting

### Common Issues

1. **Authentication Failed**:
   - Check API key and secret
   - Ensure request token is fresh (< 24 hours)
   - Verify account permissions

2. **No Data Retrieved**:
   - Check market hours
   - Verify instrument availability
   - Check API permissions

3. **Rate Limit Errors**:
   - Increase `API_DELAY` in config
   - Reduce data range
   - Check Zerodha API status

### Log Analysis

Check the log file for detailed error information:
```bash
tail -f banknifty_historical_data.log
```

## Performance Considerations

- **Large Datasets**: 1 year of daily data for all options can be substantial
- **Processing Time**: Depends on number of instruments and data points
- **Memory Usage**: Consider processing in batches for very large datasets
- **Storage**: Ensure sufficient disk space for CSV files

## Security Notes

- **API Credentials**: Never commit credentials to version control
- **Access Tokens**: Tokens expire after 24 hours
- **Data Privacy**: Historical data is public but handle responsibly

## Support

For issues related to:
- **Script functionality**: Check logs and error messages
- **Zerodha API**: Refer to Zerodha's API documentation
- **Data accuracy**: Verify with official Zerodha data sources

## License

This script is provided as-is for educational and research purposes. Use at your own risk and ensure compliance with Zerodha's terms of service. 