import os
import re
import time
import json
import html as html_module
import argparse
import logging
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple, Optional
from curl_cffi import requests as curl_requests
from telegram_notifier import send_telegram_message, format_stock_alert

# Playwright fallback launches a full browser per call, which is heavy (CPU/memory)
# and adds to the load hitting Croma's site. Under the same thread pool that runs
# the fast API checks, a burst of API 403s can trigger many browsers at once,
# which both starves the machine and makes the underlying rate-limiting worse.
# Cap concurrent Playwright fallbacks independently of API check concurrency.
PLAYWRIGHT_FALLBACK_SEMAPHORE = threading.Semaphore(2)

# Setup logging. Console stays at INFO for readability; the log file also
# captures DEBUG (raw API response bodies) for troubleshooting stock decisions.
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler("croma_checker.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger("croma_checker")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.croma.com/",
    "Origin": "https://www.croma.com"
}

# Croma's PWA API. Discovered by inspecting the network traffic that Croma's own
# site fires when a user submits a pincode on a product page. Requires TLS/HTTP2
# fingerprints that resemble a real browser (plain `requests` gets a 403 from
# Akamai), which is why calls below go through curl_cffi's `impersonate="chrome124"`.
API_BASE = "https://api.croma.com"
OMS_SUBSCRIPTION_KEY = "1131858141634e2abe2efb2b3a2a2a5d"
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.croma.com",
    "referer": "https://www.croma.com/",
    "user-agent": DEFAULT_HEADERS["User-Agent"],
}

def extract_product_id(url_or_id: str) -> Optional[str]:
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    match = re.search(r'/p/(\d+)', url_or_id)
    if match:
        return match.group(1)
    if url_or_id.isdigit():
        return url_or_id
    return None

def build_oms_payload(product_id: str, pincode: str) -> Dict[str, Any]:
    # Mirrors the exact request Croma's own PDP sends: one promiseLine per
    # fulfillment type (home delivery, store pickup, same-day delivery). A
    # product can be unavailable via HDEL but still available via SDEL/STOR,
    # so all three must be asked about together to match what "Buy Now" on
    # the actual page reflects.
    def line(fulfillment_type: str, line_id: str, req_end_date: str = "") -> Dict[str, Any]:
        return {
            "fulfillmentType": fulfillment_type,
            "mch": "",
            "itemID": product_id,
            "lineId": line_id,
            "categoryType": "mobile",
            "reqEndDate": req_end_date,
            "reqStartDate": "",
            "requiredQty": "1",
            "shipToAddress": {
                "company": "", "country": "", "city": "", "mobilePhone": "",
                "state": "", "zipCode": pincode,
                "extn": {"irlAddressLine1": "", "irlAddressLine2": ""}
            },
            "extn": {"widerStoreFlag": "N"}
        }

    return {
        "promise": {
            "allocationRuleID": "SYSTEM",
            "checkInventory": "Y",
            "organizationCode": "CROMA",
            "sourcingClassification": "EC",
            "promiseLines": {
                "promiseLine": [
                    line("HDEL", "1", req_end_date="2500-01-01"),
                    line("STOR", "2"),
                    line("SDEL", "3"),
                ]
            }
        }
    }

