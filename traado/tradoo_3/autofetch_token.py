from kiteconnect import KiteConnect, KiteTicker
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import math
import logging
from datetime import datetime, timedelta
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException



# Config
API_KEY = "d7fg3jqz3k1i6eio"
API_SECRET = "0ojki9vtqxzj6oamaf715imhse4uenp5"
Z_USERNAME = "salokesh99@gmail.com"
Z_PASSWORD = "89515665"
Z_PIN = "895156"

# Globals
kite = KiteConnect(api_key=API_KEY)
logging.basicConfig(level=logging.INFO)


def auto_login_and_get_token():
    login_url = kite.login_url()
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(login_url)

    try:
        # Login step 1: ID & password
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "userid"))).send_keys(Z_USERNAME)
        driver.find_element(By.ID, "password").send_keys(Z_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Login step 2: PIN
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pin"))).send_keys(Z_PIN)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Wait for redirect and get URL
        WebDriverWait(driver, 10).until(lambda d: "request_token=" in d.current_url)
        current_url = driver.current_url

        if "request_token=" in current_url:
            request_token = current_url.split("request_token=")[1].split("&")[0]
            return request_token
        else:
            raise Exception("Failed to extract request_token from redirect URL.")

    except TimeoutException:
        print("Timeout: Could not find expected elements during login flow.")
        print("Current URL:", driver.current_url)
        driver.save_screenshot("login_error.png")  # Optional: helps debug headless failures
        raise

    finally:
        driver.quit()


def generate_access_token(request_token):
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    return access_token

def round_to_nearest_50(x):
    return int(round(x / 50.0)) * 50

def get_atm_strike():
    ltp = kite.ltp("NSE:NIFTY 50")["NSE:NIFTY 50"]["last_price"]
    return round_to_nearest_50(ltp)

def get_current_expiry():
    today = datetime.now().date()
    weekday = today.weekday()
    days_to_thursday = (3 - weekday + 7) % 7
    expiry = today if weekday == 3 else today + timedelta(days=days_to_thursday)
    return expiry.strftime("%d%b%Y").upper()

def get_instruments():
    return kite.instruments("NFO")

def find_option_tokens(strike):
    expiry = get_current_expiry()
    ce_token = pe_token = None

    for ins in get_instruments():
        if (ins["name"] == "NIFTY"
                and ins["strike"] == strike
                and ins["expiry"].strftime("%d%b%Y").upper() == expiry
                and ins["instrument_type"] in ["CE", "PE"]):
            if ins["instrument_type"] == "CE":
                ce_token = ins["instrument_token"]
            elif ins["instrument_type"] == "PE":
                pe_token = ins["instrument_token"]

        if ce_token and pe_token:
            break

    return ce_token, pe_token

# WebSocket
def on_ticks(ws, ticks):
    prices = {tick['instrument_token']: tick['last_price'] for tick in ticks}
    ce_price = prices.get(ws.ce_token, 0)
    pe_price = prices.get(ws.pe_token, 0)
    total = ce_price + pe_price
    logging.info(f"ATM Straddle Price: CE={ce_price}, PE={pe_price}, Total={total:.2f}")

def on_connect(ws, response):
    ws.subscribe([ws.ce_token, ws.pe_token])
    ws.set_mode(ws.MODE_LTP, [ws.ce_token, ws.pe_token])

def on_close(ws, code, reason):
    logging.info("WebSocket closed")

def run_websocket(ce_token, pe_token):
    kws = KiteTicker(API_KEY, kite.access_token)
    kws.ce_token = ce_token
    kws.pe_token = pe_token
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.connect(threaded=True)

    while True:
        time.sleep(1)

# Main flow
if __name__ == "__main__":
    try:
        request_token = auto_login_and_get_token()
        print('request_token====>>>', request_token)
        access_token = generate_access_token(request_token)
        logging.info("Access token retrieved and session established.")

        atm_strike = get_atm_strike()
        ce_token, pe_token = find_option_tokens(atm_strike)

        if ce_token and pe_token:
            logging.info(f"ATM Strike: {atm_strike} | CE Token: {ce_token} | PE Token: {pe_token}")
            run_websocket(ce_token, pe_token)
        else:
            logging.error("Could not find ATM option tokens.")

    except Exception as e:
        logging.exception("Error occurred:")
