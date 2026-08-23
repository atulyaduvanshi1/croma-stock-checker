import requests
import logging
import html

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
