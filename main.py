from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import requests
import os
import json
import base64
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# ── Data Storage ───────────────────────────────────────────────
user_states = {}
marketplace = []
premium_users = {}
farmer_profiles = {}

def load_data():
    global marketplace, premium_users, farmer_profiles
    try:
        with open("marketplace.json", "r") as f:
            marketplace = json.load(f)
    except:
        marketplace = []
    try:
        with open("premium_users.json", "r") as f:
            premium_users = json.load(f)
    except:
        premium_users = {}
    try:
        with open("farmer_profiles.json", "r") as f:
            farmer_profiles = json.load(f)
    except:
        farmer_profiles = {}

def save_data():
    with open("marketplace.json", "w") as f:
        json.dump(marketplace, f)
    with open("premium_users.json", "w") as f:
        json.dump(premium_users, f)
    with open("farmer_profiles.json", "w") as f:
        json.dump(farmer_profiles, f)

load_data()

# ── Zimbabwe Regions ───────────────────────────────────────────
ZIMBABWE_REGIONS = {
    "harare": {"region": 2, "lat": -17.8252, "lon": 31.0335,
               "climate": "Sub-humid", "rainfall": "600-800mm",
               "best_crops": "Maize, Tobacco, Horticulture, Wheat"},
    "bulawayo": {"region": 4, "lat": -20.1325, "lon": 28.6264,
                 "climate": "Semi-arid", "rainfall": "400-600mm",
                 "best_crops": "Sorghum, Millet, Sunflower, Cotton"},
    "mutare": {"region": 1, "lat": -18.9707, "lon": 32.6709,
               "climate": "Sub-humid to Humid", "rainfall": "800-1200mm",
               "best_crops": "Tea, Coffee, Macadamia, Maize, Beans"},
    "masvingo": {"region": 4, "lat": -20.0635, "lon": 30.8335,
                 "climate": "Semi-arid", "rainfall": "400-600mm",
                 "best_crops": "Sorghum, Cotton, Sunflower, Groundnuts"},
    "gweru": {"region": 3, "lat": -19.4500, "lon": 29.8167,
              "climate": "Semi-humid", "rainfall": "500-700mm",
              "best_crops": "Maize, Groundnuts, Soya, Sunflower"},
    "marondera": {"region": 2, "lat": -18.1833, "lon": 31.5500,
                  "climate": "Sub-humid", "rainfall": "700-900mm",
                  "best_crops": "Maize, Tobacco, Wheat, Horticulture"},
    "chinhoyi": {"region": 2, "lat": -17.3667, "lon": 30.2000,
                 "climate": "Sub-humid", "rainfall": "700-900mm",
                 "best_crops": "Maize, Tobacco, Soya, Wheat"},
    "bindura": {"region": 2, "lat": -17.3000, "lon": 31.3333,
                "climate": "Sub-humid", "rainfall": "700-900mm",
                "best_crops": "Maize, Tobacco, Cotton, Groundnuts"},
    "victoria falls": {"region": 4, "lat": -17.9322, "lon": 25.8306,
                       "climate": "Semi-arid", "rainfall": "500-700mm",
                       "best_crops": "Maize, Cotton, Sesame, Sorghum"},
    "kariba": {"region": 4, "lat": -16.5167, "lon": 28.8000,
               "climate": "Hot semi-arid", "rainfall": "400-600mm",
               "best_crops": "Cotton, Sorghum, Millet, Sesame"},
    "chiredzi": {"region": 5, "lat": -21.0500, "lon": 31.6667,
                 "climate": "Arid", "rainfall": "300-400mm",
                 "best_crops": "Sugarcane, Cotton, Sorghum, Livestock"},
    "beitbridge": {"region": 5, "lat": -22.2167, "lon": 30.0000,
                   "climate": "Very arid", "rainfall": "200-400mm",
                   "best_crops": "Livestock, Sorghum, Millet, Drought crops"},
    "zvishavane": {"region": 4, "lat": -20.3333, "lon": 30.0333,
                   "climate": "Semi-arid", "rainfall": "400-600mm",
                   "best_crops": "Sorghum, Cotton, Groundnuts, Livestock"},
    "kwekwe": {"region": 3, "lat": -18.9167, "lon": 29.8167,
               "climate": "Semi-humid", "rainfall": "500-700mm",
               "best_crops": "Maize, Groundnuts, Soya, Cotton"},
    "kadoma": {"region": 3, "lat": -18.3500, "lon": 29.9167,
               "climate": "Semi-humid", "rainfall": "500-700mm",
               "best_crops": "Cotton, Maize, Groundnuts, Wheat"},
    "norton": {"region": 2, "lat": -17.8833, "lon": 30.7000,
               "climate": "Sub-humid", "rainfall": "600-800mm",
               "best_crops": "Maize, Tobacco, Horticulture, Wheat"},
    "rusape": {"region": 2, "lat": -18.5333, "lon": 32.1333,
               "climate": "Sub-humid", "rainfall": "700-900mm",
               "best_crops": "Maize, Tobacco, Beans, Horticulture"},
    "nyanga": {"region": 1, "lat": -18.2167, "lon": 32.7500,
               "climate": "Humid", "rainfall": "1000-1500mm",
               "best_crops": "Potatoes, Wheat, Apples, Beans, Tea"},
    "chipinge": {"region": 1, "lat": -20.1833, "lon": 32.6167,
                 "climate": "Sub-humid", "rainfall": "800-1200mm",
                 "best_crops": "Tea, Coffee, Macadamia, Avocado, Maize"},
}

