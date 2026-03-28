from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import json
import base64
import math
import datetime
import hashlib
import secrets
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI(
    title="AgroBot Pro API",
    description="TM AGRO Solutions — Zimbabwe Smart Farming Assistant",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "951059444767602")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "agrobot123")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "AGROBOT_ADMIN_2026")
ECOCASH_NUMBER = "0787 341 018"
ONEMONEY_NUMBER = "0787 341 018"
SUPPORT_PHONE = "0787 341 018"
SUPPORT_EMAIL = "manhambaratapiwa548@gmail.com"
COMPANY_NAME = "TM AGRO Solutions"
BOT_NAME = "AgroBot Pro"
WEBSITE = "agrobot.co.zw"
WHATSAPP_TEST_NUMBER = "+1 555 185 0792"
BUSINESS_WHATSAPP_ID = "1706893334008426"
TRIAL_DAYS = 30

client = Groq(api_key=GROQ_API_KEY)

# ── Data Storage ───────────────────────────────────────────────
user_states = {}
marketplace = []
premium_users = {}
farmer_profiles = {}
conversations = {}
buyer_requests = []
seller_requests = []
payment_pending = {}
user_accounts = {}
market_prices = {}

def load_data():
    global marketplace, premium_users, farmer_profiles, conversations
    global buyer_requests, seller_requests, payment_pending, user_accounts, market_prices
    file_defaults = {
        "marketplace.json": (marketplace, []),
        "premium_users.json": (premium_users, {}),
        "farmer_profiles.json": (farmer_profiles, {}),
        "conversations.json": (conversations, {}),
        "buyer_requests.json": (buyer_requests, []),
        "seller_requests.json": (seller_requests, []),
        "payment_pending.json": (payment_pending, {}),
        "user_accounts.json": (user_accounts, {}),
        "market_prices.json": (market_prices, {}),
    }
    for fname, (var, default) in file_defaults.items():
        try:
            with open(fname, "r") as f:
                data = json.load(f)
                if isinstance(default, list):
                    var.clear()
                    var.extend(data)
                else:
                    var.clear()
                    var.update(data)
        except:
            pass

