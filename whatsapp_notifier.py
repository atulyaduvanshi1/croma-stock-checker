import requests
import logging

logger = logging.getLogger("croma_checker")

def send_whatsapp_callmebot(phone: str, message: str, apikey: str) -> bool:
    """
    Sends a WhatsApp message using the free CallMeBot API.
    To get API key: Send 'I allow callmebot to send me messages' to +34 644 10 55 84 on WhatsApp.
    """
    if not phone or not apikey:
        logger.error("WhatsApp CallMeBot phone number or apikey not provided.")
        return False

    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone": phone,
        "text": message,
        "apikey": apikey
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200 and "Message queued" in response.text or "ok" in response.text.lower():
            logger.info("WhatsApp message sent successfully via CallMeBot.")
            return True
        else:
            logger.error(f"CallMeBot error (Status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending WhatsApp message via CallMeBot: {e}")
        return False

def send_whatsapp_twilio(phone: str, message: str, account_sid: str, auth_token: str, from_number: str = "whatsapp:+14155238886") -> bool:
    """
    Sends a WhatsApp message using the Twilio API.
    """
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        target_phone = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        
        msg = client.messages.create(
            from_=from_number,
            body=message,
            to=target_phone
        )
        logger.info(f"WhatsApp message sent successfully via Twilio (SID: {msg.sid}).")
        return True
    except Exception as e:
        logger.error(f"Error sending WhatsApp message via Twilio: {e}")
        return False

def send_whatsapp_alert(config: dict, message: str) -> bool:
    """
    Master WhatsApp dispatcher checking Twilio first, then CallMeBot.
    Supports environment variable overrides for GitHub Actions.
    """
    import os
    wa_cfg = config.get("whatsapp", {})
    
    phone = os.environ.get("WHATSAPP_PHONE_NUMBER") or wa_cfg.get("phone_number")
    callmebot_key = os.environ.get("CALLMEBOT_API_KEY") or wa_cfg.get("callmebot_apikey")
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID") or wa_cfg.get("twilio_account_sid")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN") or wa_cfg.get("twilio_auth_token")
    provider = (os.environ.get("WHATSAPP_PROVIDER") or wa_cfg.get("provider", "callmebot")).lower()

    if not phone or phone == "+91XXXXXXXXXX":
        return False

    if provider == "twilio" or (twilio_sid and twilio_token):
        return send_whatsapp_twilio(
            phone=phone,
            message=message,
            account_sid=twilio_sid,
            auth_token=twilio_token,
            from_number=wa_cfg.get("twilio_from_number", "whatsapp:+14155238886")
        )
    elif callmebot_key and callmebot_key != "YOUR_CALLMEBOT_API_KEY":
        return send_whatsapp_callmebot(
            phone=phone,
            message=message,
            apikey=callmebot_key
        )
    return False

def format_whatsapp_stock_alert(product_title: str, product_url: str, pincode: str, price: str = None, delivery_info: str = None, city_name: str = "India") -> str:
    """
    Formats a clean plain text / WhatsApp alert message with emoji markers.
    """
    title = product_title or "Croma Product"
    price_val = price or "N/A"
    status_val = delivery_info or "In Stock / Available for delivery"

    msg = (
        f"🚨 CROMA STOCK ALERT! 🚨\n\n"
        f"📱 Product: {title}\n"
        f"🏙 City: {city_name}\n"
        f"📍 Pincode: {pincode}\n"
        f"💰 Price: {price_val}\n"
        f"🚚 Status: {status_val}\n\n"
        f"🔗 Buy Now: {product_url}"
    )
    return msg