# ── Get Region Info ────────────────────────────────────────────
def get_region_info(location: str) -> dict:
    loc_lower = location.lower()
    for city, info in ZIMBABWE_REGIONS.items():
        if city in loc_lower:
            return info
    return {
        "region": 2, "lat": -17.8252, "lon": 31.0335,
        "climate": "Sub-humid", "rainfall": "600-800mm",
        "best_crops": "Maize, Tobacco, Horticulture"
    }

# ── Check Premium ──────────────────────────────────────────────
def is_premium(phone: str) -> bool:
    return phone in premium_users and premium_users[phone].get("active", False)

# ── Ask Groq AI ────────────────────────────────────────────────
def ask_groq(question: str, topic: str = "", location: str = "") -> str:
    try:
        region_context = ""
        if location and location in farmer_profiles:
            profile = farmer_profiles[location]
            loc = profile.get("location", "Zimbabwe")
            region_info = get_region_info(loc)
            region_context = f"""
            Farmer's location: {loc}
            Climate region: Region {region_info['region']} ({region_info['climate']})
            Annual rainfall: {region_info['rainfall']}
            Best crops for their area: {region_info['best_crops']}
            Current season: March (end of rainy season in Zimbabwe)
            """

        system_prompt = f"""You are AgroBot, an expert agriculture 
        assistant helping smallholder farmers and farming companies 
        across Zimbabwe.
        {f'Focus on: {topic}' if topic else ''}
        {region_context}
        Answer in simple clear language under 150 words.
        Give practical advice using locally available resources in Zimbabwe.
        Consider climate change impacts on Zimbabwe farming.
        Always end with one actionable tip."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq error: {e}")
        return "Sorry AgroBot is busy. Please try again shortly."

# ── Analyze Image ──────────────────────────────────────────────
def analyze_image(image_url: str) -> str:
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        img_response = requests.get(image_url, headers=headers)
        img_base64 = base64.b64encode(img_response.content).decode("utf-8")

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": """You are AgroBot, an expert crop disease specialist 
                            helping Zimbabwe farmers. Analyze this image and provide:
                            1. 🌿 Crop/plant identified
                            2. 🔍 Disease, pest or problem detected
                            3. 💊 Treatment using locally available products in Zimbabwe
                            4. 🛡️ Prevention tips for next season
                            5. ⚠️ Urgency level (Low/Medium/High)
                            Keep response under 200 words in simple language."""
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Image error: {e}")
        return "Could not analyze image. Please describe the problem in text."

# ── Regional Weather ───────────────────────────────────────────
def get_regional_weather_advice(location: str) -> str:
    try:
        region_info = get_region_info(location)
        lat = region_info["lat"]
        lon = region_info["lon"]

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,et0_fao_evapotranspiration&timezone=Africa/Harare&forecast_days=7"
        response = requests.get(url)
        data = response.json()
        daily = data["daily"]

        forecast = f"🌤️ *7-Day Forecast — {location.title()}*\n"
        forecast += f"📍 Region {region_info['region']} | {region_info['climate']}\n"
        forecast += f"🌧️ Annual Rainfall: {region_info['rainfall']}\n\n"

        total_rain = sum(daily["precipitation_sum"])
        avg_max = sum(daily["temperature_2m_max"]) / 7

        for i in range(7):
            date = daily["time"][i]
            max_t = daily["temperature_2m_max"][i]
            min_t = daily["temperature_2m_min"][i]
            rain = daily["precipitation_sum"][i]
            prob = daily["precipitation_probability_max"][i]
            wind = daily["windspeed_10m_max"][i]

            if rain > 20:
                icon = "🌧️ Heavy Rain"
            elif rain > 5:
                icon = "🌦️ Light Rain"
            elif prob > 50:
                icon = "⛅ Possible Rain"
            else:
                icon = "☀️ Clear"

            forecast += f"*{date}* {icon}\n"
            forecast += f"  🌡️ {min_t}°C-{max_t}°C 💧{rain}mm 💨{wind}km/h\n"

        prompt = f"""Zimbabwe farmer in {location} (Region {region_info['region']}, {region_info['climate']}).
        Weather this week: avg max {avg_max:.1f}°C, total rain {total_rain:.1f}mm.
        Best crops: {region_info['best_crops']}.
        Season: March (end of rainy season).
        Climate change note: Zimbabwe experiencing erratic rainfall and higher temperatures.
        Give 4 specific farming tips for THIS week. Be practical and locally relevant."""

        advice = ask_groq(prompt, "Zimbabwe regional farming and climate change adaptation")
        forecast += f"\n🌱 *Regional Farming Advice:*\n{advice}"
        return forecast

    except Exception as e:
        print(f"Weather error: {e}")
        return "Could not fetch weather data. Please try again."

# ── Find Help Nearby ───────────────────────────────────────────
def find_help_nearby(location: str) -> str:
    help_centers = {
        "harare": [
            ("🏛️ Agritex Head Office", "Borrowdale Rd, Harare", "04-700181"),
            ("🌾 GMB Harare Depot", "Willowvale, Harare", "04-621000"),
            ("🏦 Agribank Harare", "Jason Moyo Ave", "04-700476"),
            ("🛒 Farmer's World Harare", "Msasa, Harare", "04-447891"),
            ("🧪 Agro-Chem Supplies", "Willowvale", "04-621234"),
        ],
        "bulawayo": [
            ("🏛️ Agritex Bulawayo", "Fort Street", "09-888234"),
            ("🌾 GMB Bulawayo Depot", "Industrial Sites", "09-888100"),
            ("🏦 Agribank Bulawayo", "Fife Street", "09-888476"),
            ("🛒 Farmer's Choice", "Belmont, Bulawayo", "09-888567"),
        ],
        "mutare": [
            ("🏛️ Agritex Mutare", "Main Street", "020-64234"),
            ("🌾 GMB Mutare Depot", "Sakubva", "020-64100"),
            ("🏦 CBZ Agri Mutare", "Herbert Chitepo St", "020-64476"),
        ],
        "masvingo": [
            ("🏛️ Agritex Masvingo", "Hughes Street", "039-262234"),
            ("🌾 GMB Masvingo Depot", "Industrial Area", "039-262100"),
            ("🏦 Agribank Masvingo", "Robert Mugabe Way", "039-262476"),
        ],
        "marondera": [
            ("🏛️ Agritex Marondera", "Main Road", "079-23234"),
            ("🌾 GMB Marondera Depot", "Industrial Area", "079-23100"),
            ("🛒 Windmill Agro", "Main Street", "079-23567"),
        ],
        "gweru": [
            ("🏛️ Agritex Gweru", "Sixth Street", "054-223234"),
            ("🌾 GMB Gweru Depot", "Industrial Sites", "054-223100"),
            ("🏦 Agribank Gweru", "Main Street", "054-223476"),
        ],
        "chinhoyi": [
            ("🏛️ Agritex Chinhoyi", "Magamba Way", "067-22234"),
            ("🌾 GMB Chinhoyi Depot", "Industrial Area", "067-22100"),
            ("🏦 ZB Agri Chinhoyi", "Main Street", "067-22476"),
        ],
    }

    loc_lower = location.lower()
    found = None
    for city, places in help_centers.items():
        if city in loc_lower:
            found = places
            break

    if not found:
        return f"""📍 *Agricultural Help in Zimbabwe*