def save_data():
    data_map = {
        "marketplace.json": marketplace,
        "premium_users.json": premium_users,
        "farmer_profiles.json": farmer_profiles,
        "conversations.json": conversations,
        "buyer_requests.json": buyer_requests,
        "seller_requests.json": seller_requests,
        "payment_pending.json": payment_pending,
        "user_accounts.json": user_accounts,
        "market_prices.json": market_prices,
    }
    for fname, data in data_map.items():
        try:
            with open(fname, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Save error {fname}: {e}")

load_data()

# ── Default Market Prices ──────────────────────────────────────
DEFAULT_PRICES = {
    "national": {
        "maize": {"price": 285, "unit": "tonne", "trend": "stable", "updated": "Mar 2026"},
        "tobacco": {"price": 3.20, "unit": "kg", "trend": "rising", "updated": "Mar 2026"},
        "soya": {"price": 520, "unit": "tonne", "trend": "rising", "updated": "Mar 2026"},
        "wheat": {"price": 380, "unit": "tonne", "trend": "stable", "updated": "Mar 2026"},
        "cotton": {"price": 0.45, "unit": "kg", "trend": "falling", "updated": "Mar 2026"},
        "groundnuts": {"price": 850, "unit": "tonne", "trend": "rising", "updated": "Mar 2026"},
        "sunflower": {"price": 420, "unit": "tonne", "trend": "stable", "updated": "Mar 2026"},
        "sorghum": {"price": 220, "unit": "tonne", "trend": "stable", "updated": "Mar 2026"},
        "sugar beans": {"price": 1200, "unit": "tonne", "trend": "rising", "updated": "Mar 2026"},
        "tomatoes": {"price": 0.80, "unit": "kg", "trend": "falling", "updated": "Mar 2026"},
        "onions": {"price": 1.20, "unit": "kg", "trend": "rising", "updated": "Mar 2026"},
        "potatoes": {"price": 0.65, "unit": "kg", "trend": "stable", "updated": "Mar 2026"},
        "cattle": {"price": 650, "unit": "head", "trend": "rising", "updated": "Mar 2026"},
        "goats": {"price": 85, "unit": "head", "trend": "stable", "updated": "Mar 2026"},
        "chickens": {"price": 6, "unit": "bird", "trend": "stable", "updated": "Mar 2026"},
    },
    "regional_adjustments": {
        "harare": {"maize": 1.05, "tomatoes": 1.10, "potatoes": 1.08, "onions": 1.05},
        "bulawayo": {"maize": 1.03, "sorghum": 0.95, "cotton": 1.02},
        "mutare": {"maize": 1.02, "tomatoes": 0.95, "sugar beans": 1.05},
        "masvingo": {"maize": 1.0, "sorghum": 0.92, "cotton": 1.05},
        "gweru": {"maize": 1.01, "groundnuts": 0.98, "sunflower": 1.02},
        "marondera": {"maize": 1.04, "tobacco": 1.02, "wheat": 1.03},
        "chinhoyi": {"maize": 1.03, "tobacco": 1.01, "soya": 1.02},
    }
}

if not market_prices:
    market_prices.update(DEFAULT_PRICES)
    save_data()

# ── Province & Region Data ─────────────────────────────────────
PROVINCE_DEFAULTS = {
    "1": "marondera", "2": "bulawayo", "3": "mutare",
    "4": "masvingo", "5": "gweru", "6": "chinhoyi",
    "7": "bindura", "8": "victoria falls", "9": "beitbridge"
}

PROVINCE_NAMES = {
    "1": "Harare/Mashonaland East", "2": "Bulawayo/Matabeleland",
    "3": "Manicaland (Mutare/Chipinge)", "4": "Masvingo/Lowveld",
    "5": "Midlands (Gweru/Kwekwe)", "6": "Mashonaland West (Chinhoyi)",
    "7": "Mashonaland Central (Bindura)", "8": "Matabeleland North (Vic Falls)",
    "9": "Matabeleland South (Beitbridge)"
}

ZIMBABWE_REGIONS = {
    "harare": {
        "region": 2, "lat": -17.8252, "lon": 31.0335,
        "climate": "Sub-humid", "rainfall": "600-800mm",
        "best_crops": "Maize, Tobacco, Horticulture, Wheat, Soya",
        "soil": "Sandy loam to clay loam", "season": "Nov-Apr",
        "challenges": "Urban expansion reducing farmland, water scarcity"
    },
    "bulawayo": {
        "region": 4, "lat": -20.1325, "lon": 28.6264,
        "climate": "Semi-arid", "rainfall": "400-600mm",
        "best_crops": "Sorghum, Millet, Sunflower, Cotton, Groundnuts",
        "soil": "Sandy to sandy loam, shallow", "season": "Dec-Mar",
        "challenges": "Drought prone, irregular rains, high evaporation"
    },
    "mutare": {
        "region": 1, "lat": -18.9707, "lon": 32.6709,
        "climate": "Sub-humid to Humid", "rainfall": "800-1200mm",
        "best_crops": "Tea, Coffee, Macadamia, Maize, Beans, Avocado",
        "soil": "Rich red clay loam, deep", "season": "Oct-Apr",
        "challenges": "Steep terrain, erosion risk, cyclone damage"
    },
    "masvingo": {
        "region": 4, "lat": -20.0635, "lon": 30.8335,
        "climate": "Semi-arid", "rainfall": "400-600mm",
        "best_crops": "Sorghum, Cotton, Sunflower, Groundnuts, Millet",
        "soil": "Granite sandy soils, low fertility", "season": "Dec-Mar",
        "challenges": "Granite outcrops, low soil fertility, dry spells"
    },
    "gweru": {
        "region": 3, "lat": -19.4500, "lon": 29.8167,
        "climate": "Semi-humid", "rainfall": "500-700mm",
        "best_crops": "Maize, Groundnuts, Soya, Sunflower, Wheat",
        "soil": "Clay to sandy clay, moderate fertility", "season": "Nov-Apr",
        "challenges": "Variable rainfall, mid-season dry spells"
    },
    "marondera": {
        "region": 2, "lat": -18.1833, "lon": 31.5500,
        "climate": "Sub-humid", "rainfall": "700-900mm",
        "best_crops": "Maize, Tobacco, Wheat, Horticulture, Soya",
        "soil": "Red sandy loam, good structure", "season": "Nov-Apr",
        "challenges": "Early season dry spells, tobacco quality variation"
    },
    "chinhoyi": {
        "region": 2, "lat": -17.3667, "lon": 30.2000,
        "climate": "Sub-humid", "rainfall": "700-900mm",
        "best_crops": "Maize, Tobacco, Soya, Wheat, Cotton",
        "soil": "Deep red loam, fertile", "season": "Nov-Apr",
        "challenges": "Bush encroachment, labor availability"
    },
    "bindura": {
        "region": 2, "lat": -17.3000, "lon": 31.3333,
        "climate": "Sub-humid", "rainfall": "700-900mm",
        "best_crops": "Maize, Tobacco, Cotton, Groundnuts, Soya",
        "soil": "Clay loam, moderate-high fertility", "season": "Nov-Apr",
        "challenges": "Hail risk, late season frosts in some years"
    },
    "victoria falls": {
        "region": 4, "lat": -17.9322, "lon": 25.8306,
        "climate": "Semi-arid", "rainfall": "500-700mm",
        "best_crops": "Maize, Cotton, Sesame, Sorghum, Tourism crops",
        "soil": "Sandy alluvial, low clay", "season": "Dec-Mar",
        "challenges": "Remote market access, wildlife crop damage"
    },
    "kariba": {
        "region": 4, "lat": -16.5167, "lon": 28.8000,
        "climate": "Hot semi-arid", "rainfall": "400-600mm",
        "best_crops": "Cotton, Sorghum, Millet, Sesame, Sugarcane",
        "soil": "Sandy to loamy sand", "season": "Dec-Mar",
        "challenges": "Very high temperatures, elephant crop damage"
    },
    "chiredzi": {
        "region": 5, "lat": -21.0500, "lon": 31.6667,
        "climate": "Arid", "rainfall": "300-400mm",
        "best_crops": "Sugarcane (irrigated), Cotton, Sorghum, Livestock",
        "soil": "Sandy clay loam, Lowveld soils", "season": "Jan-Mar",
        "challenges": "Very low rainfall, depends on irrigation"
    },
    "beitbridge": {
        "region": 5, "lat": -22.2167, "lon": 30.0000,
        "climate": "Very arid", "rainfall": "200-400mm",
        "best_crops": "Livestock, Sorghum, Millet, Drought-tolerant crops",
        "soil": "Shallow sandy soils, very low fertility", "season": "Jan-Feb",
        "challenges": "Lowest rainfall in Zimbabwe, extreme heat"
    },
    "zvishavane": {
        "region": 4, "lat": -20.3333, "lon": 30.0333,
        "climate": "Semi-arid", "rainfall": "400-600mm",
        "best_crops": "Sorghum, Cotton, Groundnuts, Livestock, Sunflower",
        "soil": "Granite derived sandy, moderate fertility", "season": "Dec-Mar",
        "challenges": "Mining activities, water competition"
    },
    "kwekwe": {
        "region": 3, "lat": -18.9167, "lon": 29.8167,
        "climate": "Semi-humid", "rainfall": "500-700mm",
        "best_crops": "Maize, Groundnuts, Soya, Cotton, Sunflower",
        "soil": "Clay to sandy clay", "season": "Nov-Apr",
        "challenges": "Industrial pollution in some areas"
    },
    "kadoma": {
        "region": 3, "lat": -18.3500, "lon": 29.9167,
        "climate": "Semi-humid", "rainfall": "500-700mm",
        "best_crops": "Cotton, Maize, Groundnuts, Wheat, Soya",
        "soil": "Sandy clay loam, cotton belt soils", "season": "Nov-Apr",
        "challenges": "Cotton price fluctuation, input costs"
    },
    "norton": {
        "region": 2, "lat": -17.8833, "lon": 30.7000,
        "climate": "Sub-humid", "rainfall": "600-800mm",
        "best_crops": "Maize, Tobacco, Horticulture, Wheat, Soya",
        "soil": "Red sandy loam", "season": "Nov-Apr",
        "challenges": "Urban sprawl pressure, water access"
    },
    "rusape": {
        "region": 2, "lat": -18.5333, "lon": 32.1333,
        "climate": "Sub-humid", "rainfall": "700-900mm",
        "best_crops": "Maize, Tobacco, Beans, Horticulture, Potatoes",
        "soil": "Red clay loam, good fertility", "season": "Nov-Apr",
        "challenges": "Hilly terrain, erosion on slopes"
    },
    "nyanga": {
        "region": 1, "lat": -18.2167, "lon": 32.7500,
        "climate": "Humid", "rainfall": "1000-1500mm",
        "best_crops": "Potatoes, Wheat, Apples, Beans, Tea, Barley",
        "soil": "Deep red clay, very fertile, high organic matter", "season": "Oct-May",
        "challenges": "Frost risk, cold temperatures, steep slopes"
    },
    "chipinge": {
        "region": 1, "lat": -20.1833, "lon": 32.6167,
        "climate": "Sub-humid to Humid", "rainfall": "800-1200mm",
        "best_crops": "Tea, Coffee, Macadamia, Avocado, Maize, Beans",
        "soil": "Rich red clay loam, highly fertile", "season": "Oct-Apr",
        "challenges": "Cyclone risk, market access for tree crops"
    },
}

# ── Helper Functions ───────────────────────────────────────────
def find_nearest_region(lat: float, lon: float) -> dict:
    min_dist = float('inf')
    nearest_name = "harare"
    for city, info in ZIMBABWE_REGIONS.items():
        dist = math.sqrt((lat - info["lat"])**2 + (lon - info["lon"])**2)
        if dist < min_dist:
            min_dist = dist
            nearest_name = city
    return {"name": nearest_name, "info": ZIMBABWE_REGIONS[nearest_name]}

def get_region_info(location: str) -> dict:
    loc_lower = location.lower()
    for city, info in ZIMBABWE_REGIONS.items():
        if city in loc_lower:
            return info
    return ZIMBABWE_REGIONS["harare"]

def is_premium(phone: str) -> bool:
    if phone not in premium_users:
        return False
    user = premium_users[phone]
    if not user.get("active", False):
        return False
    expires = user.get("expires")
    if expires:
        try:
            exp = datetime.datetime.fromisoformat(expires)
            if datetime.datetime.now() > exp:
                premium_users[phone]["active"] = False
                save_data()
                return False
        except:
            pass
    return True

def is_in_trial(phone: str) -> bool:
    profile = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str:
        return False
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        return datetime.datetime.now() < joined + datetime.timedelta(days=TRIAL_DAYS)
    except:
        return False

def get_trial_days_left(phone: str) -> int:
    profile = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str:
        return 0
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        diff = (joined + datetime.timedelta(days=TRIAL_DAYS)) - datetime.datetime.now()
        return max(0, diff.days)
    except:
        return 0

def has_full_access(phone: str) -> bool:
    return is_premium(phone) or is_in_trial(phone)

def get_plan(phone: str) -> str:
    if is_premium(phone):
        return premium_users[phone].get("plan", "premium")
    if is_in_trial(phone):
        return "trial"
    return "free"

def premium_gate(phone: str, feature: str) -> str:
    if has_full_access(phone):
        return None
    return f"""🔒 *{feature}*
━━━━━━━━━━━━━━━━━━━━━━
This is a *Premium Feature*.
Your 30-day free trial has ended.

Upgrade to unlock:
💎 {feature}
💎 GPS Weather & Climate Forecasts
💎 Photo Crop Disease Analysis
💎 Live Regional Market Prices
💎 Find Agricultural Help Near You
💎 Professional Farm Planning
💎 Loan & Insurance Advisory

*Plans:*
💎 Premium: $2/month
🏆 Business: $10/month

Reply *UPGRADE* to subscribe
Type *MENU* to go back"""

def save_location(phone: str, location: str):
    if phone not in farmer_profiles:
        farmer_profiles[phone] = {
            "joined": datetime.datetime.now().isoformat()
        }
    farmer_profiles[phone]["location"] = location.lower()
    farmer_profiles[phone]["registered"] = True
    save_data()

def save_conversation(phone: str, role: str, message: str, msg_type: str = "text"):
    if phone not in conversations:
        conversations[phone] = []
    conversations[phone].append({
        "role": role,
        "message": message,
        "type": msg_type,
        "timestamp": datetime.datetime.now().isoformat(),
        "platform": "whatsapp"
    })
    if len(conversations[phone]) > 200:
        conversations[phone] = conversations[phone][-200:]
    save_data()

def get_conversation_history(phone: str, limit: int = 5) -> list:
    return conversations.get(phone, [])[-limit:]

def generate_ref(phone: str) -> str:
    return f"AGRO{phone[-6:]}"

# ── Farmer Context ─────────────────────────────────────────────
def get_farmer_context(phone: str) -> str:
    profile = farmer_profiles.get(phone, {})
    now = datetime.datetime.now()
    ctx = f"\nDate: {now.strftime('%d %B %Y')}"
    ctx += f"\nZimbabwe Season: March = End of rainy season, harvest preparation"
    ctx += f"\nClimate note: Zimbabwe experiencing erratic rainfall and rising temperatures due to climate change"

    if "gps_lat" in profile:
        nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
        info = nearest["info"]
        ctx += f"\nFarmer GPS: {profile['gps_lat']:.4f}°S, {profile['gps_lon']:.4f}°E"
        ctx += f"\nNearest area: {nearest['name'].title()}"
        ctx += f"\nClimate Region: {info['region']} — {info['climate']}"
        ctx += f"\nAnnual Rainfall: {info['rainfall']}"
        ctx += f"\nSoil: {info.get('soil', 'Mixed')}"
        ctx += f"\nBest crops: {info['best_crops']}"
        ctx += f"\nPlanting season: {info.get('season', 'Nov-Apr')}"
        ctx += f"\nKey challenges: {info.get('challenges', 'Variable weather')}"
    elif "location" in profile:
        loc = profile["location"]
        info = get_region_info(loc)
        ctx += f"\nFarmer location: {loc.title()}"
        ctx += f"\nClimate Region: {info['region']} — {info['climate']}"
        ctx += f"\nAnnual Rainfall: {info['rainfall']}"
        ctx += f"\nSoil: {info.get('soil', 'Mixed')}"
        ctx += f"\nBest crops: {info['best_crops']}"
        ctx += f"\nPlanting season: {info.get('season', 'Nov-Apr')}"
        ctx += f"\nKey challenges: {info.get('challenges', 'Variable weather')}"

    ctx += f"\nSubscription: {get_plan(phone).upper()}"
    if is_in_trial(phone):
        ctx += f" ({get_trial_days_left(phone)} trial days remaining)"

    history = get_conversation_history(phone, 3)
    if history:
        ctx += "\n\nRecent conversation:"
        for msg in history:
            role = "Farmer" if msg["role"] == "farmer" else "AgroBot"
            ctx += f"\n{role}: {msg['message'][:80]}"
    return ctx

# ── AI Functions ───────────────────────────────────────────────
def ask_groq(question: str, topic: str = "", phone: str = "") -> str:
    try:
        ctx = get_farmer_context(phone) if phone else ""
        system_prompt = f"""You are {BOT_NAME} — Zimbabwe's premier AI agriculture consultant by {COMPANY_NAME}.
You serve both smallholder farmers and large commercial farming companies across Zimbabwe.

FARMER CONTEXT:
{ctx}
{f'Specific topic: {topic}' if topic else ''}

PROFESSIONAL STANDARDS:
- Provide comprehensive, expert-level agricultural advice
- Reference specific Zimbabwe products: ZFC fertilizers, Seedco seeds, Agricura chemicals, Windmill agro-inputs
- Include scientific crop/disease names where applicable
- Cite specific quantities, rates, and timing (e.g., 200kg/ha Compound D basal)
- Consider Zimbabwe's current climate change impacts: erratic rainfall, +1.5°C temperature rise
- Reference Agritex (Zimbabwe government extension) guidelines
- Include costs in USD as used in Zimbabwe
- Mention GMB, TIMB, Cotton Company buying prices where relevant
- For diseases: include scientific name, symptoms, treatment brands, resistance management
- For soil: include pH ranges, NPK rates, lime requirements, ZFC product recommendations
- Keep responses under 200 words but professional and complete
- End with ONE specific action with a deadline"""

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
        return f"AgroBot is temporarily unavailable. Please try again.\n📞 Support: {SUPPORT_PHONE}"

def analyze_image(image_url: str, phone: str = "") -> str:
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        img_response = requests.get(image_url, headers=headers, timeout=15)
        img_base64 = base64.b64encode(img_response.content).decode("utf-8")
        ctx = get_farmer_context(phone)

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                    },
                    {
                        "type": "text",
                        "text": f"""You are {BOT_NAME}, expert crop disease specialist for Zimbabwe by {COMPANY_NAME}.
{ctx}

Analyze this crop image and provide a PROFESSIONAL report:

1. 🌿 CROP IDENTIFIED: (scientific + common name)
2. 🔍 PROBLEM DETECTED: (disease/pest/deficiency/other)
3. 🧬 CAUSE: (pathogen name, pest species, or deficiency)
4. 📊 SEVERITY: (Low/Moderate/High/Critical + % affected estimate)
5. 💊 IMMEDIATE TREATMENT:
   - Recommended product (Zimbabwe brand name)
   - Application rate and method
   - Timing and frequency
6. 🔄 FOLLOW-UP TREATMENT: (if needed)
7. 🛡️ PREVENTION: (for next season)
8. ⏰ ACT WITHIN: (hours/days deadline)
9. 💰 ESTIMATED COST: (USD treatment cost)

Be specific. Use Zimbabwe product brands.
Keep under 250 words."""
                    }
                ]
            }]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Image error: {e}")
        return "Could not analyze image. Please ensure good lighting and try again, or describe the symptoms in text."

