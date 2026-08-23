import requests
import logging
import html

logger = logging.getLogger("croma_checker")

CITY_RANGES = [
    ("Bangalore", 560001, 560050),
    ("Mumbai", 400001, 400050),
    ("Hyderabad", 500001, 500050),
    ("Pune", 411001, 411050),
    ("Lucknow", 226001, 226050),
    ("Ghaziabad", 201001, 201050),
    ("Delhi NCR", 110001, 110050),
    ("Jodhpur", 342001, 342050),
    ("Kolkata", 700001, 700050),
    ("Chennai", 600001, 600050)
]

def get_city_name(pincode: str) -> str:
    try:
        p = int(pincode)
        for city, start, end in CITY_RANGES:
            if start <= p <= end:
                return city
    except (ValueError, TypeError):
        pass
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

def format_stock_alert(product_title: str, product_url: str, pincode: str, price: str = None, delivery_info: str = None) -> str:
    """
    Formats a clean HTML alert message for Telegram with City name mapping.
    """
    safe_title = html.escape(product_title or "Croma Product")
    safe_pincode = html.escape(str(pincode))
    safe_city = html.escape(get_city_name(pincode))
    safe_price = html.escape(str(price)) if price else "N/A"
    safe_delivery = html.escape(str(delivery_info)) if delivery_info else "In Stock / Available for delivery"
    safe_url = html.escape(product_url)

    msg = (
        f"🚨 <b>CROMA STOCK ALERT!</b> 🚨\n\n"
        f"📱 <b>Product:</b> {safe_title}\n"
        f"🏙 <b>City:</b> {safe_city}\n"
        f"📍 <b>Pincode:</b> <code>{safe_pincode}</code>\n"
        f"💰 <b>Price:</b> {safe_price}\n"
        f"🚚 <b>Status:</b> {safe_delivery}\n\n"
        f"🔗 <a href=\"{safe_url}\">Click Here to Buy Now on Croma</a>"
    )
    return msg