🏛️ *Agritex (Free Extension Services)*
Government farming advice — find nearest:
📞 04-700181 or 0800 4040 (toll free)

🌾 *GMB (Grain Marketing Board)*
Sell your crops at official prices
📞 04-621000

🏦 *Agricultural Finance*
- Agribank: 04-700476
- CBZ Agri: 04-250579
- ZB Bank Agri: 04-758081

🛒 *Find Agro-Dealers Near {location.title()}*
Search Google Maps: "agro dealer {location}"

🌱 *NGO Support*
- FAO Zimbabwe: 04-776591
- AGRITEX: 0800 4040 (free)

Type your specific town for more help!"""

    result = f"📍 *Help Near {location.title()}:*\n\n"
    for name, address, phone in found:
        result += f"{name}\n"
        result += f"   📌 {address}\n"
        result += f"   📞 {phone}\n\n"

    result += """━━━━━━━━━━━━━━
🌱 *National Resources:*
- Agritex Helpline: 0800 4040 (free)
- GMB National: 04-621000
- Agribank: 04-700476
- FAO Zimbabwe: 04-776591"""

    return result

# ── Premium Menu ───────────────────────────────────────────────
def get_premium_menu(phone: str) -> str:
    if is_premium(phone):
        plan = premium_users[phone].get("plan", "premium")
        return f"""⭐ *Your AgroBot Account*