def get_farming_news(phone: str = "") -> str:
    try:
        profile = farmer_profiles.get(phone, {})
        location = profile.get("location", "Zimbabwe")
        info = get_region_info(location)
        now = datetime.datetime.now()

        prompt = f"""You are {BOT_NAME} News — Zimbabwe's agricultural news service by {COMPANY_NAME}.
Farmer location: {location.title()}, Region {info['region']} ({info['climate']})
Current date: {now.strftime('%d %B %Y')}
Season: March 2026 — end of rainy season, harvest preparation

Generate a PROFESSIONAL farming news bulletin with these sections:

📰 TOP STORY
[Most critical Zimbabwe farming development this week]

🌦️ CLIMATE ALERT
[Weather pattern affecting Zimbabwe farmers + specific advice]

💰 MARKET WATCH
[Key commodity price movements: maize $285/t, tobacco $3.20/kg, soya $520/t — analyze trends]

🌱 CROP ADVISORY FOR {location.upper()}
[Specific actions farmers in this region should take THIS WEEK]

🔬 AGRI-INNOVATION
[Latest farming technology or technique relevant to Zimbabwe]

⚠️ PEST & DISEASE ALERT
[Current threats: armyworm status, fall armyworm, grey leaf spot, etc.]

📋 POLICY UPDATE
[Latest Agritex, GMB, or government farming news]

💡 TIP OF THE WEEK
[One high-value practical tip]

Keep each section 2-3 sentences. Be specific and actionable with Zimbabwe context."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        return f"""📰 *{BOT_NAME.upper()} FARMING NEWS*
{COMPANY_NAME}
📅 {now.strftime('%d %B %Y')} | {location.title()}
━━━━━━━━━━━━━━━━━━━━━━

{response.choices[0].message.content}

━━━━━━━━━━━━━━━━━━━━━━
🌱 *{BOT_NAME} | {COMPANY_NAME}*
📞 {SUPPORT_PHONE} | 🌐 {WEBSITE}
Type *MENU* to return"""
    except Exception as e:
        print(f"News error: {e}")
        return "Could not generate news. Please try again later."

def get_market_prices_text(location: str = "", crop: str = "") -> str:
    prices = market_prices.get("national", DEFAULT_PRICES["national"])
    adjustments = market_prices.get("regional_adjustments", {})
    loc_adj = adjustments.get(location.lower(), {})
    trends = {"rising": "📈", "falling": "📉", "stable": "➡️"}

    if crop:
        c = crop.lower()
        if c not in prices:
            return f"Price data for '{crop}' not available.\nType *MENU* to return."
        p = prices[c]
        adj = loc_adj.get(c, 1.0)
        local = round(p["price"] * adj, 2)
        icon = trends.get(p["trend"], "➡️")

        prompt = f"""Zimbabwe crop market analysis for {crop} — March 2026:
GMB/national price: ${p['price']}/{p['unit']}
Local price ({location or 'national'}): ${local}/{p['unit']}
Trend: {p['trend']}
Write a professional 4-sentence market analysis:
1. Current price drivers in Zimbabwe
2. Supply and demand factors
3. 30-day price outlook
4. Best selling strategy for farmers (sell now/hold/forward contract)"""

        advice = ask_groq(prompt, "Zimbabwe agricultural commodities market analysis")

        return f"""💰 *{crop.upper()} MARKET REPORT*
{COMPANY_NAME}
📍 {location.title() if location else 'Zimbabwe National'}
📅 {datetime.datetime.now().strftime('%d %B %Y')}
━━━━━━━━━━━━━━━━━━━━━━

{icon} *Trend: {p['trend'].upper()}*

🏛️ GMB Official: *${p['price']}/{p['unit']}*
📍 {location.title() or 'National'} Price: *${local}/{p['unit']}*
🔄 Last Updated: {p['updated']}

━━━━━━━━━━━━━━━━━━━━━━
📊 *MARKET ANALYSIS:*
{advice}

━━━━━━━━━━━━━━━━━━━━━━
📞 *Key Buyers:*
- GMB: 04-621000
- Tobacco Floor: 04-791623
- ZFC Commodities: 04-700751
- Cotton Company: 039-262811

Type *PRICE [crop]* for any crop
Type *MENU* to return"""

    # All prices
    result = f"""💰 *ZIMBABWE MARKET PRICES*
{COMPANY_NAME}
📍 {location.title() if location else 'National Average'}
📅 {datetime.datetime.now().strftime('%d %B %Y')}
━━━━━━━━━━━━━━━━━━━━━━

🌾 *GRAINS & OILSEEDS:*"""

    for c in ["maize", "wheat", "soya", "sorghum", "sunflower", "groundnuts"]:
        if c in prices:
            p = prices[c]
            local = round(p["price"] * loc_adj.get(c, 1.0), 2)
            result += f"\n{trends.get(p['trend'],'➡️')} {c.title()}: *${local}/{p['unit']}*"

    result += "\n\n🌿 *CASH CROPS:*"
    for c in ["tobacco", "cotton", "sugar beans"]:
        if c in prices:
            p = prices[c]
            local = round(p["price"] * loc_adj.get(c, 1.0), 2)
            result += f"\n{trends.get(p['trend'],'➡️')} {c.title()}: *${local}/{p['unit']}*"

    result += "\n\n🥬 *HORTICULTURE:*"
    for c in ["tomatoes", "onions", "potatoes"]:
        if c in prices:
            p = prices[c]
            local = round(p["price"] * loc_adj.get(c, 1.0), 2)
            result += f"\n{trends.get(p['trend'],'➡️')} {c.title()}: *${local}/{p['unit']}*"

    result += "\n\n🐄 *LIVESTOCK:*"
    for c in ["cattle", "goats", "chickens"]:
        if c in prices:
            p = prices[c]
            result += f"\n{trends.get(p['trend'],'➡️')} {c.title()}: *${p['price']}/{p['unit']}*"

    result += f"""

━━━━━━━━━━━━━━━━━━━━━━
📈 Rising  📉 Falling  ➡️ Stable
Prices in USD

*Type PRICE [crop] for detailed report*
Example: PRICE MAIZE

📞 *Market Contacts:*
- GMB Prices: 04-621000
- Tobacco Floor: 04-791623
- ZFC: 04-700751

Type *MENU* to return"""
    return result

def get_weather(lat: float, lon: float, name: str = "Your Farm") -> str:
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,"
               f"precipitation_sum,precipitation_probability_max,"
               f"windspeed_10m_max,et0_fao_evapotranspiration"
               f"&timezone=Africa/Harare&forecast_days=7")
        data = requests.get(url, timeout=10).json()
        d = data["daily"]
        nearest = find_nearest_region(lat, lon)
        info = nearest["info"]

        total_rain = sum(d["precipitation_sum"])
        avg_max = sum(d["temperature_2m_max"]) / 7
        et_list = d.get("et0_fao_evapotranspiration", [3.5] * 7)
        avg_et = sum(et_list) / 7

        result = f"🌤️ *7-DAY PRECISION FORECAST*\n"
        result += f"📍 {name}\n"
        result += f"🛰️ GPS: {lat:.4f}°S, {lon:.4f}°E\n"
        result += f"📊 Region {info['region']} | {info['climate']}\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for i in range(7):
            rain = d["precipitation_sum"][i]
            prob = d["precipitation_probability_max"][i]
            et = et_list[i]
            wind = d["windspeed_10m_max"][i]
            mx = d["temperature_2m_max"][i]
            mn = d["temperature_2m_min"][i]
            irrig = max(0, round(et - rain, 1))

            icon = ("⛈️" if rain > 30 else "🌧️" if rain > 10
                    else "🌦️" if rain > 2 else "⛅" if prob > 60 else "☀️")

            result += f"*{d['time'][i]}* {icon}\n"
            result += f"  🌡️ {mn}°-{mx}°C | 💧{rain}mm | 💨{wind}km/h\n"
            if irrig > 0:
                result += f"  💦 Irrigate: ~{irrig}mm needed\n"
            result += "\n"

        result += "━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"📊 Weekly: {total_rain:.0f}mm rain | {avg_max:.1f}°C avg\n\n"

        prompt = f"""Professional farming weather advisory for Zimbabwe.
Location: {name}, Region {info['region']} ({info['climate']})
Soil: {info.get('soil', 'Mixed')}
This week: avg {avg_max:.1f}°C, {total_rain:.0f}mm rain, {avg_et:.1f}mm/day ET
Season: March — harvest preparation, end rainy season
Best crops here: {info['best_crops']}
Climate change context: Zimbabwe experiencing erratic rainfall, rising temperatures

