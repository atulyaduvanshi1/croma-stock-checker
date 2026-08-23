import requests
import logging
import html

logger = logging.getLogger("croma_checker")

CITY_PINCODE_MAP = {
    # Bangalore
    "560001": "Bangalore (MG Road)", "560002": "Bangalore (City Market)", "560003": "Bangalore (Malleshwaram)",
    "560004": "Bangalore (Basavanagudi)", "560008": "Bangalore (Halasuru)", "560010": "Bangalore (Rajajinagar)",
    "560011": "Bangalore (Jayanagar)", "560017": "Bangalore (HAL/Vimanapura)", "560025": "Bangalore (Richmond Town)",
    "560034": "Bangalore (Koramangala)", "560037": "Bangalore (Marathahalli)", "560038": "Bangalore (Indiranagar)",
    "560040": "Bangalore (Vijayanagar)", "560066": "Bangalore (Whitefield)", "560068": "Bangalore (BTM Layout)",
    "560076": "Bangalore (JP Nagar)", "560078": "Bangalore (JP Nagar 6th Phase)", "560085": "Bangalore (Banashankari)",
    "560092": "Bangalore (Hebbal)", "560100": "Bangalore (Electronic City)",

    # Mumbai
    "400001": "Mumbai (Fort/South)", "400002": "Mumbai (Kalbadevi)", "400005": "Mumbai (Colaba)",
    "400012": "Mumbai (Parel)", "400013": "Mumbai (Lower Parel)", "400014": "Mumbai (Dadar)",
    "400018": "Mumbai (Worli)", "400020": "Mumbai (Churchgate)", "400050": "Mumbai (Bandra West)",
    "400051": "Mumbai (BKC/Bandra East)", "400053": "Mumbai (Andheri West)", "400058": "Mumbai (Lokhandwala)",
    "400069": "Mumbai (Andheri East)", "400070": "Mumbai (Kurla)", "400076": "Mumbai (Powai)",
    "400077": "Mumbai (Ghatkopar)", "400080": "Mumbai (Mulund)", "400092": "Mumbai (Borivali)",
    "400097": "Mumbai (Malad East)", "400101": "Mumbai (Kandivali)",

    # Hyderabad
    "500001": "Hyderabad (Abids)", "500003": "Hyderabad (Secunderabad)", "500004": "Hyderabad (Khairatabad)",
    "500016": "Hyderabad (Begumpet)", "500018": "Hyderabad (SR Nagar)", "500028": "Hyderabad (Masab Tank)",
    "500032": "Hyderabad (Gachibowli)", "500033": "Hyderabad (Jubilee Hills)", "500034": "Hyderabad (Banjara Hills)",
    "500038": "Hyderabad (Srinagar Colony)", "500049": "Hyderabad (Miyapur)", "500050": "Hyderabad (Chanda Nagar)",
    "500072": "Hyderabad (Kukatpally)", "500081": "Hyderabad (HITEC City)", "500082": "Hyderabad (Somajiguda)",
    "500084": "Hyderabad (Kondapur)", "500085": "Hyderabad (KPHB Colony)", "500089": "Hyderabad (Manikonda)",
    "500090": "Hyderabad (Nizampet)", "500096": "Hyderabad (Madhapur)",

    # Pune
    "411001": "Pune (Station/Camp)", "411002": "Pune (Bajirao Road)", "411004": "Pune (Deccan Gymkhana)",
    "411005": "Pune (Shivajinagar)", "411006": "Pune (Yerwada)", "411007": "Pune (Aundh)",
    "411014": "Pune (Viman Nagar)", "411016": "Pune (Model Colony)", "411028": "Pune (Hadapsar)",
    "411030": "Pune (Sadashiv Peth)", "411037": "Pune (Bibvewadi)", "411038": "Pune (Kothrud)",
    "411040": "Pune (Wanowrie)", "411041": "Pune (Vadgaon)", "411043": "Pune (Dhankawadi)",
    "411045": "Pune (Baner)", "411052": "Pune (Karve Nagar)", "411057": "Pune (Hinjawadi)",
    "411061": "Pune (Pimple Saudagar)", "411062": "Pune (Nigdi)",

    # Lucknow
    "226001": "Lucknow (Hazratganj)", "226002": "Lucknow (Charbagh)", "226003": "Lucknow (Chowk)",
    "226004": "Lucknow (Mahanagar)", "226005": "Lucknow (Alambagh)", "226006": "Lucknow (Rajajipuram)",
    "226007": "Lucknow (Nirala Nagar)", "226010": "Lucknow (Gomti Nagar)", "226012": "Lucknow (Kanpur Road)",
    "226016": "Lucknow (Indira Nagar)", "226017": "Lucknow (Vikas Nagar)", "226018": "Lucknow (Aminabad)",
    "226020": "Lucknow (Janki Puram)", "226021": "Lucknow (Sitapur Road)", "226022": "Lucknow (Aliganj)",
    "226024": "Lucknow (Aashiana)", "226025": "Lucknow (Sushant Golf City)", "226026": "Lucknow (Sardar Patel Marg)",
    "226028": "Lucknow (Chinhat)", "226030": "Lucknow (Telibagh)",

    # Ghaziabad
    "201001": "Ghaziabad (Central)", "201002": "Ghaziabad (Raj Nagar)", "201003": "Ghaziabad (Kavi Nagar)",
    "201004": "Ghaziabad (Modinagar)", "201005": "Ghaziabad (Sahibabad)", "201006": "Ghaziabad (Mohan Nagar)",
    "201007": "Ghaziabad (Govindpuri)", "201008": "Ghaziabad (Muradnagar)", "201009": "Ghaziabad (Vijay Nagar)",
    "201010": "Ghaziabad (Indirapuram)", "201011": "Ghaziabad (Crossings Republik)", "201012": "Ghaziabad (Loni)",
    "201013": "Ghaziabad (Kaushambi)", "201014": "Ghaziabad (Vasundhara)", "201015": "Ghaziabad (Vaishali)",
    "201016": "Ghaziabad (Surya Nagar)", "201017": "Ghaziabad (Chander Nagar)", "201018": "Ghaziabad (Bhopura)",
    "201019": "Ghaziabad (Rajendra Nagar)", "201020": "Ghaziabad (Shalimar Garden)",

    # Delhi / NCR & UP
    "110001": "Delhi (Connaught Place)", "110003": "Delhi (Lodhi Road)", "110014": "Delhi (Jangpura)",
    "110016": "Delhi (Hauz Khas)", "110017": "Delhi (Malviya Nagar)", "110019": "Delhi (Kalkaji)",
    "110020": "Delhi (Okhla)", "110024": "Delhi (Lajpat Nagar)", "110029": "Delhi (Safdarjung)",
    "110048": "Delhi (Greater Kailash)", "110070": "Delhi (Vasant Kunj)", "110075": "Delhi (Dwarka)",
    "110085": "Delhi (Rohini)", "110091": "Delhi (Mayur Vihar)", "110092": "Delhi (Preet Vihar)",
    "201301": "Noida (Sector 18)", "201304": "Noida (Sector 137)", "201309": "Noida (Expressway)",
    "208001": "Kanpur (Central)", "221001": "Varanasi (Central)",

    # Jodhpur
    "342001": "Jodhpur (Old City/HO)", "342002": "Jodhpur (Pratap Nagar)", "342003": "Jodhpur (Ratanada)",
    "342004": "Jodhpur (Sardarpura)", "342005": "Jodhpur (Shastri Nagar)", "342006": "Jodhpur (Chopasni)",
    "342007": "Jodhpur (Residency Road)", "342008": "Jodhpur (Paota)", "342009": "Jodhpur (Basni)",
    "342010": "Jodhpur (Bhadwasiya)", "342011": "Jodhpur (Mandore)", "342014": "Jodhpur (Boranada)",
    "342015": "Jodhpur (Salawas)", "342024": "Jodhpur (Kuri Bhagtasani)", "342026": "Jodhpur (Jhalamand)",
    "342027": "Jodhpur (Pal Road)", "342304": "Jodhpur (Tinwari)", "342012": "Jodhpur (Mahamandir)",
    "342013": "Jodhpur (Airforce)", "342021": "Jodhpur (Dangiyawas)",

    # Kolkata
    "700001": "Kolkata (Central/BBD Bagh)", "700007": "Kolkata (Burrabazar)", "700016": "Kolkata (Park Street)",
    "700019": "Kolkata (Ballygunge)", "700020": "Kolkata (AJC Bose Rd)", "700027": "Kolkata (Alipore)",
    "700029": "Kolkata (Gariahat)", "700032": "Kolkata (Jadavpur)", "700047": "Kolkata (Garia)",
    "700053": "Kolkata (New Alipore)", "700054": "Kolkata (Kankurgachi)", "700064": "Kolkata (Salt Lake Sec 1)",
    "700078": "Kolkata (Kasba)", "700089": "Kolkata (Lake Town)", "700091": "Kolkata (Salt Lake Sec 5)",
    "700094": "Kolkata (EM Bypass)", "700102": "Kolkata (Dum Dum)", "700106": "Kolkata (Salt Lake Sec 3)",
    "700135": "Kolkata (New Town Sec 1)", "700156": "Kolkata (New Town Sec 2)",

    # Chennai
    "600001": "Chennai (Parrys)", "600002": "Chennai (Anna Salai)", "600004": "Chennai (Mylapore)",
    "600006": "Chennai (Nungambakkam)", "600017": "Chennai (T. Nagar)", "600018": "Chennai (Teynampet)",
    "600020": "Chennai (Adyar)", "600028": "Chennai (RA Puram)", "600032": "Chennai (Guindy)",
    "600034": "Chennai (Kodambakkam)", "600040": "Chennai (Anna Nagar)", "600041": "Chennai (Thiruvanmiyur)",
    "600042": "Chennai (Velachery)", "600078": "Chennai (KK Nagar)", "600083": "Chennai (Ashok Nagar)",
    "600096": "Chennai (Perungudi)", "600097": "Chennai (Kandanchavadi)", "600100": "Chennai (Medavakkam)",
    "600113": "Chennai (Taramani/OMR)", "600119": "Chennai (Sholinganallur)"
}

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
    city_name = CITY_PINCODE_MAP.get(str(pincode), "India")
    safe_city = html.escape(city_name)
    safe_price = html.escape(str(price)) if price else "N/A"
    safe_delivery = html.escape(str(delivery_info)) if delivery_info else "In Stock / Available for delivery"
    safe_url = html.escape(product_url)

    msg = (
        f"🚨 <b>CROMA STOCK ALERT!</b> 🚨\n\n"
        f"📱 <b>Product:</b> {safe_title}\n"
        f"🏙 <b>City / Area:</b> {safe_city}\n"
        f"📍 <b>Pincode:</b> <code>{safe_pincode}</code>\n"
        f"💰 <b>Price:</b> {safe_price}\n"
        f"🚚 <b>Status:</b> {safe_delivery}\n\n"
        f"🔗 <a href=\"{safe_url}\">Click Here to Buy Now on Croma</a>"
    )
    return msg