Plan: *{plan.upper()}*
Status: ✅ Active

All Premium Features Unlocked:
✅ Regional Weather Forecasts
✅ Photo Crop Analysis
✅ Find Help Near You
✅ Loan & Insurance Advice
✅ Farm Planning Calendar
✅ Climate Change Alerts
✅ Priority AI Responses

Type *MENU* to use all features!"""
    else:
        return """⭐ *Upgrade to AgroBot Premium*

*FREE Plan (Current):*
✅ Basic crop disease advice
✅ Soil health analysis
✅ Marketplace
✅ Ask farming questions

*PREMIUM — $2/month:*
💎 Regional weather forecasts
💎 Photo crop analysis
💎 Find help near you
💎 Loan & insurance advice
💎 Farm planning calendar
💎 Climate change alerts
💎 Priority responses

*BUSINESS — $10/month:*
🏆 Everything in Premium
🏆 Dedicated farm consultant AI
🏆 Export market connections
🏆 Bulk buyer matching
🏆 Custom farm reports
🏆 Multiple farm management

*To Subscribe:*
Reply *1* for Premium ($2/month)
Reply *2* for Business ($10/month)
Reply *0* to go back"""

# ── Payment Request ────────────────────────────────────────────
def process_payment_request(phone: str, plan: str) -> str:
    amount = "2" if plan == "premium" else "10"
    ref = f"AGRO{phone[-6:]}"

    return f"""💳 *AgroBot {plan.upper()} Subscription*

Amount: *${amount}/month*

━━━━━━━━━━━━━━
*Pay via EcoCash:*
1. Dial *151#
2. Select Send Money
3. Enter number: *0787 341 018*
4. Amount: ${amount}
5. Reference: *{ref}*
━━━━━━━━━━━━━━
*Pay via OneMoney:*
1. Dial *111#
2. Select Send Money
3. Number: *0713313250*
4. Amount: ${amount}
5. Reference: *{ref}*
━━━━━━━━━━━━━━

*After paying reply:*
*PAID {ref}*

Activated within 30 minutes! ✅

Questions? Call: *0787 341 018*"""

# ── Verify Payment ─────────────────────────────────────────────
def verify_payment(phone: str, ref: str) -> str:
    expected_ref = f"AGRO{phone[-6:]}"
    if ref.upper() == expected_ref.upper():
        return f"""✅ *Payment Reference Received!*

Reference: *{ref}*

Your payment is being verified.
Premium will be activated within 
30 minutes after confirmation.

For instant activation:
📞 *0787 341 018*

Thank you for supporting AgroBot! 🌱
Zimbabwe's Smart Farming Assistant"""
    else:
        return "❌ Invalid reference. Please check and try again.\nOr call 0787 341 018 for help."