def check_stock_via_api(product_url: str, pincode: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Fast path: calls Croma's own PWA APIs directly instead of driving a browser.
    - GET .../pdp/deliveryoption/ tells us whether the product is generally sellable.
    - POST .../inventory/oms/v2/tms/details-pwa/ is the real per-pincode delivery
      promise check; an empty "unavailableLines" list means it can be fulfilled there.
    """
    clean_pin = str(pincode).strip()
    if not clean_pin or not re.match(r'^[1-8]\d{5}$', clean_pin):
        logger.warning(f"Invalid PIN code format rejected: {pincode}")
        return False, None, None, "Invalid Pincode Format"

    product_id = extract_product_id(product_url)
    if not product_id:
        logger.error(f"Could not extract product ID from URL: {product_url}")
        return False, None, None, "Invalid Product URL"

    try:
        oms_headers = dict(API_HEADERS)
        oms_headers["oms-apim-subscription-key"] = OMS_SUBSCRIPTION_KEY
        payload = build_oms_payload(product_id, clean_pin)

        # Akamai occasionally 403s the API under high concurrency (rate-limiting,
        # not a hard block) — retry a couple times with backoff before giving up
        # on the fast path and paying for a full Playwright browser fallback.
        resp = None
        last_status = None
        for attempt in range(3):
            resp = curl_requests.post(
                f"{API_BASE}/inventory/oms/v2/tms/details-pwa/",
                headers=oms_headers,
                json=payload,
                impersonate="chrome124",
                timeout=10,
            )
            if resp.status_code == 200:
                break
            last_status = resp.status_code
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))

        if resp is None or resp.status_code != 200:
            logger.debug(f"OMS API non-200 body for product {product_id} @ {clean_pin}: {resp.text if resp else '<no response>'}")
            raise RuntimeError(f"OMS API returned status {last_status}")

        logger.debug(f"OMS API response for product {product_id} @ {clean_pin}: {resp.text}")

        data = resp.json()
        suggested_option = data.get("promise", {}).get("suggestedOption", {})
        available = suggested_option.get("option", {}).get("promiseLines", {}).get("promiseLine", [])
        unavailable = suggested_option.get("unavailableLines", {}).get("unavailableLine", [])

        # A product can be unavailable via one fulfillment type (e.g. home
        # delivery) but still purchasable via another (e.g. same-day delivery
        # or store pickup) — it's in stock if ANY line came back fulfillable,
        # matching what "Buy Now" reflects on the actual product page.
        is_in_stock = len(available) > 0

        if is_in_stock:
            fulfillment = available[0].get("fulfillmentType", "unknown")
            status_info = f"In Stock (deliverable to pincode via {fulfillment})"
        else:
            reason = unavailable[0].get("unavailableReason", "unavailable") if unavailable else "unavailable"
            status_info = f"Out of Stock ({reason})"

        logger.info(
            f"{'✅ IN STOCK' if is_in_stock else '❌ OUT OF STOCK'} for pincode {clean_pin} "
            f"(Product ID: {product_id})"
        )
        return is_in_stock, None, None, status_info

    except Exception as e:
        logger.warning(f"API check failed for {product_url} @ {clean_pin}: {e}")
        raise

def check_stock_via_playwright(product_url: str, pincode: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Checks stock for a specific pincode by opening Croma's location modal, submitting the pincode,
    validating pincode legitimacy, waiting for React DOM updates, and strictly verifying 'buyNowBtn'.
    """
    # 1. Format validation for Indian PIN codes (6 digits, starting with 1-8)
    clean_pin = str(pincode).strip()
    if not clean_pin or not re.match(r'^[1-8]\d{5}$', clean_pin):
        logger.warning(f"Invalid PIN code format rejected: {pincode}")
        return False, None, None, "Invalid Pincode Format"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright is not installed. Required for dynamic pincode stock checking.")
        return False, None, None, "Playwright not installed"

    logger.info(f"Checking Croma stock for {product_url} at pincode {clean_pin}...")
    try:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                f"--user-agent={DEFAULT_HEADERS['User-Agent']}"
            ]
            try:
                browser = p.chromium.launch(channel="chrome", headless=True, args=launch_args)
            except Exception:
                browser = p.chromium.launch(headless=True, args=launch_args)

            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "sec-ch-ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                }
            )
            page = context.new_page()

            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en-US', 'en']});
            """)

            page.goto(product_url, wait_until="domcontentloaded", timeout=30000)

            title = page.title()
            if "access denied" in title.lower() or "forbidden" in title.lower():
                logger.warning(f"Access denied by Croma anti-bot protection (Title: '{title}').")
                browser.close()
                return False, "Access Denied", None, "Anti-bot Blocked"

            # Clean product title
            title = re.sub(r'\s*-\s*Croma\s*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'^\s*Buy\s+', '', title, flags=re.IGNORECASE)

            # Step 1: Open Pincode Location Modal
            pincode_btn = page.query_selector("button.add-pincode-link, .add-pincode-header-prompt, .delivery-location")
            if pincode_btn:
                try:
                    pincode_btn.click(timeout=3000)
                    time.sleep(1)
                except Exception:
                    pass

            # Step 2: Fill input.pinElem
            pin_input = page.query_selector("input.pinElem, input[placeholder*='Enter Pincode' i], input[placeholder*='pincode' i]")
            if pin_input:
                pin_input.fill(clean_pin)
                time.sleep(1)

                # Step 3: Click Apply/Continue button
                apply_btn = page.query_selector("button#apply-pincode-btn, button.sign-in-pincode-continue")
                if apply_btn:
                    apply_btn.click()

            # Step 4: CRITICAL WAIT -> Wait 3 seconds for Croma's React API to process the pincode and update DOM
            time.sleep(3)

            # Step 5: Check for Croma Modal Error Messages (Invalid Pincode Rejection)
            page_text_lower = page.content().lower()
            invalid_keywords = [
                "please enter valid pincode",
                "enter valid pincode",
                "invalid pincode",
                "pincode not found",
                "service not available",
                "pincode is invalid"
            ]
            has_pin_error = any(kw in page_text_lower for kw in invalid_keywords)

            # Step 6: Check if modal is still open (rejected pincode)
            modal_elem = page.query_selector(".select-pincode-container, .MuiDialog-paper")
            is_modal_open = modal_elem and modal_elem.is_visible()

            if has_pin_error or is_modal_open:
                logger.warning(f"❌ Pincode {clean_pin} was rejected by Croma (Invalid/Unserviceable PIN).")
                browser.close()
                return False, title, None, "Invalid / Rejected Pincode"

            # Step 7: Check button classes AFTER React updates DOM
            buy_now_button = page.query_selector("button[class*='buynow' i], button.buyNowBtn")
            cart_button = page.query_selector("button.pdp-add-to-cart, button[class*='addtocart' i]")

            buy_cls = (buy_now_button.get_attribute("class") or "").lower() if buy_now_button else ""
            cart_cls = (cart_button.get_attribute("class") or "").lower() if cart_button else ""

            buy_disabled = "disable" in buy_cls or (buy_now_button and buy_now_button.is_disabled()) if buy_now_button else True
            cart_disabled = "disable" in cart_cls or (cart_button and cart_button.is_disabled()) if cart_button else True

            has_out_of_stock = any(txt in page_text_lower for txt in ["currently unavailable", "out of stock", "not deliverable", "item unavailable"])

            # Extract price if visible
            price = None
            price_elem = page.query_selector(".pdp-price, .amount, [class*='price' i]")
            if price_elem:
                p_text = price_elem.inner_text().strip()
                p_match = re.search(r'₹[\d,]+', p_text)
                if p_match:
                    price = p_match.group(0)

            browser.close()

            is_in_stock = (not buy_disabled or not cart_disabled) and not has_out_of_stock
            status_info = "In Stock (Buy Now Enabled)" if is_in_stock else "Out of Stock (buyNowBtn not present or disabled)"

            if is_in_stock:
                logger.info(f"✅ IN STOCK for pincode {clean_pin}! (Product: {title})")
                return True, title, price, status_info
            else:
                logger.info(f"❌ OUT OF STOCK for pincode {clean_pin}. (Product: {title})")
                return False, title, price, status_info

    except Exception as e:
        logger.error(f"Playwright check failed: {e}")
        return False, None, None, f"Browser error: {e}"

def fetch_product_title(product_url: str) -> Optional[str]:
    """Best-effort product title lookup via a plain page fetch (used only for Telegram alert text)."""
    try:
        resp = curl_requests.get(product_url, headers=API_HEADERS, impersonate="chrome124", timeout=10)
        match = re.search(r"<title>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        title = html_module.unescape(match.group(1).strip())
        title = re.sub(r'\s*-\s*Croma\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^\s*Buy\s+', '', title, flags=re.IGNORECASE)
        return title
    except Exception as e:
        logger.warning(f"Could not fetch product title for {product_url}: {e}")
        return None

def check_product_pincode(product_url: str, pincode: str, use_playwright_fallback: bool = True) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    try:
        return check_stock_via_api(product_url, pincode)
    except Exception:
        if not use_playwright_fallback:
            return False, None, None, "API check failed"
        logger.info(f"Falling back to Playwright for {product_url} @ {pincode}...")
        with PLAYWRIGHT_FALLBACK_SEMAPHORE:
            return check_stock_via_playwright(product_url, pincode)

def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_checker_loop(config_path: str, run_once: bool = False):
    config = load_config(config_path)
    telegram_cfg = config.get("telegram", {})
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or telegram_cfg.get("bot_token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or telegram_cfg.get("chat_id")
    
    products = config.get("products", [])
    pincodes = config.get("pincodes", [])
    settings = config.get("settings", {})

    check_interval = settings.get("check_interval_seconds", 3600)
    cooldown_minutes = settings.get("notify_cooldown_minutes", 60)
    max_workers = settings.get("max_concurrent_checks", 20)
    use_playwright_fallback = settings.get("use_playwright_fallback", True)

    logger.info(f"Loaded {len(products)} product(s) and {len(pincodes)} pincode(s).")

    # Tracking notified state: key = (product_url, pincode), val = timestamp
    notified_state: Dict[Tuple[str, str], float] = {}

    while True:
        iteration_start = time.time()
        logger.info(f"--- Starting Stock Checking Pass ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

        product_titles = {url: fetch_product_title(url) for url in products}

        tasks = [(product_url, pincode) for pincode in pincodes for product_url in products]
        cooldown_seconds = cooldown_minutes * 60

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(check_product_pincode, product_url, pincode, use_playwright_fallback): (product_url, pincode)
                for product_url, pincode in tasks
            }

            for future in as_completed(future_to_task):
                product_url, pincode = future_to_task[future]
                try:
                    in_stock, title, price, delivery_info = future.result()
                except Exception as e:
                    logger.error(f"Check failed for {product_url} @ {pincode}: {e}")
                    continue

                title = title or product_titles.get(product_url)
                state_key = (product_url, pincode)
                last_notified = notified_state.get(state_key, 0)

                if in_stock:
                    logger.info(f"✅ IN STOCK! Product: {title or product_url} | Pincode: {pincode} | Price: {price}")

                    if (time.time() - last_notified) > cooldown_seconds:
                        alert_msg = format_stock_alert(
                            product_title=title or "Croma Product",
                            product_url=product_url,
                            pincode=pincode,
                            price=price,
                            delivery_info=delivery_info
                        )
                        sent_tg = send_telegram_message(bot_token, chat_id, alert_msg)
                        if sent_tg:
                            notified_state[state_key] = time.time()
                    else:
                        logger.info(f"Skipping alert for {state_key} (cooldown active).")
                else:
                    logger.info(f"❌ OUT OF STOCK / Unavailable for product {product_url} at pincode {pincode}. Reason: {delivery_info}")

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
            print("[SUCCESS] Test message sent successfully! Check your Telegram chat.")
        else:
            print("[ERROR] Failed to send test message. Make sure you pressed START on your bot in Telegram first.")
        return

    run_checker_loop(args.config, run_once=args.once)

if __name__ == "__main__":
    main()