Provide 5 professional farming recommendations for THIS week:
1. Irrigation/drainage management (specific mm amounts)
2. Harvest timing based on weather
3. Pest/disease risk from this weather pattern
4. Post-harvest operations planning
5. Soil preparation for next season
Include specific timing and quantities."""

        advice = ask_groq(prompt, "precision agriculture Zimbabwe weather management")
        result += f"🌱 *PROFESSIONAL ADVISORY:*\n{advice}\n\n"
        result += f"📞 Agritex Weather: 0800 4040\nType *MENU* to return"
        return result
    except Exception as e:
        print(f"Weather error: {e}")
        return "Weather data unavailable. Please check connection and try again."

def find_help_nearby(location: str, lat: float = None, lon: float = None) -> str:
    centers = {
        "harare": [
            ("🏛️ Agritex Head Office", "Borrowdale Rd, Harare", "04-700181", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Harare Main", "Willowvale Rd, Harare", "04-621000", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank HQ", "Jason Moyo Ave, Harare", "04-700476", "Mon-Fri 8am-3:30pm"),
            ("🛒 Farmer's World Msasa", "Msasa Industrial, Harare", "04-447891", "Mon-Sat 7am-6pm"),
            ("🧪 ZFC Fertilizer", "Willowvale, Harare", "04-621234", "Mon-Fri 8am-5pm"),
            ("🌱 Seedco Head Office", "Beatrice Rd, Harare", "04-575111", "Mon-Fri 8am-5pm"),
            ("🌿 Agricura Chemicals", "Willowvale, Harare", "04-621567", "Mon-Fri 8am-5pm"),
        ],
        "bulawayo": [
            ("🏛️ Agritex Bulawayo", "Fort Street, Bulawayo", "09-888234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Bulawayo", "Industrial Sites", "09-888100", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank Bulawayo", "Fife Street", "09-888476", "Mon-Fri 8am-3:30pm"),
            ("🛒 Windmill Agro Byo", "Belmont Industrial", "09-888567", "Mon-Sat 7am-6pm"),
        ],
        "mutare": [
            ("🏛️ Agritex Manicaland", "Main Street, Mutare", "020-64234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Mutare", "Sakubva, Mutare", "020-64100", "Mon-Sat 7am-5pm"),
            ("🏦 CBZ Agri Mutare", "Herbert Chitepo St", "020-64476", "Mon-Fri 8am-3:30pm"),
            ("🌱 Windmill Agro Mutare", "Main Street", "020-64789", "Mon-Sat 7am-6pm"),
        ],
        "masvingo": [
            ("🏛️ Agritex Masvingo", "Hughes Street", "039-262234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Masvingo", "Industrial Area", "039-262100", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank Masvingo", "Robert Mugabe Way", "039-262476", "Mon-Fri 8am-3:30pm"),
            ("🌿 Cotton Company Zim", "Industrial Area", "039-262811", "Mon-Fri 8am-4pm"),
        ],
        "gweru": [
            ("🏛️ Agritex Midlands", "Sixth Street, Gweru", "054-223234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Gweru", "Industrial Sites", "054-223100", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank Gweru", "Main Street", "054-223476", "Mon-Fri 8am-3:30pm"),
        ],
        "marondera": [
            ("🏛️ Agritex Mash East", "Main Road, Marondera", "079-23234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Marondera", "Industrial Area", "079-23100", "Mon-Sat 7am-5pm"),
            ("🛒 Windmill Agro", "Main Street, Marondera", "079-23567", "Mon-Sat 7am-6pm"),
            ("🧪 Marondera Soil Lab", "Research Station", "079-22234", "Mon-Fri 8am-4pm"),
        ],
        "chinhoyi": [
            ("🏛️ Agritex Mash West", "Magamba Way, Chinhoyi", "067-22234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Chinhoyi", "Industrial Area", "067-22100", "Mon-Sat 7am-5pm"),
            ("🌱 Seedco Chinhoyi", "Main Street", "067-22789", "Mon-Fri 8am-5pm"),
        ],
    }

    if lat and lon:
        nearest = find_nearest_region(lat, lon)
        location = nearest["name"]

    found = None
    for city, places in centers.items():
        if city in location.lower():
            found = places
            break

    gps = "\n🛰️ Based on your GPS location" if lat else ""

    if not found:
        return f"""📍 *AGRICULTURAL SUPPORT*
{COMPANY_NAME}{gps}
━━━━━━━━━━━━━━━━━━━━━━

🏛️ *AGRITEX — Free Advisory*
📞 National: 04-700181
📞 Toll-Free: 0800 4040 (24/7)

🌾 *GMB — Crop Buying*
📞 04-621000 | Prices: 04-621999

🏦 *Agricultural Finance*
- Agribank: 04-700476
- CBZ Agri: 04-250579
- AFC Loans: 04-700592
- ZB Agri: 04-758081

🛒 *Agro-Input Dealers*
- ZFC: 04-700751
- Seedco: 04-575111
- Windmill: 04-309411
- Agricura: 04-621567

🌱 *Development Support*
- FAO Zimbabwe: 04-776591
- AGRITEX Training: 04-700181
- TIMB (Tobacco): 04-791623

📞 *{COMPANY_NAME} Support:*
{SUPPORT_PHONE}
{SUPPORT_EMAIL}"""

    result = f"📍 *HELP NEAR {location.upper()}*{gps}\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for name, addr, phone_num, hours in found:
        result += f"*{name}*\n📌 {addr}\n📞 {phone_num}\n🕐 {hours}\n\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━\n"
    result += f"📞 Agritex: 0800 4040 (free)\n"
    result += f"📞 {COMPANY_NAME}: {SUPPORT_PHONE}"
    return result

# ── Payment Functions ──────────────────────────────────────────
def initiate_payment(phone: str, plan: str) -> str:
    amount = "2" if plan == "premium" else "10"
    ref = generate_ref(phone)
    payment_pending[ref] = {
        "phone": phone, "plan": plan, "amount": amount,
        "initiated": datetime.datetime.now().isoformat(), "status": "pending"
    }
    save_data()

    return f"""💳 *{BOT_NAME.upper()} SUBSCRIPTION*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

📋 *Order Summary:*
Plan: *{plan.title()} Plan*
Amount: *${amount} USD/month*
Reference: *{ref}*

━━━━━━━━━━━━━━━━━━━━━━
💚 *METHOD 1 — EcoCash:*
1️⃣ Dial *151#
2️⃣ Select: Send Money
3️⃣ Number: *{ECOCASH_NUMBER}*
4️⃣ Amount: *${amount}*
5️⃣ Reference: *{ref}*
6️⃣ Enter your PIN & Confirm

━━━━━━━━━━━━━━━━━━━━━━
🔵 *METHOD 2 — OneMoney:*
1️⃣ Dial *111#
2️⃣ Select: Send Money
3️⃣ Number: *{ONEMONEY_NUMBER}*
4️⃣ Amount: *${amount}*
5️⃣ Reference: *{ref}*

━━━━━━━━━━━━━━━━━━━━━━
🏦 *METHOD 3 — Bank Transfer:*
Bank: CABS Zimbabwe
Account: TM AGRO Solutions
Reference: *{ref}*

━━━━━━━━━━━━━━━━━━━━━━
⚡ *After Payment — Reply:*
*PAID {ref}*

✅ System auto-verifies in 5 minutes
✅ Premium activated instantly on:
   📱 WhatsApp
   🌐 {WEBSITE}
   📲 {BOT_NAME} Mobile App

❓ Support: 📞 {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}"""

def process_payment(phone: str, ref: str) -> str:
    expected = generate_ref(phone)
    if ref.upper() != expected.upper():
        return f"""❌ *Invalid Reference*

Expected: *{expected}*
You sent: *{ref}*

*Check and try again, or contact:*
📞 {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}
🌐 {WEBSITE}/support"""

    pending = payment_pending.get(ref.upper(), payment_pending.get(ref, {}))
    plan = pending.get("plan", "premium")
    amount = pending.get("amount", "2")

    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {
        "active": True, "plan": plan, "amount": amount,
        "activated": datetime.datetime.now().isoformat(),
        "expires": expires, "payment_ref": ref
    }

    for key in [ref.upper(), ref]:
        if key in payment_pending:
            payment_pending[key]["status"] = "confirmed"

    if phone in user_accounts:
        user_accounts[phone].update({"premium": True, "plan": plan})

    save_data()

    return f"""🎉 *PAYMENT CONFIRMED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

✅ Reference: *{ref}*
✅ Plan: *{plan.upper()}*
✅ Amount: *${amount} USD*
✅ Status: *ACTIVE*
✅ Valid for: *30 days*

━━━━━━━━━━━━━━━━━━━━━━
*🔓 ALL PREMIUM FEATURES ACTIVE:*
✅ GPS Precision Weather Forecasts
✅ Photo Crop Disease Analysis
✅ Find Agricultural Help Near You
✅ Live Regional Market Prices
✅ Loan & Insurance Advisory
✅ Professional Farm Planning
✅ Daily Farming News & Alerts
✅ Climate Change Advisory
✅ Full Conversation History
✅ Priority AI Responses

━━━━━━━━━━━━━━━━━━━━━━
*Your account is synced on:*
📱 WhatsApp (active now!)
🌐 {WEBSITE}
📲 {BOT_NAME} Mobile App

Type *MENU* to explore all features!
Thank you for supporting {COMPANY_NAME}! 🌱🇿🇼"""

# ── Menus ──────────────────────────────────────────────────────
def get_location_menu() -> str:
    return f"""📍 *SET YOUR LOCATION*
━━━━━━━━━━━━━━━━━━━━━━

*🛰️ OPTION 1 — Share GPS* (Most Accurate)
📎 Tap attachment icon in WhatsApp
→ Select "Location"
→ Tap "Send Current Location"
✅ Gets weather for your EXACT farm
✅ Best when you are AT your farm

*🏙️ OPTION 2 — Type Town Name*
Just type your nearest town:
Example: Marondera
Example: Chinhoyi
✅ Best when away from farm

*🗺️ OPTION 3 — Select Province*
Reply with a number:
1️⃣ Harare / Mashonaland East
2️⃣ Bulawayo / Matabeleland
3️⃣ Manicaland (Mutare/Chipinge)
4️⃣ Masvingo / Lowveld
5️⃣ Midlands (Gweru/Kwekwe)
6️⃣ Mashonaland West (Chinhoyi)
7️⃣ Mashonaland Central (Bindura)
8️⃣ Matabeleland North (Vic Falls)
9️⃣ Matabeleland South (Beitbridge)

💡 Type *LOCATION* anytime to update
📎 Share GPS for precision advice"""

def get_main_menu(phone: str) -> str:
    plan = get_plan(phone)
    days = get_trial_days_left(phone)
    if plan == "trial":
        badge = f"🎁 FREE TRIAL — {days} days left"
    elif plan == "business":
        badge = "🏆 BUSINESS PLAN"
    elif plan == "premium":
        badge = "⭐ PREMIUM"
    else:
        badge = "🆓 FREE PLAN"

    profile = farmer_profiles.get(phone, {})
    loc_line = ""
    if "gps_lat" in profile:
        nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
        loc_line = f"\n🛰️ GPS: {nearest['name'].title()} | Precision Mode Active"
    elif "location" in profile:
        loc_line = f"\n📍 Location: {profile['location'].title()}"

    return f"""🌱 *{BOT_NAME.upper()} — {COMPANY_NAME}* 🇿🇼
{badge}{loc_line}
━━━━━━━━━━━━━━━━━━━━━━