# ── Main Menu ──────────────────────────────────────────────────
def get_main_menu(phone: str) -> str:
    badge = "⭐ PREMIUM" if is_premium(phone) else "🆓 FREE"
    location_info = ""
    if phone in farmer_profiles:
        loc = farmer_profiles[phone].get("location", "")
        if loc:
            region = get_region_info(loc)
            location_info = f"📍 {loc.title()} | Region {region['region']}\n"

    return f"""🌱 *AgroBot Zimbabwe*
Smart Farming Assistant
{badge} {location_info}
━━━━━━━━━━━━━━
*FREE SERVICES:*
1️⃣ Crop Disease & Pest Advice
2️⃣ Soil Health Analysis
3️⃣ 🛒 Marketplace
4️⃣ Ask Any Question

*PREMIUM 💎:*
5️⃣ Weather & Climate Forecast
6️⃣ 📸 Photo Crop Analysis
7️⃣ 📍 Find Help Near You
8️⃣ Loan & Insurance Advice
9️⃣ Farm Planning Calendar

0️⃣ ⭐ My Account / Subscribe
━━━━━━━━━━━━━━
Type *MENU* anytime to return"""

# ── Marketplace Menu ───────────────────────────────────────────
def get_marketplace_menu() -> str:
    return """🛒 *AGROBOT MARKETPLACE*
Zimbabwe Buy & Sell Platform

1️⃣ Post item for SALE
2️⃣ Search for BUYERS
3️⃣ Search for SELLERS
4️⃣ View all listings
0️⃣ Back to main menu"""

def get_all_listings() -> str:
    if not marketplace:
        return "📭 No listings yet!\nBe the first to post — reply *MENU* then select 3️⃣"
    result = "📋 *Marketplace Listings:*\n\n"
    for i, item in enumerate(marketplace[-10:], 1):
        result += f"*{i}. {item.get('category', item['type']).upper()}*\n"
        result += f"📦 {item['item']}\n"
        result += f"📍 {item['location']}\n"
        result += f"💰 {item['price']}\n"
        result += f"📞 {item['phone']}\n\n"
    return result

def search_listings(search_type: str, query: str = "") -> str:
    results = [x for x in marketplace if x['type'] == search_type]
    if query:
        results = [x for x in results
                   if query.lower() in x['item'].lower()
                   or query.lower() in x.get('category', '').lower()]
    if not results:
        return f"📭 No {search_type}s found for '{query}'.\nTry a different search!"
    result = f"🔍 *{search_type.upper()} Listings:*\n\n"
    for item in results[-5:]:
        result += f"📦 {item['item']}\n"
        result += f"📍 {item['location']}\n"
        result += f"💰 {item['price']}\n"
        result += f"📞 {item['phone']}\n\n"
    return result

