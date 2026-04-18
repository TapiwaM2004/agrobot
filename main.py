from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import httpx
import os
import threading
import time
import json
import base64
import math
import datetime
import hashlib
import secrets
import asyncio
from dotenv import load_dotenv
from groq import Groq
from typing import Dict, List

load_dotenv()

app = FastAPI(
    title="AgroBot Pro API",
    description="TM AGRO Solutions — Zimbabwe Smart Farming Assistant",
    version="4.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
ACCESS_TOKEN      = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID   = os.getenv("PHONE_NUMBER_ID", "951059444767602")
VERIFY_TOKEN      = os.getenv("VERIFY_TOKEN", "agrobot123")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
GNEWS_API_KEY     = os.getenv("GNEWS_API_KEY", "86b26ba02bf77b0ca9826d4e95ba089e")
ADMIN_SECRET      = os.getenv("ADMIN_SECRET", "AGROBOT_ADMIN_2026")
ECOCASH_NUMBER    = "0787 341 018"
ONEMONEY_NUMBER   = "0787 341 018"
SUPPORT_PHONE     = "0787 341 018"
SUPPORT_EMAIL     = "manhambaratapiwa548@gmail.com"
COMPANY_NAME      = "TM AGRO Solutions"
BOT_NAME          = "AgroBot Pro"
WEBSITE           = "agrobot.co.zw"
TRIAL_DAYS        = 30

client = Groq(api_key=GROQ_API_KEY)

# ── WebSocket Connection Manager ───────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_info: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, channel: str, phone: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        profile = farmer_profiles.get(phone, {})
        self.user_info[websocket] = {
            "phone":    phone,
            "name":     profile.get("name", f"Farmer {phone[-4:]}"),
            "location": profile.get("location", "Zimbabwe").title(),
            "channel":  channel,
        }

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
        if websocket in self.user_info:
            del self.user_info[websocket]

    async def broadcast_to_channel(self, channel: str, message: dict):
        if channel in self.active_connections:
            disconnected = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.active_connections[channel].remove(conn)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    def get_channel_members(self, channel: str) -> list:
        members = []
        if channel in self.active_connections:
            for ws in self.active_connections[channel]:
                info = self.user_info.get(ws, {})
                if info:
                    members.append({
                        "name":     info.get("name"),
                        "location": info.get("location"),
                    })
        return members

manager = ConnectionManager()

# ── Data Storage ───────────────────────────────────────────────
user_states      = {}
marketplace      = []
premium_users    = {}
farmer_profiles  = {}
conversations    = {}
buyer_requests   = []
payment_pending  = {}
user_accounts    = {}
market_prices    = {}
community_posts  = []
support_tickets  = {}
notifications    = []
admin_updates    = []
payment_checks   = {}

community_channels = {
    "general":     {"name": "🌍 General Farming",  "description": "All farming topics",       "messages": []},
    "maize":       {"name": "🌽 Maize Farmers",     "description": "Maize growing community",  "messages": []},
    "tobacco":     {"name": "🍂 Tobacco Growers",   "description": "Tobacco farming",          "messages": []},
    "livestock":   {"name": "🐄 Livestock Farmers", "description": "Cattle, goats, poultry",   "messages": []},
    "horticulture":{"name": "🥬 Horticulture",      "description": "Vegetables & fruits",      "messages": []},
    "weather":     {"name": "🌧️ Weather Reports",  "description": "Local weather sharing",    "messages": []},
    "prices":      {"name": "💰 Market Prices",     "description": "Price discussions",        "messages": []},
}

user_activity      = {}
live_price_cache   = {"data": {}, "last_updated": None}


def load_data():
    global marketplace, premium_users, farmer_profiles, conversations
    global buyer_requests, payment_pending, user_accounts, market_prices
    global community_posts, community_channels, user_activity, live_price_cache

    file_defaults = {
        "marketplace.json":      (marketplace,       []),
        "premium_users.json":    (premium_users,     {}),
        "farmer_profiles.json":  (farmer_profiles,   {}),
        "conversations.json":    (conversations,     {}),
        "buyer_requests.json":   (buyer_requests,    []),
        "payment_pending.json":  (payment_pending,   {}),
        "user_accounts.json":    (user_accounts,     {}),
        "market_prices.json":    (market_prices,     {}),
        "community_posts.json":  (community_posts,   []),
        "community_channels.json":(community_channels,{}),
        "user_activity.json":    (user_activity,     {}),
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
        except Exception:
            pass

    for fname, target in [
        ("support_tickets.json", support_tickets),
        ("admin_updates.json",   admin_updates),
    ]:
        try:
            with open(fname, "r") as f:
                data = json.load(f)
                if isinstance(target, list):
                    target.extend(data)
                else:
                    target.update(data)
        except Exception:
            pass

    try:
        with open("notifications.json", "r") as f:
            notifications.extend(json.load(f))
    except Exception:
        pass


def save_data():
    data_map = {
        "marketplace.json":       marketplace,
        "premium_users.json":     premium_users,
        "farmer_profiles.json":   farmer_profiles,
        "conversations.json":     conversations,
        "buyer_requests.json":    buyer_requests,
        "payment_pending.json":   payment_pending,
        "user_accounts.json":     user_accounts,
        "market_prices.json":     market_prices,
        "community_posts.json":   community_posts,
        "community_channels.json":community_channels,
        "user_activity.json":     user_activity,
    }
    for fname, data in data_map.items():
        try:
            with open(fname, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Save error {fname}: {e}")

    for fname, data in [
        ("support_tickets.json", support_tickets),
        ("notifications.json",   notifications),
        ("admin_updates.json",   admin_updates),
    ]:
        try:
            with open(fname, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Save error {fname}: {e}")


load_data()

# ══════════════════════════════════════════════════════════════
# ── LIVE MARKET PRICES ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

ZIMBABWE_PRICE_FACTORS = {
    "maize":      {"factor": 1.15, "unit": "tonne", "local_name": "Maize (White)"},
    "wheat":      {"factor": 1.20, "unit": "tonne", "local_name": "Wheat"},
    "soya":       {"factor": 1.10, "unit": "tonne", "local_name": "Soya Beans"},
    "cotton":     {"factor": 1.05, "unit": "kg",    "local_name": "Cotton (Seed)"},
    "groundnuts": {"factor": 1.25, "unit": "tonne", "local_name": "Groundnuts"},
    "sunflower":  {"factor": 1.15, "unit": "tonne", "local_name": "Sunflower"},
    "sorghum":    {"factor": 1.10, "unit": "tonne", "local_name": "Sorghum"},
    "tobacco":    {"factor": 1.0,  "unit": "kg",    "local_name": "Flue-cured Tobacco"},
    "sugar":      {"factor": 1.05, "unit": "tonne", "local_name": "Sugarcane"},
}

REGIONAL_PRICE_ADJ = {
    "harare":    {"maize": 1.05, "tomatoes": 1.10, "potatoes": 1.08},
    "bulawayo":  {"maize": 1.03, "sorghum": 0.95,  "cotton": 1.02},
    "mutare":    {"maize": 1.02, "tomatoes": 0.95},
    "masvingo":  {"maize": 1.0,  "sorghum": 0.92,  "cotton": 1.05},
    "gweru":     {"maize": 1.01, "groundnuts": 0.98},
    "marondera": {"maize": 1.04, "tobacco": 1.02,  "wheat": 1.03},
    "chinhoyi":  {"maize": 1.03, "tobacco": 1.01,  "soya": 1.02},
}


async def fetch_world_bank_prices() -> dict:
    """
    Fetch real commodity benchmark prices from World Bank Pink Sheet API.
    Maps global commodity codes to Zimbabwe crops.
    Returns dict of {crop: usd_per_tonne} or empty if unavailable.
    """
    # World Bank Pink Sheet indicator codes → our crop names
    WB_INDICATORS = {
        "PMAIZMMT": "maize",       # Maize $/mt
        "PSOYB":    "soya",        # Soybean $/mt
        "PWHEAMT":  "wheat",       # Wheat $/mt
        "PCOTTIND": "cotton_lint", # Cotton index $/kg
        "PSUGAISA": "sugar",       # Sugar $/kg
        "PGNUTS":   "groundnuts",  # Groundnuts $/mt
        "PSUNFL":   "sunflower",   # Sunflower oil $/mt
    }
    wb_prices = {}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            for indicator, crop in WB_INDICATORS.items():
                try:
                    r = await http.get(
                        f"https://api.worldbank.org/v2/en/indicator/{indicator}",
                        params={"format": "json", "mrv": "1", "frequency": "M"},
                    )
                    data = r.json()
                    # World Bank returns [metadata, [records]]
                    if isinstance(data, list) and len(data) > 1:
                        records = data[1]
                        if records and records[0].get("value"):
                            wb_prices[crop] = float(records[0]["value"])
                except Exception:
                    pass
    except Exception as e:
        print(f"World Bank fetch error: {e}")
    return wb_prices


async def fetch_live_commodity_prices() -> dict:
    """
    LIVE prices pipeline:
    1. World Bank Pink Sheet API  → real global benchmark prices (free, no key)
    2. Groq AI                    → converts globals to Zimbabwe local prices,
                                    adds crops WB doesn't cover (tobacco, livestock),
                                    adds GMB/private buyer split, trends
    3. Cache for 6 hours
    """
    now   = datetime.datetime.now()
    cache = live_price_cache

    # Return cache if fresh (< 6 hours)
    if cache["last_updated"]:
        try:
            last = datetime.datetime.fromisoformat(cache["last_updated"])
            if (now - last).total_seconds() < 21600 and cache["data"]:
                return cache["data"]
        except Exception:
            pass

    prices = {}

    # ── Step 1: Fetch World Bank benchmark prices ──────────────
    wb_prices = await fetch_world_bank_prices()
    wb_context = ""
    if wb_prices:
        wb_lines = "\n".join([f"  {crop}: ${val}/tonne" for crop, val in wb_prices.items()])
        wb_context = f"""
WORLD BANK LIVE BENCHMARK PRICES (fetched right now):
{wb_lines}

Use these as the base for global-linked crops.
Zimbabwe prices are typically World Bank price × 1.1-1.3 (transport + local premium).
"""
        print(f"World Bank prices fetched: {list(wb_prices.keys())}")

    # ── Step 2: Groq enriches to full Zimbabwe price set ───────
    try:
        price_prompt = f"""You are a Zimbabwe agricultural commodity price analyst.
Today is {now.strftime('%d %B %Y, %A')}.
{wb_context}

Based on the World Bank benchmarks above AND your knowledge of Zimbabwe's
current agricultural market (GMB gazette prices, tobacco floor prices,
ZFC commodity prices, Mbare Musika wholesale prices), provide CURRENT
Zimbabwe market prices.

Return ONLY a valid JSON object, no other text:
{{
  "maize":       {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "tobacco":     {{"price": <number>, "unit": "kg",    "trend": "<rising|stable|falling>", "floor": <number>}},
  "soya":        {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "wheat":       {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "cotton":      {{"price": <number>, "unit": "kg",    "trend": "<rising|stable|falling>", "ccc": <number>, "private": <number>}},
  "groundnuts":  {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "sunflower":   {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "sorghum":     {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "sugar_beans": {{"price": <number>, "unit": "tonne", "trend": "<rising|stable|falling>", "gmb": <number>, "private": <number>}},
  "tomatoes":    {{"price": <number>, "unit": "kg",    "trend": "<rising|stable|falling>", "wholesale": <number>, "retail": <number>}},
  "onions":      {{"price": <number>, "unit": "kg",    "trend": "<rising|stable|falling>", "wholesale": <number>, "retail": <number>}},
  "potatoes":    {{"price": <number>, "unit": "kg",    "trend": "<rising|stable|falling>", "wholesale": <number>, "retail": <number>}},
  "cattle":      {{"price": <number>, "unit": "head",  "trend": "<rising|stable|falling>", "auction": <number>, "private": <number>}},
  "goats":       {{"price": <number>, "unit": "head",  "trend": "<rising|stable|falling>", "auction": <number>, "private": <number>}},
  "chickens":    {{"price": <number>, "unit": "bird",  "trend": "<rising|stable|falling>", "wholesale": <number>, "retail": <number>}}
}}

All prices in USD. Use realistic current Zimbabwe market prices for {now.strftime('%B %Y')}."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": price_prompt}],
            max_tokens=900,
        )
        raw = response.choices[0].message.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        prices = json.loads(raw)

        # Tag each price with source info
        source_label = "World Bank + Zimbabwe Market" if wb_prices else "Zimbabwe Market AI"
        for crop in prices:
            prices[crop]["updated"] = now.strftime("%d %b %Y %H:%M")
            prices[crop]["source"]  = source_label

        live_price_cache["data"]         = prices
        live_price_cache["last_updated"] = now.isoformat()
        print(f"✅ Live prices updated at {now.strftime('%H:%M')} | WB data: {bool(wb_prices)}")

    except Exception as e:
        print(f"Price fetch error: {e}")
        # Use last cached if available
        if cache["data"]:
            return cache["data"]
        # Absolute last resort — trigger a fresh Groq-only call with no WB data
        try:
            fallback_prompt = f"""Zimbabwe agricultural prices {now.strftime('%B %Y')}.
Return ONLY JSON with current USD prices:
{{"maize":{{"price":280,"unit":"tonne","trend":"stable","gmb":265,"private":290,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"tobacco":{{"price":3.10,"unit":"kg","trend":"stable","floor":3.05,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"soya":{{"price":510,"unit":"tonne","trend":"stable","gmb":495,"private":520,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"wheat":{{"price":375,"unit":"tonne","trend":"stable","gmb":365,"private":380,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"cotton":{{"price":0.44,"unit":"kg","trend":"stable","ccc":0.43,"private":0.45,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"groundnuts":{{"price":840,"unit":"tonne","trend":"stable","gmb":810,"private":860,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"sunflower":{{"price":415,"unit":"tonne","trend":"stable","gmb":405,"private":420,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"sorghum":{{"price":215,"unit":"tonne","trend":"stable","gmb":205,"private":220,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"sugar_beans":{{"price":1180,"unit":"tonne","trend":"stable","gmb":1140,"private":1210,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"tomatoes":{{"price":0.75,"unit":"kg","trend":"stable","wholesale":0.60,"retail":0.85,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"onions":{{"price":1.15,"unit":"kg","trend":"stable","wholesale":0.95,"retail":1.30,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"potatoes":{{"price":0.62,"unit":"kg","trend":"stable","wholesale":0.52,"retail":0.72,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"cattle":{{"price":640,"unit":"head","trend":"stable","auction":615,"private":665,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"goats":{{"price":82,"unit":"head","trend":"stable","auction":78,"private":88,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}},
"chickens":{{"price":5.80,"unit":"bird","trend":"stable","wholesale":5.20,"retail":6.30,"updated":"{now.strftime('%d %b %Y')}","source":"AI Estimate"}}}}"""
            r2 = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": fallback_prompt}],
                max_tokens=600,
            )
            raw2 = r2.choices[0].message.content.strip()
            if "```" in raw2:
                raw2 = raw2.split("```")[1].split("```")[0].replace("json","").strip()
            prices = json.loads(raw2)
            live_price_cache["data"]         = prices
            live_price_cache["last_updated"] = now.isoformat()
        except Exception as e2:
            print(f"Fallback price error: {e2}")

    return prices


def get_sync_prices() -> dict:
    """Return cached live prices. Cache populated by background refresh every 6h."""
    if live_price_cache["data"]:
        return live_price_cache["data"]
    return {
        "maize":   {"price": 280, "unit": "tonne", "trend": "stable", "source": "Pending live update..."},
        "tobacco": {"price": 3.10,"unit": "kg",    "trend": "stable", "source": "Pending live update..."},
        "soya":    {"price": 510, "unit": "tonne", "trend": "stable", "source": "Pending live update..."},
    }


async def get_live_price_text(location: str = "", crop: str = "") -> str:
    prices = await fetch_live_commodity_prices()
    adj    = REGIONAL_PRICE_ADJ.get(location.lower(), {})
    trends = {"rising": "📈", "falling": "📉", "stable": "➡️"}
    now    = datetime.datetime.now()

    if crop:
        c = crop.lower().replace(" ", "_")
        p = prices.get(c, prices.get(crop.lower()))
        if not p:
            return f"No live price for '{crop}' right now.\nTry: PRICE MAIZE\nType *MENU* to return."

        local_factor = adj.get(crop.lower(), 1.0)
        local_price  = round(p["price"] * local_factor, 2)
        icon         = trends.get(p.get("trend", "stable"), "➡️")
        source       = p.get("source", "Live Data")

        analysis = ask_groq(
            f"Zimbabwe market analysis for {crop} on {now.strftime('%d %B %Y')}. "
            f"Current price: ${p['price']}/{p['unit']}. Trend: {p.get('trend','stable')}. "
            f"GMB price: ${p.get('gmb', p['price'])}. "
            f"Write 3-sentence professional market analysis: drivers, outlook, selling strategy.",
            "Zimbabwe agricultural market analysis",
        )

        gmb_info     = f"\n🏛️ GMB Official: *${p.get('gmb', p['price'])}/{p['unit']}*"   if p.get("gmb")     else ""
        private_info = f"\n🏪 Private Buyers: *${p.get('private', local_price)}/{p['unit']}*" if p.get("private") else ""
        floor_info   = f"\n🏭 Tobacco Floor: *${p.get('floor', p['price'])}/{p['unit']}*" if p.get("floor")   else ""

        return f"""💰 *{crop.upper()} — LIVE PRICE*
{COMPANY_NAME}
📍 {location.title() if location else 'Zimbabwe National'}
🕐 Updated: {p.get('updated', now.strftime('%d %b %Y %H:%M'))}
📡 Source: {source}
━━━━━━━━━━━━━━━━━━━━━━

{icon} *Trend: {p.get('trend', 'stable').upper()}*

💵 Market Price: *${p['price']}/{p['unit']}*
📍 Local ({location.title() or 'Avg'}): *${local_price}/{p['unit']}*{gmb_info}{private_info}{floor_info}

━━━━━━━━━━━━━━━━━━━━━━
📊 *LIVE MARKET ANALYSIS:*
{analysis}

━━━━━━━━━━━━━━━━━━━━━━
📞 GMB: 04-621000
📞 Tobacco Floor: 04-791623
📞 ZFC Commodities: 04-700751
Type *PRICE [crop]* for any crop
Type *MENU* to return"""

    result = f"""💰 *ZIMBABWE LIVE MARKET PRICES*
{COMPANY_NAME}
📍 {location.title() if location else 'National Average'}
🕐 {now.strftime('%d %b %Y %H:%M')}
📡 Source: Live AI Market Data
━━━━━━━━━━━━━━━━━━━━━━

🌾 *GRAINS & OILSEEDS:*"""

    for c in ["maize", "wheat", "soya", "sorghum", "sunflower", "groundnuts"]:
        p = prices.get(c)
        if p:
            local = round(p["price"] * adj.get(c, 1.0), 2)
            icon  = trends.get(p.get("trend", "stable"), "➡️")
            result += f"\n{icon} {c.title()}: *${local}/{p['unit']}*"

    result += "\n\n🌿 *CASH CROPS:*"
    for c in ["tobacco", "cotton", "sugar_beans"]:
        p = prices.get(c)
        if p:
            local   = round(p["price"] * adj.get(c.replace("_", " "), adj.get(c, 1.0)), 2)
            icon    = trends.get(p.get("trend", "stable"), "➡️")
            display = c.replace("_", " ").title()
            result += f"\n{icon} {display}: *${local}/{p['unit']}*"

    result += "\n\n🥬 *HORTICULTURE:*"
    for c in ["tomatoes", "onions", "potatoes"]:
        p = prices.get(c)
        if p:
            local = round(p["price"] * adj.get(c, 1.0), 2)
            icon  = trends.get(p.get("trend", "stable"), "➡️")
            result += f"\n{icon} {c.title()}: *${local}/{p['unit']}*"

    result += "\n\n🐄 *LIVESTOCK:*"
    for c in ["cattle", "goats", "chickens"]:
        p = prices.get(c)
        if p:
            icon = trends.get(p.get("trend", "stable"), "➡️")
            result += f"\n{icon} {c.title()}: *${p['price']}/{p['unit']}*"

    result += f"""

━━━━━━━━━━━━━━━━━━━━━━
📈 Rising 📉 Falling ➡️ Stable
⏰ Prices updated every 6 hours

*Type PRICE [crop] for detailed report*
Example: PRICE MAIZE | PRICE TOBACCO

📞 GMB: 04-621000 | ZFC: 04-700751
Type *MENU* to return"""
    return result


# ══════════════════════════════════════════════════════════════
# ── SEED BRAND RECOMMENDATIONS ─────────────────────────────────
# ══════════════════════════════════════════════════════════════

SEED_BRANDS = {
    "maize": {
        "Region 1": [
            {"brand": "Seedco",  "variety": "SC403",     "yield": "8-12 t/ha",  "days": "120-130", "traits": "Drought tolerant, high yield",           "price_per_kg": 8.50},
            {"brand": "Seedco",  "variety": "SC513",     "yield": "9-13 t/ha",  "days": "130-140", "traits": "High yield, good standability",          "price_per_kg": 9.00},
            {"brand": "Pannar",  "variety": "PAN 53",    "yield": "8-11 t/ha",  "days": "125-135", "traits": "Good disease resistance",                "price_per_kg": 8.00},
            {"brand": "ZFC Seeds","variety":"ZFC 803",   "yield": "7-10 t/ha",  "days": "120-130", "traits": "Affordable, locally adapted",            "price_per_kg": 7.50},
        ],
        "Region 2": [
            {"brand": "Seedco",  "variety": "SC403",     "yield": "8-12 t/ha",  "days": "120-130", "traits": "Best for Region 2, drought tolerant",    "price_per_kg": 8.50},
            {"brand": "Seedco",  "variety": "SC633",     "yield": "10-14 t/ha", "days": "130-140", "traits": "Top commercial yield",                   "price_per_kg": 9.50},
            {"brand": "Pannar",  "variety": "PAN 6479",  "yield": "9-12 t/ha",  "days": "128-135", "traits": "Drought tolerant, grey leaf spot resistant","price_per_kg": 8.80},
            {"brand": "ARDA Seeds","variety":"R201",     "yield": "6-9 t/ha",   "days": "115-125", "traits": "Open pollinated, good for small farms",  "price_per_kg": 4.50},
            {"brand": "ZFC Seeds","variety":"ZFC 803",   "yield": "7-10 t/ha",  "days": "120-130", "traits": "Affordable, good for smallholders",      "price_per_kg": 7.50},
        ],
        "Region 3": [
            {"brand": "Seedco",  "variety": "SC403",     "yield": "7-10 t/ha",  "days": "120-130", "traits": "Drought tolerant — essential for Region 3","price_per_kg": 8.50},
            {"brand": "Seedco",  "variety": "SC301",     "yield": "6-9 t/ha",   "days": "110-120", "traits": "Short season, drought escape",           "price_per_kg": 8.00},
            {"brand": "Pannar",  "variety": "PAN 67",    "yield": "7-10 t/ha",  "days": "115-125", "traits": "Good for variable rainfall",             "price_per_kg": 8.20},
            {"brand": "Pioneer", "variety": "PHB 30G19", "yield": "8-11 t/ha",  "days": "120-130", "traits": "Heat tolerant, good standability",       "price_per_kg": 9.00},
        ],
        "Region 4": [
            {"brand": "Seedco",  "variety": "SC301",     "yield": "5-8 t/ha",   "days": "105-115", "traits": "Short season, drought escape",           "price_per_kg": 8.00},
            {"brand": "Seedco",  "variety": "SC403",     "yield": "6-9 t/ha",   "days": "115-125", "traits": "Drought tolerant #1 choice",             "price_per_kg": 8.50},
            {"brand": "Pannar",  "variety": "PAN 53",    "yield": "5-8 t/ha",   "days": "110-120", "traits": "Reliable in dry conditions",             "price_per_kg": 8.00},
            {"brand": "Drought Tolerant OPV","variety":"ZM309","yield":"4-7 t/ha","days":"100-110","traits":"Extreme drought tolerant, open pollinated","price_per_kg": 3.50},
        ],
        "Region 5": [
            {"brand": "Sorghum (Better than maize)","variety":"SX-17","yield":"3-6 t/ha","days":"90-100","traits":"More drought tolerant than maize for Region 5","price_per_kg": 4.00},
            {"brand": "Seedco",  "variety": "SC301",     "yield": "4-6 t/ha",   "days": "100-110", "traits": "Earliest maturing, drought escape",      "price_per_kg": 8.00},
        ],
    },
    "soya": {
        "Region 1": [
            {"brand": "Seedco",  "variety": "SC Soya 6", "yield": "3-4.5 t/ha", "days": "120-130", "traits": "High protein, good yield",               "price_per_kg": 6.50},
            {"brand": "Pannar",  "variety": "Pannar 717","yield": "2.5-4 t/ha", "days": "115-125", "traits": "Disease resistant",                      "price_per_kg": 6.00},
        ],
        "Region 2": [
            {"brand": "Seedco",  "variety": "SC Soya 6", "yield": "2.8-4 t/ha", "days": "120-130", "traits": "Best performing in Region 2",            "price_per_kg": 6.50},
            {"brand": "Naseco",  "variety": "NS-1",      "yield": "2.5-3.5 t/ha","days":"115-120", "traits": "Good protein content",                   "price_per_kg": 5.80},
            {"brand": "Tikolore","variety": "Tikolore",  "yield": "2-3 t/ha",   "days": "110-120", "traits": "Affordable OPV option",                  "price_per_kg": 4.50},
        ],
    },
    "tobacco": {
        "All Regions": [
            {"brand": "Seedco",    "variety": "KRK 26",        "yield": "2.5-3.5 t/ha", "days": "100-110", "traits": "#1 Zimbabwe tobacco variety, high grade", "price_per_kg": 45.00},
            {"brand": "Seedco",    "variety": "T 66",          "yield": "2.8-3.8 t/ha", "days": "105-115", "traits": "High yield, good curing",                "price_per_kg": 42.00},
            {"brand": "SeedTech",  "variety": "KE1",           "yield": "2.5-3.5 t/ha", "days": "100-110", "traits": "Good drought tolerance",                 "price_per_kg": 40.00},
            {"brand": "ZFC Seeds", "variety": "Zimbabwe Gold", "yield": "2.2-3.0 t/ha", "days": "95-105",  "traits": "Affordable, good curing quality",         "price_per_kg": 35.00},
        ],
    },
    "wheat": {
        "Region 1": [
            {"brand": "Seedco", "variety": "SC Wheat 1", "yield": "5-7 t/ha", "days": "120-140", "traits": "High yield under irrigation", "price_per_kg": 4.50},
            {"brand": "Pannar", "variety": "Delphos",    "yield": "5-8 t/ha", "days": "120-135", "traits": "Top yielding, rust resistant", "price_per_kg": 5.00},
        ],
        "Region 2": [
            {"brand": "Seedco",    "variety": "SC Wheat 1", "yield": "4-6 t/ha",   "days": "120-140", "traits": "Good for Region 2 irrigation", "price_per_kg": 4.50},
            {"brand": "ZFC Seeds", "variety": "ZFC W3",     "yield": "4-5.5 t/ha", "days": "125-140", "traits": "Affordable, locally adapted",  "price_per_kg": 4.00},
        ],
    },
    "cotton": {
        "Region 3": [
            {"brand": "Quton",   "variety": "QM 302", "yield": "1.5-2.5 t/ha", "days": "160-180", "traits": "#1 cotton for Zimbabwe, high lint%", "price_per_kg": 12.00},
            {"brand": "Quton",   "variety": "QM 902", "yield": "1.8-2.8 t/ha", "days": "165-185", "traits": "Bollworm resistant, high yield",      "price_per_kg": 13.00},
            {"brand": "SeedTech","variety": "ST 468", "yield": "1.6-2.4 t/ha", "days": "160-175", "traits": "Early maturing, drought tolerant",    "price_per_kg": 11.00},
        ],
        "Region 4": [
            {"brand": "Quton",   "variety": "QM 302", "yield": "1.2-2.0 t/ha", "days": "160-175", "traits": "Best performing in dry conditions",    "price_per_kg": 12.00},
            {"brand": "SeedTech","variety": "ST 468", "yield": "1.3-2.0 t/ha", "days": "155-170", "traits": "Early maturing cotton for dry regions","price_per_kg": 11.00},
        ],
    },
    "sorghum": {
        "Region 3": [
            {"brand": "Pannar", "variety": "PAN 8816",       "yield": "4-7 t/ha", "days": "90-110",  "traits": "High grain yield, bird resistant", "price_per_kg": 5.50},
            {"brand": "Seedco", "variety": "SC Sorghum 1",   "yield": "3-6 t/ha", "days": "85-100",  "traits": "Drought tolerant, good quality",  "price_per_kg": 5.00},
        ],
        "Region 4": [
            {"brand": "Pannar",     "variety": "PAN 8816", "yield": "3-6 t/ha",   "days": "90-110", "traits": "Best sorghum for dry regions",    "price_per_kg": 5.50},
            {"brand": "ARDA Seeds", "variety": "Serena",   "yield": "2.5-5 t/ha", "days": "85-100", "traits": "Traditional variety, affordable", "price_per_kg": 3.50},
        ],
        "Region 5": [
            {"brand": "Pannar",     "variety": "PAN 8816", "yield": "2-4 t/ha",   "days": "85-100", "traits": "Best crop choice for Region 5",   "price_per_kg": 5.50},
            {"brand": "ARDA Seeds", "variety": "Serena",   "yield": "1.5-3 t/ha", "days": "80-95",  "traits": "Most affordable, drought tolerant","price_per_kg": 3.50},
        ],
    },
    "groundnuts": {
        "Region 2": [
            {"brand": "ARDA Seeds", "variety": "Ruduku",       "yield": "1.5-2.5 t/ha", "days": "90-110", "traits": "Popular Zimbabwe variety",      "price_per_kg": 5.00},
            {"brand": "ARDA Seeds", "variety": "Natal Common", "yield": "1.2-2.0 t/ha", "days": "85-100", "traits": "Spreading type, good yield",    "price_per_kg": 4.50},
        ],
        "Region 3": [
            {"brand": "ARDA Seeds", "variety": "Ruduku",  "yield": "1.2-2.0 t/ha", "days": "90-105",  "traits": "Best performing in Region 3",     "price_per_kg": 5.00},
            {"brand": "Pannar",     "variety": "Bonanza", "yield": "1.5-2.5 t/ha", "days": "90-110",  "traits": "High oil content, disease resistant","price_per_kg": 6.00},
        ],
    },
}

SEED_SUPPLIERS = {
    "harare": [
        ("🌱 Seedco Head Office",  "Beatrice Rd, Harare",     "04-575111"),
        ("🌿 Pannar Zimbabwe",     "Harare",                  "04-700892"),
        ("🧪 ZFC Seeds",           "Willowvale, Harare",      "04-621234"),
        ("🌾 ARDA Seeds",          "Rotten Row, Harare",      "04-700311"),
        ("🏪 Farmer's World",      "Msasa, Harare",           "04-447891"),
        ("🛒 Windmill Agro",       "Msasa, Harare",           "04-309411"),
    ],
    "bulawayo": [
        ("🌱 Seedco Bulawayo",  "Fort Street, Bulawayo",   "09-888345"),
        ("🏪 Farmer's Choice", "Belmont, Bulawayo",        "09-888567"),
        ("🛒 ZFC Bulawayo",    "Industrial, Bulawayo",     "09-888234"),
    ],
    "mutare": [
        ("🌱 Seedco Mutare",    "Main Street, Mutare", "020-64567"),
        ("🛒 Windmill Agro Mutare","Main Street, Mutare","020-64789"),
    ],
    "marondera": [
        ("🌱 Seedco Marondera Agent","Main Road",       "079-23567"),
        ("🧪 ZFC Marondera",         "Industrial Area", "079-23234"),
    ],
}


async def fetch_live_seed_prices(crop: str, location: str, region_num: int) -> dict:
    """
    Ask Groq for current Zimbabwe seed prices for this crop.
    Returns dict of {variety: price_per_kg} based on current market.
    """
    now = datetime.datetime.now()
    try:
        prompt = f"""You are a Zimbabwe seed market analyst. Today is {now.strftime('%d %B %Y')}.

Provide CURRENT retail seed prices in USD/kg for {crop.upper()} seeds
available in Zimbabwe ({location.title()}, Agro-Ecological Region {region_num}).

Return ONLY a JSON object mapping variety name to current price:
{{
  "Seedco SC403": 9.50,
  "Seedco SC633": 11.00,
  "Pannar PAN 6479": 10.20,
  "ARDA R201 (OPV)": 5.00,
  "ZFC 803": 8.80
}}

Use realistic {now.strftime('%B %Y')} Zimbabwe agro-dealer prices.
Include 4-6 varieties commonly available in {location.title()}."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].split("```")[0].replace("json","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Live seed price error: {e}")
        return {}


def geocode_location_free(location: str) -> tuple:
    """
    Free geocoding using OpenStreetMap Nominatim.
    No API key needed. Returns (lat, lon, display_name) or (None, None, location).
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q":              f"{location}, Zimbabwe",
                "format":         "json",
                "limit":          1,
                "countrycodes":   "zw",
                "addressdetails": 1,
            },
            headers={"User-Agent": "AgroBotPro/4.1 (agrobot.co.zw)"},
            timeout=8,
        )
        results = r.json()
        if results:
            res          = results[0]
            lat          = float(res["lat"])
            lon          = float(res["lon"])
            display_name = res.get("display_name", location).split(",")[0]
            return lat, lon, display_name
    except Exception as e:
        print(f"Nominatim geocode error: {e}")
    return None, None, location


def find_agri_places_osm(lat: float, lon: float, radius_m: int = 20000) -> list:
    """
    Find agricultural businesses near a point using OpenStreetMap Overpass API.
    Free, no key needed. Returns list of (name, address, phone).
    """
    results = []
    try:
        # Overpass query: agro dealers, farm supply shops, banks near point
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
[out:json][timeout:15];
(
  node["shop"="agrarian"](around:{radius_m},{lat},{lon});
  node["shop"="farm"](around:{radius_m},{lat},{lon});
  node["amenity"="bank"]["name"~"Agribank|ZB Bank|CBZ",i](around:{radius_m},{lat},{lon});
  node["office"="government"]["name"~"Agritex|GMB|Grain Marketing",i](around:{radius_m},{lat},{lon});
  node["name"~"Seedco|ZFC|Agritex|GMB|Farmer|Windmill|Agricura",i](around:{radius_m},{lat},{lon});
);
out body 8;
"""
        r       = requests.post(overpass_url, data={"data": query}, timeout=15)
        elements = r.json().get("elements", [])
        for el in elements:
            tags    = el.get("tags", {})
            name    = tags.get("name", "")
            if not name:
                continue
            street  = tags.get("addr:street", "")
            city    = tags.get("addr:city", "")
            address = f"{street}, {city}".strip(", ") or "See OpenStreetMap"
            phone   = tags.get("phone", tags.get("contact:phone", "—"))
            results.append((f"🏪 {name}", address, phone))

    except Exception as e:
        print(f"Overpass API error: {e}")

    return results


async def find_seed_suppliers_free(location: str, lat: float = None, lon: float = None) -> list:
    """
    Find seed suppliers using free OpenStreetMap Overpass API.
    Falls back to SEED_SUPPLIERS dict if Overpass returns nothing.
    """
    # Get coordinates if not provided
    if not (lat and lon):
        lat, lon, _ = geocode_location_free(location)

    if lat and lon:
        osm_results = find_agri_places_osm(lat, lon, radius_m=15000)
        if osm_results:
            return osm_results

    # Final fallback: known suppliers dict
    return SEED_SUPPLIERS.get(location.lower(), SEED_SUPPLIERS.get("harare", []))


def get_seed_recommendations(location: str, crop: str = "") -> str:
    """Sync wrapper — live seed prices fetched async on specific crop requests."""
    info       = get_region_info(location)
    region_num = info["region"]
    region_key = f"Region {region_num}"

    if not crop:
        result = f"""🌱 *SEED RECOMMENDATIONS*
{COMPANY_NAME}
📍 {location.title()} — Region {region_num}
🌤️ {info['climate']} | {info['rainfall']}
━━━━━━━━━━━━━━━━━━━━━━

*BEST CROPS FOR YOUR REGION:*
{info['best_crops']}

*TOP SEED BRANDS AVAILABLE:*

"""
        for crop_name, regions in SEED_BRANDS.items():
            if region_key in regions or "All Regions" in regions:
                seeds = regions.get(region_key, regions.get("All Regions", []))
                if seeds:
                    top = seeds[0]
                    result += f"🌿 *{crop_name.upper()}*\n"
                    result += f"   🏆 {top['brand']} {top['variety']}\n"
                    result += f"   📊 Yield: {top['yield']}\n"
                    result += f"   💰 Current prices: Type *SEEDS {crop_name.upper()}*\n\n"

        result += f"""━━━━━━━━━━━━━━━━━━━━━━
*Type SEEDS [crop] for live prices*
Example: SEEDS MAIZE
Example: SEEDS TOBACCO

📞 Seedco: 04-575111
📞 ZFC Seeds: 04-621234
📞 ARDA Seeds: 04-700311
Type *MENU* to return"""
        return result

    crop_lower = crop.lower()
    crops_data = SEED_BRANDS.get(crop_lower)

    if not crops_data:
        # Ask Groq for any crop not in our list
        ai_info = ask_groq(
            f"What seed varieties are available for {crop} in {location} Zimbabwe Region {region_num}? "
            f"List top 3 brands with variety name, expected yield, and current approximate retail price in USD/kg.",
            f"Zimbabwe {crop} seed varieties and prices",
        )
        return f"""🌱 *{crop.upper()} SEEDS — {location.title()}*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{ai_info}

━━━━━━━━━━━━━━━━━━━━━━
📞 Seedco: 04-575111
📞 Pannar: 04-700892
📞 ZFC Seeds: 04-621234
📞 ARDA Seeds: 04-700311
Type *SEEDS* for region recommendations
Type *MENU* to return"""

    seeds = crops_data.get(region_key, crops_data.get("All Regions", []))

    if not seeds:
        for r in range(max(1, region_num - 1), min(6, region_num + 2)):
            seeds = crops_data.get(f"Region {r}", [])
            if seeds:
                break

    result = f"""🌱 *{crop.upper()} SEED RECOMMENDATIONS*
{COMPANY_NAME}
📍 {location.title()} — Region {region_num}
🌤️ {info['climate']} | {info['rainfall']}
━━━━━━━━━━━━━━━━━━━━━━

"""
    if not seeds:
        result += f"⚠️ {crop.title()} not commonly grown in your region.\n"
        result += f"Best crops here: {info['best_crops']}\n"
        result += "Type *SEEDS* for region-appropriate crops.\n"
        result += "Type *MENU* to return"
        return result

    # Fetch live seed prices from Groq
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            live_prices = {}  # In async context, prices shown from SEED_BRANDS
        else:
            live_prices = loop.run_until_complete(fetch_live_seed_prices(crop, location, region_num))
    except Exception:
        live_prices = {}

    for i, seed in enumerate(seeds, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        # Try to get live price for this variety
        live_price = None
        for key, val in live_prices.items():
            if seed["variety"].lower() in key.lower() or seed["brand"].lower() in key.lower():
                live_price = val
                break
        price_str = f"*${live_price}/kg* 📡 Live" if live_price else f"~${seed['price_per_kg']}/kg"

        result += f"{medal} *{seed['brand']} — {seed['variety']}*\n"
        result += f"   📊 Expected Yield: {seed['yield']}\n"
        result += f"   📅 Days to Maturity: {seed['days']} days\n"
        result += f"   🔬 Key Traits: {seed['traits']}\n"
        result += f"   💰 Seed Price: {price_str}\n\n"

    # Get nearby suppliers — try live OSM first, fallback to known list
    profile     = farmer_profiles.get("", {})
    lat_f       = profile.get("gps_lat")
    lon_f       = profile.get("gps_lon")
    try:
        # Run async function synchronously
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        suppliers = loop.run_until_complete(
            find_seed_suppliers_free(location, lat_f, lon_f)
        )
        loop.close()
    except Exception:
        suppliers = SEED_SUPPLIERS.get(location.lower(), SEED_SUPPLIERS.get("harare", []))

    result += "━━━━━━━━━━━━━━━━━━━━━━\n"
    result += f"*📍 BUY SEEDS NEAR {location.upper()}:*\n"
    for name, addr, phone_num in suppliers[:3]:
        result += f"{name}\n📌 {addr} | 📞 {phone_num}\n"

    ai_advice = ask_groq(
        f"Give 3 specific planting tips for {crop} in {location} Zimbabwe, "
        f"Region {region_num} ({info['climate']}). Include: optimal planting date, "
        f"seeding rate (kg/ha), row spacing, and fertilizer at planting.",
        f"Zimbabwe {crop} agronomy and seed management",
    )

    result += f"""
━━━━━━━━━━━━━━━━━━━━━━
🌱 *PLANTING ADVISORY:*
{ai_advice}

━━━━━━━━━━━━━━━━━━━━━━
📞 Seedco: 04-575111
📞 Pannar: 04-700892
📞 ZFC Seeds: 04-621234
Type *SEEDS* for other crops
Type *MENU* to return"""
    return result


# ══════════════════════════════════════════════════════════════
# ── IMAGE ANALYSIS ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

def analyze_image_improved(image_url: str, phone: str = "") -> str:
    try:
        headers      = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        img_response = requests.get(image_url, headers=headers, timeout=20)

        if img_response.status_code != 200:
            return "Could not download image. Please try again with a clearer photo."

        img_bytes = img_response.content
        if len(img_bytes) < 1000:
            return "Image too small or corrupted. Please send a clearer photo."

        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        if img_bytes[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1'):
            img_type = "image/jpeg"
        elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            img_type = "image/png"
        elif img_bytes[:4] == b'WEBP':
            img_type = "image/webp"
        else:
            img_type = "image/jpeg"

        ctx = get_farmer_context(phone)

        detailed_prompt = f"""You are an expert plant pathologist and agronomist specialising in Zimbabwe and sub-Saharan African agriculture.

{ctx}

Please analyse this image and provide:

🌿 PLANT IDENTIFICATION:
- Common name, Scientific name, Growth stage, Confidence level

🔍 PROBLEM DIAGNOSIS:
- Is there a problem? YES/NO
- Type: DISEASE / PEST DAMAGE / NUTRIENT DEFICIENCY / ENVIRONMENTAL / NORMAL
- Specific problem name, Symptoms visible

📊 SEVERITY ASSESSMENT:
- Severity: LOW / MODERATE / HIGH / CRITICAL
- % of plant affected, Spread rate

💊 TREATMENT RECOMMENDATION:
- Primary treatment (Zimbabwe brand name + product)
- Application rate and method, When to apply, Estimated cost USD

🛡️ PREVENTION:
- How to prevent next season, Cultural practices

⏰ URGENCY: Action needed within [X hours/days/weeks]

If image quality is poor, state clearly what you CAN and CANNOT determine."""

        models_to_try = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ]

        last_error = None
        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{img_type};base64,{img_base64}"}},
                            {"type": "text",      "text": detailed_prompt},
                        ],
                    }],
                    max_tokens=1000,
                )
                analysis = response.choices[0].message.content

                if len(analysis) < 100:
                    continue

                cant_see = ["cannot see", "can't see", "no image", "not provided", "unable to view", "i don't see"]
                if any(p in analysis.lower() for p in cant_see):
                    last_error = "Vision model could not process this image"
                    continue

                return f"""{analysis}

━━━━━━━━━━━━━━━━━━━━━━
📸 Analysed by {BOT_NAME} Vision AI
🛒 Treatment supplies:
- Agricura: 04-621567
- ZFC: 04-700751
- Windmill Agro: 04-309411
📞 Agritex Helpline: 0800 4040"""

            except Exception as model_error:
                last_error = str(model_error)
                print(f"Model {model_name} failed: {model_error}")
                continue

        print(f"All vision models failed: {last_error}")
        return fallback_image_analysis(phone)

    except Exception as e:
        print(f"Image analysis error: {e}")
        return f"""❌ *Image Analysis Failed*

Could not process your image. Please:
✅ Ensure good lighting
✅ Hold camera steady
✅ Get close to show symptoms clearly
✅ Try JPG or PNG format under 5MB

📞 Agritex Plant Clinic: 0800 4040"""


def fallback_image_analysis(phone: str) -> str:
    user_states[phone] = "image_describe"
    return """📸 *Image received but needs description*

Our vision AI needs more detail.
Please describe what you see:

1. What crop is it?
2. What do the leaves/stems look like?
3. What colour changes do you see?
4. How many plants affected?
5. When did you first notice?"""


# ── Province & Region Data ─────────────────────────────────────
PROVINCE_DEFAULTS = {
    "1": "marondera", "2": "bulawayo",      "3": "mutare",
    "4": "masvingo",  "5": "gweru",         "6": "chinhoyi",
    "7": "bindura",   "8": "victoria falls","9": "beitbridge",
}

PROVINCE_NAMES = {
    "1": "Harare/Mashonaland East",     "2": "Bulawayo/Matabeleland",
    "3": "Manicaland",                  "4": "Masvingo/Lowveld",
    "5": "Midlands",                    "6": "Mashonaland West",
    "7": "Mashonaland Central",         "8": "Matabeleland North",
    "9": "Matabeleland South",
}

ZIMBABWE_REGIONS = {
    "harare":         {"region": 2, "lat": -17.8252, "lon": 31.0335, "climate": "Sub-humid",           "rainfall": "600-800mm",   "best_crops": "Maize, Tobacco, Horticulture, Wheat, Soya",        "soil": "Sandy loam to clay loam", "season": "Nov-Apr", "challenges": "Urban expansion, water scarcity"},
    "bulawayo":       {"region": 4, "lat": -20.1325, "lon": 28.6264, "climate": "Semi-arid",            "rainfall": "400-600mm",   "best_crops": "Sorghum, Millet, Sunflower, Cotton, Groundnuts",   "soil": "Sandy to sandy loam",     "season": "Dec-Mar", "challenges": "Drought prone, irregular rains"},
    "mutare":         {"region": 1, "lat": -18.9707, "lon": 32.6709, "climate": "Sub-humid to Humid",   "rainfall": "800-1200mm",  "best_crops": "Tea, Coffee, Macadamia, Maize, Beans, Avocado",    "soil": "Rich red clay loam",      "season": "Oct-Apr", "challenges": "Steep terrain, erosion, cyclone risk"},
    "masvingo":       {"region": 4, "lat": -20.0635, "lon": 30.8335, "climate": "Semi-arid",            "rainfall": "400-600mm",   "best_crops": "Sorghum, Cotton, Sunflower, Groundnuts",           "soil": "Granite sandy soils",     "season": "Dec-Mar", "challenges": "Low soil fertility, dry spells"},
    "gweru":          {"region": 3, "lat": -19.4500, "lon": 29.8167, "climate": "Semi-humid",           "rainfall": "500-700mm",   "best_crops": "Maize, Groundnuts, Soya, Sunflower",               "soil": "Clay to sandy clay",      "season": "Nov-Apr", "challenges": "Variable rainfall"},
    "marondera":      {"region": 2, "lat": -18.1833, "lon": 31.5500, "climate": "Sub-humid",            "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Wheat, Horticulture, Soya",        "soil": "Red sandy loam",          "season": "Nov-Apr", "challenges": "Early season dry spells"},
    "chinhoyi":       {"region": 2, "lat": -17.3667, "lon": 30.2000, "climate": "Sub-humid",            "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Soya, Wheat, Cotton",              "soil": "Deep red loam",           "season": "Nov-Apr", "challenges": "Bush encroachment"},
    "bindura":        {"region": 2, "lat": -17.3000, "lon": 31.3333, "climate": "Sub-humid",            "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Cotton, Groundnuts",               "soil": "Clay loam",               "season": "Nov-Apr", "challenges": "Hail risk"},
    "victoria falls": {"region": 4, "lat": -17.9322, "lon": 25.8306, "climate": "Semi-arid",            "rainfall": "500-700mm",   "best_crops": "Maize, Cotton, Sesame, Sorghum",                   "soil": "Sandy alluvial",          "season": "Dec-Mar", "challenges": "Remote markets, wildlife"},
    "kariba":         {"region": 4, "lat": -16.5167, "lon": 28.8000, "climate": "Hot semi-arid",        "rainfall": "400-600mm",   "best_crops": "Cotton, Sorghum, Millet, Sesame",                  "soil": "Sandy to loamy sand",     "season": "Dec-Mar", "challenges": "Very high temps"},
    "chiredzi":       {"region": 5, "lat": -21.0500, "lon": 31.6667, "climate": "Arid",                 "rainfall": "300-400mm",   "best_crops": "Sugarcane, Cotton, Sorghum, Livestock",            "soil": "Sandy clay loam",         "season": "Jan-Mar", "challenges": "Very low rainfall"},
    "beitbridge":     {"region": 5, "lat": -22.2167, "lon": 30.0000, "climate": "Very arid",            "rainfall": "200-400mm",   "best_crops": "Livestock, Sorghum, Millet, Drought crops",        "soil": "Shallow sandy",           "season": "Jan-Feb", "challenges": "Lowest rainfall, extreme heat"},
    "zvishavane":     {"region": 4, "lat": -20.3333, "lon": 30.0333, "climate": "Semi-arid",            "rainfall": "400-600mm",   "best_crops": "Sorghum, Cotton, Groundnuts, Livestock",           "soil": "Granite sandy",           "season": "Dec-Mar", "challenges": "Mining water competition"},
    "kwekwe":         {"region": 3, "lat": -18.9167, "lon": 29.8167, "climate": "Semi-humid",           "rainfall": "500-700mm",   "best_crops": "Maize, Groundnuts, Soya, Cotton",                  "soil": "Clay to sandy clay",      "season": "Nov-Apr", "challenges": "Industrial pollution"},
    "kadoma":         {"region": 3, "lat": -18.3500, "lon": 29.9167, "climate": "Semi-humid",           "rainfall": "500-700mm",   "best_crops": "Cotton, Maize, Groundnuts, Wheat",                 "soil": "Sandy clay loam",         "season": "Nov-Apr", "challenges": "Cotton price fluctuation"},
    "norton":         {"region": 2, "lat": -17.8833, "lon": 30.7000, "climate": "Sub-humid",            "rainfall": "600-800mm",   "best_crops": "Maize, Tobacco, Horticulture, Wheat",              "soil": "Red sandy loam",          "season": "Nov-Apr", "challenges": "Urban sprawl"},
    "rusape":         {"region": 2, "lat": -18.5333, "lon": 32.1333, "climate": "Sub-humid",            "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Beans, Horticulture",              "soil": "Red clay loam",           "season": "Nov-Apr", "challenges": "Hilly terrain"},
    "nyanga":         {"region": 1, "lat": -18.2167, "lon": 32.7500, "climate": "Humid",                "rainfall": "1000-1500mm", "best_crops": "Potatoes, Wheat, Apples, Beans, Tea",              "soil": "Deep red clay",           "season": "Oct-May", "challenges": "Frost risk"},
    "chipinge":       {"region": 1, "lat": -20.1833, "lon": 32.6167, "climate": "Sub-humid to Humid",   "rainfall": "800-1200mm",  "best_crops": "Tea, Coffee, Macadamia, Avocado, Maize",           "soil": "Rich red clay loam",      "season": "Oct-Apr", "challenges": "Cyclone risk"},
}


def find_nearest_region(lat: float, lon: float) -> dict:
    min_dist     = float("inf")
    nearest_name = "harare"
    for city, info in ZIMBABWE_REGIONS.items():
        dist = math.sqrt((lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2)
        if dist < min_dist:
            min_dist     = dist
            nearest_name = city
    return {"name": nearest_name, "info": ZIMBABWE_REGIONS[nearest_name]}


def get_region_info(location: str) -> dict:
    loc_lower = location.lower()
    for city, info in ZIMBABWE_REGIONS.items():
        if city in loc_lower:
            return info
    return ZIMBABWE_REGIONS["harare"]


# ── User Activity Tracking ─────────────────────────────────────
def track_activity(phone: str, action: str = "message"):
    now   = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")

    if phone not in user_activity:
        user_activity[phone] = {
            "first_seen":       now.isoformat(),
            "last_seen":        now.isoformat(),
            "total_messages":   0,
            "daily_activity":   {},
            "total_days_active":0,
            "streak_days":      0,
            "last_active_date": today,
            "actions":          {},
        }

    activity               = user_activity[phone]
    activity["last_seen"]  = now.isoformat()
    activity["total_messages"] = activity.get("total_messages", 0) + 1

    if today not in activity["daily_activity"]:
        activity["daily_activity"][today] = 0
        activity["total_days_active"]     = len(activity["daily_activity"])
        yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if activity.get("last_active_date") == yesterday:
            activity["streak_days"] = activity.get("streak_days", 0) + 1
        else:
            activity["streak_days"] = 1
        activity["last_active_date"] = today

    activity["daily_activity"][today] = activity["daily_activity"].get(today, 0) + 1
    activity["actions"][action]       = activity["actions"].get(action, 0) + 1

    if len(activity["daily_activity"]) > 90:
        sorted_days = sorted(activity["daily_activity"].keys())
        for old_day in sorted_days[:-90]:
            del activity["daily_activity"][old_day]

    save_data()


def get_user_stats(phone: str) -> dict:
    profile    = farmer_profiles.get(phone, {})
    activity   = user_activity.get(phone, {})
    now        = datetime.datetime.now()
    joined_str = profile.get("joined", now.isoformat())

    try:
        joined          = datetime.datetime.fromisoformat(joined_str)
        days_registered = (now - joined).days + 1
        trial_end       = joined + datetime.timedelta(days=TRIAL_DAYS)
        trial_days_left = max(0, (trial_end - now).days)
        trial_expired   = now > trial_end
        trial_end_str   = trial_end.strftime("%d %B %Y")
    except Exception:
        days_registered = 1
        trial_days_left = TRIAL_DAYS
        trial_expired   = False
        trial_end_str   = "Unknown"

    return {
        "phone":             phone,
        "name":              profile.get("name", f"Farmer {phone[-4:]}"),
        "location":          profile.get("location", "Unknown"),
        "joined":            joined_str[:10] if joined_str else "Unknown",
        "days_since_joining":days_registered,
        "trial_days_left":   trial_days_left,
        "trial_expired":     trial_expired,
        "trial_end_date":    trial_end_str,
        "plan":              get_plan(phone),
        "is_premium":        is_premium(phone),
        "total_messages":    activity.get("total_messages", 0),
        "total_days_active": activity.get("total_days_active", 0),
        "streak_days":       activity.get("streak_days", 0),
        "last_seen":         activity.get("last_seen", "Never")[:10],
        "conversations":     len(conversations.get(phone, [])),
        "marketplace_posts": len([x for x in marketplace if x.get("poster") == phone]),
        "community_posts":   len([x for x in community_posts if x.get("phone") == phone]),
    }


# ── Premium Functions ──────────────────────────────────────────
def is_premium(phone: str) -> bool:
    if phone not in premium_users:
        return False
    user = premium_users[phone]
    if not user.get("active", False):
        return False
    expires = user.get("expires")
    if expires:
        try:
            if datetime.datetime.now() > datetime.datetime.fromisoformat(expires):
                premium_users[phone]["active"] = False
                save_data()
                return False
        except Exception:
            pass
    return True


def is_in_trial(phone: str) -> bool:
    profile    = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str:
        return False
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        return datetime.datetime.now() < joined + datetime.timedelta(days=TRIAL_DAYS)
    except Exception:
        return False


def get_trial_days_left(phone: str) -> int:
    profile    = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str:
        return 0
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        diff   = (joined + datetime.timedelta(days=TRIAL_DAYS)) - datetime.datetime.now()
        return max(0, diff.days)
    except Exception:
        return 0


def has_full_access(phone: str) -> bool:
    return is_premium(phone) or is_in_trial(phone)


def get_plan(phone: str) -> str:
    if is_premium(phone):
        return premium_users[phone].get("plan", "premium")
    if is_in_trial(phone):
        return "trial"
    return "free"


def premium_gate(phone: str, feature: str):
    if has_full_access(phone):
        return None
    return f"""🔒 *{feature} — Premium Required*
━━━━━━━━━━━━━━━━━━━━━━
Your {TRIAL_DAYS}-day free trial has ended.

Reply *UPGRADE* to subscribe:
💎 Premium: $2/month
🏆 Business: $10/month

Type *MENU* to go back"""


def generate_ref(phone: str) -> str:
    return f"AGRO{phone[-6:]}"


def save_location(phone: str, location: str):
    if phone not in farmer_profiles:
        farmer_profiles[phone] = {"joined": datetime.datetime.now().isoformat()}
    farmer_profiles[phone]["location"]   = location.lower()
    farmer_profiles[phone]["registered"] = True
    save_data()


def save_conversation(phone: str, role: str, message: str, msg_type: str = "text"):
    if phone not in conversations:
        conversations[phone] = []
    conversations[phone].append({
        "role":      role,
        "message":   message,
        "type":      msg_type,
        "timestamp": datetime.datetime.now().isoformat(),
        "platform":  "whatsapp",
    })
    if len(conversations[phone]) > 500:
        conversations[phone] = conversations[phone][-500:]
    save_data()


def get_conversation_history(phone: str, limit: int = 5) -> list:
    return conversations.get(phone, [])[-limit:]


# ── Community Functions ────────────────────────────────────────
def get_community_menu() -> str:
    total_members = len(farmer_profiles)
    total_posts   = len(community_posts)
    online        = sum(len(v) for v in manager.active_connections.values())
    return f"""👥 *AGROBOT FARMER COMMUNITY*
{COMPANY_NAME}
📊 {total_members} Members | {total_posts} Posts | 🟢 {online} Online
━━━━━━━━━━━━━━━━━━━━━━

*💬 CHANNELS:*
1️⃣ 🌍 General Farming
2️⃣ 🌽 Maize Farmers
3️⃣ 🍂 Tobacco Growers
4️⃣ 🐄 Livestock Farmers
5️⃣ 🥬 Horticulture
6️⃣ 🌧️ Weather Reports
7️⃣ 💰 Market Prices

*📢 ACTIONS:*
8️⃣ Post a Message
9️⃣ Latest Posts
🔟 My Community Profile

0️⃣ ◀️ Back to Main Menu
━━━━━━━━━━━━━━━━━━━━━━
🌐 Also chat at: {WEBSITE}/community
📲 Real-time on {BOT_NAME} App!"""


def get_channel_posts(channel: str, limit: int = 5) -> str:
    ch_data  = community_channels.get(channel, {})
    messages = ch_data.get("messages", [])
    ch_name  = ch_data.get("name", channel.title())
    online   = len(manager.active_connections.get(channel, []))

    if not messages:
        return f"""💬 *{ch_name}*
🟢 {online} online now
━━━━━━━━━━━━━━━━━━━━━━

📭 No posts yet. Be the first!

Type your message to post here.
Type *COMMUNITY* to go back."""

    result = f"💬 *{ch_name}*\n🟢 {online} online now\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for post in messages[-limit:]:
        ph       = post.get("phone", "")
        profile  = farmer_profiles.get(ph, {})
        name     = profile.get("name", f"Farmer {ph[-4:]}")
        loc      = profile.get("location", "Zimbabwe").title()
        time_str = post.get("timestamp", "")[:16].replace("T", " ")
        result  += f"👤 *{name}* — {loc}\n⏰ {time_str}\n💬 {post.get('message', '')}\n\n"

    result += "━━━━━━━━━━━━━━━━━━━━━━\n"
    result += "Reply to post your message\n"
    result += "Type *COMMUNITY* to go back\n"
    result += f"🌐 Real-time chat: {WEBSITE}/community"
    return result


def post_to_community(phone: str, channel: str, message: str) -> str:
    profile  = farmer_profiles.get(phone, {})
    name     = profile.get("name", f"Farmer {phone[-4:]}")
    location = profile.get("location", "Zimbabwe").title()

    post = {
        "id":        secrets.token_hex(8),
        "phone":     phone,
        "name":      name,
        "location":  location,
        "channel":   channel,
        "message":   message,
        "timestamp": datetime.datetime.now().isoformat(),
        "likes":     0,
        "replies":   [],
    }

    community_posts.append(post)

    if channel not in community_channels:
        community_channels[channel] = {"name": channel.title(), "messages": []}
    community_channels[channel]["messages"].append(post)

    if len(community_channels[channel]["messages"]) > 100:
        community_channels[channel]["messages"] = community_channels[channel]["messages"][-100:]

    save_data()
    track_activity(phone, "community_post")

    ch_name = community_channels.get(channel, {}).get("name", channel.title())
    return f"""✅ *Posted to {ch_name}!*
━━━━━━━━━━━━━━━━━━━━━━
👤 {name} | {location}
💬 {message}

Visible to all AgroBot farmers!
🌐 Also at: {WEBSITE}/community
📲 Real-time on {BOT_NAME} App

Type *COMMUNITY* to see more
Type *MENU* to return"""


# ── Farmer Context ─────────────────────────────────────────────
def get_farmer_context(phone: str) -> str:
    profile  = farmer_profiles.get(phone, {})
    activity = user_activity.get(phone, {})
    now      = datetime.datetime.now()

    ctx  = f"\nDate: {now.strftime('%d %B %Y')}"
    ctx += f"\nSeason: March — End of rainy season, harvest approaching"
    ctx += f"\nClimate change: Zimbabwe experiencing erratic rainfall, +1.5°C rise"

    if "gps_lat" in profile:
        nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
        info    = nearest["info"]
        ctx += f"\nFarmer GPS: {profile['gps_lat']:.4f}°S, {profile['gps_lon']:.4f}°E"
        ctx += f"\nNearest: {nearest['name'].title()}"
        ctx += f"\nClimate: Region {info['region']} — {info['climate']}"
        ctx += f"\nRainfall: {info['rainfall']} | Soil: {info.get('soil', 'Mixed')}"
        ctx += f"\nBest crops: {info['best_crops']}"
        ctx += f"\nChallenges: {info.get('challenges', 'Variable weather')}"
    elif "location" in profile:
        loc  = profile["location"]
        info = get_region_info(loc)
        ctx += f"\nLocation: {loc.title()}"
        ctx += f"\nClimate: Region {info['region']} — {info['climate']}"
        ctx += f"\nRainfall: {info['rainfall']} | Soil: {info.get('soil', 'Mixed')}"
        ctx += f"\nBest crops: {info['best_crops']}"

    ctx += f"\nPlan: {get_plan(phone).upper()}"
    ctx += f"\nDays on AgroBot: {activity.get('total_days_active', 1)}"

    history = get_conversation_history(phone, 3)
    if history:
        ctx += "\nRecent conversation:"
        for msg in history:
            role  = "Farmer" if msg["role"] == "farmer" else "AgroBot"
            ctx  += f"\n{role}: {msg['message'][:80]}"
    return ctx


# ── AI ─────────────────────────────────────────────────────────
def ask_groq(question: str, topic: str = "", phone: str = "") -> str:
    try:
        profile  = farmer_profiles.get(phone, {})
        now      = datetime.datetime.now()
        gps_used = False

        if "gps_lat" in profile:
            lat     = profile["gps_lat"]
            lon     = profile["gps_lon"]
            nearest = find_nearest_region(lat, lon)
            info    = nearest["info"]
            gps_used = True
            location_context = f"""
FARMER EXACT GPS LOCATION:
Coordinates: {lat:.6f}°S, {lon:.6f}°E
Nearest Town: {nearest['name'].title()}
Climate Region: Region {info['region']} — {info['climate']}
Annual Rainfall: {info['rainfall']}
Soil Type: {info.get('soil', 'Mixed soils')}
Best Crops: {info['best_crops']}
Planting Season: {info.get('season', 'November-April')}
Local Challenges: {info.get('challenges', 'Variable rainfall')}"""
        elif "location" in profile:
            loc  = profile["location"]
            info = get_region_info(loc)
            location_context = f"""
FARMER SPECIFIC LOCATION: {loc.title()}
Climate Region: Region {info['region']} — {info['climate']}
Annual Rainfall: {info['rainfall']}
Soil Type: {info.get('soil', 'Mixed soils')}
Best Crops for {loc.title()}: {info['best_crops']}
Planting Season: {info.get('season', 'November-April')}
Local Challenges: {info.get('challenges', 'Variable rainfall')}"""
        else:
            location_context = "FARMER LOCATION: Not set — give general Zimbabwe advice."

        season_note = (
            "Late season — harvest preparation, soil conservation"  if now.month in [3, 4]  else
            "Post-harvest — land preparation, planning"             if now.month in [5, 6, 7] else
            "Pre-season — input procurement, land prep"             if now.month in [8, 9, 10] else
            "Planting season — crop establishment critical"
        )

        system_prompt = f"""You are {BOT_NAME} — Zimbabwe's most advanced AI agriculture consultant by {COMPANY_NAME}.

TODAY'S DATE: {now.strftime('%d %B %Y')}
CURRENT SEASON: {season_note}

{location_context}

SUBSCRIPTION: {get_plan(phone).upper()}

RESPONSE REQUIREMENTS:
1. Give SPECIFIC advice for the farmer's location
2. Reference specific local conditions, soil, rainfall
3. Include Zimbabwe-available product names (ZFC, Agricura, Seedco, Windmill, Pannar)
4. Include specific quantities and rates (kg/ha, litres/ha)
5. Include realistic costs in USD
6. Give timing specific to current season
7. 150–300 words, clear sections
8. End with ONE urgent specific action

{f'FOCUS TOPIC: {topic}' if topic else ''}"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": question},
            ],
            max_tokens=600,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Groq error: {e}")
        return f"AgroBot temporarily unavailable. Please try again.\n📞 {SUPPORT_PHONE}"


def get_farming_news(phone: str = "") -> str:
    """Groq AI news summary — used as WhatsApp text fallback only."""
    try:
        now      = datetime.datetime.now()
        profile  = farmer_profiles.get(phone, {})
        location = profile.get("location", "Zimbabwe")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""You are a Zimbabwe farming news editor. Today is {now.strftime('%d %B %Y')}.
Write a concise farming news bulletin for {location} farmers.
Include: top story, weather/climate, market prices, crop update, livestock, agri-tech tip, pest alert, farming tip.
Format with emoji headings. 300 words max."""}],
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"News generation error: {e}")
        return "📰 News temporarily unavailable. Please try again later."


def get_weather_by_name(location_name: str) -> str:
    """
    Resolve location name → coordinates using free Nominatim (OSM),
    then fetch live weather from Open-Meteo (also free).
    """
    lat, lon, display = geocode_location_free(location_name)

    # Fall back to ZIMBABWE_REGIONS coords if Nominatim failed
    if not lat:
        info         = get_region_info(location_name)
        lat, lon     = info["lat"], info["lon"]
        display      = location_name.title()

    return get_weather(lat, lon, display)


def get_weather(lat: float, lon: float, name: str = "Your Farm") -> str:
    """
    Live 7-day weather from Open-Meteo (free, no key needed).
    Includes evapotranspiration-based irrigation advisory.
    """
    try:
        url  = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,"
            f"precipitation_sum,precipitation_probability_max,"
            f"windspeed_10m_max,et0_fao_evapotranspiration"
            f"&timezone=Africa/Harare&forecast_days=7"
        )
        data    = requests.get(url, timeout=12).json()
        d       = data.get("daily", {})
        if not d:
            return "Weather data unavailable. Please try again."

        nearest    = find_nearest_region(lat, lon)
        info       = nearest["info"]
        et_list    = d.get("et0_fao_evapotranspiration", [3.5] * 7)
        total_rain = sum(d.get("precipitation_sum", [0]*7))
        avg_max    = sum(d.get("temperature_2m_max", [25]*7)) / 7
        now        = datetime.datetime.now()

        result  = f"🌤️ *7-DAY FORECAST — LIVE*\n"
        result += f"📍 {name}\n"
        result += f"📡 Source: Open-Meteo | {now.strftime('%d %b %Y %H:%M')}\n"
        result += f"🌍 Region {info['region']} | {info['climate']}\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        times     = d.get("time", [])
        rain_list = d.get("precipitation_sum", [0]*7)
        prob_list = d.get("precipitation_probability_max", [0]*7)
        tmax_list = d.get("temperature_2m_max", [25]*7)
        tmin_list = d.get("temperature_2m_min", [15]*7)

        for i in range(min(7, len(times))):
            rain  = rain_list[i]
            prob  = prob_list[i]
            et    = et_list[i] if i < len(et_list) else 3.5
            irrig = max(0, round(et - rain, 1))
            icon  = ("⛈️" if rain > 30 else "🌧️" if rain > 10
                     else "🌦️" if rain > 2  else "⛅" if prob > 60 else "☀️")
            result += f"*{times[i]}* {icon}\n"
            result += f"  🌡️ {tmin_list[i]}°–{tmax_list[i]}°C  💧 {rain}mm  💨 {prob}%\n"
            if irrig > 0:
                result += f"  💦 Irrigation needed: ~{irrig}mm\n"
            result += "\n"

        result += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"📊 Week total: {total_rain:.0f}mm | Avg max: {avg_max:.1f}°C\n\n"

        # Season-aware AI farming advice
        season = (
            "harvest / post-harvest" if now.month in [3, 4, 5] else
            "land prep / off-season" if now.month in [6, 7, 8] else
            "pre-planting"           if now.month in [9, 10]   else
            "active growing season"
        )
        advice = ask_groq(
            f"Farm at {name}, Zimbabwe Region {info['region']} ({info['climate']}). "
            f"Current season: {season}. "
            f"This week's weather: avg max {avg_max:.1f}°C, total rain {total_rain:.0f}mm. "
            f"Give 4 specific actionable farming tasks for this week.",
            "Zimbabwe precision agriculture weather advisory",
        )
        result += f"🌱 *THIS WEEK'S ADVISORY:*\n{advice}\n"
        result += "\nType *MENU* to return"
        return result

    except Exception as e:
        print(f"Weather error: {e}")
        return "Weather unavailable right now. Please try again in a few minutes."


def find_help_nearby(location: str, lat: float = None, lon: float = None) -> str:
    """
    Find real agricultural help near the farmer.
    1. Overpass API (OpenStreetMap) → live agri businesses near GPS (free, no key)
    2. Nominatim geocoding          → resolves location names to coords (free, no key)
    3. Groq AI                      → finds contacts for towns not in Overpass
    4. Known contacts               → reliable fallback for main cities
    """
    gps_note = "\n🛰️ Based on your GPS location" if lat else ""

    # ── Step 1: Get coordinates ────────────────────────────────
    if not (lat and lon):
        lat, lon, _ = geocode_location_free(location)

    # ── Step 2: OpenStreetMap Overpass live search ─────────────
    if lat and lon:
        try:
            osm_places = find_agri_places_osm(lat, lon, radius_m=20000)
            if osm_places:
                display_loc = location.title() if location else f"{lat:.3f}°S, {lon:.3f}°E"
                result  = f"📍 *AGRICULTURAL HELP NEAR YOU*{gps_note}\n"
                result += f"📡 Live map results — {display_loc}\n"
                result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for name, addr, ph in osm_places[:6]:
                    result += f"*{name}*\n📌 {addr}\n📞 {ph}\n\n"
                result += "━━━━━━━━━━━━━━━━━━━━━━\n"
                result += f"📞 Agritex Hotline: 0800 4040 (free)\n"
                result += f"📞 {COMPANY_NAME}: {SUPPORT_PHONE}"
                return result
        except Exception as e:
            print(f"Overpass help error: {e}")

    # ── Step 3: Resolve GPS to nearest town name ───────────────
    if lat and lon:
        nearest  = find_nearest_region(lat, lon)
        location = nearest["name"]

    # ── Step 4: Known contacts for main cities ─────────────────
    KNOWN_CENTERS = {
        "harare":    [
            ("🏛️ Agritex Head Office", "Borrowdale Rd",    "04-700181", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Harare",          "Willowvale Rd",    "04-621000", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank HQ",         "Jason Moyo Ave",   "04-700476", "Mon-Fri 8am-3:30pm"),
            ("🌱 Seedco HQ",           "Beatrice Rd",      "04-575111", "Mon-Fri 8am-5pm"),
            ("🛒 Farmer's World",      "Msasa Industrial", "04-447891", "Mon-Sat 7am-6pm"),
        ],
        "bulawayo":  [
            ("🏛️ Agritex Bulawayo", "Fort Street",      "09-888234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Bulawayo",     "Industrial Sites", "09-888100", "Mon-Sat 7am-5pm"),
            ("🏦 Agribank Byo",     "Fife Street",      "09-888476", "Mon-Fri 8am-3:30pm"),
        ],
        "mutare":    [
            ("🏛️ Agritex Manicaland", "Main Street", "020-64234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Mutare",          "Sakubva",     "020-64100", "Mon-Sat 7am-5pm"),
        ],
        "masvingo":  [
            ("🏛️ Agritex Masvingo", "Hughes Street",   "039-262234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Masvingo",     "Industrial Area", "039-262100", "Mon-Sat 7am-5pm"),
        ],
        "marondera": [
            ("🏛️ Agritex Mash East", "Main Road",        "079-23234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Marondera",     "Industrial Area",  "079-23100", "Mon-Sat 7am-5pm"),
            ("🧪 Marondera Soil Lab","Research Station", "079-22234", "Mon-Fri 8am-4pm"),
        ],
        "chinhoyi":  [
            ("🏛️ Agritex Mash West", "Main Road",       "067-22234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Chinhoyi",      "Industrial Area", "067-22100", "Mon-Sat 7am-5pm"),
        ],
        "gweru":     [
            ("🏛️ Agritex Midlands", "R Mugabe Way",    "054-222234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Gweru",        "Industrial Area", "054-222100", "Mon-Sat 7am-5pm"),
        ],
        "bindura":   [
            ("🏛️ Agritex Mash Central", "Main Road",       "071-22234", "Mon-Fri 8am-4pm"),
            ("🌾 GMB Bindura",           "Industrial Area", "071-22100", "Mon-Sat 7am-5pm"),
        ],
    }

    found = None
    for city, places in KNOWN_CENTERS.items():
        if city in location.lower():
            found = places
            break

    # ── Step 5: Groq for unknown towns ────────────────────────
    if not found:
        ai_help = ask_groq(
            f"List the nearest Agritex office, GMB depot, Agribank branch, and agro-dealer "
            f"to {location} Zimbabwe. Include street address and phone number for each.",
            "Zimbabwe agricultural services directory",
        )
        return f"""📍 *AGRICULTURAL HELP NEAR {location.upper()}*{gps_note}
━━━━━━━━━━━━━━━━━━━━━━

{ai_help}

━━━━━━━━━━━━━━━━━━━━━━
📞 Agritex Hotline: 0800 4040 (free)
📞 {COMPANY_NAME}: {SUPPORT_PHONE}"""

    result  = f"📍 *HELP NEAR {location.upper()}*{gps_note}\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for n, addr, ph, hrs in found:
        result += f"*{n}*\n📌 {addr}\n📞 {ph}\n🕐 {hrs}\n\n"
    result += f"📞 Agritex: 0800 4040 | {COMPANY_NAME}: {SUPPORT_PHONE}"
    return result


def initiate_payment(phone: str, plan: str) -> str:
    amount = "2" if plan == "premium" else "10"
    ref    = generate_ref(phone)
    payment_pending[ref] = {
        "phone":     phone,
        "plan":      plan,
        "amount":    amount,
        "initiated": datetime.datetime.now().isoformat(),
        "status":    "pending",
    }
    save_data()
    return f"""💳 *{BOT_NAME.upper()} SUBSCRIPTION*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Plan: *{plan.title()}* | Amount: *${amount}/month*
Reference: *{ref}*
━━━━━━━━━━━━━━━━━━━━━━
💚 *EcoCash:*
Dial *151# → Send Money
Number: *{ECOCASH_NUMBER}*
Amount: ${amount} | Ref: *{ref}*
━━━━━━━━━━━━━━━━━━━━━━
🔵 *OneMoney:*
Dial *111# → Send Money
Number: *{ONEMONEY_NUMBER}*
Amount: ${amount} | Ref: *{ref}*
━━━━━━━━━━━━━━━━━━━━━━
⚡ After payment reply: *PAID {ref}*
✅ Auto-verified in 5 minutes
📞 {SUPPORT_PHONE} | 📧 {SUPPORT_EMAIL}"""


def process_payment(phone: str, ref: str) -> str:
    expected = generate_ref(phone)
    if ref.upper() != expected.upper():
        return f"❌ Invalid reference.\nExpected: *{expected}*\n📞 {SUPPORT_PHONE}"

    pending = payment_pending.get(ref.upper(), payment_pending.get(ref, {}))
    plan    = pending.get("plan", "premium")
    amount  = pending.get("amount", "2")
    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()

    premium_users[phone] = {
        "active":      True,
        "plan":        plan,
        "amount":      amount,
        "activated":   datetime.datetime.now().isoformat(),
        "expires":     expires,
        "payment_ref": ref,
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
✅ Ref: *{ref}* | Plan: *{plan.upper()}*
✅ Amount: *${amount}* | Status: *ACTIVE*
✅ Valid: 30 days
━━━━━━━━━━━━━━━━━━━━━━
ALL PREMIUM FEATURES ACTIVE:
✅ GPS Precision Weather
✅ Photo Crop Analysis
✅ Live Market Prices
✅ Seed Brand Recommendations
✅ Find Help Near You
✅ Loan & Insurance Advisory
✅ Farm Planning Calendar
✅ Farmer Community Chat
✅ Full History & Activity Reports
✅ Priority AI Responses
━━━━━━━━━━━━━━━━━━━━━━
Type *MENU* to explore! 🌱🇿🇼"""


# ── Menus ──────────────────────────────────────────────────────
def get_location_menu() -> str:
    return f"""📍 *SET YOUR LOCATION*
━━━━━━━━━━━━━━━━━━━━━━

*🛰️ OPTION 1 — GPS* (Most Accurate)
📎 Tap attachment → Location
→ Send Current Location

*🏙️ OPTION 2 — Type Town Name*
Type: Marondera or Chinhoyi

*🗺️ OPTION 3 — Select Province*
1️⃣ Harare/Mashonaland East
2️⃣ Bulawayo/Matabeleland
3️⃣ Manicaland (Mutare/Chipinge)
4️⃣ Masvingo/Lowveld
5️⃣ Midlands (Gweru/Kwekwe)
6️⃣ Mashonaland West (Chinhoyi)
7️⃣ Mashonaland Central (Bindura)
8️⃣ Matabeleland North (Vic Falls)
9️⃣ Matabeleland South (Beitbridge)

💡 Type *LOCATION* anytime to update"""


def get_main_menu(phone: str) -> str:
    plan    = get_plan(phone)
    days    = get_trial_days_left(phone)
    stats   = get_user_stats(phone)
    profile = farmer_profiles.get(phone, {})

    if plan == "trial":
        badge = f"🎁 FREE TRIAL — {days} days left"
    elif plan == "business":
        badge = "🏆 BUSINESS PLAN"
    elif plan == "premium":
        badge = "⭐ PREMIUM"
    else:
        badge = "🆓 FREE PLAN"

    loc_line = ""
    if "gps_lat" in profile:
        nearest  = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
        loc_line = f"\n🛰️ GPS: {nearest['name'].title()} | Precision Active"
    elif "location" in profile:
        loc_line = f"\n📍 {profile['location'].title()}"

    return f"""🌱 *{BOT_NAME.upper()}* 🇿🇼
{COMPANY_NAME}
{badge}{loc_line}
⏱️ Day {stats['days_since_joining']} on AgroBot
━━━━━━━━━━━━━━━━━━━━━━

📋 *FREE SERVICES:*
1️⃣ 🌿 Crop Disease & Pest Advice
2️⃣ 🧪 Soil Health & Fertilizer
3️⃣ 🛒 Marketplace — Buy & Sell
4️⃣ 💬 Ask Any Farming Question
5️⃣ 📰 Free Farming News

━━━━━━━━━━━━━━━━━━━━━━

💎 *PREMIUM SERVICES:*
6️⃣ 🌤️ GPS Weather & Climate
7️⃣ 📸 Photo Crop Analysis
8️⃣ 📍 Find Help Near You
9️⃣ 💰 Live Market Prices
🔟 🏦 Loan & Insurance Advice

━━━━━━━━━━━━━━━━━━━━━━

👥 *COMMUNITY* — Farmer Chat
*SEEDS* — Seed Brand Recommendations

⚙️ 0️⃣ My Account & Stats
━━━━━━━━━━━━━━━━━━━━━━
*MENU* | *NEWS* | *PRICE [crop]*
*SEEDS [crop]* | *LOCATION* | *COMMUNITY*
📞 {SUPPORT_PHONE} | 🌐 {WEBSITE}"""


def get_premium_menu(phone: str) -> str:
    stats = get_user_stats(phone)
    plan  = get_plan(phone)

    if is_premium(phone):
        exp = premium_users[phone].get("expires", "")
        try:
            exp_str = datetime.datetime.fromisoformat(exp).strftime("%d %B %Y")
        except Exception:
            exp_str = "30 days"
        return f"""⭐ *YOUR AGROBOT ACCOUNT*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Plan: *{plan.upper()}* ✅ ACTIVE
Expires: {exp_str}
Member for: {stats['days_since_joining']} days
Messages sent: {stats['total_messages']}
━━━━━━━━━━━━━━━━━━━━━━
All premium features active!
Type *MENU* to use them.
📞 {SUPPORT_PHONE}"""

    if plan == "trial":
        return f"""🎁 *FREE TRIAL ACTIVE*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
⏳ *{stats['trial_days_left']} days remaining*
Trial ends: {stats['trial_end_date']}
Member for: {stats['days_since_joining']} days

Subscribe before trial ends:

💎 *PREMIUM — $2/month*
All premium features

🏆 *BUSINESS — $10/month*
Premium + Export connections
+ Dedicated AI consultant
+ Custom reports

Reply *1* — Premium ($2/month)
Reply *2* — Business ($10/month)
Reply *0* — Back"""

    return f"""⭐ *UPGRADE TO {BOT_NAME.upper()} PRO*
{COMPANY_NAME}
Member for: {stats['days_since_joining']} days
━━━━━━━━━━━━━━━━━━━━━━

*🆓 FREE:* Basic advice + News + Community

*💎 PREMIUM — $2/month:*
🌤️ GPS precision weather
📸 Photo crop analysis
📍 Find help near you
💰 Live market prices
🌱 Seed brand recommendations
🏦 Loan & insurance advice
📅 Farm planning calendar
🌍 Climate change advisory
📊 Full history & activity reports
⚡ Priority AI responses

*🏆 BUSINESS — $10/month:*
✅ Everything in Premium PLUS:
👨‍💼 Dedicated AI farm consultant
🌍 Export market connections
📦 Bulk buyer/seller matching
📋 Custom weekly farm reports
🏗️ Multiple farm management
📱 Priority phone support

🎁 *{TRIAL_DAYS}-DAY FREE TRIAL INCLUDED!*

Reply *1* — Premium ($2/month)
Reply *2* — Business ($10/month)
Reply *0* — Back
━━━━━━━━━━━━━━━━━━━━━━
📞 {SUPPORT_PHONE} | 📧 {SUPPORT_EMAIL}"""


def get_marketplace_menu() -> str:
    total = len(marketplace) + len(buyer_requests)
    return f"""🛒 *AGROBOT MARKETPLACE*
{COMPANY_NAME} | {total} Active Listings
━━━━━━━━━━━━━━━━━━━━━━
1️⃣ Post SELL listing
2️⃣ Post BUY request
3️⃣ Browse Sellers
4️⃣ Browse Buyer Requests
5️⃣ Search Items
0️⃣ ◀️ Back
━━━━━━━━━━━━━━━━━━━━━━
🌐 {WEBSITE}/marketplace"""


def get_account_menu(phone: str) -> str:
    stats = get_user_stats(phone)
    plan  = get_plan(phone)
    days_left = get_trial_days_left(phone)

    if is_premium(phone):
        exp = premium_users[phone].get("expires", "")
        try:
            exp_str = datetime.datetime.fromisoformat(exp).strftime("%d %B %Y")
        except Exception:
            exp_str = "30 days"
        plan_info = f"⭐ *{plan.upper()}* — Active until {exp_str}"
    elif plan == "trial":
        plan_info = f"🎁 *FREE TRIAL* — {days_left} days left (ends {stats['trial_end_date']})"
    else:
        plan_info = "🆓 *FREE PLAN* — Trial expired"

    streak       = stats.get("streak_days", 0)
    streak_emoji = "🔥" if streak >= 7 else "✅" if streak >= 3 else "📅"

    return f"""📊 *MY AGROBOT ACCOUNT*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

👤 *Profile:*
📍 Location: {stats['location'].title()}
📅 Member since: {stats['joined']}
⏱️ Days on AgroBot: *{stats['days_since_joining']} days*

━━━━━━━━━━━━━━━━━━━━━━
💎 *Subscription:*
{plan_info}

━━━━━━━━━━━━━━━━━━━━━━
📈 *Your Activity:*
💬 Total messages: {stats['total_messages']}
📅 Days active: {stats['total_days_active']}
{streak_emoji} Streak: {stats['streak_days']} days
🌐 Conversations: {stats['conversations']}
🛒 Marketplace posts: {stats['marketplace_posts']}
👥 Community posts: {stats['community_posts']}

━━━━━━━━━━━━━━━━━━━━━━
Reply:
1️⃣ Upgrade/Subscribe
2️⃣ View Conversation History
3️⃣ My Marketplace Posts
4️⃣ Set My Name
0️⃣ Back to Menu"""


# ══════════════════════════════════════════════════════════════
# ── PROCESS MESSAGE ────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

def process_message(from_number: str, msg_text: str) -> str:
    msg   = msg_text.strip()
    state = user_states.get(from_number, "menu")

    track_activity(from_number, "message")
    save_conversation(from_number, "farmer", msg_text)

    # ── GLOBAL COMMANDS ──────────────────────────────────────
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
    if msg.upper() == "COMMUNITY":
        user_states[from_number] = "community"
        return get_community_menu()
    if msg.upper() == "HISTORY":
        return get_user_history(from_number)
    if msg.upper() == "STATS":
        return get_account_menu(from_number)

    if msg.upper().startswith("PRICE "):
        crop   = msg.split(" ", 1)[1].strip()
        profile = farmer_profiles.get(from_number, {})
        prices = get_sync_prices()
        adj    = REGIONAL_PRICE_ADJ.get(profile.get("location", "").lower(), {})
        trends = {"rising": "📈", "falling": "📉", "stable": "➡️"}
        c = crop.lower().replace(" ", "_")
        p = prices.get(c, prices.get(crop.lower()))
        if p:
            local = round(p["price"] * adj.get(crop.lower(), 1.0), 2)
            icon  = trends.get(p.get("trend", "stable"), "➡️")
            return f"""💰 *{crop.upper()} LIVE PRICE*
📡 {p.get('source','Live Data')} | {p.get('updated','Today')}
━━━━━━━━━━━━━━━━━━━━━━
{icon} Trend: {p.get('trend','stable').upper()}
💵 Price: *${p['price']}/{p['unit']}*
📍 Local: *${local}/{p['unit']}*
Type *MENU* to return"""
        return f"No live price for '{crop}'. Try: PRICE MAIZE\nType *MENU* to return."

    if msg.upper().startswith("SEEDS"):
        profile  = farmer_profiles.get(from_number, {})
        location = profile.get("location", "harare")
        parts    = msg.split(" ", 1)
        crop     = parts[1].strip() if len(parts) > 1 else ""
        return get_seed_recommendations(location, crop)

    if msg.upper().startswith("PAID "):
        ref = msg.split(" ", 1)[1].strip()
        return process_payment(from_number, ref)

    # ── NEW FARMER ────────────────────────────────────────────
    if from_number not in farmer_profiles:
        if msg.lower() in ["hi", "hello", "hey", "start", "help", "0", "00"]:
            user_states[from_number] = "register_location"
            return f"""🌱 *WELCOME TO {BOT_NAME.upper()}!* 🇿🇼
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Zimbabwe's Most Advanced AI Farming Assistant

🎁 *SPECIAL WELCOME OFFER:*
Get *{TRIAL_DAYS} DAYS FREE* access to ALL premium features!

✅ No payment required
✅ All features unlocked immediately

━━━━━━━━━━━━━━━━━━━━━━
Please set your location:

{get_location_menu()}"""
        else:
            user_states[from_number] = "register_location"
            return f"🌱 *Welcome to {BOT_NAME}!*\n\nPlease set your location:\n\n{get_location_menu()}"

    # ── LOCATION STATES ───────────────────────────────────────
    elif state in ["register_location", "update_location"]:
        is_new        = state == "register_location"
        location      = PROVINCE_DEFAULTS.get(msg, msg.lower())
        province_name = PROVINCE_NAMES.get(msg, msg.title())
        save_location(from_number, location)
        info = get_region_info(location)
        user_states[from_number] = "menu"

        top_seed_info = ""
        region_key    = f"Region {info['region']}"
        maize_seeds   = SEED_BRANDS.get("maize", {}).get(region_key, [])
        if maize_seeds:
            top = maize_seeds[0]
            top_seed_info = f"\n🌱 Top seed for your area: *{top['brand']} {top['variety']}*"

        trial_msg = ""
        if is_new:
            trial_msg = f"\n\n🎁 *{TRIAL_DAYS}-DAY FREE TRIAL STARTED!*\nAll features unlocked!\nType *SEEDS* for seed recommendations!"

        return f"""✅ *LOCATION SET: {province_name}*
━━━━━━━━━━━━━━━━━━━━━━
📍 {location.title()}
🌤️ Region {info['region']} — {info['climate']}
🌧️ Rainfall: {info['rainfall']}
🌱 Best Crops: {info['best_crops']}
🏔️ Soil: {info.get('soil', 'Mixed')}
📅 Season: {info.get('season', 'Nov-Apr')}
⚠️ Challenges: {info.get('challenges', 'Variable weather')}{top_seed_info}
{trial_msg}

💡 Type *SEEDS* for seed brand recommendations!
📎 Share GPS for farm-specific advice

{get_main_menu(from_number)}"""

    # ── IMAGE DESCRIBE STATE ──────────────────────────────────
    elif state == "image_describe":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "crop disease and pest diagnosis based on farmer description, Zimbabwe context",
            phone=from_number)
        return f"""🌿 *DIAGNOSIS FROM DESCRIPTION*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
📸 Send another photo for visual confirmation
📞 Agritex Plant Clinic: 0800 4040
Type *MENU* to return"""

    # ── COMMUNITY STATES ──────────────────────────────────────
    elif state == "community":
        if msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        elif msg in ["1","2","3","4","5","6","7"]:
            channels = ["general","maize","tobacco","livestock","horticulture","weather","prices"]
            channel  = channels[int(msg) - 1]
            user_states[from_number] = f"community_channel_{channel}"
            return get_channel_posts(channel)
        elif msg == "8":
            user_states[from_number] = "community_post_select"
            return """📢 *POST TO COMMUNITY*
━━━━━━━━━━━━━━━━━━━━━━
Select channel:
1️⃣ 🌍 General | 2️⃣ 🌽 Maize
3️⃣ 🍂 Tobacco | 4️⃣ 🐄 Livestock
5️⃣ 🥬 Horticulture | 6️⃣ 🌧️ Weather
7️⃣ 💰 Prices | 0️⃣ Back"""
        elif msg == "9":
            all_posts = sorted(community_posts, key=lambda x: x.get("timestamp",""), reverse=True)
            if not all_posts:
                return "📭 No posts yet.\nType *COMMUNITY* to go back."
            result = "📋 *LATEST POSTS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for post in all_posts[:8]:
                ph       = post.get("phone","")
                p        = farmer_profiles.get(ph, {})
                name     = p.get("name", f"Farmer {ph[-4:]}")
                loc      = p.get("location","Zimbabwe").title()
                ch       = post.get("channel","general").title()
                time_str = post.get("timestamp","")[:16].replace("T"," ")
                result  += f"*#{ch}* | 👤 {name} — {loc}\n⏰ {time_str}\n💬 {post.get('message','')[:100]}\n\n"
            result += "Type *COMMUNITY* for channels\nType *MENU* to return"
            return result
        elif msg == "10":
            stats   = get_user_stats(from_number)
            profile = farmer_profiles.get(from_number, {})
            return f"""👤 *MY COMMUNITY PROFILE*
━━━━━━━━━━━━━━━━━━━━━━
Name: {profile.get('name', f'Farmer {from_number[-4:]}')}
Location: {stats['location'].title()}
Member since: {stats['joined']}
Days on AgroBot: {stats['days_since_joining']}
Posts: {stats['community_posts']}
Plan: {stats['plan'].upper()}
Type *COMMUNITY* to go back"""
        return get_community_menu()

    elif state.startswith("community_channel_"):
        channel = state.replace("community_channel_", "")
        if msg.upper() in ["BACK", "0", "COMMUNITY"]:
            user_states[from_number] = "community"
            return get_community_menu()
        result = post_to_community(from_number, channel, msg)
        user_states[from_number] = "menu"
        return result

    elif state == "community_post_select":
        channel_map = {"1":"general","2":"maize","3":"tobacco","4":"livestock","5":"horticulture","6":"weather","7":"prices"}
        if msg in channel_map:
            channel = channel_map[msg]
            ch_name = community_channels.get(channel, {}).get("name", channel.title())
            user_states[from_number] = f"community_posting_{channel}"
            return f"""✍️ *POST TO {ch_name.upper()}*
━━━━━━━━━━━━━━━━━━━━━━
Type your message now.
All AgroBot farmers will see it!"""
        elif msg == "0":
            user_states[from_number] = "community"
            return get_community_menu()
        return "Reply 1-7 or 0 to go back."

    elif state.startswith("community_posting_"):
        channel = state.replace("community_posting_", "")
        result  = post_to_community(from_number, channel, msg)
        user_states[from_number] = "menu"
        return result

    # ── MENU STATE ────────────────────────────────────────────
    elif state == "menu":
        if msg.lower() in ["hi","hello","hey","start","help"]:
            return get_main_menu(from_number)

        elif msg == "1":
            user_states[from_number] = "disease"
            track_activity(from_number, "disease_query")
            profile  = farmer_profiles.get(from_number, {})
            loc      = profile.get("location","")
            loc_note = f"\n📍 Personalised for {loc.title()}" if loc else ""
            return f"""🌿 *CROP DISEASE & PEST ADVISORY*{loc_note}
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Describe your problem in detail:
🌱 What crop is affected?
🔍 What symptoms do you see?
📏 How much is affected?
📅 When did you first notice?
💊 Any treatments applied?

📸 *OR send a PHOTO* for visual diagnosis!"""

        elif msg == "2":
            user_states[from_number] = "soil"
            return f"""🧪 *SOIL HEALTH & FERTILITY ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

For professional analysis tell me:
🎨 Soil colour | 👆 Texture
💧 Drainage | 🌿 Previous crop
🌱 Next crop | 📏 Field size (acres)

💡 Soil Lab: 079-22234"""

        elif msg == "3":
            user_states[from_number] = "marketplace"
            track_activity(from_number, "marketplace")
            return get_marketplace_menu()

        elif msg == "4":
            user_states[from_number] = "freeask"
            return f"""💬 *ASK {BOT_NAME.upper()} ANYTHING*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Ask about crops, pests, soil, irrigation,
livestock, markets, technology — anything!"""

        elif msg == "5":
            track_activity(from_number, "news")
            return get_farming_news(from_number)

        elif msg == "6":
            gate = premium_gate(from_number, "GPS Weather & Climate Forecast")
            if gate:
                return gate
            track_activity(from_number, "weather")
            profile = farmer_profiles.get(from_number, {})
            if "gps_lat" in profile:
                nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
                return get_weather(profile["gps_lat"], profile["gps_lon"],
                                   f"{nearest['name'].title()} (GPS)")
            elif "location" in profile:
                return get_weather_by_name(profile["location"])
            else:
                user_states[from_number] = "weather"
                return f"🌤️ *Weather*\n\nSet location:\n\n{get_location_menu()}"

        elif msg == "7":
            gate = premium_gate(from_number, "Photo Crop Disease Analysis")
            if gate:
                return gate
            user_states[from_number] = "image_prompt"
            return f"""📸 *PHOTO CROP DISEASE ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Send a clear photo of your affected crop!

📷 Tips for best accuracy:
✅ Good natural lighting
✅ Close enough to see symptoms
✅ Steady camera — no blur

Send your photo now!"""

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
                return f"📍 *Find Help*\n\nSet location:\n\n{get_location_menu()}"

        elif msg == "9":
            gate = premium_gate(from_number, "Live Regional Market Prices")
            if gate:
                return gate
            profile  = farmer_profiles.get(from_number, {})
            track_activity(from_number, "market_prices")
            prices   = get_sync_prices()
            location = profile.get("location", "")
            adj      = REGIONAL_PRICE_ADJ.get(location.lower(), {})
            trends   = {"rising": "📈", "falling": "📉", "stable": "➡️"}
            now      = datetime.datetime.now()

            result = f"""💰 *LIVE MARKET PRICES*
{COMPANY_NAME}
📍 {location.title() if location else 'Zimbabwe'}
🕐 {now.strftime('%d %b %Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━

🌾 *GRAINS:*"""
            for c in ["maize","wheat","soya","sorghum","groundnuts"]:
                p = prices.get(c)
                if p:
                    local = round(p["price"] * adj.get(c, 1.0), 2)
                    result += f"\n{trends.get(p.get('trend','stable'),'➡️')} {c.title()}: *${local}/{p['unit']}*"
            result += "\n\n🌿 *CASH CROPS:*"
            for c in ["tobacco","cotton","sugar_beans"]:
                p = prices.get(c)
                if p:
                    result += f"\n{trends.get(p.get('trend','stable'),'➡️')} {c.replace('_',' ').title()}: *${p['price']}/{p['unit']}*"
            result += "\n\n🥬 *HORTICULTURE:*"
            for c in ["tomatoes","onions","potatoes"]:
                p = prices.get(c)
                if p:
                    local = round(p["price"] * adj.get(c, 1.0), 2)
                    result += f"\n{trends.get(p.get('trend','stable'),'➡️')} {c.title()}: *${local}/{p['unit']}*"
            result += f"""

━━━━━━━━━━━━━━━━━━━━━━
⏰ Prices updated every 6 hours
Type *PRICE [crop]* for detailed report
Type *MENU* to return"""
            return result

        elif msg == "10":
            gate = premium_gate(from_number, "Loan & Insurance Advisory")
            if gate:
                return gate
            user_states[from_number] = "loan"
            return f"""🏦 *AGRICULTURAL FINANCE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

I advise on:
💳 Loans (Agribank, CBZ, ZB, AFC)
🛡️ Crop & livestock insurance
📊 Farm financial planning
💰 Government subsidies & grants

Tell me your farm situation:
- Farm size (acres/ha)
- Main crops you grow
- What you need (loan/insurance/both)
- Annual turnover (approximate)"""

        elif msg == "0":
            user_states[from_number] = "account"
            return get_account_menu(from_number)

        else:
            reply = ask_groq(msg, phone=from_number)
            return f"""💬 *{BOT_NAME.upper()} ADVICE*
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
Type *SEEDS [crop]* for seed brands
Type *MENU* | 📞 {SUPPORT_PHONE}"""

    # ── ACCOUNT STATE ─────────────────────────────────────────
    elif state == "account":
        if msg == "1":
            user_states[from_number] = "subscribe"
            return get_premium_menu(from_number)
        elif msg == "2":
            user_states[from_number] = "menu"
            return get_user_history(from_number)
        elif msg == "3":
            posts = [x for x in marketplace if x.get("poster") == from_number]
            if not posts:
                user_states[from_number] = "menu"
                return "📭 No marketplace posts yet.\nType *MENU* to return."
            result = "🛒 *MY LISTINGS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for p in posts[-5:]:
                result += f"📦 {p['item']}\n💰 {p['price']}\n📍 {p['location']}\n📅 {p.get('timestamp','')[:10]}\n\n"
            user_states[from_number] = "menu"
            return result + "Type *MENU* to return"
        elif msg == "4":
            user_states[from_number] = "set_name"
            return "👤 *Set Your Name*\n\nWhat name should AgroBot use?\nExample: John Moyo"
        elif msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        return get_account_menu(from_number)

    elif state == "set_name":
        farmer_profiles[from_number]["name"] = msg
        if from_number in user_accounts:
            user_accounts[from_number]["name"] = msg
        save_data()
        user_states[from_number] = "menu"
        return f"✅ *Name saved: {msg}*\n\nType *MENU* to return."

    elif state == "disease":
        user_states[from_number] = "menu"
        track_activity(from_number, "disease_query")
        reply = ask_groq(msg,
            "Crop disease diagnosis: scientific name, symptoms, Zimbabwe-brand treatment, rates, timing, cost USD",
            phone=from_number)
        return f"""🌿 *PROFESSIONAL DISEASE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
🛒 Agricura: 04-621567 | ZFC: 04-700751
📞 Agritex: 0800 4040
Type *MENU* to return"""

    elif state == "soil":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "Soil analysis: pH, ZFC fertilizer rates (kg/ha), lime requirements, best crops, cost USD",
            phone=from_number)
        return f"""🧪 *SOIL ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
🔬 Soil Lab: 079-22234 | ZFC: 04-700751
Type *MENU* to return"""

    elif state == "freeask":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, phone=from_number)
        return f"""💬 *{BOT_NAME.upper()} ADVICE*
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
Type *SEEDS [crop]* for seed brands
Type *MENU* | 📞 {SUPPORT_PHONE}"""

    elif state == "weather":
        user_states[from_number] = "menu"
        location = PROVINCE_DEFAULTS.get(msg, msg)
        return get_weather_by_name(location)

    elif state == "location_help":
        user_states[from_number] = "menu"
        return find_help_nearby(PROVINCE_DEFAULTS.get(msg, msg))

    elif state == "loan":
        user_states[from_number] = "menu"
        reply = ask_groq(msg,
            "Agricultural finance: Agribank/CBZ/ZB/AFC loans, interest rates, crop insurance Zimbabwe, government subsidies",
            phone=from_number)
        return f"""🏦 *FINANCE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
📞 Agribank: 04-700476 | CBZ: 04-250579
Type *MENU* to return"""

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

    # ── MARKETPLACE ───────────────────────────────────────────
    elif state == "marketplace":
        if msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu(from_number)
        elif msg == "1":
            user_states[from_number] = "post_sell_type"
            return "📢 *POST SELL*\n1️⃣ Crops\n2️⃣ Fertilizer\n3️⃣ Equipment\n4️⃣ Livestock\n5️⃣ Other\n0️⃣ Back"
        elif msg == "2":
            user_states[from_number] = "post_buy_item"
            return "🤝 *POST BUY REQUEST*\nWhat do you want to BUY?\nBe specific: name + quantity + quality"
        elif msg == "3":
            sellers = [x for x in marketplace if x.get("type") == "seller"]
            if not sellers:
                return "📭 No sellers yet.\nType *MENU* to return."
            result = "🏪 *SELLERS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, x in enumerate(sellers[-10:], 1):
                result += f"*{i}.* 📦 {x['item']}\n📍 {x['location']}\n💰 {x['price']}\n📞 {x['phone']}\n\n"
            return result + "Type *MENU* to return"
        elif msg == "4":
            if not buyer_requests:
                return "📭 No buyer requests.\nType *MENU* to return."
            result = "🤝 *BUYER REQUESTS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, x in enumerate(buyer_requests[-10:], 1):
                result += f"*{i}.* WANTED: {x.get('item','?')}\nQty: {x.get('quantity','Flex')}\n💰 {x.get('budget','Negotiable')}\n📞 {x['phone']}\n\n"
            return result + "Type *MENU* to return"
        elif msg == "5":
            user_states[from_number] = "search_marketplace"
            return "🔍 Type what you are looking for:"
        return get_marketplace_menu()

    elif state == "post_sell_type":
        cats = {"1":"Crops & Grains","2":"Fertilizer & Chemicals","3":"Farm Equipment","4":"Livestock","5":"Other"}
        if msg in cats:
            user_states[from_number] = f"post_sell_item_{cats[msg]}"
            return f"📦 *{cats[msg]}*\nDescribe what you are selling:\nName + Quantity + Condition"
        elif msg == "0":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()
        return "Reply 1-5 or 0"

    elif state.startswith("post_sell_item_"):
        cat = state.replace("post_sell_item_", "")
        user_states[from_number] = f"post_sell_loc_{cat}_{msg}"
        profile = farmer_profiles.get(from_number, {})
        saved   = profile.get("location", "")
        hint    = f"Saved: *{saved.title()}* — confirm or type new:" if saved else "Type your location:"
        return f"📍 *LOCATION*\n{hint}"

    elif state.startswith("post_sell_loc_"):
        parts = state.replace("post_sell_loc_", "").split("_", 1)
        cat   = parts[0]
        item  = parts[1] if len(parts) > 1 else "Unknown"
        user_states[from_number] = f"post_sell_price_{cat}_{item}_{msg}"
        return "💰 *ASKING PRICE*\nExample: $50/bag | $285/tonne | Negotiable"

    elif state.startswith("post_sell_price_"):
        parts = state.replace("post_sell_price_", "").split("_", 2)
        cat   = parts[0]
        item  = parts[1] if len(parts) > 1 else "Unknown"
        loc   = parts[2] if len(parts) > 2 else "Unknown"
        user_states[from_number] = f"post_sell_phone_{cat}_{item}_{loc}_{msg}"
        return "📞 *CONTACT NUMBER*\nBuyers will call/WhatsApp this:"

    elif state.startswith("post_sell_phone_"):
        parts = state.replace("post_sell_phone_", "").split("_", 3)
        cat   = parts[0]
        item  = parts[1] if len(parts) > 1 else "Unknown"
        loc   = parts[2] if len(parts) > 2 else "Unknown"
        price = parts[3] if len(parts) > 3 else "Negotiable"
        listing = {
            "type":      "seller",
            "category":  cat,
            "item":      item,
            "location":  loc,
            "price":     price,
            "phone":     msg,
            "poster":    from_number,
            "timestamp": datetime.datetime.now().isoformat(),
            "status":    "active",
        }
        marketplace.append(listing)
        save_data()
        track_activity(from_number, "marketplace_post")
        user_states[from_number] = "menu"
        return f"✅ *LISTING POSTED!*\n📦 {item} | 📍 {loc} | 💰 {price}\n📞 {msg}\nType *MENU* to return."

    elif state == "post_buy_item":
        user_states[from_number] = f"post_buy_qty_{msg}"
        return f"📦 Want: *{msg}*\nHow much quantity do you need?"

    elif state.startswith("post_buy_qty_"):
        item = state.replace("post_buy_qty_", "")
        user_states[from_number] = f"post_buy_budget_{item}_{msg}"
        return "💰 Your budget?\nExample: $45/bag | Up to $280/tonne | Negotiable"

    elif state.startswith("post_buy_budget_"):
        parts  = state.replace("post_buy_budget_", "").split("_", 1)
        item   = parts[0]
        qty    = parts[1] if len(parts) > 1 else "Flexible"
        user_states[from_number] = f"post_buy_loc_{item}_{qty}_{msg}"
        return "📍 Your location?\nExample: Harare CBD"

    elif state.startswith("post_buy_loc_"):
        parts  = state.replace("post_buy_loc_", "").split("_", 2)
        item   = parts[0]
        qty    = parts[1] if len(parts) > 1 else "Flexible"
        budget = parts[2] if len(parts) > 2 else "Negotiable"
        user_states[from_number] = f"post_buy_phone_{item}_{qty}_{budget}_{msg}"
        return "📞 Your contact number?\nSellers will call/WhatsApp you."

    elif state.startswith("post_buy_phone_"):
        parts  = state.replace("post_buy_phone_", "").split("_", 3)
        item   = parts[0]
        qty    = parts[1] if len(parts) > 1 else "Flexible"
        budget = parts[2] if len(parts) > 2 else "Negotiable"
        loc    = parts[3] if len(parts) > 3 else "Zimbabwe"
        req = {
            "type":      "buyer",
            "item":      item,
            "quantity":  qty,
            "budget":    budget,
            "location":  loc,
            "phone":     msg,
            "poster":    from_number,
            "timestamp": datetime.datetime.now().isoformat(),
            "status":    "active",
        }
        buyer_requests.append(req)
        save_data()
        track_activity(from_number, "buy_request")
        user_states[from_number] = "menu"
        return f"✅ *BUY REQUEST POSTED!*\nWANTED: *{item}* | Qty: {qty}\nSellers will contact {msg}!\nType *MENU* to return."

    elif state == "search_marketplace":
        user_states[from_number] = "menu"
        q       = msg.lower()
        sellers = [x for x in marketplace     if q in x.get("item","").lower() or q in x.get("category","").lower()]
        buyers  = [x for x in buyer_requests  if q in x.get("item","").lower()]
        if not sellers and not buyers:
            return f"📭 No results for '{msg}'.\nType *MENU* to return."
        result = f"🔍 *{msg.upper()}*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if sellers:
            result += "🏪 *SELLERS:*\n"
            for x in sellers[-5:]:
                result += f"📦 {x['item']}\n📍 {x['location']}\n💰 {x['price']}\n📞 {x['phone']}\n\n"
        if buyers:
            result += "🤝 *BUYERS:*\n"
            for x in buyers[-5:]:
                result += f"📦 {x['item']} | {x.get('quantity','Flex')}\n💰 {x.get('budget','Neg')}\n📞 {x['phone']}\n\n"
        return result + "Type *MENU* to return"

    else:
        user_states[from_number] = "menu"
        return get_main_menu(from_number)


def get_user_history(phone: str) -> str:
    history = conversations.get(phone, [])
    stats   = get_user_stats(phone)

    if not history:
        return "📭 No conversation history yet.\nType *MENU* to return."

    result = f"""📋 *MY CONVERSATION HISTORY*
{COMPANY_NAME}
Total: {len(history)} messages
Member for: {stats['days_since_joining']} days
━━━━━━━━━━━━━━━━━━━━━━

"""
    for msg in history[-10:]:
        role    = "👤 You" if msg["role"] == "farmer" else "🤖 AgroBot"
        t       = msg.get("timestamp","")[:16].replace("T"," ")
        message = msg.get("message","")[:100]
        if len(msg.get("message","")) > 100:
            message += "..."
        result += f"*{role}* | {t}\n{message}\n\n"

    result += f"""━━━━━━━━━━━━━━━━━━━━━━
📊 Stats:
⏱️ Member: {stats['days_since_joining']} days
💬 Messages: {stats['total_messages']}
📅 Days active: {stats['total_days_active']}
Type *MENU* to return"""
    return result


# ══════════════════════════════════════════════════════════════
# ── WEBSOCKET — REAL-TIME COMMUNITY CHAT ──────────────────────
# ══════════════════════════════════════════════════════════════

@app.websocket("/ws/community/{channel}/{phone}")
async def websocket_community(websocket: WebSocket, channel: str, phone: str):
    await manager.connect(websocket, channel, phone)

    profile  = farmer_profiles.get(phone, {})
    name     = profile.get("name", f"Farmer {phone[-4:]}")
    location = profile.get("location", "Zimbabwe").title()
    ch_data  = community_channels.get(channel, {})
    ch_name  = ch_data.get("name", channel.title())
    recent   = ch_data.get("messages", [])[-20:]

    await manager.send_personal_message({
        "type":           "welcome",
        "channel":        channel,
        "channel_name":   ch_name,
        "user":           {"name": name, "location": location, "phone": phone},
        "recent_messages":recent,
        "online_count":   len(manager.active_connections.get(channel, [])),
    }, websocket)

    await manager.broadcast_to_channel(channel, {
        "type":         "user_joined",
        "name":         name,
        "location":     location,
        "timestamp":    datetime.datetime.now().isoformat(),
        "online_count": len(manager.active_connections.get(channel, [])),
    })

    try:
        while True:
            data     = await websocket.receive_json()
            msg_text = data.get("message", "").strip()
            if not msg_text:
                continue

            post = {
                "id":        secrets.token_hex(8),
                "phone":     phone,
                "name":      name,
                "location":  location,
                "channel":   channel,
                "message":   msg_text,
                "timestamp": datetime.datetime.now().isoformat(),
                "likes":     0,
            }

            community_posts.append(post)
            community_channels.setdefault(channel, {"messages": []})
            community_channels[channel]["messages"].append(post)
            if len(community_channels[channel]["messages"]) > 200:
                community_channels[channel]["messages"] = community_channels[channel]["messages"][-200:]

            save_data()
            track_activity(phone, "community_chat")

            await manager.broadcast_to_channel(channel, {
                "type":      "message",
                "id":        post["id"],
                "phone":     phone,
                "name":      name,
                "location":  location,
                "message":   msg_text,
                "timestamp": post["timestamp"],
                "channel":   channel,
            })

            if msg_text.lower().startswith("@agrobot"):
                question = msg_text[8:].strip()
                if question:
                    ai_response = ask_groq(question, phone=phone)
                    await manager.broadcast_to_channel(channel, {
                        "type":      "bot_message",
                        "name":      f"🤖 {BOT_NAME}",
                        "location":  "AI Assistant",
                        "message":   ai_response,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "channel":   channel,
                    })

    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
        await manager.broadcast_to_channel(channel, {
            "type":         "user_left",
            "name":         name,
            "timestamp":    datetime.datetime.now().isoformat(),
            "online_count": len(manager.active_connections.get(channel, [])),
        })


@app.get("/ws/community/channels")
async def get_ws_channels():
    result = {}
    for ch_id, ch_data in community_channels.items():
        result[ch_id] = {
            "name":          ch_data.get("name", ch_id),
            "description":   ch_data.get("description", ""),
            "total_messages":len(ch_data.get("messages", [])),
            "online_now":    len(manager.active_connections.get(ch_id, [])),
            "members":       manager.get_channel_members(ch_id),
        }
    return JSONResponse(result)


# ══════════════════════════════════════════════════════════════
# ── REST API ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/register")
async def register_user(request: Request):
    body  = await request.json()
    phone = body.get("phone", "").strip()
    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)

    if phone not in user_accounts:
        user_accounts[phone] = {
            "phone":     phone,
            "name":      body.get("name",""),
            "email":     body.get("email",""),
            "google_id": body.get("google_id",""),
            "platforms": [body.get("platform","web")],
            "registered":datetime.datetime.now().isoformat(),
        }
    else:
        for f in ["name","email","google_id"]:
            if body.get(f):
                user_accounts[phone][f] = body[f]
        plat = body.get("platform","web")
        if plat not in user_accounts[phone].get("platforms",[]):
            user_accounts[phone].setdefault("platforms",[]).append(plat)

    if body.get("name") and phone in farmer_profiles:
        farmer_profiles[phone]["name"] = body["name"]

    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
    user_accounts[phone]["last_token"] = token
    track_activity(phone, "login")
    save_data()

    stats = get_user_stats(phone)
    return JSONResponse({
        "success":        True,
        "token":          token,
        "phone":          phone,
        "profile":        farmer_profiles.get(phone, {}),
        "account":        user_accounts.get(phone, {}),
        "premium":        is_premium(phone),
        "plan":           get_plan(phone),
        "trial_days_left":get_trial_days_left(phone),
        "stats":          stats,
        "conversations":  conversations.get(phone, [])[-20:],
    })


@app.get("/api/farmer/{phone}")
async def get_farmer(phone: str):
    if phone not in farmer_profiles:
        return JSONResponse({"error": "Farmer not found"}, status_code=404)
    stats = get_user_stats(phone)
    return JSONResponse({
        "phone":           phone,
        "profile":         farmer_profiles[phone],
        "account":         user_accounts.get(phone, {}),
        "activity":        user_activity.get(phone, {}),
        "stats":           stats,
        "region_info":     get_region_info(farmer_profiles[phone].get("location","")),
        "is_premium":      is_premium(phone),
        "plan":            get_plan(phone),
        "trial_days_left": get_trial_days_left(phone),
    })


@app.get("/api/farmer/{phone}/conversations")
async def get_conversations(phone: str, limit: int = 50):
    return JSONResponse({
        "phone":         phone,
        "total":         len(conversations.get(phone, [])),
        "conversations": conversations.get(phone, [])[-limit:],
    })


@app.get("/api/farmer/{phone}/activity")
async def get_activity(phone: str):
    stats    = get_user_stats(phone)
    activity = user_activity.get(phone, {})
    return JSONResponse({
        "phone":          phone,
        "stats":          stats,
        "daily_activity": activity.get("daily_activity", {}),
        "actions":        activity.get("actions", {}),
        "streak_days":    activity.get("streak_days", 0),
    })


@app.get("/api/community")
async def get_community_api(channel: str = "", limit: int = 20):
    if channel and channel in community_channels:
        posts = community_channels[channel].get("messages", [])[-limit:]
        return JSONResponse({
            "channel":      channel,
            "name":         community_channels[channel].get("name",""),
            "total":        len(community_channels[channel].get("messages",[])),
            "online":       len(manager.active_connections.get(channel,[])),
            "posts":        posts,
        })
    all_posts = sorted(community_posts, key=lambda x: x.get("timestamp",""), reverse=True)
    return JSONResponse({
        "total_posts": len(all_posts),
        "channels": {
            k: {
                "name":   v.get("name",""),
                "total":  len(v.get("messages",[])),
                "online": len(manager.active_connections.get(k,[])),
            } for k, v in community_channels.items()
        },
        "recent_posts": all_posts[:limit],
    })


@app.post("/api/community/post")
async def api_post_community(request: Request):
    body    = await request.json()
    phone   = body.get("phone","")
    channel = body.get("channel","general")
    message = body.get("message","")
    if not phone or not message:
        return JSONResponse({"error": "phone and message required"}, status_code=400)

    post_to_community(phone, channel, message)

    profile = farmer_profiles.get(phone, {})
    await manager.broadcast_to_channel(channel, {
        "type":      "message",
        "phone":     phone,
        "name":      profile.get("name", f"Farmer {phone[-4:]}"),
        "location":  profile.get("location", "Zimbabwe").title(),
        "message":   message,
        "timestamp": datetime.datetime.now().isoformat(),
        "channel":   channel,
        "platform":  "web",
    })
    return JSONResponse({"success": True})


@app.get("/api/seeds")
async def get_seeds_api(location: str = "", crop: str = ""):
    if not location:
        return JSONResponse({"crops": list(SEED_BRANDS.keys()), "suppliers": SEED_SUPPLIERS})

    info       = get_region_info(location)
    region_key = f"Region {info['region']}"
    result     = {}
    for crop_name, regions in SEED_BRANDS.items():
        seeds = regions.get(region_key, regions.get("All Regions", []))
        if seeds:
            if crop and crop.lower() != crop_name:
                continue
            result[crop_name] = seeds

    # Geocode location for live supplier search
    lat, lon, _ = geocode_location_free(location)
    suppliers   = await find_seed_suppliers_free(location, lat, lon)

    # Fetch live seed prices if specific crop requested
    live_prices = {}
    if crop:
        live_prices = await fetch_live_seed_prices(crop, location, info["region"])

    return JSONResponse({
        "location":             location,
        "region":               info["region"],
        "climate":              info["climate"],
        "best_crops":           info["best_crops"],
        "seed_recommendations": result,
        "live_seed_prices":     live_prices,
        "suppliers":            suppliers,
        "sources": {
            "seed_data":    "AgroBot Variety Database",
            "prices":       "Live Groq AI Market Analysis",
            "suppliers":    "OpenStreetMap Overpass API",
        },
    })


@app.get("/api/market-prices")
async def get_prices_api(location: str = "", crop: str = ""):
    prices = await fetch_live_commodity_prices()
    adj    = REGIONAL_PRICE_ADJ.get(location.lower(), {})
    result = {}
    for c, p in prices.items():
        if crop and crop.lower().replace(" ","_") != c and crop.lower() != c:
            continue
        result[c] = {**p, "local_price": round(p["price"] * adj.get(c.replace("_"," "), adj.get(c, 1.0)), 2)}
    return JSONResponse({
        "prices":       result,
        "location":     location or "national",
        "last_updated": live_price_cache.get("last_updated", ""),
    })


@app.put("/api/market-prices")
async def update_prices(request: Request):
    body = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    market_prices.setdefault("national", {}).update(body.get("prices", {}))
    if live_price_cache["data"]:
        live_price_cache["data"].update(body.get("prices", {}))
    save_data()
    return JSONResponse({"success": True})


@app.get("/api/weather/{lat}/{lon}")
async def weather_api(lat: float, lon: float):
    nearest = find_nearest_region(lat, lon)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"precipitation_probability_max,et0_fao_evapotranspiration"
        f"&timezone=Africa/Harare&forecast_days=7"
    )
    data = requests.get(url, timeout=12).json()
    return JSONResponse({
        "location":    nearest["name"],
        "region_info": nearest["info"],
        "forecast":    data.get("daily", {}),
        "source":      "Open-Meteo Live",
        "generated":   datetime.datetime.now().isoformat(),
    })


@app.get("/api/weather/by-name")
async def weather_by_name_api(location: str = "harare"):
    """Get live weather for a location name. Uses free Nominatim (OSM) geocoding."""
    lat, lon, display = geocode_location_free(location)

    if not lat:
        info    = get_region_info(location)
        lat, lon = info["lat"], info["lon"]
        display  = location.title()

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"precipitation_probability_max,et0_fao_evapotranspiration"
        f"&timezone=Africa/Harare&forecast_days=7"
    )
    data    = requests.get(url, timeout=12).json()
    nearest = find_nearest_region(lat, lon)
    return JSONResponse({
        "location":    display,
        "lat":         lat,
        "lon":         lon,
        "region_info": nearest["info"],
        "forecast":    data.get("daily", {}),
        "source":      "Open-Meteo Live",
        "generated":   datetime.datetime.now().isoformat(),
    })


@app.get("/api/regions")
async def regions_api():
    return JSONResponse(ZIMBABWE_REGIONS)


# ══════════════════════════════════════════════════════════════
# ── /api/news  — GNews server-side fetch + Groq fallback ──────
# ══════════════════════════════════════════════════════════════

CATEGORY_QUERIES = {
    "farming":    "Zimbabwe farming agriculture crops",
    "weather":    "Zimbabwe weather climate rainfall",
    "prices":     "Zimbabwe crop commodity prices market",
    "livestock":  "Zimbabwe livestock cattle farmers",
    "technology": "Africa agricultural technology innovation",
}

@app.get("/api/news")
async def news_api(phone: str = "", category: str = "farming"):
    """
    Fetches live GNews articles server-side (no CORS issues).
    Returns structured article objects with images.
    Falls back to Groq AI bulletin if GNews fails.
    """
    query = CATEGORY_QUERIES.get(category, "Zimbabwe farming agriculture")

    # ── STEP 1: Try GNews with Zimbabwe filter ─────────────────
    try:
        async with httpx.AsyncClient(timeout=12) as http:
            res  = await http.get(
                "https://gnews.io/api/v4/search",
                params={
                    "q":       query,
                    "lang":    "en",
                    "country": "zw",
                    "max":     10,
                    "apikey":  GNEWS_API_KEY,
                    "sortby":  "publishedAt",
                },
            )
            data     = res.json()
            articles = data.get("articles", [])

        # Broaden if Zimbabwe filter returns < 3
        if len(articles) < 3:
            async with httpx.AsyncClient(timeout=12) as http:
                res2     = await http.get(
                    "https://gnews.io/api/v4/search",
                    params={
                        "q":      query,
                        "lang":   "en",
                        "max":    10,
                        "apikey": GNEWS_API_KEY,
                        "sortby": "publishedAt",
                    },
                )
                data2    = res2.json()
                articles = data2.get("articles", [])

        if articles:
            return JSONResponse({
                "source":    "live",
                "category":  category,
                "articles":  articles,
                "generated": datetime.datetime.now().isoformat(),
            })

    except Exception as e:
        print(f"GNews error: {e}")

    # ── STEP 2: Groq AI fallback ───────────────────────────────
    try:
        now       = datetime.datetime.now()
        ai_prompt = f"""You are a Zimbabwe farming news editor. Today is {now.strftime('%d %B %Y')}.

Write 5 realistic Zimbabwe farming news articles as a JSON array.
Return ONLY valid JSON, no other text:

[
  {{
    "title": "Headline here",
    "description": "2-3 sentence article summary.",
    "source": {{"name": "AgroBot News"}},
    "publishedAt": "{now.isoformat()}",
    "url": null,
    "image": null,
    "category": "{category}"
  }}
]

Topics: {query}. Make articles realistic and specific to Zimbabwe farmers."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": ai_prompt}],
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        ai_articles = json.loads(raw)
        return JSONResponse({
            "source":    "ai",
            "category":  category,
            "articles":  ai_articles,
            "generated": datetime.datetime.now().isoformat(),
        })

    except Exception as e:
        print(f"AI news fallback error: {e}")

    return JSONResponse({
        "source":    "none",
        "category":  category,
        "articles":  [],
        "generated": datetime.datetime.now().isoformat(),
    })


@app.post("/api/ask")
async def ask_api(request: Request):
    body  = await request.json()
    q     = body.get("question","")
    phone = body.get("phone","")
    if not q:
        return JSONResponse({"error": "Question required"}, status_code=400)
    if phone:
        save_conversation(phone, "farmer", q, "api")
        track_activity(phone, "api_question")
    answer = ask_groq(q, body.get("topic",""), phone)
    if phone:
        save_conversation(phone, "agrobot", answer, "api")
    return JSONResponse({
        "answer":    answer,
        "phone":     phone,
        "timestamp": datetime.datetime.now().isoformat(),
    })


@app.post("/api/payment/initiate")
async def payment_initiate(request: Request):
    body  = await request.json()
    phone = body.get("phone", "")
    plan  = body.get("plan", "premium")
    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)
    amount = "2" if plan == "premium" else "10"
    ref    = generate_ref(phone)
    payment_pending[ref] = {
        "phone":     phone,
        "plan":      plan,
        "amount":    amount,
        "initiated": datetime.datetime.now().isoformat(),
        "status":    "pending",
    }
    save_data()
    return JSONResponse({
        "reference":      ref,
        "amount":         amount,
        "plan":           plan,
        "ecocash_number": ECOCASH_NUMBER,
        "onemoney_number":ONEMONEY_NUMBER,
        "instructions":   f"Pay ${amount} to {ECOCASH_NUMBER} with reference {ref}",
    })


@app.post("/api/payment/confirm")
async def payment_confirm(request: Request):
    body  = await request.json()
    phone = body.get("phone", "")
    ref   = body.get("reference", "")
    if body.get("secret") != ADMIN_SECRET and not body.get("gateway_token"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    result = process_payment(phone, ref)
    send_whatsapp_message(phone, result)
    return JSONResponse({
        "success": is_premium(phone),
        "phone":   phone,
        "plan":    get_plan(phone),
        "message": "Premium activated" if is_premium(phone) else "Payment failed",
    })


@app.post("/api/activate-premium")
async def activate_premium(request: Request):
    body  = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    phone   = body.get("phone", "")
    plan    = body.get("plan", "premium")
    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {
        "active":    True,
        "plan":      plan,
        "activated": datetime.datetime.now().isoformat(),
        "expires":   expires,
    }
    save_data()
    send_whatsapp_message(phone,
        f"🎉 *{plan.upper()} ACTIVATED!*\nAll features now active!\nType *MENU* to explore! 🌱")
    return JSONResponse({"success": True, "phone": phone, "expires": expires})


@app.get("/api/stats")
async def stats_api():
    all_activity   = user_activity.values()
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    active_7d      = sum(1 for a in all_activity if a.get("last_active_date","") >= seven_days_ago)
    total_messages = sum(a.get("total_messages", 0) for a in all_activity)
    online_now     = sum(len(v) for v in manager.active_connections.values())

    return JSONResponse({
        "company": COMPANY_NAME, "product": BOT_NAME, "version": "4.1.0",
        "support": {"phone": SUPPORT_PHONE, "email": SUPPORT_EMAIL, "website": WEBSITE},
        "farmers": {
            "total":        len(farmer_profiles),
            "premium":      len([p for p in premium_users.values() if p.get("active")]),
            "trial":        sum(1 for p in farmer_profiles if is_in_trial(p)),
            "active_7_days":active_7d,
            "online_now":   online_now,
        },
        "engagement": {
            "total_messages":     total_messages,
            "total_conversations":sum(len(c) for c in conversations.values()),
            "community_posts":    len(community_posts),
        },
        "marketplace": {"sellers": len(marketplace), "buyers": len(buyer_requests)},
        "community":   {"channels": len(community_channels), "total_posts": len(community_posts), "online_now": online_now},
        "coverage":    {"zimbabwe_regions": len(ZIMBABWE_REGIONS)},
        "timestamp":   datetime.datetime.now().isoformat(),
    })


@app.get("/api/farmers")
async def all_farmers():
    return JSONResponse({
        "total": len(farmer_profiles),
        "farmers": [
            {
                "phone":          p,
                "location":       farmer_profiles[p].get("location", "Unknown"),
                "plan":           get_plan(p),
                "joined":         farmer_profiles[p].get("joined", "")[:10],
                "days_active":    user_activity.get(p, {}).get("total_days_active", 0),
                "trial_days_left":get_trial_days_left(p),
            }
            for p in farmer_profiles
        ],
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
        message     = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]
        msg_type    = message.get("type", "text")

        if msg_type == "location":
            lat = message["location"]["latitude"]
            lon = message["location"]["longitude"]
            if from_number not in farmer_profiles:
                farmer_profiles[from_number] = {"joined": datetime.datetime.now().isoformat()}
            farmer_profiles[from_number].update({
                "gps_lat":    lat,
                "gps_lon":    lon,
                "registered": True,
            })
            save_data()
            track_activity(from_number, "gps_share")
            nearest = find_nearest_region(lat, lon)
            info    = nearest["info"]
            save_conversation(from_number, "farmer", f"[GPS: {lat:.4f}, {lon:.4f}]", "location")

            region_key  = f"Region {info['region']}"
            maize_seeds = SEED_BRANDS.get("maize", {}).get(region_key, [])
            seed_tip    = ""
            if maize_seeds:
                top      = maize_seeds[0]
                seed_tip = f"\n🌱 Top seed: *{top['brand']} {top['variety']}*"

            stats      = get_user_stats(from_number)
            trial_note = ""
            if is_in_trial(from_number):
                trial_note = f"\n🎁 Trial: {get_trial_days_left(from_number)} days left"

            reply = f"""📍 *GPS LOCATION SAVED!* 🛰️
{COMPANY_NAME} | Day {stats['days_since_joining']}
━━━━━━━━━━━━━━━━━━━━━━
🌍 {lat:.4f}°S, {lon:.4f}°E
📍 *{nearest['name'].title()}*
🌤️ {info['climate']} | {info['rainfall']}
🏔️ {info.get('soil', 'Mixed')}
🌱 Best: {info['best_crops']}{seed_tip}
{trial_note}

✅ All advice personalised to your farm!
Type *SEEDS* for seed recommendations!
{get_main_menu(from_number)}"""
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

        elif msg_type == "image":
            save_conversation(from_number, "farmer", "[Photo sent]", "image")
            track_activity(from_number, "image_sent")

            if has_full_access(from_number):
                image_id     = message["image"]["id"]
                img_url_resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{image_id}",
                    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
                    timeout=15,
                )
                image_url = img_url_resp.json().get("url")

                if not image_url:
                    reply = "❌ Could not retrieve image URL. Please try again."
                else:
                    send_whatsapp_message(from_number,
                        f"🔍 *Analysing your crop image...*\n{COMPANY_NAME}\n\nPlease wait 15-20 seconds...")
                    reply = analyze_image_improved(image_url, from_number)
            else:
                reply = f"""🔒 *PHOTO ANALYSIS — PREMIUM REQUIRED*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Your {TRIAL_DAYS}-day free trial has ended.

Upgrade for $2/month to unlock photo analysis.

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


# ── Send WhatsApp Message ──────────────────────────────────────
def send_whatsapp_message(to: str, message: str):
    url     = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "text",
        "text": {"body": message},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Sent [{to}]: {resp.status_code}")
    except Exception as e:
        print(f"Send error: {e}")


# ── Background: Refresh prices every 6 hours ──────────────────
@app.on_event("startup")
async def startup_event():
    print(f"🌱 {BOT_NAME} v4.1.0 starting...")
    print(f"📊 {COMPANY_NAME}")
    asyncio.create_task(refresh_prices_background())


async def refresh_prices_background():
    while True:
        try:
            await fetch_live_commodity_prices()
            print("✅ Live prices refreshed")
        except Exception as e:
            print(f"Price refresh error: {e}")
        await asyncio.sleep(21600)


# ══════════════════════════════════════════════════════════════
# ── SUPPORT TICKET SYSTEM ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/support/ticket")
async def create_support_ticket(request: Request):
    body     = await request.json()
    phone    = body.get("phone", "")
    subject  = body.get("subject", "")
    message  = body.get("message", "")
    category = body.get("category", "general")

    if not phone or not message:
        return JSONResponse({"error": "Phone and message required"}, status_code=400)

    ticket_id = f"TKT{secrets.token_hex(4).upper()}"
    ticket    = {
        "id":       ticket_id,
        "phone":    phone,
        "subject":  subject,
        "message":  message,
        "category": category,
        "status":   "open",
        "created":  datetime.datetime.now().isoformat(),
        "replies":  [],
        "resolved": False,
    }

    if phone not in support_tickets:
        support_tickets[phone] = []
    support_tickets[phone].append(ticket)
    save_data()

    send_whatsapp_message(phone, f"""✅ *Support Ticket Created*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
🎫 Ticket ID: *{ticket_id}*
📋 Subject: {subject}
📊 Status: *Open*

We will respond within 24 hours.
📞 Urgent: {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}""")

    return JSONResponse({"success": True, "ticket_id": ticket_id, "message": "Ticket created successfully"})


@app.get("/api/support/tickets/{phone}")
async def get_user_tickets(phone: str):
    tickets = support_tickets.get(phone, [])
    return JSONResponse({"phone": phone, "total": len(tickets), "tickets": tickets})


@app.get("/api/support/all")
async def get_all_tickets(request: Request):
    secret = request.headers.get("x-admin-secret", "")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    all_tickets = []
    for phone, tickets in support_tickets.items():
        for t in tickets:
            all_tickets.append({**t, "user_phone": phone})
    all_tickets.sort(key=lambda x: x.get("created", ""), reverse=True)

    return JSONResponse({
        "total":    len(all_tickets),
        "open":     len([t for t in all_tickets if t["status"] == "open"]),
        "resolved": len([t for t in all_tickets if t["status"] == "resolved"]),
        "tickets":  all_tickets,
    })


@app.post("/api/support/reply")
async def reply_to_ticket(request: Request):
    body      = await request.json()
    secret    = body.get("secret", "")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    ticket_id = body.get("ticket_id", "")
    reply_msg = body.get("reply", "")
    resolve   = body.get("resolve", False)

    for phone, tickets in support_tickets.items():
        for ticket in tickets:
            if ticket["id"] == ticket_id:
                ticket["replies"].append({
                    "message":   reply_msg,
                    "from":      "admin",
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                if resolve:
                    ticket["status"]   = "resolved"
                    ticket["resolved"] = True
                save_data()
                send_whatsapp_message(phone, f"""📬 *Support Reply — {COMPANY_NAME}*
━━━━━━━━━━━━━━━━━━━━━━
🎫 Ticket: *{ticket_id}*
📋 Subject: {ticket.get('subject','')}

💬 *Response:*
{reply_msg}

Status: {'✅ Resolved' if resolve else '🔄 In Progress'}
Reply here or call: {SUPPORT_PHONE}""")
                return JSONResponse({"success": True, "ticket_id": ticket_id})

    return JSONResponse({"error": "Ticket not found"}, status_code=404)


@app.post("/api/support/admin-fix")
async def admin_fix_account(request: Request):
    body   = await request.json()
    secret = body.get("secret", "")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    phone  = body.get("phone", "")
    action = body.get("action", "")
    note   = body.get("note", "")
    result = {"success": False, "action": action, "phone": phone}

    if action == "reset_trial":
        if phone in farmer_profiles:
            farmer_profiles[phone]["joined"] = datetime.datetime.now().isoformat()
            save_data()
            result.update({"success": True, "message": f"Trial reset for {phone}"})
            send_whatsapp_message(phone,
                f"🎁 *Trial Reset by {COMPANY_NAME}*\nYour 30-day free trial has been reset!\nType *MENU* to continue! 🌱")

    elif action == "extend_premium":
        days = body.get("days", 30)
        if phone in premium_users:
            current_exp = premium_users[phone].get("expires", datetime.datetime.now().isoformat())
            try:
                exp_dt = datetime.datetime.fromisoformat(current_exp)
            except Exception:
                exp_dt = datetime.datetime.now()
            new_exp = exp_dt + datetime.timedelta(days=days)
            premium_users[phone]["expires"] = new_exp.isoformat()
            premium_users[phone]["active"]  = True
        else:
            premium_users[phone] = {
                "active":    True,
                "plan":      "premium",
                "activated": datetime.datetime.now().isoformat(),
                "expires":   (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(),
            }
        save_data()
        result.update({"success": True, "message": f"Premium extended {days} days for {phone}"})
        send_whatsapp_message(phone,
            f"✅ *Account Updated — {COMPANY_NAME}*\nPremium extended by {days} days!\nType *MENU* to continue! 🌱")

    elif action == "clear_history":
        if phone in conversations:
            conversations[phone] = []
            save_data()
        result.update({"success": True, "message": f"History cleared for {phone}"})

    elif action == "refund_reset":
        if phone in premium_users:
            premium_users[phone]["active"] = False
            save_data()
        result.update({"success": True, "message": f"Premium deactivated for {phone}"})
        send_whatsapp_message(phone,
            f"ℹ️ *Account Update — {COMPANY_NAME}*\n{note or 'Your account has been updated.'}\nContact: {SUPPORT_PHONE}")

    elif action == "send_message":
        send_whatsapp_message(phone, note)
        result.update({"success": True, "message": f"Message sent to {phone}"})

    return JSONResponse(result)


# ══════════════════════════════════════════════════════════════
# ── NOTIFICATIONS ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/notifications/send")
async def send_notification(request: Request):
    body   = await request.json()
    secret = body.get("secret", "")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    title         = body.get("title", "")
    message       = body.get("message", "")
    notify_type   = body.get("type", "update")
    target        = body.get("target", "all")
    target_phone  = body.get("phone", "")

    notif = {
        "id":      secrets.token_hex(8),
        "title":   title,
        "message": message,
        "type":    notify_type,
        "target":  target,
        "created": datetime.datetime.now().isoformat(),
        "read_by": [],
    }
    notifications.append(notif)
    save_data()

    targets = []
    if target == "all":
        targets = list(farmer_profiles.keys())
    elif target == "premium":
        targets = [p for p in premium_users if premium_users[p].get("active")]
    elif target == "trial":
        targets = [p for p in farmer_profiles if is_in_trial(p)]
    elif target == "specific" and target_phone:
        targets = [target_phone]

    whatsapp_msg = f"""📢 *{title}*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
{message}
━━━━━━━━━━━━━━━━━━━━━━
Type *MENU* to continue 🌱"""

    sent_count = 0
    for phone in targets[:50]:
        try:
            send_whatsapp_message(phone, whatsapp_msg)
            sent_count += 1
        except Exception:
            pass

    return JSONResponse({"success": True, "notification_id": notif["id"], "sent_to": sent_count})


@app.get("/api/notifications")
async def get_notifications(phone: str = ""):
    plan        = get_plan(phone) if phone else "free"
    user_notifs = []
    for n in notifications[-20:]:
        target = n.get("target", "all")
        if (target == "all"
                or (target == "premium" and plan in ["premium","business"])
                or (target == "trial"   and plan == "trial")
                or (target == "specific" and n.get("phone") == phone)):
            user_notifs.append({**n, "read": phone in n.get("read_by", [])})
    return JSONResponse({
        "total":         len(user_notifs),
        "unread":        len([n for n in user_notifs if not n.get("read")]),
        "notifications": list(reversed(user_notifs)),
    })


@app.post("/api/notifications/read")
async def mark_notification_read(request: Request):
    body     = await request.json()
    phone    = body.get("phone", "")
    notif_id = body.get("notification_id", "")
    for n in notifications:
        if n["id"] == notif_id and phone not in n.get("read_by", []):
            n.setdefault("read_by", []).append(phone)
    save_data()
    return JSONResponse({"success": True})


# ══════════════════════════════════════════════════════════════
# ── ECOCASH PAYMENT WEBHOOKS ───────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/payment/ecocash-webhook")
async def ecocash_webhook(request: Request):
    try:
        body           = await request.json()
        transaction_id = body.get("transactionId") or body.get("transaction_id", "")
        amount         = str(body.get("amount", ""))
        payer_phone    = body.get("msisdn") or body.get("phone", "")
        reference      = body.get("reference") or body.get("clientCorrelator", "")
        status         = body.get("transactionOperationStatus") or body.get("status", "")

        success_statuses = ["COMPLETED","SUCCESS","SUCCESSFUL","completed","success"]
        if status not in success_statuses:
            return JSONResponse({"status": "pending", "message": f"Payment status: {status}"})

        matched_phone = None
        matched_plan  = None

        for ref_key, pending in payment_pending.items():
            if (reference and ref_key.upper() == reference.upper()) or \
               (payer_phone and pending.get("phone","").endswith(payer_phone[-9:])):
                matched_phone = pending["phone"]
                matched_plan  = pending.get("plan","premium")
                break

        if not matched_phone and payer_phone:
            clean_payer = payer_phone.replace("+","").replace(" ","")
            for phone in farmer_profiles:
                clean_farmer = phone.replace("+","").replace(" ","")
                if clean_payer.endswith(clean_farmer[-9:]) or clean_farmer.endswith(clean_payer[-9:]):
                    matched_phone = phone
                    matched_plan  = "business" if float(amount or 0) >= 10 else "premium"
                    break

        if not matched_phone:
            return JSONResponse({"status": "unmatched", "message": "No matching farmer found"})

        expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        premium_users[matched_phone] = {
            "active":         True,
            "plan":           matched_plan,
            "amount":         amount,
            "activated":      datetime.datetime.now().isoformat(),
            "expires":        expires,
            "transaction_id": transaction_id,
            "payment_method": "ecocash",
            "auto_verified":  True,
        }

        for ref_key in list(payment_pending.keys()):
            if payment_pending[ref_key].get("phone") == matched_phone:
                payment_pending[ref_key]["status"]         = "confirmed"
                payment_pending[ref_key]["transaction_id"] = transaction_id

        if matched_phone in user_accounts:
            user_accounts[matched_phone].update({"premium": True, "plan": matched_plan})

        save_data()

        send_whatsapp_message(matched_phone, f"""🎉 *PAYMENT CONFIRMED AUTOMATICALLY!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
✅ Amount: *${amount} USD*
✅ Plan: *{matched_plan.upper()}*
✅ Transaction: {transaction_id}
✅ Status: *ACTIVE*
✅ Valid: 30 days

Type *MENU* to explore all features! 🌱🇿🇼""")

        return JSONResponse({"status": "success", "phone": matched_phone, "plan": matched_plan})

    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/payment/verify-manual")
async def verify_payment_manual(request: Request):
    body      = await request.json()
    phone     = body.get("phone", "")
    reference = body.get("reference", "")
    amount    = body.get("amount", "")

    if not phone or not reference:
        return JSONResponse({"error": "Phone and reference required"}, status_code=400)

    expected_ref = f"AGRO{phone[-6:]}"
    if reference.upper() != expected_ref.upper():
        return JSONResponse({"success": False, "expected": expected_ref, "message": "Reference does not match"}, status_code=400)

    pending    = payment_pending.get(reference.upper(), {})
    plan       = pending.get("plan", "premium" if float(amount or 2) < 10 else "business")
    pay_amount = pending.get("amount", amount or "2")
    expires    = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()

    premium_users[phone] = {
        "active":          True,
        "plan":            plan,
        "amount":          pay_amount,
        "activated":       datetime.datetime.now().isoformat(),
        "expires":         expires,
        "payment_ref":     reference,
        "manual_verified": True,
    }

    if reference.upper() in payment_pending:
        payment_pending[reference.upper()]["status"] = "confirmed"
    if phone in user_accounts:
        user_accounts[phone].update({"premium": True, "plan": plan})

    save_data()
    confirmation = process_payment(phone, reference)
    send_whatsapp_message(phone, confirmation)

    return JSONResponse({"success": True, "plan": plan, "expires": expires, "message": "Premium activated successfully"})


@app.post("/api/payment/ecocash-notify")
async def ecocash_notify(request: Request):
    try:
        body = await request.json()
        print(f"EcoCash notification: {body}")

        payer_phone = (body.get("msisdn") or body.get("senderMsisdn") or
                       body.get("phone")  or body.get("payer", "")).replace("+","").replace(" ","")
        try:
            amount = float(str(body.get("amount") or body.get("transactionAmount") or body.get("value") or "0"))
        except Exception:
            amount = 0.0

        transaction_id = (body.get("transactionId") or body.get("id") or
                          body.get("ftid") or secrets.token_hex(8))
        status = (body.get("transactionOperationStatus") or body.get("status") or "COMPLETED").upper()

        if status not in ["COMPLETED","SUCCESS","SUCCESSFUL"]:
            return JSONResponse({"status": "pending"})
        if amount < 1.5:
            return JSONResponse({"status": "ignored", "reason": f"Amount ${amount} too low"})

        plan        = "business" if amount >= 9.0 else "premium"
        clean_payer = payer_phone.replace("+","").replace(" ","").replace("-","")
        matched_phone = None

        for farmer_phone in farmer_profiles:
            clean_farmer = farmer_phone.replace("+","").replace(" ","").replace("-","")
            if clean_payer[-9:] == clean_farmer[-9:] or clean_payer[-8:] == clean_farmer[-8:]:
                matched_phone = farmer_phone
                break

        if not matched_phone:
            for acc_phone in user_accounts:
                clean_acc = acc_phone.replace("+","").replace(" ","").replace("-","")
                if clean_payer[-9:] == clean_acc[-9:] or clean_payer[-8:] == clean_acc[-8:]:
                    matched_phone = acc_phone
                    break

        if not matched_phone:
            unmatched_key = f"unmatched_{transaction_id}"
            payment_pending[unmatched_key] = {
                "payer_phone":   payer_phone,
                "amount":        amount,
                "plan":          plan,
                "transaction_id":transaction_id,
                "status":        "unmatched",
                "received":      datetime.datetime.now().isoformat(),
            }
            save_data()
            return JSONResponse({"status": "unmatched", "transaction_id": transaction_id})

        expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        premium_users[matched_phone] = {
            "active":         True,
            "plan":           plan,
            "amount":         str(amount),
            "activated":      datetime.datetime.now().isoformat(),
            "expires":        expires,
            "transaction_id": transaction_id,
            "payer_phone":    payer_phone,
            "payment_method": "ecocash_auto",
            "no_reference":   True,
        }
        if matched_phone in user_accounts:
            user_accounts[matched_phone].update({"premium": True, "plan": plan})
        save_data()

        send_whatsapp_message(matched_phone, f"""🎉 *PAYMENT RECEIVED — PREMIUM ACTIVATED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
✅ Amount: *${amount:.2f} USD* received!
✅ Plan: *{plan.upper()}*
✅ Transaction: {transaction_id}
✅ Status: *ACTIVE NOW*
✅ Valid: 30 days

Type *MENU* to use all features! 🌱🇿🇼
Thank you for supporting {COMPANY_NAME}!""")

        return JSONResponse({"status": "success", "phone": matched_phone, "plan": plan, "amount": amount})

    except Exception as e:
        print(f"EcoCash notify error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/payment/unmatched")
async def get_unmatched_payments(request: Request):
    secret = request.headers.get("x-admin-secret","")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    unmatched = [
        {**v, "ref": k}
        for k, v in payment_pending.items()
        if v.get("status") == "unmatched"
    ]
    return JSONResponse({"total": len(unmatched), "unmatched": unmatched})


@app.post("/api/payment/match-manual")
async def match_unmatched_payment(request: Request):
    body   = await request.json()
    secret = body.get("secret","")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)

    ref   = body.get("ref","")
    phone = body.get("phone","")

    if ref not in payment_pending:
        return JSONResponse({"error":"Payment not found"}, status_code=404)

    pending = payment_pending[ref]
    amount  = float(pending.get("amount", 2))
    plan    = "business" if amount >= 9 else "premium"

    premium_users[phone] = {
        "active":           True,
        "plan":             plan,
        "amount":           str(amount),
        "activated":        datetime.datetime.now().isoformat(),
        "expires":          (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat(),
        "transaction_id":   pending.get("transaction_id",""),
        "manually_matched": True,
    }
    payment_pending[ref]["status"]        = "matched"
    payment_pending[ref]["matched_phone"] = phone
    save_data()

    send_whatsapp_message(phone,
        f"🎉 *Payment Matched & Premium Activated!*\n{COMPANY_NAME}\n\n"
        f"✅ ${amount} payment confirmed!\n✅ {plan.upper()} plan is now ACTIVE!\n\n"
        f"Type *MENU* to explore all features! 🌱")

    return JSONResponse({"success": True, "phone": phone, "plan": plan})


@app.post("/api/payment/initiate-ussd")
async def initiate_ussd_payment(request: Request):
    body        = await request.json()
    phone       = body.get("phone", "")
    payer_phone = body.get("payer_phone", "")
    plan        = body.get("plan", "premium")
    amount      = body.get("amount", 2)
    method      = body.get("method", "ecocash")

    if not payer_phone:
        return JSONResponse({"success": False, "message": "Phone number required"}, status_code=400)

    clean_phone = payer_phone.replace("+","").replace(" ","").replace("-","")
    if not clean_phone.startswith("263"):
        clean_phone = "263" + (clean_phone[1:] if clean_phone.startswith("0") else clean_phone)

    ref = generate_ref(phone)
    payment_pending[ref] = {
        "phone":       phone,
        "payer_phone": clean_phone,
        "plan":        plan,
        "amount":      str(amount),
        "method":      method,
        "initiated":   datetime.datetime.now().isoformat(),
        "status":      "pending",
        "ussd_push":   True,
    }
    save_data()

    try:
        ECOCASH_MERCHANT_CODE = os.getenv("ECOCASH_MERCHANT_CODE", "")
        ECOCASH_MERCHANT_PIN  = os.getenv("ECOCASH_MERCHANT_PIN", "")
        ECOCASH_API_URL       = os.getenv("ECOCASH_API_URL", "https://www.ecocash.co.zw/api/payment")

        if ECOCASH_MERCHANT_CODE and ECOCASH_MERCHANT_PIN:
            ecocash_payload = {
                "msisdn":           clean_phone,
                "amount":           amount,
                "merchantCode":     ECOCASH_MERCHANT_CODE,
                "merchantPin":      ECOCASH_MERCHANT_PIN,
                "merchantNumber":   ECOCASH_NUMBER.replace(" ",""),
                "merchantName":     COMPANY_NAME,
                "clientCorrelator": ref,
                "narration":        f"AgroBot {plan.title()} subscription",
                "notifyUrl":        "https://agrobot-c6ff.onrender.com/api/payment/ecocash-notify",
            }
            try:
                ecocash_res  = requests.post(ECOCASH_API_URL, json=ecocash_payload, timeout=30,
                                             headers={"Content-Type":"application/json"})
                ecocash_data = ecocash_res.json()
                if ecocash_data.get("status") not in ["failed","error"]:
                    send_whatsapp_message(phone, f"""💳 *Payment Request Sent!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
A payment request of *${amount}* has been
sent to your {method.title()} number.
Please check your phone and enter your PIN.
Plan: *{plan.upper()}* | Amount: *${amount}*
📞 Help: {SUPPORT_PHONE}""")
                    return JSONResponse({"success": True, "reference": ref,
                                         "message": f"Payment request sent to {clean_phone}"})
            except Exception as eco_err:
                print(f"EcoCash API error: {eco_err}")

        dial_code = "*151#" if method == "ecocash" else "*111#"
        send_whatsapp_message(phone, f"""💳 *Complete Your Payment*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Plan: *{plan.upper()} — ${amount}/month*

📱 *Pay via {method.title()}:*
1️⃣ Dial {dial_code}
2️⃣ Select: Send Money
3️⃣ Number: *{ECOCASH_NUMBER}*
4️⃣ Amount: *${amount}*
5️⃣ Reference: *{ref}*

After paying reply: *PAID {ref}*
✅ Premium activates instantly!
📞 Help: {SUPPORT_PHONE}""")

        return JSONResponse({"success": True, "reference": ref,
                              "message": "Payment instructions sent via WhatsApp", "fallback": True})

    except Exception as e:
        print(f"Payment initiation error: {e}")
        return JSONResponse({"success": False, "message": "Could not initiate payment. Please try again."}, status_code=500)


@app.get("/api/payment/status/{reference}")
async def check_payment_status(reference: str):
    pending = payment_pending.get(reference, {})
    phone   = pending.get("phone","")
    if is_premium(phone):
        return JSONResponse({"status": "confirmed", "active": True, "plan": get_plan(phone), "message": "Premium active"})
    status = pending.get("status","pending")
    if status == "confirmed":
        return JSONResponse({"status": "confirmed", "active": True, "plan": pending.get("plan","premium")})
    return JSONResponse({"status": status, "active": False, "message": "Waiting for payment"})


# ══════════════════════════════════════════════════════════════
# ── WEB IMAGE ANALYSIS ────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/analyse-image-web")
async def analyse_image_web(request: Request):
    try:
        body             = await request.json()
        img_base64       = body.get("image_base64", "")
        img_type         = body.get("image_type", "image/jpeg")
        phone            = body.get("phone", "")
        location_context = body.get("location_context", "")

        if not img_base64:
            return JSONResponse({"error": "No image provided"}, status_code=400)

        farmer_ctx = get_farmer_context(phone) if phone else ""
        models     = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ]

        prompt = f"""You are {BOT_NAME} — expert plant pathologist for Zimbabwe agriculture.

{farmer_ctx}
{location_context}

Analyse this crop image and provide a COMPLETE professional report:

🌿 CROP IDENTIFIED: (Common + scientific name + growth stage)
🔍 PROBLEM DETECTED: (Disease/pest/deficiency/environmental)
🧬 CAUSE: (Pathogen species OR pest species OR nutrient)
📊 SEVERITY: Low / Moderate / High / Critical (% affected)
💊 IMMEDIATE TREATMENT: (Zimbabwe brand name, rate, method, timing)
🔄 FOLLOW-UP TREATMENT: (if needed)
🛡️ PREVENTION NEXT SEASON: (2-3 steps)
⏰ URGENCY: Act within [X hours/days]
💰 ESTIMATED COST: $[X] USD

If image quality is poor, state what you CAN see and what confidence level you have."""

        last_error = ""
        for model in models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{img_type};base64,{img_base64}"}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                    max_tokens=800,
                )
                analysis = response.choices[0].message.content
                fail_phrases = ["cannot see","can't see","no image","not provided","unable to view","i don't see","no photo","image not"]
                if any(p in analysis.lower() for p in fail_phrases):
                    last_error = "Vision model could not process image"
                    continue
                if phone:
                    save_conversation(phone, "farmer",  "[Uploaded crop photo via website]", "image")
                    save_conversation(phone, "agrobot", analysis, "image_analysis")
                return JSONResponse({"success": True, "analysis": analysis, "model": model})

            except Exception as model_err:
                last_error = str(model_err)
                print(f"Model {model} failed: {model_err}")
                continue

        return JSONResponse({"error": "Could not analyse image. Try a clearer photo.", "detail": last_error}, status_code=500)

    except Exception as e:
        print(f"Web image analysis error: {e}")
        return JSONResponse({"error": "Analysis failed. Please try again."}, status_code=500)


# ══════════════════════════════════════════════════════════════
# ── LOCATION VERIFICATION ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.post("/api/verify-location")
async def verify_location(request: Request):
    """
    Verify and resolve farmer location.
    1. Nominatim (OpenStreetMap) → precise lat/lon, free, no key needed
    2. Direct city name match    → against ZIMBABWE_REGIONS dict
    3. Groq AI                   → fuzzy match for village/ward/farm names
    """
    body     = await request.json()
    phone    = body.get("phone", "")
    location = body.get("location", "").strip()

    if not phone or not location:
        return JSONResponse({"error": "Phone and location required"}, status_code=400)

    matched_city = None
    matched_info = None
    precise_lat  = None
    precise_lon  = None
    ai_note      = ""

    # ── Step 1: Nominatim geocoding (free OSM, no key) ─────────
    try:
        nom_lat, nom_lon, nom_display = geocode_location_free(location)
        if nom_lat:
            precise_lat  = nom_lat
            precise_lon  = nom_lon
            nearest      = find_nearest_region(precise_lat, precise_lon)
            matched_city = nearest["name"]
            matched_info = nearest["info"]
            ai_note      = f"📡 OpenStreetMap verified: {nom_display}"
            print(f"Nominatim: '{location}' → {matched_city} ({precise_lat:.4f}, {precise_lon:.4f})")
    except Exception as e:
        print(f"Nominatim error: {e}")

    # ── Step 2: Direct city name match ─────────────────────────
    if not matched_city:
        loc_lower = location.lower()
        for city, info in ZIMBABWE_REGIONS.items():
            if city in loc_lower or loc_lower in city:
                matched_city = city
                matched_info = info
                ai_note      = f"Matched to {city.title()}"
                break

    # ── Step 3: Groq fuzzy match for villages/wards/farms ──────
    if not matched_city:
        try:
            prompt = f"""A Zimbabwe farmer says their location is: "{location}"
This could be a village, ward, farm, or suburb name.
Match it to the nearest major town from this list.
Return ONLY valid JSON:
{{"city": "marondera", "confidence": "high", "note": "Village in Mashonaland East, nearest town Marondera"}}
Towns: harare, bulawayo, mutare, masvingo, gweru, marondera, chinhoyi, bindura, victoria falls, kariba, chiredzi, beitbridge, zvishavane, kwekwe, kadoma, norton, rusape, nyanga, chipinge"""
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
            )
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].split("```")[0].replace("json", "").strip()
            rj           = json.loads(raw)
            matched_city = rj.get("city", "harare")
            matched_info = ZIMBABWE_REGIONS.get(matched_city, ZIMBABWE_REGIONS["harare"])
            ai_note      = rj.get("note", f"Matched to {matched_city.title()}")
        except Exception:
            matched_city = "harare"
            matched_info = ZIMBABWE_REGIONS["harare"]
            ai_note      = "Could not verify — defaulted to Harare"

    if phone not in farmer_profiles:
        farmer_profiles[phone] = {"joined": datetime.datetime.now().isoformat()}

    update = {
        "location":          matched_city,
        "location_input":    location,
        "location_verified": True,
    }
    if precise_lat:
        update["gps_lat"] = precise_lat
        update["gps_lon"] = precise_lon
    farmer_profiles[phone].update(update)
    save_data()

    return JSONResponse({
        "success":      True,
        "input":        location,
        "matched_city": matched_city,
        "note":         ai_note,
        "region_info":  matched_info,
        "lat":          precise_lat,
        "lon":          precise_lon,
        "message":      f"Location verified as {matched_city.title()}",
    })


# ══════════════════════════════════════════════════════════════
# ── PREMIUM EXPIRY AUTO-CHECK (background thread) ─────────────
# ══════════════════════════════════════════════════════════════

def check_premium_expiries():
    while True:
        try:
            now = datetime.datetime.now()

            for phone, data in list(premium_users.items()):
                if not data.get("active"):
                    continue
                expires_str = data.get("expires", "")
                if not expires_str:
                    continue
                try:
                    expires   = datetime.datetime.fromisoformat(expires_str)
                    days_left = (expires - now).days

                    if days_left == 3:
                        send_whatsapp_message(phone, f"""⚠️ *Premium Expiring Soon!*
{COMPANY_NAME}
Your {data.get('plan','premium').upper()} plan expires in *3 days*.
Renew: EcoCash *{ECOCASH_NUMBER}* | Ref: *AGRO{phone[-6:]}*
Then reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                    elif days_left == 1:
                        send_whatsapp_message(phone, f"""🚨 *Premium Expires TOMORROW!*
{COMPANY_NAME}
Renew NOW — Pay ${data.get('amount','2')} via EcoCash: *{ECOCASH_NUMBER}*
Ref: *AGRO{phone[-6:]}* | Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                    elif days_left < 0:
                        premium_users[phone]["active"] = False
                        save_data()
                        send_whatsapp_message(phone, f"""😔 *Premium Plan Expired*
{COMPANY_NAME}
To renew: Pay ${data.get('amount','2')} to EcoCash *{ECOCASH_NUMBER}*
Ref: *AGRO{phone[-6:]}* | Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                except Exception as e:
                    print(f"Expiry check error {phone}: {e}")

            for phone, profile in list(farmer_profiles.items()):
                if is_premium(phone):
                    continue
                days_left = get_trial_days_left(phone)
                if days_left == 7:
                    send_whatsapp_message(phone, f"""⏰ *Trial Ending in 7 Days!*
{COMPANY_NAME}
Subscribe: 💎 Premium $2/month | 🏆 Business $10/month
EcoCash: *{ECOCASH_NUMBER}* | Ref: *AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                elif days_left == 1:
                    send_whatsapp_message(phone, f"""🚨 *Trial Ends TOMORROW!*
{COMPANY_NAME}
Subscribe NOW: $2/month via EcoCash *{ECOCASH_NUMBER}*
Ref: *AGRO{phone[-6:]}* | Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                elif days_left == 0:
                    joined_str = profile.get("joined", "")
                    try:
                        joined    = datetime.datetime.fromisoformat(joined_str)
                        trial_end = joined + datetime.timedelta(days=TRIAL_DAYS)
                        hours_ago = (now - trial_end).total_seconds() / 3600
                        if 0 < hours_ago < 2:
                            send_whatsapp_message(phone, f"""😔 *Free Trial Has Ended*
{COMPANY_NAME}
Subscribe: EcoCash *{ECOCASH_NUMBER}* | Ref: *AGRO{phone[-6:]}*
Then reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                    except Exception:
                        pass

            save_data()
        except Exception as e:
            print(f"Background check error: {e}")
        time.sleep(3600)


expiry_thread = threading.Thread(target=check_premium_expiries, daemon=True)
expiry_thread.start()
print("✅ Premium expiry checker started")


# ══════════════════════════════════════════════════════════════
# ── ADMIN DASHBOARD ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.get("/api/admin/dashboard")
async def admin_dashboard(request: Request):
    secret = request.headers.get("x-admin-secret", "")
    if secret != ADMIN_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    now        = datetime.datetime.now()
    all_tickets = [t for tickets in support_tickets.values() for t in tickets]

    expiring_soon = []
    for phone, data in premium_users.items():
        if data.get("active"):
            try:
                exp = datetime.datetime.fromisoformat(data.get("expires",""))
                if (exp - now).days <= 7:
                    expiring_soon.append({
                        "phone":     phone,
                        "plan":      data.get("plan"),
                        "expires":   data.get("expires"),
                        "days_left": (exp - now).days,
                    })
            except Exception:
                pass

    premium_count  = len([p for p in premium_users.values() if p.get("active") and p.get("plan") == "premium"])
    business_count = len([p for p in premium_users.values() if p.get("active") and p.get("plan") == "business"])
    monthly_revenue = (premium_count * 2) + (business_count * 10)

    return JSONResponse({
        "summary": {
            "total_farmers":      len(farmer_profiles),
            "premium_active":     premium_count,
            "business_active":    business_count,
            "trial_active":       sum(1 for p in farmer_profiles if is_in_trial(p)),
            "expired_trial":      sum(1 for p in farmer_profiles if not is_in_trial(p) and not is_premium(p)),
            "monthly_revenue_usd":monthly_revenue,
            "open_tickets":       len([t for t in all_tickets if t.get("status") == "open"]),
            "total_conversations":sum(len(c) for c in conversations.values()),
            "community_posts":    len(community_posts),
            "marketplace_listings":len(marketplace) + len(buyer_requests),
        },
        "expiring_soon":   expiring_soon,
        "recent_payments": [{**v, "phone": k} for k, v in list(premium_users.items())[-10:] if v.get("activated")],
        "recent_tickets":  all_tickets[:10],
        "farmers_list": [
            {
                "phone":           p,
                "location":        farmer_profiles[p].get("location",""),
                "plan":            get_plan(p),
                "trial_days_left": get_trial_days_left(p),
                "days_active":     user_activity.get(p,{}).get("total_days_active",0),
                "joined":          farmer_profiles[p].get("joined","")[:10],
                "messages":        user_activity.get(p,{}).get("total_messages",0),
            }
            for p in farmer_profiles
        ],
    })


# ── Admin Password Management ──────────────────────────────────
admin_config = {}


def load_admin_config():
    global admin_config
    try:
        with open("admin_config.json", "r") as f:
            admin_config.update(json.load(f))
    except Exception:
        admin_config = {
            "password":     "AGROBOT_ADMIN_2026",
            "last_changed": datetime.datetime.now().isoformat(),
        }


def save_admin_config():
    with open("admin_config.json", "w") as f:
        json.dump(admin_config, f, indent=2)


load_admin_config()


@app.post("/api/admin/change-password")
async def change_admin_password(request: Request):
    body      = await request.json()
    current   = body.get("current_password", "")
    new_pass  = body.get("new_password", "")
    confirm   = body.get("confirm_password", "")
    stored    = admin_config.get("password", ADMIN_SECRET)

    if current != stored and current != ADMIN_SECRET:
        return JSONResponse({"success": False, "error": "Current password is incorrect"}, status_code=401)
    if not new_pass or len(new_pass) < 8:
        return JSONResponse({"success": False, "error": "New password must be at least 8 characters"}, status_code=400)
    if new_pass != confirm:
        return JSONResponse({"success": False, "error": "New passwords do not match"}, status_code=400)
    if new_pass == current:
        return JSONResponse({"success": False, "error": "New password must be different from current"}, status_code=400)

    admin_config["password"]     = new_pass
    admin_config["last_changed"] = datetime.datetime.now().isoformat()
    save_admin_config()

    return JSONResponse({"success": True, "message": "Password changed successfully", "last_changed": admin_config["last_changed"]})


@app.post("/api/admin/verify-password")
async def verify_admin_password(request: Request):
    body     = await request.json()
    password = body.get("password", "")
    stored   = admin_config.get("password", ADMIN_SECRET)
    if password == stored or password == ADMIN_SECRET:
        return JSONResponse({"success": True, "last_changed": admin_config.get("last_changed", "Unknown")})
    return JSONResponse({"success": False, "error": "Incorrect password"}, status_code=401)


# ── Health Check ───────────────────────────────────────────────
@app.get("/")
def home():
    online = sum(len(v) for v in manager.active_connections.values())
    return {
        "name":    BOT_NAME,
        "company": COMPANY_NAME,
        "version": "4.1.0",
        "status":  "operational",
        "support": {"phone": SUPPORT_PHONE, "email": SUPPORT_EMAIL, "website": WEBSITE},
        "stats": {
            "farmers":         len(farmer_profiles),
            "premium":         len([p for p in premium_users.values() if p.get("active")]),
            "conversations":   sum(len(c) for c in conversations.values()),
            "community_posts": len(community_posts),
            "online_now":      online,
            "marketplace":     len(marketplace) + len(buyer_requests),
        },
        "features": [
            "WhatsApp AI Chatbot",
            "Real-time WebSocket Community Chat",
            "Live GNews News with Photos (GNews API)",
            "Live Market Prices (World Bank + Groq AI, 6hr refresh)",
            "Live Seed Prices (Groq AI, per-request)",
            "Live Nearby Agri Help (OpenStreetMap Overpass API)",
            "Live Weather 7-Day Forecast (Open-Meteo, free)",
            "Free Geocoding for Any Location (Nominatim/OSM)",
            "Photo Crop Disease Analysis (multi-model AI)",
            "GPS Precision Farming",
            "30-Day Free Trial",
            "EcoCash/OneMoney Payments",
            "REST API for Website & App",
        ],
    }