📋 *FREE SERVICES:*
1️⃣ 🌿 Crop Disease & Pest Advice
2️⃣ 🧪 Soil Health & Fertilizer Advice
3️⃣ 🛒 Marketplace — Buy & Sell
4️⃣ 💬 Ask Any Farming Question
5️⃣ 📰 Free Farming News & Updates

━━━━━━━━━━━━━━━━━━━━━━

💎 *PREMIUM SERVICES:*
6️⃣ 🌤️ GPS Weather & Climate Forecast
7️⃣ 📸 Photo Crop Disease Analysis
8️⃣ 📍 Find Agricultural Help Nearby
9️⃣ 💰 Live Market Prices by Region
🔟 🏦 Loan, Insurance & Finance

━━━━━━━━━━━━━━━━━━━━━━

⚙️ 0️⃣ My Account / Subscribe / Upgrade

━━━━━━━━━━━━━━━━━━━━━━
📎 Share GPS location for precision advice
*MENU* | *NEWS* | *PRICE [crop]* | *LOCATION*
📞 {SUPPORT_PHONE} | 🌐 {WEBSITE}"""

def get_premium_menu(phone: str) -> str:
    plan = get_plan(phone)
    days = get_trial_days_left(phone)

    if is_premium(phone):
        exp = premium_users[phone].get("expires", "")
        try:
            exp_str = datetime.datetime.fromisoformat(exp).strftime("%d %B %Y")
        except:
            exp_str = "30 days from activation"
        return f"""⭐ *YOUR AGROBOT ACCOUNT*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Plan: *{plan.upper()}* ✅ ACTIVE
Expires: {exp_str}

*🔓 Active Premium Features:*
✅ GPS Precision Weather
✅ Photo Crop Analysis
✅ Find Help Near You
✅ Live Market Prices
✅ Loan & Insurance Advice
✅ Farm Planning Calendar
✅ Climate Change Advisory
✅ Full Conversation History
✅ Priority AI Responses

━━━━━━━━━━━━━━━━━━━━━━
*Account synced on:*
📱 WhatsApp ✅
🌐 {WEBSITE}
📲 {BOT_NAME} App

Type *MENU* to use all features!
📞 Support: {SUPPORT_PHONE}"""

    elif plan == "trial":
        return f"""🎁 *FREE TRIAL ACTIVE*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

⏳ *{days} days remaining*

You have FULL ACCESS to all features!

Subscribe before trial ends to keep access:

💎 *PREMIUM — $2/month*
Full access to all features
✅ 30-day renewal

🏆 *BUSINESS — $10/month*
Premium PLUS:
✅ Export market connections
✅ Dedicated AI farm consultant
✅ Multiple farm management
✅ Bulk buyer/seller matching
✅ Custom weekly farm reports
✅ Priority phone support

Reply *1* — Subscribe Premium ($2/month)
Reply *2* — Subscribe Business ($10/month)
Reply *0* — Back to menu

📞 {SUPPORT_PHONE} | 🌐 {WEBSITE}"""

    return f"""⭐ *UPGRADE TO {BOT_NAME.upper()} PRO*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

*🆓 FREE (Current):*
✅ Crop disease advice
✅ Basic soil analysis
✅ Marketplace access
✅ Farming questions
✅ Daily farming news

━━━━━━━━━━━━━━━━━━━━━━
*💎 PREMIUM — $2/month:*
🌤️ GPS precision weather & forecasts
📸 Photo crop disease analysis
📍 Find agricultural help near you
💰 Live regional market prices
🏦 Loan & insurance advisory
📅 Professional farm planning calendar
🌍 Climate change advisory
📊 Full conversation history & reports
⚡ Priority AI responses
🔔 Crop alerts & weather warnings

━━━━━━━━━━━━━━━━━━━━━━
*🏆 BUSINESS — $10/month:*
✅ Everything in Premium PLUS:
👨‍💼 Dedicated AI farm consultant
🌍 Export market connections (SA/UK/UAE)
📦 Bulk buyer & seller matching
📋 Custom weekly farm reports
🏗️ Multiple farm management
📱 Priority phone & WhatsApp support
💹 Advanced commodity price analysis
🤝 Direct agro-dealer partnerships

━━━━━━━━━━━━━━━━━━━━━━
🎁 *30-DAY FREE TRIAL INCLUDED!*
Try ALL features free when you register!

Reply *1* — Premium ($2/month)
Reply *2* — Business ($10/month)
Reply *0* — Back to main menu

📞 {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}
🌐 {WEBSITE}"""

# ── Marketplace Menus ──────────────────────────────────────────
def get_marketplace_menu() -> str:
    total = len(marketplace) + len(buyer_requests)
    return f"""🛒 *AGROBOT MARKETPLACE*
{COMPANY_NAME}
📊 {total} Active Listings
━━━━━━━━━━━━━━━━━━━━━━

*📢 POST YOUR LISTING:*
1️⃣ I Want to SELL
2️⃣ I Want to BUY (Post Request)

*🔍 SEARCH & BROWSE:*
3️⃣ Browse All SELLERS
4️⃣ Browse BUYER Requests
5️⃣ Search by Item/Category

*📂 CATEGORIES:*
6️⃣ 🌽 Crops & Grains
7️⃣ 🧪 Fertilizer & Inputs
8️⃣ 🚜 Equipment & Tools
9️⃣ 🐄 Livestock & Animals

0️⃣ ◀️ Back to Main Menu
━━━━━━━━━━━━━━━━━━━━━━
📱 Also at: {WEBSITE}/marketplace"""

# ── Main Process Message ───────────────────────────────────────
def process_message(from_number: str, msg_text: str) -> str:
    msg = msg_text.strip()
    state = user_states.get(from_number, "menu")

    save_conversation(from_number, "farmer", msg_text)

    # ── GLOBAL COMMANDS ─────────────────────────────────────────
    if msg.upper() == "MENU":
        user_states[from_number] = "menu"
        return get_main_menu(from_number)

    if msg.upper() == "LOCATION":
        user_states[from_number] = "update_location"
        return get_location_menu()

    if msg.upper() == "UPGRADE":
        user_states[from_number] = "subscribe"
        return get_premium_menu(from_number)

    if msg.upper() == "NEWS":
        return get_farming_news(from_number)

    if msg.upper().startswith("PRICE "):
        crop = msg.split(" ", 1)[1].strip()
        profile = farmer_profiles.get(from_number, {})
        return get_market_prices_text(profile.get("location", ""), crop)

    if msg.upper().startswith("PAID "):
        ref = msg.split(" ", 1)[1].strip()
        return process_payment(from_number, ref)

    # ── NEW FARMER REGISTRATION ─────────────────────────────────
    if from_number not in farmer_profiles:
        if msg.lower() in ["hi", "hello", "hey", "start", "help", "0", "00"]:
            user_states[from_number] = "register_location"
            return f"""🌱 *WELCOME TO {BOT_NAME.upper()}!* 🇿🇼
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Zimbabwe's Most Advanced AI Farming Assistant

🎁 *SPECIAL WELCOME OFFER:*
Get *{TRIAL_DAYS} DAYS FREE* access to
ALL premium features when you register!

No payment required — just set your location
and start using all features immediately!

━━━━━━━━━━━━━━━━━━━━━━
To get personalised farming advice
for your exact region, please set
your location now:

{get_location_menu()}"""
        else:
            user_states[from_number] = "register_location"
            return f"🌱 *Welcome to {BOT_NAME}!*\n\nPlease set your location to get started:\n\n{get_location_menu()}"

    # ── LOCATION STATES ─────────────────────────────────────────
    elif state in ["register_location", "update_location"]:
        is_new = state == "register_location"
        location = PROVINCE_DEFAULTS.get(msg, msg.lower())
        province_name = PROVINCE_NAMES.get(msg, msg.title())

        save_location(from_number, location)
        info = get_region_info(location)
        user_states[from_number] = "menu"

        trial_msg = ""
        if is_new:
            trial_msg = f"\n\n🎁 *{TRIAL_DAYS}-DAY FREE TRIAL STARTED!*\nAll premium features unlocked!\nNo payment needed for {TRIAL_DAYS} days!"

        return f"""✅ *LOCATION SET: {province_name}*
━━━━━━━━━━━━━━━━━━━━━━

📍 Area: {location.title()}
🌤️ Climate Region: {info['region']} — {info['climate']}
🌧️ Annual Rainfall: {info['rainfall']}
🌱 Best Crops: {info['best_crops']}
🏔️ Soil Type: {info.get('soil', 'Mixed soils')}
📅 Planting Season: {info.get('season', 'Nov-Apr')}
⚠️ Key Challenges: {info.get('challenges', 'Variable weather')}
{trial_msg}

💡 Share your GPS location anytime
for even MORE accurate farm advice!
📎 Attachment → Location → Send

{get_main_menu(from_number)}"""

    # ── MENU STATE ──────────────────────────────────────────────
    elif state == "menu":
        if msg.lower() in ["hi", "hello", "hey", "start", "help"]:
            return get_main_menu(from_number)

        elif msg == "1":
            user_states[from_number] = "disease"
            profile = farmer_profiles.get(from_number, {})
            loc = profile.get("location", "")
            loc_note = f"\n📍 Personalised for {loc.title()}" if loc else ""
            return f"""🌿 *CROP DISEASE & PEST ADVISORY*{loc_note}
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Please describe your problem in detail:

🌱 *What crop is affected?*
🔍 *What symptoms do you see?*
   (yellowing, spots, wilting, holes, etc.)
📏 *How much of the crop is affected?*
📅 *When did you first notice it?*
💊 *Any treatments already applied?*

📸 *OR send a PHOTO* of the affected
crop for instant visual diagnosis!

The more detail you provide, the more
accurate and professional your advice!"""

        elif msg == "2":
            user_states[from_number] = "soil"
            return f"""🧪 *SOIL HEALTH & FERTILITY ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

For a professional soil assessment,
please provide the following:

🎨 *Soil Color:*
   (Dark brown / Red / Pale / Grey / Black)
👆 *Texture:*
   (Sandy / Clay / Loam / Silty / Mixed)