# ── Process Message ────────────────────────────────────────────
def process_message(from_number: str, msg_text: str) -> str:
    msg = msg_text.strip()
    state = user_states.get(from_number, "menu")

    # Always return to menu
    if msg.upper() == "MENU":
        user_states[from_number] = "menu"
        return get_main_menu(from_number)

    # Check for upgrade keyword
    if msg.upper() == "UPGRADE":
        user_states[from_number] = "subscribe"
        return get_premium_menu(from_number)

    # Check for payment confirmation
    if msg.upper().startswith("PAID "):
        ref = msg.split(" ", 1)[1].strip() if len(msg.split()) > 1 else ""
        return verify_payment(from_number, ref)

    # ── NEW FARMER REGISTRATION ─────────────────────────────────
    if state == "menu" and from_number not in farmer_profiles:
        if msg.lower() in ["hi", "hello", "hey", "start", "help"]:
            user_states[from_number] = "register_location"
            return """🌱 *Welcome to AgroBot Zimbabwe!*
Smart Farming Assistant

To give you accurate regional advice,
what is your *district or town*?

Examples:
- Harare • Bulawayo • Mutare
- Marondera • Masvingo • Gweru
- Chinhoyi • Bindura • Rusape
- Nyanga • Chipinge • Chiredzi

This helps us give you:
✅ Weather for your exact area
✅ Crops suited to your climate
✅ Climate change adapted advice
✅ Local help centers near you"""
        else:
            user_states[from_number] = "register_location"
            return "🌱 *Welcome to AgroBot!*\n\nWhat is your *district or town* in Zimbabwe?\n(e.g. Harare, Bulawayo, Marondera)"

    # ── REGISTER LOCATION STATE ─────────────────────────────────
    elif state == "register_location":
        farmer_profiles[from_number] = {
            "location": msg.lower(),
            "registered": True
        }
        save_data()
        region = get_region_info(msg)
        user_states[from_number] = "menu"
        return f"""✅ *Location Saved: {msg.title()}*

📍 Climate Region: *{region['region']}*
🌤️ Climate Type: {region['climate']}
🌧️ Annual Rainfall: {region['rainfall']}
🌱 Best crops for your area:
   {region['best_crops']}

All your advice is now personalised
for your region and climate! 🎉

{get_main_menu(from_number)}"""

    # ── MENU STATE ──────────────────────────────────────────────
    elif state == "menu":
        if msg.lower() in ["hi", "hello", "hey", "start", "help"]:
            return get_main_menu(from_number)

        elif msg == "1":
            user_states[from_number] = "disease"
            farmer_loc = farmer_profiles.get(from_number, {}).get("location", "")
            region_note = ""
            if farmer_loc:
                region = get_region_info(farmer_loc)
                region_note = f"\n📍 Advice will be specific to {farmer_loc.title()} (Region {region['region']})"
            return f"🌿 *Crop Disease & Pest Advice*{region_note}\n\nDescribe your crop problem or send a photo!\nWhat crop is affected and what symptoms do you see?"

        elif msg == "2":
            user_states[from_number] = "soil"
            return "🧪 *Soil Health Analysis*\n\nTell me about your soil:\n- Color (dark/red/pale/light)\n- Texture (sandy/clay/loam)\n- Crop you want to grow\n- What grew there before"

        elif msg == "3":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()

        elif msg == "4":
            user_states[from_number] = "freeask"
            return "💬 *Ask Any Farming Question*\n\nWhat would you like to know? Ask me anything!"

        elif msg == "5":
            if is_premium(from_number):
                user_states[from_number] = "weather"
                farmer_loc = farmer_profiles.get(from_number, {}).get("location", "")
                if farmer_loc:
                    return f"🌤️ *Weather Forecast*\n\nI have your location as *{farmer_loc.title()}*.\n\nReply with your location to confirm\nor type a different location:"
                return "🌤️ *Weather Forecast*\n\nEnter your location:\n(e.g. Harare, Bulawayo, Mutare)"
            else:
                return "🔒 *Weather is a Premium Feature*\n\nUpgrade for $2/month to unlock!\n\nReply *UPGRADE* to subscribe\nOr type *MENU* to go back"

        elif msg == "6":
            if is_premium(from_number):
                user_states[from_number] = "image_prompt"
                return "📸 *Photo Crop Analysis*\n\nSend me a photo of your affected crop!\nI will identify diseases and recommend treatment."
            else:
                return "🔒 *Photo Analysis is Premium*\n\nUpgrade for $2/month!\nReply *UPGRADE* or type *MENU*"

        elif msg == "7":
            if is_premium(from_number):
                user_states[from_number] = "location_help"
                farmer_loc = farmer_profiles.get(from_number, {}).get("location", "")
                if farmer_loc:
                    return f"📍 *Find Help Near You*\n\nYour saved location: *{farmer_loc.title()}*\n\nReply with location to confirm\nor enter a different location:"
                return "📍 *Find Help Near You*\n\nEnter your location:\n(e.g. Harare, Bulawayo, Mutare)"
            else:
                return "🔒 *Location Help is Premium*\n\nUpgrade for $2/month!\nReply *UPGRADE* or type *MENU*"

        elif msg == "8":
            if is_premium(from_number):
                user_states[from_number] = "loan"
                return "🏦 *Loan & Insurance Advice*\n\nTell me:\n- Your farm size (acres)\n- Main crop you grow\n- What you need (loan/insurance/both)\n- Your province/district"
            else:
                return "🔒 *Loan Advice is Premium*\n\nUpgrade for $2/month!\nReply *UPGRADE* or type *MENU*"

        elif msg == "9":
            if is_premium(from_number):
                user_states[from_number] = "farm_plan"
                farmer_loc = farmer_profiles.get(from_number, {}).get("location", "Zimbabwe")
                return f"📅 *Farm Planning Calendar*\n\nTell me:\n- Farm size (acres)\n- Crops you want to grow\n- Do you have irrigation? (yes/no)\n- Your budget range\n\nYour location: {farmer_loc.title()}"
            else:
                return "🔒 *Farm Planning is Premium*\n\nUpgrade for $2/month!\nReply *UPGRADE* or type *MENU*"

        elif msg == "0":
            user_states[from_number] = "subscribe"
            return get_premium_menu(from_number)

        else:
            # Smart fallback — answer any farming question
            reply = ask_groq(msg, location=from_number)
            return f"💬 *AgroBot Answer:*\n\n{reply}\n\nType *MENU* for main menu."

    # ── DISEASE STATE ───────────────────────────────────────────
    elif state == "disease":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "crop disease, pest identification and organic/chemical treatment in Zimbabwe",
            location=from_number)
        return f"🌿 *Disease Advice:*\n\n{reply}\n\nType *MENU* to return."

    # ── SOIL STATE ──────────────────────────────────────────────
    elif state == "soil":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "soil health, pH correction and fertilizer recommendations for Zimbabwe",
            location=from_number)
        return f"🧪 *Soil Advice:*\n\n{reply}\n\nType *MENU* to return."

    # ── FREE ASK STATE ──────────────────────────────────────────
    elif state == "freeask":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, location=from_number)
        return f"💬 *AgroBot Answer:*\n\n{reply}\n\nType *MENU* to return."

    # ── WEATHER STATE ───────────────────────────────────────────
    elif state == "weather":
        user_states[from_number] = "menu"
        reply = get_regional_weather_advice(msg)
        return f"{reply}\n\nType *MENU* to return."

    # ── LOCATION HELP STATE ─────────────────────────────────────
    elif state == "location_help":
        user_states[from_number] = "menu"
        reply = find_help_nearby(msg)
        return f"{reply}\n\nType *MENU* to return."

    # ── LOAN STATE ──────────────────────────────────────────────
    elif state == "loan":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "agricultural loans, crop insurance, Agribank, CBZ Agri, ZB Bank farming finance in Zimbabwe",
            location=from_number)
        return f"🏦 *Finance Advice:*\n\n{reply}\n\nType *MENU* to return."

    # ── FARM PLAN STATE ─────────────────────────────────────────
    elif state == "farm_plan":
        user_states[from_number] = "menu"
        farmer_loc = farmer_profiles.get(from_number, {}).get("location", "Zimbabwe")
        region = get_region_info(farmer_loc)
        context = f"Location: {farmer_loc}, Region {region['region']}, {region['climate']}, {region['rainfall']} rainfall, best crops: {region['best_crops']}"
        reply = ask_groq(f"{msg}. Farm context: {context}",
            "detailed farm planning, crop calendar, planting schedules, Zimbabwe seasonal farming",
            location=from_number)
        return f"📅 *Your Farm Plan:*\n\n{reply}\n\nType *MENU* to return."

    # ── SUBSCRIBE STATE ─────────────────────────────────────────
    elif state == "subscribe":
        if msg == "1":
            user_states[from_number] = "menu"
            return process_payment_request(from_number, "premium")
        elif msg == "2":
            user_states[from_number] = "menu"
            return process_payment_request(from_number, "business")
        elif msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        else:
            return get_premium_menu(from_number)

    # ── MARKETPLACE STATE ───────────────────────────────────────
    elif state == "marketplace":
        if msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        elif msg == "1":
            user_states[from_number] = "post_type"
            return """📢 *Post an Item for Sale*

What are you selling?
1️⃣ Crops (maize, tomatoes, etc.)
2️⃣ Fertilizer & Chemicals
3️⃣ Equipment & Tools
4️⃣ Livestock & Animals
0️⃣ Back"""
        elif msg == "2":
            user_states[from_number] = "search_buyer"
            return "🔍 *Search for Buyers*\n\nWhat item are you looking to sell?\n(e.g. maize, tomatoes, tobacco)"
        elif msg == "3":
            user_states[from_number] = "search_seller"
            return "🔍 *Search for Sellers*\n\nWhat item are you looking to buy?\n(e.g. fertilizer, equipment, seeds)"
        elif msg == "4":
            user_states[from_number] = "menu"
            return get_all_listings()
        else:
            return get_marketplace_menu()

    # ── POST TYPE ───────────────────────────────────────────────
    elif state == "post_type":
        types = {"1": "Crops", "2": "Fertilizer & Chemicals",
                 "3": "Equipment & Tools", "4": "Livestock"}
        if msg in types:
            user_states[from_number] = f"post_item_{types[msg]}"
            return f"📦 What *{types[msg]}* are you selling?\nInclude quantity.\nExample: 10 x 50kg bags of maize"
        elif msg == "0":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()
        else:
            return "Please reply 1, 2, 3 or 4"

    elif state.startswith("post_item_"):
        category = state.replace("post_item_", "")
        user_states[from_number] = f"post_location_{category}_{msg}"
        farmer_loc = farmer_profiles.get(from_number, {}).get("location", "")
        loc_hint = f"Your saved location: {farmer_loc.title()}\nOr enter a different location:" if farmer_loc else "Enter location:"
        return f"📍 *Location?*\n{loc_hint}\nExample: Marondera, Mashonaland East"

    elif state.startswith("post_location_"):
        parts = state.replace("post_location_", "").split("_", 1)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        user_states[from_number] = f"post_price_{category}_{item}_{msg}"
        return "💰 *Price?*\nExample: $50 per bag\nOr: Negotiable"

    elif state.startswith("post_price_"):
        parts = state.replace("post_price_", "").split("_", 2)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        location = parts[2] if len(parts) > 2 else "Unknown"
        user_states[from_number] = f"post_phone_{category}_{item}_{location}_{msg}"
        return "📞 *Contact number?*\nExample: 0771234567"

    elif state.startswith("post_phone_"):
        parts = state.replace("post_phone_", "").split("_", 3)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        location = parts[2] if len(parts) > 2 else "Unknown"
        price = parts[3] if len(parts) > 3 else "Negotiable"
        listing = {
            "type": "seller",
            "category": category,
            "item": item,
            "location": location,
            "price": price,
            "phone": msg,
            "poster": from_number
        }
        marketplace.append(listing)
        save_data()
        user_states[from_number] = "menu"
        return f"""✅ *Listing Posted Successfully!*

📦 {item}
📂 {category}
📍 {location}
💰 {price}
📞 {msg}

Visible to all AgroBot users
across Zimbabwe! 🇿🇼

Type *MENU* to return."""

    elif state == "search_buyer":
        user_states[from_number] = "menu"
        return f"{search_listings('buyer', msg)}\nType *MENU* to return."

    elif state == "search_seller":
        user_states[from_number] = "menu"
        return f"{search_listings('seller', msg)}\nType *MENU* to return."

    else:
        user_states[from_number] = "menu"
        return get_main_menu(from_number)

