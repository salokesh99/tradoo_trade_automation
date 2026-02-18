## Traado – Trading & Market Data Toolkit

This repository contains a small collection of **Python tools and scripts** for working with Indian equity/index derivatives, with a focus on **Bank Nifty and Nifty options**.  
The code covers three main areas:

- **Strategy scripts** for intraday/expiry‑based options trading
- **Historical data collection** using Zerodha Kite Connect
- **Utility scripts** around accounts, instruments, and session management

The project is intentionally simple and script‑driven, aimed at experimentation, learning, and basic research rather than being a full trading platform.

### Project overview

- **Intraday / strategy scripts**
  - Automate or semi‑automate intraday strategies such as **ATM straddles** around specific times (e.g. 9:15, 9:45, 10:00+).
  - Use **rule‑based entry and exit logic** driven by price ranges, crossovers, and time‑based exits.
  - Some scripts simulate or paper‑trade by logging orders and P&L rather than sending real orders.

- **Historical data collection**
  - `traado/banknifty_historical_data.py` fetches **Bank Nifty options historical OHLC data** via the **Kite Connect** API.
  - Data is written to **CSV** for later analysis (backtesting, feature engineering, statistics) and accompanied by JSON summaries.
  - Designed to respect API limits, provide detailed logging, and keep a reproducible record of fetched data.

- **Zerodha utilities**
  - Small helpers in `traado/zerodha/` for:
    - Generating login/token URLs
    - Inspecting the profile
    - Downloading instrument lists
  - These are used to support both the live strategy scripts and the data tools.

### Repository structure (simplified)

- **Root**
  - Log files and scratch notes (`*.log`, `915streak.txt`, etc.)
  - `trado_25_08/` – older/archived experiments.
- **`traado/`**
  - `tradoo_2/`, `tradoo_3/`, `tradoo_4/` – multiple iterations of **Bank Nifty/Nifty strategy scripts**.
  - `zerodha/` – utilities around **token generation, profile checks, instrument lists**, etc.
  - `banknifty_historical_data.py` – main **historical options data fetcher** (CSV + JSON summary output).
  - `run_example.py` – simple entrypoint that shows how to configure and run the data fetcher.
  - `requirements.txt` – Python dependencies for the main tools in this folder.

Some of the code under `tradoo_*` is deliberately left as “work in progress” to reflect real‑world iteration and quick prototyping.

### Tech stack (in detail)

- **Language**
  - **Python 3.x** (developed with Python 3.8 in mind)

- **Core libraries**
  - **`kiteconnect`** – official Zerodha Kite Connect client, used for:
    - Account/profile queries
    - Instrument list downloads
    - Live price data (LTP, WebSocket ticks)
    - Historical OHLC data requests
  - **`pandas`** – used mainly in data tools (`banknifty_historical_data.py`) for:
    - Structuring OHLC data in DataFrames
    - Computing summary statistics (unique dates/strikes/expiries, ranges)
    - Saving to/reading from CSV when needed
  - **`pytz`** – timezone handling, especially for **Asia/Kolkata** for exchange times.
  - **`holidays`** (in some strategy scripts) – handling Indian market holidays in addition to weekends.
  - **Standard library modules**
    - `datetime`, `time` – scheduling, intraday windows, and historical ranges
    - `logging` – structured logs for each run (both console + file)
    - `json`, `csv`, `os`, `sys` – configuration, file I/O, and basic plumbing

- **Environment & tooling**
  - **Virtual environments**
    - There are virtualenvs under `myenv/` and `traado/` (ignored via `.gitignore`).
    - Dependencies for the main toolkit are captured in `traado/requirements.txt`.
  - **Data & logs**
    - Log files (`*.log`) at the project root and under `traado/` capture runs of strategies and utilities.
    - Fetched historical data is stored under a `historical_data/` directory (ignored from version control).

### Setup (for the `traado` tools)

- **Create / activate a virtual environment** (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

- **Install dependencies**:

```bash
cd traado
pip install -r requirements.txt
```

- **Configure Zerodha API credentials** (one option):

```bash
export KITE_API_KEY="your_key"
export KITE_API_SECRET="your_secret"
```

or edit `config.py` in `traado/` to hard‑code keys for local use (not recommended for shared repos).

- **Run the historical data example**:

```bash
cd traado
python run_example.py
```

This script walks you through the **Kite login flow**, then invokes `banknifty_historical_data.py` to fetch and store Bank Nifty options data.

### Notes and limitations

- The project is designed for **experimentation** and **learning**, not as a complete trading system.
- Kite Connect’s historical/intraday data has **API and look‑back limits**; scripts are written with these constraints in mind.
- Some of the strategy scripts depend on a valid, active **Kite access token** and may require minor adjustments (e.g. symbols, timings) for different market conditions.

If you are exploring this repository, the best starting points are:

- `traado/banknifty_historical_data.py` and `run_example.py` – for data collection.
- One of the `tradoo_*` strategy scripts – to see how intraday logic and WebSocket ticks are wired together.