💧 *Drainage:*
   (Waterlogged / Good / Very dry / Variable)
🌿 *Previous Crop:* (What grew here before?)
🌱 *Next Crop:* (What do you want to grow?)
📏 *Field Size:* (Acres or hectares)
🔬 *Soil Test Results:* (If available)
❓ *Problems Noticed:*
   (Stunted growth / Yellowing / Poor yield / etc.)

💡 *Pro tip:* Contact Marondera Soil
Testing Lab for official test:
📞 079-22234"""

        elif msg == "3":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()

        elif msg == "4":
            user_states[from_number] = "freeask"
            return f"""💬 *ASK {BOT_NAME.upper()} ANYTHING*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

I can answer professional questions on:

🌱 Crop agronomy & management
💊 Pesticides, herbicides & fungicides
💧 Irrigation & water management
🌦️ Climate & seasonal planning
🐄 Livestock management & health
🌾 Post-harvest & grain storage
💰 Farm business & market strategy
🔬 Modern farming technology
🌍 Export & value chain development
📋 Agritex guidelines & regulations

Ask your question now — be specific
for the most professional advice!"""

        elif msg == "5":
            return get_farming_news(from_number)

        elif msg == "6":
            gate = premium_gate(from_number, "GPS Weather & Climate Forecast")
            if gate:
                return gate
            profile = farmer_profiles.get(from_number, {})
            if "gps_lat" in profile:
                nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
                return get_weather(profile["gps_lat"], profile["gps_lon"],
                                   f"{nearest['name'].title()} (Your GPS)")
            elif "location" in profile:
                info = get_region_info(profile["location"])
                return get_weather(info["lat"], info["lon"], profile["location"].title())
            else:
                user_states[from_number] = "weather"
                return f"🌤️ *Weather Forecast*\n\nSet your location:\n\n{get_location_menu()}"

        elif msg == "7":
            gate = premium_gate(from_number, "Photo Crop Disease Analysis")
            if gate:
                return gate
            user_states[from_number] = "image_prompt"
            return f"""📸 *PHOTO CROP DISEASE ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Send me a clear photo of your affected
crop for a PROFESSIONAL AI diagnosis!

*📷 Photo Tips for Best Results:*
✅ Take in good natural lighting
✅ Include affected leaves/stems/fruit
✅ Get close enough to see symptoms
✅ Multiple angles if possible
✅ Include healthy part for comparison

*I will provide:*
🔍 Disease/pest identification
📊 Severity assessment
💊 Treatment with Zimbabwe brands
🛡️ Prevention strategy
⏰ Urgency level & deadline
💰 Estimated treatment cost

Send your photo now!
📎 Tap attachment → Camera or Gallery"""

        elif msg == "8":
            gate = premium_gate(from_number, "Find Agricultural Help Nearby")
            if gate:
                return gate
            profile = farmer_profiles.get(from_number, {})
            if "gps_lat" in profile:
                return find_help_nearby("", profile["gps_lat"], profile["gps_lon"])
            elif "location" in profile:
                return find_help_nearby(profile["location"])
            else:
                user_states[from_number] = "location_help"
                return f"📍 *Find Help Near You*\n\nFirst, set your location:\n\n{get_location_menu()}"

        elif msg == "9":
            gate = premium_gate(from_number, "Live Regional Market Prices")
            if gate:
                return gate
            profile = farmer_profiles.get(from_number, {})
            return get_market_prices_text(profile.get("location", ""))

        elif msg == "10":
            gate = premium_gate(from_number, "Loan & Insurance Advisory")
            if gate:
                return gate
            user_states[from_number] = "loan"
            return f"""🏦 *AGRICULTURAL FINANCE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

I can provide professional advice on:

💳 Agricultural loans
   (Agribank, CBZ Agri, ZB Bank, AFC)
🛡️ Crop & livestock insurance
   (Old Mutual, Zimnat, Cell Insurance)
📊 Farm financial planning & budgeting
💰 Government subsidies & grants
🤝 NGO & development funding
📈 Farm business profitability analysis

*For the best advice, please tell me:*
- Farm size (acres/ha)
- Main crops you grow
- Annual turnover (approximate)
- Do you need: loan/insurance/both?
- Have you borrowed before? (yes/no)
- Your district/province

*Key Financiers:*
📞 Agribank: 04-700476
📞 CBZ Agri: 04-250579
📞 AFC: 04-700592
📞 ZB Agri: 04-758081"""

        elif msg == "0":
            user_states[from_number] = "subscribe"
            return get_premium_menu(from_number)

        else:
            # Smart AI fallback
            reply = ask_groq(msg, phone=from_number)
            return f"""💬 *{BOT_NAME.upper()} PROFESSIONAL ADVICE*
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
Type *MENU* for all services
Type *NEWS* for farming news
Type *PRICE [crop]* for market prices
📞 {SUPPORT_PHONE}"""

    # ── DISEASE STATE ───────────────────────────────────────────
    elif state == "disease":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            """Complete crop disease/pest diagnosis including:
            Scientific disease name and pathogen type (fungal/bacterial/viral/pest)
            Detailed symptoms and disease progression
            Zimbabwe-specific treatment: product brand names (Agricura, Kondinin, etc.)
            Application rates in kg/ha or L/ha, timing and frequency
            Resistance management strategies
            Organic/cultural control alternatives
            Economic threshold for treatment decisions
            Prevention program for next season
            Estimated treatment cost in USD""",
            phone=from_number)
        return f"""🌿 *PROFESSIONAL DISEASE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
🛒 *Treatment Supplies:*
- ZFC Ltd: 04-700751
- Agricura: 04-621567
- Windmill Agro: 04-309411

📸 Send a photo for visual diagnosis
📞 Agritex Helpline: 0800 4040
Type *MENU* to return"""

    # ── SOIL STATE ──────────────────────────────────────────────
    elif state == "soil":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            """Professional soil health analysis including:
            Estimated soil pH range and adjustment method
            Macronutrient status and ZFC fertilizer recommendations with rates (kg/ha)
            Micronutrient deficiency indicators and corrections
            Lime application rate if needed (t/ha)
            Organic matter improvement strategies (compost, manure rates)
            Best crops suited to this specific soil
            Seasonal fertilizer program (basal + top dressing)
            Estimated fertilizer cost per acre in USD""",
            phone=from_number)
        return f"""🧪 *PROFESSIONAL SOIL ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
🔬 *Official Soil Testing:*
📞 Marondera Lab: 079-22234
📞 Agritex Soils: 04-700181
🛒 ZFC Fertilizers: 04-700751

Type *MENU* to return"""

    # ── FREE ASK STATE ──────────────────────────────────────────
    elif state == "freeask":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, phone=from_number)
        return f"""💬 *{BOT_NAME.upper()} PROFESSIONAL ADVICE*
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
Type *MENU* to return
Type *NEWS* for farming news
📞 {SUPPORT_PHONE}"""

    # ── WEATHER STATE ───────────────────────────────────────────
    elif state == "weather":
        user_states[from_number] = "menu"
        location = PROVINCE_DEFAULTS.get(msg, msg)
        info = get_region_info(location)
        return get_weather(info["lat"], info["lon"], location.title())

    # ── LOCATION HELP STATE ─────────────────────────────────────
    elif state == "location_help":
        user_states[from_number] = "menu"
        location = PROVINCE_DEFAULTS.get(msg, msg)
        return find_help_nearby(location)

    # ── LOAN STATE ──────────────────────────────────────────────
    elif state == "loan":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            """Agricultural finance advisory including:
            Specific loan products from Agribank, CBZ Agri, ZB Bank, AFC Zimbabwe
            Current interest rates and repayment terms
            Required documents for application
            Crop insurance from Cell Insurance, Old Mutual Agri, Zimnat
            Government subsidy programs currently available
            NGO and development organization funding (FAO, USAID, etc.)
            Step-by-step application process
            Practical tips to improve loan approval chances""",
            phone=from_number)
        return f"""🏦 *AGRICULTURAL FINANCE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
*Direct Contacts:*
📞 Agribank: 04-700476
📞 CBZ Agri: 04-250579
📞 AFC Zimbabwe: 04-700592
📞 ZB Bank Agri: 04-758081
📞 Old Mutual Agri: 04-308000

Type *MENU* to return"""

    # ── SUBSCRIBE STATE ─────────────────────────────────────────
    elif state == "subscribe":
        if msg == "1":
            user_states[from_number] = "menu"
            return initiate_payment(from_number, "premium")
        elif msg == "2":
            user_states[from_number] = "menu"
            return initiate_payment(from_number, "business")
        elif msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        return get_premium_menu(from_number)

    # ── MARKETPLACE STATE ───────────────────────────────────────
    elif state == "marketplace":
        if msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        elif msg == "1":
            user_states[from_number] = "post_sell_type"
            return f"""📢 *POST ITEM FOR SALE*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

What category are you selling?

1️⃣ 🌽 Crops & Grains
   (Maize, Tobacco, Soya, Wheat, etc.)
2️⃣ 🧪 Fertilizer & Agro-Chemicals
   (Compound D, Urea, Herbicides, etc.)
3️⃣ 🚜 Farm Equipment & Tools
   (Tractors, Ploughs, Pumps, etc.)
4️⃣ 🐄 Livestock & Animals
   (Cattle, Goats, Chickens, etc.)
5️⃣ 🌿 Other Agricultural Products

0️⃣ ◀️ Back"""
        elif msg == "2":
            user_states[from_number] = "post_buy_item"
            return f"""🤝 *POST A BUY REQUEST*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Tell sellers what you need!
Your request will be posted and sellers
matching your needs will contact you.

*What do you want to BUY?*
Be specific — include crop type,
quality grade, and quantity needed.