# ── Webhook Verification ───────────────────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params["hub.challenge"])
    return {"error": "Invalid verify token"}

# ── Receive Messages ───────────────────────────────────────────
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]
        msg_type = message.get("type", "text")

        # ── Image Messages ─────────────────────────────────────
        if msg_type == "image":
            if is_premium(from_number):
                image_id = message["image"]["id"]
                img_url_response = requests.get(
                    f"https://graph.facebook.com/v19.0/{image_id}",
                    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}
                )
                image_url = img_url_response.json().get("url")
                send_whatsapp_message(from_number,
                    "🔍 Analyzing your crop image...\nPlease wait 10-15 seconds!")
                analysis = analyze_image(image_url)
                reply = f"🌿 *AgroBot Crop Analysis:*\n\n{analysis}\n\nType *MENU* for main menu."
            else:
                reply = "🔒 *Photo analysis is a Premium feature!*\n\nUpgrade for $2/month to unlock instant crop disease detection.\n\nReply *UPGRADE* to subscribe!"
            send_whatsapp_message(from_number, reply)

        # ── Text Messages ──────────────────────────────────────
        elif msg_type == "text":
            msg_text = message["text"]["body"]
            print(f"Message from {from_number}: {msg_text}")
            reply = process_message(from_number, msg_text)
            send_whatsapp_message(from_number, reply)

    except (KeyError, IndexError) as e:
        print(f"Error: {e}")
    return {"status": "ok"}

# ── Send WhatsApp Message ──────────────────────────────────────
def send_whatsapp_message(to: str, message: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"Sent: {response.status_code}")

@app.get("/")
def home():
    return {"message": "AgroBot Pro Zimbabwe is running! 🌱"}
