import requests
import logging
import html
from typing import Dict, Any

logger = logging.getLogger("croma_checker")

CITY_MAP = {
    # Lucknow
    "226": "Lucknow",
    # Mumbai
    "400": "Mumbai",
    # Delhi
    "110": "Delhi",
    # Bangalore
    "560": "Bangalore",
    # Noida
    "2013": "Noida", "2031": "Noida", "2032": "Noida",
    # Gurgaon
    "122": "Gurgaon",
    # Ghaziabad
    "2010": "Ghaziabad", "2011": "Ghaziabad", "2012": "Ghaziabad", "2451": "Ghaziabad", "2452": "Ghaziabad",
    # Cuttack
    "753": "Cuttack", "754": "Cuttack",
    # Nashik
    "422": "Nashik",
    # Pune
    "411": "Pune", "412": "Pune",
    # Jodhpur
    "342": "Jodhpur",
    # Jaipur
    "302": "Jaipur", "303": "Jaipur"
}

def get_city_name(pincode: str) -> str:
    pin_str = str(pincode).strip()
    for prefix in ["2013", "2031", "2032", "2010", "2011", "2012", "2451", "2452", "754", "412", "303", "226", "400", "110", "560", "122", "753", "422", "411", "342", "302"]:
        if pin_str.startswith(prefix):
            return CITY_MAP.get(prefix, "India")
    return "India"

def send_telegram_message(bot_token: str, chat_id: str, message: str, parse_mode: str = "HTML") -> bool:
    """
    Sends a notification message to a specified Telegram Chat using the Telegram Bot API.
    """
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Telegram bot token is not configured.")
        return False
    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        logger.error("Telegram chat ID is not configured.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200 and res_data.get("ok"):
            logger.info("Telegram message sent successfully.")
            return True
        else:
            description = res_data.get("description", response.text)
            logger.error(f"Failed to send Telegram message: {description}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False

def format_grouped_stock_alert(city_hits: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
    """
    Builds a single consolidated HTML alert for an entire check pass, grouped
    by city then by product, listing every pincode where that product is in
    stock. This replaces sending one message per (product, pincode) hit, which
    turned into back-to-back spam whenever a whole city had stock at once.

    city_hits shape: { city_name: { product_title: {"pins": [pincode, ...], "url": product_url} } }
    """
    lines = ["🚨 <b>CROMA STOCK ALERT!</b> 🚨"]

    for city in sorted(city_hits.keys()):
        products = city_hits[city]
        lines.append(f"\n🏙 <b>{html.escape(city)}</b>")
        for product_title in sorted(products.keys()):
            info = products[product_title]
            safe_title = html.escape(product_title or "Croma Product")
            safe_url = html.escape(info.get("url", ""))
            pins = sorted(set(info.get("pins", [])))
            safe_pins = ", ".join(html.escape(str(p)) for p in pins)
            lines.append(
                f"📱 <a href=\"{safe_url}\">{safe_title}</a>\n"
                f"📍 Pincodes: <code>{safe_pins}</code>"
            )

    return "\n".join(lines)