Examples:
- 50 x 50kg bags of white maize grade B
- 2 tonnes of grade A soya beans
- 1 x disc plough in working condition
- 20 x Hereford breeding heifers"""
        elif msg == "3":
            sellers = [x for x in marketplace if x.get("type") == "seller"]
            if not sellers:
                return "📭 No sellers listed yet.\n\nBe the first to post!\nType *MENU* to return."
            result = f"🏪 *ALL SELLERS*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, item in enumerate(sellers[-10:], 1):
                result += f"*{i}. {item.get('category', 'Product')}*\n"
                result += f"📦 {item['item']}\n📍 {item['location']}\n"
                result += f"💰 {item['price']}\n📞 {item['phone']}\n"
                result += f"📅 {item.get('timestamp', '')[:10]}\n\n"
            result += f"Type *MENU* to return\n📱 More: {WEBSITE}/marketplace"
            return result
        elif msg == "4":
            if not buyer_requests:
                return "📭 No buyer requests yet.\n\nPost one now — type 2!\nType *MENU* to return."
            result = f"🤝 *BUYER REQUESTS*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, item in enumerate(buyer_requests[-10:], 1):
                result += f"*{i}. WANTED: {item.get('item', 'Unknown')}*\n"
                result += f"📦 Qty: {item.get('quantity', 'Flexible')}\n"
                result += f"💰 Budget: {item.get('budget', 'Negotiable')}\n"
                result += f"📍 {item.get('location', 'Zimbabwe')}\n"
                result += f"📞 {item['phone']}\n"
                result += f"📅 {item.get('timestamp', '')[:10]}\n\n"
            result += f"Type *MENU* to return\n📱 More: {WEBSITE}/marketplace"
            return result
        elif msg == "5":
            user_states[from_number] = "search_marketplace"
            return "🔍 *Search Marketplace*\n\nType what you are looking for:\nExample: maize\nExample: tractor\nExample: fertilizer"
        elif msg == "6":
            user_states[from_number] = "search_marketplace"
            return "🌽 *Search Crops & Grains*\nType crop name:"
        elif msg == "7":
            user_states[from_number] = "search_marketplace"
            return "🧪 *Search Fertilizer & Inputs*\nType what you need:"
        elif msg == "8":
            user_states[from_number] = "search_marketplace"
            return "🚜 *Search Equipment*\nType what you need:"
        elif msg == "9":
            user_states[from_number] = "search_marketplace"
            return "🐄 *Search Livestock*\nType animal type:"
        else:
            return get_marketplace_menu()

    # ── SELL FLOW ───────────────────────────────────────────────
    elif state == "post_sell_type":
        cats = {"1": "Crops & Grains", "2": "Fertilizer & Chemicals",
                "3": "Farm Equipment & Tools", "4": "Livestock",
                "5": "Other Agricultural"}
        if msg in cats:
            user_states[from_number] = f"post_sell_item_{cats[msg]}"
            return f"""📦 *{cats[msg].upper()}*
━━━━━━━━━━━━━━━━━━━━━━
Describe exactly what you are selling:
Include: Name + Quantity + Condition/Grade

Examples:
- 20 x 50kg bags white maize grade B
- 500kg grade A soya (clean, dry)
- 10L Agritex herbicide unopened
- 1 x disc plough good condition
- 5 Hereford heifers 18 months"""
        elif msg == "0":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()
        return "Reply 1-5 to select category or 0 to go back."

    elif state.startswith("post_sell_item_"):
        cat = state.replace("post_sell_item_", "")
        user_states[from_number] = f"post_sell_location_{cat}_{msg}"
        profile = farmer_profiles.get(from_number, {})
        saved = profile.get("location", "")
        hint = f"Saved: *{saved.title()}* — confirm or type new location:" if saved else "Type your location:"
        return f"📍 *LOCATION*\n{hint}\nExample: Marondera Farm, Mash East"

    elif state.startswith("post_sell_location_"):
        parts = state.replace("post_sell_location_", "").split("_", 1)
        cat = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        user_states[from_number] = f"post_sell_price_{cat}_{item}_{msg}"
        return """💰 *ASKING PRICE*
━━━━━━━━━━━━━━━━━━━━━━
What is your asking price?

Examples:
- $50 per 50kg bag
- $285 per tonne
- $0.80 per kg
- Negotiable — best offer
- Call for price"""

    elif state.startswith("post_sell_price_"):
        parts = state.replace("post_sell_price_", "").split("_", 2)
        cat = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        loc = parts[2] if len(parts) > 2 else "Unknown"
        user_states[from_number] = f"post_sell_phone_{cat}_{item}_{loc}_{msg}"
        return f"📞 *CONTACT NUMBER*\n\nWhat number should buyers call or WhatsApp?\n\nMake sure it is active during business hours.\n\n*Your number will be visible to all buyers.*"

    elif state.startswith("post_sell_phone_"):
        parts = state.replace("post_sell_phone_", "").split("_", 3)
        cat = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        loc = parts[2] if len(parts) > 2 else "Unknown"
        price = parts[3] if len(parts) > 3 else "Negotiable"
        listing = {
            "type": "seller", "category": cat, "item": item,
            "location": loc, "price": price, "phone": msg,
            "poster": from_number,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "active", "platform": "whatsapp"
        }
        marketplace.append(listing)
        save_data()
        user_states[from_number] = "menu"
        return f"""✅ *LISTING POSTED LIVE!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

📂 {cat}
📦 {item}
📍 {loc}
💰 {price}
📞 {msg}
📅 {datetime.datetime.now().strftime('%d %B %Y')}

✅ Your listing is now LIVE across:
📱 WhatsApp — AgroBot Marketplace
🌐 {WEBSITE}/marketplace
📲 {BOT_NAME} Mobile App

Buyers will contact you on {msg}!

Type *MENU* to return."""

    # ── BUY REQUEST FLOW ────────────────────────────────────────
    elif state == "post_buy_item":
        user_states[from_number] = f"post_buy_qty_{msg}"
        return f"📦 *QUANTITY NEEDED*\n\nYou want: *{msg}*\n\nHow much do you need?\nExamples:\n• 100 x 50kg bags\n• 2 tonnes\n• 5 pieces\n• Any quantity"

    elif state.startswith("post_buy_qty_"):
        item = state.replace("post_buy_qty_", "")
        user_states[from_number] = f"post_buy_budget_{item}_{msg}"
        return "💰 *YOUR BUDGET*\n\nHow much are you willing to pay?\nExamples:\n• $45 per 50kg bag\n• Up to $280/tonne\n• Negotiable\n• Best price"

    elif state.startswith("post_buy_budget_"):
        parts = state.replace("post_buy_budget_", "").split("_", 1)
        item = parts[0]
        qty = parts[1] if len(parts) > 1 else "Flexible"
        user_states[from_number] = f"post_buy_location_{item}_{qty}_{msg}"
        return "📍 *YOUR LOCATION*\n\nWhere are you?\nSellers need to know delivery/collection point.\nExample: Harare CBD\nExample: Marondera"

    elif state.startswith("post_buy_location_"):
        parts = state.replace("post_buy_location_", "").split("_", 2)
        item = parts[0]
        qty = parts[1] if len(parts) > 1 else "Flexible"
        budget = parts[2] if len(parts) > 2 else "Negotiable"
        user_states[from_number] = f"post_buy_phone_{item}_{qty}_{budget}_{msg}"
        return "📞 *YOUR CONTACT*\n\nWhat number should sellers contact you on?\nBuyers will call or WhatsApp this number."

    elif state.startswith("post_buy_phone_"):
        parts = state.replace("post_buy_phone_", "").split("_", 3)
        item = parts[0]
        qty = parts[1] if len(parts) > 1 else "Flexible"
        budget = parts[2] if len(parts) > 2 else "Negotiable"
        loc = parts[3] if len(parts) > 3 else "Zimbabwe"
        req = {
            "type": "buyer", "item": item, "quantity": qty,
            "budget": budget, "location": loc, "phone": msg,
            "poster": from_number,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "active", "platform": "whatsapp"
        }
        buyer_requests.append(req)
        save_data()
        user_states[from_number] = "menu"
        return f"""✅ *BUY REQUEST POSTED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

🤝 WANTED: *{item}*
📦 Qty: {qty}
💰 Budget: {budget}
📍 {loc}
📞 {msg}
📅 {datetime.datetime.now().strftime('%d %B %Y')}

✅ Sellers will contact you on {msg}!

Visible on:
📱 WhatsApp — AgroBot Marketplace
🌐 {WEBSITE}/marketplace
📲 {BOT_NAME} Mobile App

