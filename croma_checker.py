import os
import re
import time
import json
import argparse
import logging
import datetime
from typing import Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup
from telegram_notifier import send_telegram_message, format_stock_alert

# Try importing curl_cffi for TLS fingerprint bypass, fallback to requests
try:
    from curl_cffi import requests as http_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests as http_requests
    HAS_CURL_CFFI = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("croma_checker.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("croma_checker")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.croma.com/",
    "Origin": "https://www.croma.com"
}

def extract_product_id(url_or_id: str) -> Optional[str]:
    """
    Extracts Croma product ID from a URL or raw ID string.
    Example: https://www.croma.com/apple-iphone-17-256gb-black-/p/317396 -> 317396
    """
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    match = re.search(r'/p/(\d+)', url_or_id)
    if match:
        return match.group(1)
    if url_or_id.isdigit():
        return url_or_id
    return None

def check_stock_via_http(product_url: str, pincode: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Fetches the Croma product page using curl_cffi (Chrome impersonation) or requests
    and parses exact button states (disableBuyNow, disableCartBtn, disabled) to evaluate stock.
    Returns: (is_in_stock, product_title, price, delivery_status_info)
    """
    if HAS_CURL_CFFI:
        session = http_requests.Session(impersonate="chrome120")
    else:
        session = http_requests.Session()

    session.headers.update(DEFAULT_HEADERS)

    try:
        res = session.get(product_url, timeout=15)
        if res.status_code != 200:
            logger.warning(f"HTTP request returned status {res.status_code} for {product_url}")
            return False, None, None, f"HTTP Status {res.status_code}"

        html_text = res.text
        soup = BeautifulSoup(html_text, "html.parser")
        title = soup.title.string.strip() if soup.title else "Croma Product"

        # Check for Access Denied / WAF blocking
        if "access denied" in title.lower() or "forbidden" in title.lower() or "just a moment" in title.lower():
            logger.warning(f"Access denied by Croma anti-bot protection (Title: '{title}').")
            return False, title, None, "Access Denied (WAF Blocked)"

        # Clean product title
        title = re.sub(r'\s*-\s*Croma\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^\s*Buy\s+', '', title, flags=re.IGNORECASE)

        # Parse price
        price = None
        price_elem = soup.find(class_=lambda c: c and ("amount" in c.lower() or "price" in c.lower() or "pdp-price" in c.lower()))
        if price_elem:
            price_text = price_elem.get_text().strip()
            price_match = re.search(r'₹[\d,]+', price_text)
            if price_match:
                price = price_match.group(0)

        # Inspect Cart & Buy Now buttons specifically
        cart_btn = soup.find("button", class_=lambda c: c and ("pdp-add-to-cart" in c or "addtocart" in c.lower()))
        buy_btn = soup.find("button", class_=lambda c: c and ("buynow" in c.lower() or "disablebuynow" in c.lower()))

        def is_button_disabled(btn):
            if not btn:
                return False
            classes = btn.get("class", [])
            if isinstance(classes, str):
                classes = classes.split()
            for cls in classes:
                if any(d in cls.lower() for d in ["disable", "disabled"]):
                    return True
            if btn.has_attr("disabled"):
                return True
            return False

        # Evaluate button states
        cart_disabled = is_button_disabled(cart_btn) if cart_btn else True
        buy_disabled = is_button_disabled(buy_btn) if buy_btn else True

        # Check explicit out of stock text in PDP container
        page_lower = html_text.lower()
        has_out_of_stock_text = "out of stock" in page_lower or "currently unavailable" in page_lower or "sold out" in page_lower

        if cart_disabled and buy_disabled:
            logger.info(f"Product is OUT OF STOCK (Cart & Buy buttons disabled / {title}).")
            return False, title, price, "Out of Stock (Buttons Disabled)"

        if has_out_of_stock_text:
            logger.info(f"Product is OUT OF STOCK (Page text indicates out of stock / {title}).")
            return False, title, price, "Out of Stock"

        if (cart_btn and not cart_disabled) or (buy_btn and not buy_disabled):
            logger.info(f"Product is IN STOCK! ({title})")
            return True, title, price, "In Stock (Add to Cart Available)"

        return False, title, price, "Out of Stock / Unknown"

    except Exception as e:
        logger.error(f"Error fetching product via HTTP: {e}")
        return False, None, None, f"HTTP Fetch Error: {e}"

def check_stock_via_playwright(product_url: str, pincode: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Fallback browser check using Playwright with stealth options.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed. Skipping browser fallback.")
        return False, None, None, "Playwright not installed"

    logger.info(f"Running Playwright browser check for {product_url} at pincode {pincode}...")
    try:
        with sync_playwright() as p:
            launch_options = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ]
            }
            try:
                browser = p.chromium.launch(channel="chrome", **launch_options)
            except Exception:
                browser = p.chromium.launch(**launch_options)

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); window.chrome = { runtime: {} };")

            page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            title = page.title()
            if "access denied" in title.lower() or "forbidden" in title.lower():
                browser.close()
                return False, "Access Denied", None, "Anti-bot Blocked"

            # Check for disabled buttons in DOM
            cart_btn = page.query_selector("button.pdp-add-to-cart, button[class*='addtocart' i]")
            buy_btn = page.query_selector("button[class*='buynow' i]")

            cart_cls = cart_btn.get_attribute("class") if cart_btn else ""
            buy_cls = buy_btn.get_attribute("class") if buy_btn else ""

            is_disabled = (
                "disable" in (cart_cls or "").lower() or
                "disable" in (buy_cls or "").lower() or
                (cart_btn and cart_btn.is_disabled()) or
                (buy_btn and buy_btn.is_disabled())
            )

            browser.close()

            if is_disabled:
                return False, title, None, "Out of Stock (Buttons Disabled)"
            
            return True, title, None, "In Stock"
    except Exception as e:
        logger.error(f"Playwright check failed: {e}")
        return False, None, None, f"Browser error: {e}"

def check_product_pincode(product_url: str, pincode: str, use_playwright_fallback: bool = True) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Master check method combining curl_cffi/HTTP parsing and Playwright fallback.
    """
    # Strategy 1: HTTP / TLS fingerprint fetch via curl_cffi
    in_stock, title, price, delivery_info = check_stock_via_http(product_url, pincode)
    
    # If HTTP returned valid status or explicitly confirmed out of stock
    if in_stock:
        return True, title, price, delivery_info
    
    if delivery_info and "Out of Stock" in delivery_info:
        return False, title, price, delivery_info

    # Strategy 2: Playwright fallback if HTTP request was blocked
    if use_playwright_fallback and (not delivery_info or "Blocked" in delivery_info):
        return check_stock_via_playwright(product_url, pincode)

    return False, title, price, delivery_info or "Out of Stock"

def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_checker_loop(config_path: str, run_once: bool = False):
    config = load_config(config_path)
    telegram_cfg = config.get("telegram", {})
    
    # Priority: Environment variables -> config.json
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or telegram_cfg.get("bot_token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or telegram_cfg.get("chat_id")
    
    products = config.get("products", [])
    pincodes = config.get("pincodes", [])
    settings = config.get("settings", {})

    check_interval = settings.get("check_interval_seconds", 60)
    cooldown_minutes = settings.get("notify_cooldown_minutes", 30)
    use_playwright = settings.get("use_playwright_fallback", True)

    logger.info(f"Loaded {len(products)} product(s) and {len(pincodes)} pincode(s).")
    logger.info(f"Checking interval: {check_interval}s | Cooldown: {cooldown_minutes}m")

    # Tracking notified state: key = (product_url, pincode), val = timestamp
    notified_state: Dict[Tuple[str, str], float] = {}

    while True:
        iteration_start = time.time()
        logger.info(f"--- Starting Stock Checking Pass ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

        for product_url in products:
            for pincode in pincodes:
                logger.info(f"Checking product: {product_url} | Pincode: {pincode}")
                in_stock, title, price, delivery_info = check_product_pincode(product_url, pincode, use_playwright)

                state_key = (product_url, pincode)
                last_notified = notified_state.get(state_key, 0)
                cooldown_seconds = cooldown_minutes * 60

                if in_stock:
                    logger.info(f"✅ IN STOCK! Product: {title or product_url} | Pincode: {pincode} | Price: {price}")
                    
                    if (time.time() - last_notified) > cooldown_seconds:
                        # 1. Send Telegram Alert
                        alert_msg = format_stock_alert(
                            product_title=title or "Croma Product",
                            product_url=product_url,
                            pincode=pincode,
                            price=price,
                            delivery_info=delivery_info
                        )
                        sent_tg = send_telegram_message(bot_token, chat_id, alert_msg)
                        
                        # 2. Send WhatsApp Alert
                        try:
                            from whatsapp_notifier import send_whatsapp_alert, format_whatsapp_stock_alert, CITY_PINCODE_MAP
                            city_name = CITY_PINCODE_MAP.get(str(pincode), "India")
                            wa_msg = format_whatsapp_stock_alert(
                                product_title=title or "Croma Product",
                                product_url=product_url,
                                pincode=pincode,
                                price=price,
                                delivery_info=delivery_info,
                                city_name=city_name
                            )
                            send_whatsapp_alert(config, wa_msg)
                        except Exception as wa_err:
                            logger.error(f"WhatsApp notification error: {wa_err}")

                        if sent_tg:
                            notified_state[state_key] = time.time()
                    else:
                        logger.info(f"Skipping alert for {state_key} (cooldown active).")
                else:
                    logger.info(f"❌ OUT OF STOCK / Unavailable for pincode {pincode}. Reason: {delivery_info}")

        if run_once:
            logger.info("Single pass complete (--once flag passed). Exiting.")
            break

        elapsed = time.time() - iteration_start
        sleep_time = max(1, check_interval - elapsed)
        logger.info(f"Pass completed in {elapsed:.2f}s. Sleeping for {sleep_time:.2f}s...\n")
        time.sleep(sleep_time)

def main():
    parser = argparse.ArgumentParser(description="Croma Stock & Pincode Availability Checker")
    parser.add_argument("--config", default="config.json", help="Path to config.json file")
    parser.add_argument("--once", action="store_true", help="Run a single check pass and exit")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message to verify Telegram bot setup")

    args = parser.parse_args()

    if args.test_telegram:
        config = load_config(args.config)
        telegram_cfg = config.get("telegram", {})
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or telegram_cfg.get("bot_token")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID") or telegram_cfg.get("chat_id")
        test_msg = "<b>🤖 Croma Stock Bot Test</b>\n\nYour Telegram bot configuration is working correctly!"
        logger.info("Sending test Telegram message...")
        success = send_telegram_message(bot_token, chat_id, test_msg)
        if success:
            print("✅ Test message sent successfully! Check your Telegram chat.")
        else:
            print("❌ Failed to send test message. Check bot_token and chat_id in config.json.")
        return

    run_checker_loop(args.config, run_once=args.once)

if __name__ == "__main__":
    main()