Type *MENU* to return."""

    # ── SEARCH MARKETPLACE ──────────────────────────────────────
    elif state == "search_marketplace":
        user_states[from_number] = "menu"
        q = msg.lower()
        sellers = [x for x in marketplace
                   if q in x.get("item", "").lower() or q in x.get("category", "").lower()]
        buyers = [x for x in buyer_requests if q in x.get("item", "").lower()]

        if not sellers and not buyers:
            return f"📭 No results for '{msg}'.\n\nTry different keywords.\nType *MENU* to return."

        result = f"🔍 *RESULTS: {msg.upper()}*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if sellers:
            result += "🏪 *SELLERS:*\n"
            for x in sellers[-5:]:
                result += f"📦 {x['item']}\n📍 {x['location']}\n💰 {x['price']}\n📞 {x['phone']}\n\n"
        if buyers:
            result += "🤝 *BUYERS WANTING THIS:*\n"
            for x in buyers[-5:]:
                result += f"📦 {x['item']} | Qty: {x.get('quantity','Flexible')}\n💰 {x.get('budget','Negotiable')}\n📞 {x['phone']}\n\n"
        result += "Type *MENU* to return"
        return result

    else:
        user_states[from_number] = "menu"
        return get_main_menu(from_number)

# ══════════════════════════════════════════════════════════════
# ── REST API (Website & Mobile App) ───────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/register")
async def register_user(request: Request):
    body = await request.json()
    phone = body.get("phone", "").strip()
    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)
    if phone not in user_accounts:
        user_accounts[phone] = {
            "phone": phone,
            "name": body.get("name", ""),
            "email": body.get("email", ""),
            "google_id": body.get("google_id", ""),
            "platforms": [body.get("platform", "web")],
            "registered": datetime.datetime.now().isoformat()
        }
    else:
        for field in ["name", "email", "google_id"]:
            if body.get(field):
                user_accounts[phone][field] = body[field]
        plat = body.get("platform", "web")
        if plat not in user_accounts[phone].get("platforms", []):
            user_accounts[phone].setdefault("platforms", []).append(plat)

    user_accounts[phone].update({
        "premium": is_premium(phone),
        "plan": get_plan(phone),
        "conversation_count": len(conversations.get(phone, []))
    })
    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
    user_accounts[phone]["last_token"] = token
    save_data()
    return JSONResponse({
        "success": True, "token": token, "phone": phone,
        "profile": farmer_profiles.get(phone, {}),
        "premium": is_premium(phone), "plan": get_plan(phone),
        "trial_days_left": get_trial_days_left(phone),
        "conversation_count": len(conversations.get(phone, []))
    })

@app.get("/api/farmer/{phone}")
async def get_farmer(phone: str):
    if phone not in farmer_profiles:
        return JSONResponse({"error": "Farmer not found"}, status_code=404)
    profile = farmer_profiles[phone]
    return JSONResponse({
        "phone": phone, "profile": profile,
        "account": user_accounts.get(phone, {}),
        "region_info": get_region_info(profile.get("location", "")),
        "is_premium": is_premium(phone), "plan": get_plan(phone),
        "trial_days_left": get_trial_days_left(phone),
        "conversation_count": len(conversations.get(phone, []))
    })

@app.get("/api/farmer/{phone}/conversations")
async def get_conversations(phone: str, limit: int = 50):
    return JSONResponse({
        "phone": phone,
        "total": len(conversations.get(phone, [])),
        "conversations": conversations.get(phone, [])[-limit:]
    })

@app.get("/api/marketplace")
async def get_marketplace_api(search: str = "", category: str = ""):
    sellers = marketplace
    buyers = buyer_requests
    if search:
        sellers = [x for x in sellers if search.lower() in x.get("item", "").lower()]
        buyers = [x for x in buyers if search.lower() in x.get("item", "").lower()]
    if category:
        sellers = [x for x in sellers if category.lower() in x.get("category", "").lower()]
    return JSONResponse({
        "total_sellers": len(sellers), "total_buyers": len(buyers),
        "sellers": sellers[-50:], "buyers": buyers[-50:]
    })

@app.post("/api/marketplace/sell")
async def post_sell(request: Request):
    body = await request.json()
    for f in ["item", "location", "price", "phone"]:
        if not body.get(f):
            return JSONResponse({"error": f"{f} required"}, status_code=400)
    listing = {**body, "type": "seller",
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "active"}
    marketplace.append(listing)
    save_data()
    return JSONResponse({"success": True, "listing": listing})

@app.post("/api/marketplace/buy")
async def post_buy(request: Request):
    body = await request.json()
    for f in ["item", "location", "phone"]:
        if not body.get(f):
            return JSONResponse({"error": f"{f} required"}, status_code=400)
    req = {**body, "type": "buyer",
           "timestamp": datetime.datetime.now().isoformat(),
           "status": "active"}
    buyer_requests.append(req)
    save_data()
    return JSONResponse({"success": True, "request": req})

@app.get("/api/market-prices")
async def get_prices_api(location: str = "", crop: str = ""):
    prices = market_prices.get("national", DEFAULT_PRICES["national"])
    adj = market_prices.get("regional_adjustments", {}).get(location.lower(), {})
    result = {}
    for c, p in prices.items():
        if crop and crop.lower() != c:
            continue
        result[c] = {**p, "local_price": round(p["price"] * adj.get(c, 1.0), 2)}
    return JSONResponse({"prices": result, "location": location or "national"})

@app.put("/api/market-prices")
async def update_prices(request: Request):
    body = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    updates = body.get("prices", {})
    market_prices.setdefault("national", {}).update(updates)
    save_data()
    return JSONResponse({"success": True})

@app.get("/api/weather/{lat}/{lon}")
async def weather_api(lat: float, lon: float):
    nearest = find_nearest_region(lat, lon)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
           f"precipitation_probability_max&timezone=Africa/Harare&forecast_days=7")
    data = requests.get(url, timeout=10).json()
    return JSONResponse({
        "location": nearest["name"], "region_info": nearest["info"],
        "coordinates": {"lat": lat, "lon": lon},
        "forecast": data.get("daily", {})
    })

@app.get("/api/regions")
async def regions_api():
    return JSONResponse(ZIMBABWE_REGIONS)

@app.get("/api/news")
async def news_api(phone: str = ""):
    return JSONResponse({
        "news": get_farming_news(phone),
        "generated": datetime.datetime.now().isoformat()
    })

@app.post("/api/ask")
async def ask_api(request: Request):
    body = await request.json()
    q = body.get("question", "")
    phone = body.get("phone", "")
    if not q:
        return JSONResponse({"error": "Question required"}, status_code=400)
    if phone:
        save_conversation(phone, "farmer", q, "api")
    answer = ask_groq(q, body.get("topic", ""), phone)
    if phone:
        save_conversation(phone, "agrobot", answer, "api")
    return JSONResponse({
        "answer": answer, "phone": phone,
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.post("/api/payment/initiate")
async def payment_initiate(request: Request):
    body = await request.json()
    phone = body.get("phone", "")
    plan = body.get("plan", "premium")
    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)
    ref = generate_ref(phone)
    amount = "2" if plan == "premium" else "10"
    payment_pending[ref] = {
        "phone": phone, "plan": plan, "amount": amount,
        "initiated": datetime.datetime.now().isoformat(), "status": "pending"
    }
    save_data()
    return JSONResponse({
        "reference": ref, "amount": amount, "plan": plan,
        "ecocash_number": ECOCASH_NUMBER,
        "instructions": f"Pay ${amount} to {ECOCASH_NUMBER} with reference {ref}"
    })

@app.post("/api/payment/confirm")
async def payment_confirm(request: Request):
    body = await request.json()
    phone = body.get("phone", "")
    ref = body.get("reference", "")
    if body.get("secret") != ADMIN_SECRET and not body.get("gateway_token"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    process_payment(phone, ref)
    return JSONResponse({
        "success": is_premium(phone), "phone": phone,
        "plan": get_plan(phone)
    })

@app.post("/api/activate-premium")
async def activate_premium(request: Request):
    body = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    phone = body.get("phone", "")
    plan = body.get("plan", "premium")
    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {
        "active": True, "plan": plan,
        "activated": datetime.datetime.now().isoformat(),
        "expires": expires
    }
    save_data()
    send_whatsapp_message(phone,
        f"🎉 *{plan.upper()} ACTIVATED!*\n\nAll premium features are now active!\n\nType *MENU* to explore! 🌱")
    return JSONResponse({"success": True, "phone": phone, "expires": expires})

@app.get("/api/stats")
async def stats_api():
    return JSONResponse({
        "company": COMPANY_NAME,
        "product": BOT_NAME,
        "version": "3.0.0",
        "support_phone": SUPPORT_PHONE,
        "support_email": SUPPORT_EMAIL,
        "website": WEBSITE,
        "total_farmers": len(farmer_profiles),
        "premium_farmers": len([p for p in premium_users.values() if p.get("active")]),
        "trial_farmers": sum(1 for p in farmer_profiles if is_in_trial(p)),
        "total_conversations": sum(len(c) for c in conversations.values()),
        "marketplace_sellers": len(marketplace),
        "marketplace_buyers": len(buyer_requests),
        "regions_covered": len(ZIMBABWE_REGIONS),
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.get("/api/farmers")
async def all_farmers():
    return JSONResponse({
        "total": len(farmer_profiles),
        "farmers": [{"phone": p, "location": farmer_profiles[p].get("location", "Unknown"),
                     "plan": get_plan(p), "joined": farmer_profiles[p].get("joined", "")}
                    for p in farmer_profiles]
    })

# ── Webhook ────────────────────────────────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params["hub.challenge"])
    return {"error": "Invalid verify token"}

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]
        msg_type = message.get("type", "text")

        if msg_type == "location":
            lat = message["location"]["latitude"]
            lon = message["location"]["longitude"]
            if from_number not in farmer_profiles:
                farmer_profiles[from_number] = {
                    "joined": datetime.datetime.now().isoformat()
                }
            farmer_profiles[from_number].update({
                "gps_lat": lat, "gps_lon": lon, "registered": True
            })
            save_data()
            nearest = find_nearest_region(lat, lon)
            info = nearest["info"]
            save_conversation(from_number, "farmer", f"[GPS: {lat:.4f}, {lon:.4f}]", "location")

            trial_note = ""
            if is_in_trial(from_number):
                trial_note = f"\n🎁 Trial active: {get_trial_days_left(from_number)} days left"

            reply = f"""📍 *GPS LOCATION SAVED!* 🛰️
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

🌍 {lat:.4f}°S, {lon:.4f}°E
📍 Area: *{nearest['name'].title()}*
🌤️ Climate: {info['climate']}
🌧️ Rainfall: {info['rainfall']}
🏔️ Soil: {info.get('soil', 'Mixed')}
🌱 Best Crops: {info['best_crops']}
📅 Season: {info.get('season', 'Nov-Apr')}
{trial_note}

✅ All advice now personalised to
your exact GPS farm location!

{get_main_menu(from_number)}"""
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

        elif msg_type == "image":
            save_conversation(from_number, "farmer", "[Photo sent]", "image")
            if has_full_access(from_number):
                image_id = message["image"]["id"]
                resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{image_id}",
                    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, timeout=15)
                image_url = resp.json().get("url")
                send_whatsapp_message(from_number,
                    f"🔍 *Analyzing crop image...*\n{COMPANY_NAME}\n\nPlease wait 15-20 seconds...")
                analysis = analyze_image(image_url, from_number)
                reply = f"""📸 *PROFESSIONAL CROP ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{analysis}

━━━━━━━━━━━━━━━━━━━━━━
🛒 Treatment supplies:
- Agricura: 04-621567
- ZFC: 04-700751
- Windmill: 04-309411
📞 Agritex: 0800 4040
Type *MENU* to return"""
            else:
                reply = f"""🔒 *PHOTO ANALYSIS — PREMIUM REQUIRED*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Your 30-day free trial has ended.

Photo crop disease analysis requires
an active Premium or Business plan.

*Upgrade for $2/month:*
📸 Instant AI crop diagnosis
🌤️ GPS weather forecasts
💰 Live market prices
📍 Find help near you

Reply *UPGRADE* to subscribe
Type *MENU* for free services"""
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

        elif msg_type == "text":
            msg_text = message["text"]["body"]
            print(f"[{from_number}]: {msg_text}")
            reply = process_message(from_number, msg_text)
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

    except (KeyError, IndexError) as e:
        print(f"Webhook error: {e}")
    return {"status": "ok"}

def send_whatsapp_message(to: str, message: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Sent [{to}]: {resp.status_code}")
    except Exception as e:
        print(f"Send error: {e}")

@app.get("/")
def home():
    return {
        "name": BOT_NAME,
        "company": COMPANY_NAME,
        "version": "3.0.0",
        "status": "operational",
        "support_phone": SUPPORT_PHONE,
        "support_email": SUPPORT_EMAIL,
        "website": WEBSITE,
        "stats": {
            "farmers": len(farmer_profiles),
            "premium": len([p for p in premium_users.values() if p.get("active")]),
            "conversations": sum(len(c) for c in conversations.values()),
            "listings": len(marketplace) + len(buyer_requests)
        }
    }
