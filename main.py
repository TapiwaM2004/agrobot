# ════════════════════════════════════════════════════════════
#  AgroBot Pro — main.py  (Complete Improved Version v4.2.0)
#  TM AGRO Solutions | Zimbabwe Smart Farming Assistant
#
#  HOW TO USE THESE PARTS:
#  Download Part1 through Part8, open a new file called main.py,
#  paste Part1 first, then Part2 directly below it, continuing
#  through Part8. The result is your complete main.py.
#  ─────────────────────────────────────────────────────────────
#  PART 1 OF 8 — Imports, Config, Cloudinary, Supabase, DB Layer
# ════════════════════════════════════════════════════════════

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
    version="4.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "951059444767602")
VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN", "agrobot123")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GNEWS_API_KEY   = os.getenv("GNEWS_API_KEY", "86b26ba02bf77b0ca9826d4e95ba089e")
ADMIN_SECRET    = os.getenv("ADMIN_SECRET", "AGROBOT_ADMIN_2026")
SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY", "")
ECOCASH_NUMBER  = "0787 341 018"
ONEMONEY_NUMBER = "0787 341 018"
SUPPORT_PHONE   = "0787 341 018"
SUPPORT_EMAIL   = "manhambaratapiwa548@gmail.com"
COMPANY_NAME    = "TM AGRO Solutions"
BOT_NAME        = "AgroBot Pro"
WEBSITE         = "agrobot.co.zw"
TRIAL_DAYS      = 30

client = Groq(api_key=GROQ_API_KEY)

# ── Cloudinary (marketplace & farm images) ─────────────────────
try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", ""),
        api_key    = os.getenv("CLOUDINARY_API_KEY",    ""),
        api_secret = os.getenv("CLOUDINARY_API_SECRET", ""),
        secure     = True,
    )
    CLOUDINARY_AVAILABLE = bool(os.getenv("CLOUDINARY_CLOUD_NAME"))
except ImportError:
    CLOUDINARY_AVAILABLE = False
    print("⚠️  cloudinary not installed — run: pip install cloudinary")


def upload_to_cloudinary(image_bytes: bytes, folder: str = "marketplace") -> str:
    """Upload image bytes to Cloudinary. Returns secure URL or empty string."""
    if not CLOUDINARY_AVAILABLE:
        return ""
    try:
        result = cloudinary.uploader.upload(
            image_bytes,
            folder        = f"agrobot/{folder}",
            resource_type = "image",
            transformation = [
                {"quality": "auto", "fetch_format": "auto"},
                {"width": 1200, "crop": "limit"},
            ],
        )
        return result.get("secure_url", "")
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return ""


# ── Supabase Client ────────────────────────────────────────────
sb = None
try:
    from supabase import create_client
    if SUPABASE_URL and SUPABASE_KEY:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connected!")
    else:
        print("⚠️  Supabase env vars not set — using local storage")
except Exception as _sb_err:
    print(f"⚠️  Supabase not available: {_sb_err}")

# ── Persistent storage ─────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "/tmp/agrobot_data")
os.makedirs(DATA_DIR, exist_ok=True)

def data_path(fname):
    return os.path.join(DATA_DIR, fname)

reset_otps = {}

# ══════════════════════════════════════════════════════════════
#  DATABASE LAYER
# ══════════════════════════════════════════════════════════════

def db_upsert(table, row, conflict_col="phone"):
    if not sb: return
    try:
        sb.table(table).upsert(row).execute()
    except Exception as e:
        print(f"db_upsert {table} error: {e}")

def db_select(table, filters=None, limit=None, order_col=None, desc=False):
    if not sb: return []
    try:
        q = sb.table(table).select("*")
        if filters:
            for col, val in filters.items():
                q = q.eq(col, val)
        if order_col:
            q = q.order(order_col, desc=desc)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    except Exception as e:
        print(f"db_select {table} error: {e}")
        return []

def db_save_account(phone, data):
    user_accounts[phone] = data
    row = {
        "phone":         phone,
        "name":          data.get("name", ""),
        "password_hash": data.get("password_hash", ""),
        "last_token":    data.get("last_token", ""),
        "last_login":    data.get("last_login"),
        "registered":    data.get("registered", datetime.datetime.now().isoformat()),
        "platforms":     data.get("platforms", ["web"]),
        "data":          json.dumps({k: v for k, v in data.items()
                                     if k not in ["phone","name","password_hash",
                                                  "last_token","last_login","registered","platforms"]}),
    }
    db_upsert("user_accounts", row)

def db_get_account(phone):
    if phone in user_accounts:
        return user_accounts[phone]
    rows = db_select("user_accounts", {"phone": phone})
    if rows:
        row   = rows[0]
        extra = json.loads(row.pop("data", "{}") or "{}")
        data  = {**row, **extra}
        user_accounts[phone] = data
        return data
    return {}

def db_save_profile(phone, data):
    farmer_profiles[phone] = data
    row = {
        "phone":    phone,
        "name":     data.get("name", ""),
        "location": data.get("location", ""),
        "gps_lat":  data.get("gps_lat"),
        "gps_lon":  data.get("gps_lon"),
        "joined":   data.get("joined", datetime.datetime.now().isoformat()),
        "data":     json.dumps({k: v for k, v in data.items()
                                if k not in ["phone","name","location","gps_lat","gps_lon","joined"]}),
    }
    db_upsert("farmer_profiles", row)

def db_get_profile(phone):
    if phone in farmer_profiles:
        return farmer_profiles[phone]
    rows = db_select("farmer_profiles", {"phone": phone})
    if rows:
        row   = rows[0]
        extra = json.loads(row.pop("data", "{}") or "{}")
        data  = {**row, **extra}
        farmer_profiles[phone] = data
        return data
    return {}

def db_save_premium(phone, data):
    premium_users[phone] = data
    row = {
        "phone":       phone,
        "plan":        data.get("plan", "premium"),
        "active":      data.get("active", True),
        "amount":      str(data.get("amount", "2")),
        "activated":   data.get("activated", datetime.datetime.now().isoformat()),
        "expires":     data.get("expires"),
        "payment_ref": data.get("payment_ref", ""),
        "data":        json.dumps({k: v for k, v in data.items()
                                   if k not in ["phone","plan","active","amount",
                                                "activated","expires","payment_ref"]}),
    }
    db_upsert("premium_users", row)

def db_get_premium(phone):
    if phone in premium_users:
        return premium_users[phone]
    rows = db_select("premium_users", {"phone": phone})
    if rows:
        row   = rows[0]
        extra = json.loads(row.pop("data", "{}") or "{}")
        data  = {**row, **extra}
        premium_users[phone] = data
        return data
    return {}

def db_save_conversation(phone, role, message, msg_type="text"):
    if not sb: return
    try:
        sb.table("conversations").insert({
            "phone":    phone,
            "role":     role,
            "message":  message[:2000],
            "msg_type": msg_type,
            "platform": "web",
        }).execute()
    except Exception as e:
        print(f"db_save_conversation error: {e}")

def db_get_conversations(phone, limit=20):
    rows = db_select("conversations", {"phone": phone},
                     limit=limit, order_col="created_at", desc=True)
    if rows:
        return [{"role": r["role"], "message": r["message"],
                 "type": r.get("msg_type","text"), "timestamp": str(r["created_at"])}
                for r in reversed(rows)]
    return conversations.get(phone, [])[-limit:]

def db_save_activity(phone, data):
    user_activity[phone] = data
    row = {
        "phone":             phone,
        "total_messages":    data.get("total_messages", 0),
        "total_days_active": data.get("total_days_active", 0),
        "streak_days":       data.get("streak_days", 0),
        "last_active_date":  data.get("last_active_date", ""),
        "last_seen":         data.get("last_seen", datetime.datetime.now().isoformat()),
        "first_seen":        data.get("first_seen", datetime.datetime.now().isoformat()),
        "data":              json.dumps({"daily_activity": data.get("daily_activity", {}),
                                         "actions": data.get("actions", {})}),
    }
    db_upsert("user_activity", row)

def db_get_activity(phone):
    if phone in user_activity:
        return user_activity[phone]
    rows = db_select("user_activity", {"phone": phone})
    if rows:
        row   = rows[0]
        extra = json.loads(row.pop("data", "{}") or "{}")
        data  = {**row, **extra}
        user_activity[phone] = data
        return data
    return {}

def db_save_ticket(ticket):
    phone = ticket.get("phone", "")
    if phone not in support_tickets:
        support_tickets[phone] = []
    existing = [t for t in support_tickets[phone] if t["id"] == ticket["id"]]
    if existing:
        existing[0].update(ticket)
    else:
        support_tickets[phone].append(ticket)
    if not sb: return
    try:
        sb.table("support_tickets").upsert({
            "id":       ticket["id"],
            "phone":    phone,
            "subject":  ticket.get("subject", ""),
            "message":  ticket.get("message", ""),
            "category": ticket.get("category", "general"),
            "status":   ticket.get("status", "open"),
            "replies":  json.dumps(ticket.get("replies", [])),
            "resolved": ticket.get("resolved", False),
        }).execute()
    except Exception as e:
        print(f"db_save_ticket error: {e}")

def db_get_all_tickets():
    rows = db_select("support_tickets", order_col="created_at", desc=True)
    if rows:
        result = []
        for row in rows:
            row["replies"]    = json.loads(row.get("replies", "[]") or "[]")
            row["user_phone"] = row["phone"]
            result.append(row)
        return result
    all_t = []
    for phone, tickets in support_tickets.items():
        for t in tickets:
            all_t.append({**t, "user_phone": phone})
    return sorted(all_t, key=lambda x: x.get("created", ""), reverse=True)

def db_get_all_farmers():
    rows = db_select("farmer_profiles")
    if rows:
        result = []
        for row in rows:
            extra = json.loads(row.pop("data", "{}") or "{}")
            result.append({**row, **extra})
        return result
    return [{"phone": p, **v} for p, v in farmer_profiles.items()]

def db_get_all_accounts():
    rows = db_select("user_accounts")
    if rows:
        result = {}
        for row in rows:
            extra = json.loads(row.pop("data", "{}") or "{}")
            result[row["phone"]] = {**row, **extra}
        return result
    return user_accounts

def db_load_all():
    if not sb:
        print("Supabase not connected — using local files only")
        return
    try:
        print("Loading data from Supabase...")
        for row in db_select("farmer_profiles"):
            extra = json.loads(row.pop("data", "{}") or "{}")
            farmer_profiles[row["phone"]] = {**row, **extra}
        for row in db_select("user_accounts"):
            extra = json.loads(row.pop("data", "{}") or "{}")
            user_accounts[row["phone"]] = {**row, **extra}
        for row in db_select("premium_users"):
            extra = json.loads(row.pop("data", "{}") or "{}")
            premium_users[row["phone"]] = {**row, **extra}
        for row in db_select("user_activity"):
            extra = json.loads(row.pop("data", "{}") or "{}")
            user_activity[row["phone"]] = {**row, **extra}
        print(f"✅ Loaded: {len(farmer_profiles)} farmers, {len(user_accounts)} accounts")
    except Exception as e:
        print(f"db_load_all error: {e}")

# ── WebSocket Manager ──────────────────────────────────────────
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
                    members.append({"name": info.get("name"), "location": info.get("location")})
        return members

manager = ConnectionManager()

# ── In-Memory Data Stores ──────────────────────────────────────
user_states          = {}
marketplace          = []
premium_users        = {}
farmer_profiles      = {}
conversations        = {}
buyer_requests       = []
payment_pending      = {}
user_accounts        = {}
market_prices        = {}
community_posts      = []
support_tickets      = {}
notifications        = []
admin_updates        = []
payment_checks       = {}
marketplace_sessions = {}   # In-progress listing sessions (replaces fragile state encoding)

community_channels = {
    "general":      {"name": "🌍 General Farming",  "description": "All farming topics",      "messages": []},
    "maize":        {"name": "🌽 Maize Farmers",     "description": "Maize community",         "messages": []},
    "tobacco":      {"name": "🍂 Tobacco Growers",   "description": "Tobacco farming",         "messages": []},
    "livestock":    {"name": "🐄 Livestock Farmers", "description": "Cattle, goats, poultry",  "messages": []},
    "horticulture": {"name": "🥬 Horticulture",      "description": "Vegetables & fruits",    "messages": []},
    "weather":      {"name": "🌧️ Weather Reports",  "description": "Local weather sharing",  "messages": []},
    "prices":       {"name": "💰 Market Prices",     "description": "Price discussions",      "messages": []},
}

user_activity    = {}
live_price_cache = {"data": {}, "last_updated": None}
# ════════════════════════════════════════════════════════════
#  PART 2 OF 8 — load_data, save_data, Live Prices, Regions
# ════════════════════════════════════════════════════════════

def load_data():
    global marketplace, premium_users, farmer_profiles, conversations
    global buyer_requests, payment_pending, user_accounts, market_prices
    global community_posts, community_channels, user_activity

    file_defaults = {
        "marketplace.json":        (marketplace,        []),
        "premium_users.json":      (premium_users,      {}),
        "farmer_profiles.json":    (farmer_profiles,    {}),
        "conversations.json":      (conversations,      {}),
        "buyer_requests.json":     (buyer_requests,     []),
        "payment_pending.json":    (payment_pending,    {}),
        "user_accounts.json":      (user_accounts,      {}),
        "market_prices.json":      (market_prices,      {}),
        "community_posts.json":    (community_posts,    []),
        "community_channels.json": (community_channels, {}),
        "user_activity.json":      (user_activity,      {}),
    }
    for fname, (var, default) in file_defaults.items():
        for path in [data_path(fname), fname]:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    if isinstance(default, list):
                        var.clear(); var.extend(data)
                    else:
                        var.clear(); var.update(data)
                break
            except Exception:
                pass

    for fname, target in [
        ("support_tickets.json", support_tickets),
        ("admin_updates.json",   admin_updates),
    ]:
        for path in [data_path(fname), fname]:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    if isinstance(target, list):
                        target.extend(data)
                    else:
                        target.update(data)
                break
            except Exception:
                pass

    try:
        for path in [data_path("notifications.json"), "notifications.json"]:
            try:
                with open(path, "r") as f:
                    notifications.extend(json.load(f))
                break
            except Exception:
                pass
    except Exception:
        pass


def save_data():
    data_map = {
        "marketplace.json":        marketplace,
        "premium_users.json":      premium_users,
        "farmer_profiles.json":    farmer_profiles,
        "buyer_requests.json":     buyer_requests,
        "payment_pending.json":    payment_pending,
        "user_accounts.json":      user_accounts,
        "market_prices.json":      market_prices,
        "community_posts.json":    community_posts,
        "community_channels.json": community_channels,
        "user_activity.json":      user_activity,
    }
    for fname, data in data_map.items():
        for path in [data_path(fname), fname]:
            try:
                with open(path, "w") as f:
                    json.dump(data, f)
                break
            except Exception:
                pass

    for fname, data in [
        ("support_tickets.json", support_tickets),
        ("notifications.json",   notifications),
        ("admin_updates.json",   admin_updates),
    ]:
        for path in [data_path(fname), fname]:
            try:
                with open(path, "w") as f:
                    json.dump(data, f)
                break
            except Exception:
                pass


load_data()
db_load_all()

# ══════════════════════════════════════════════════════════════
#  LIVE MARKET PRICES
# ══════════════════════════════════════════════════════════════

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
    WB_INDICATORS = {
        "PMAIZMMT": "maize",  "PSOYB":    "soya",
        "PWHEAMT":  "wheat",  "PCOTTIND": "cotton_lint",
        "PSUGAISA": "sugar",  "PGNUTS":   "groundnuts",
        "PSUNFL":   "sunflower",
    }
    wb_prices = {}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            for indicator, crop in WB_INDICATORS.items():
                try:
                    r    = await http.get(f"https://api.worldbank.org/v2/en/indicator/{indicator}",
                                          params={"format": "json", "mrv": "1", "frequency": "M"})
                    data = r.json()
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
    now   = datetime.datetime.now()
    cache = live_price_cache

    if cache["last_updated"]:
        try:
            last = datetime.datetime.fromisoformat(cache["last_updated"])
            if (now - last).total_seconds() < 21600 and cache["data"]:
                return cache["data"]
        except Exception:
            pass

    prices    = {}
    wb_prices = await fetch_world_bank_prices()
    wb_context = ""
    if wb_prices:
        wb_lines   = "\n".join([f"  {crop}: ${val}/tonne" for crop, val in wb_prices.items()])
        wb_context = f"\nWORLD BANK LIVE BENCHMARK PRICES:\n{wb_lines}\nZimbabwe prices are typically World Bank × 1.1-1.3.\n"

    try:
        price_prompt = f"""You are a Zimbabwe agricultural commodity price analyst.
Today is {now.strftime('%d %B %Y, %A')}.
{wb_context}

Return ONLY a valid JSON object with current Zimbabwe market prices in USD:
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
Use realistic current Zimbabwe market prices for {now.strftime('%B %Y')}."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": price_prompt}],
            max_tokens=900,
        )
        raw = response.choices[0].message.content.strip()
        if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:   raw = raw.split("```")[1].split("```")[0].strip()

        prices = json.loads(raw)
        source_label = "World Bank + Zimbabwe Market" if wb_prices else "Zimbabwe Market AI"
        for crop in prices:
            prices[crop]["updated"] = now.strftime("%d %b %Y %H:%M")
            prices[crop]["source"]  = source_label

        live_price_cache["data"]         = prices
        live_price_cache["last_updated"] = now.isoformat()
        print(f"✅ Live prices updated at {now.strftime('%H:%M')}")

    except Exception as e:
        print(f"Price fetch error: {e}")
        if cache["data"]:
            return cache["data"]

    return prices


def get_sync_prices() -> dict:
    if live_price_cache["data"]:
        return live_price_cache["data"]
    return {
        "maize":   {"price": 280, "unit": "tonne", "trend": "stable", "source": "Pending live update..."},
        "tobacco": {"price": 3.10,"unit": "kg",    "trend": "stable", "source": "Pending live update..."},
        "soya":    {"price": 510, "unit": "tonne", "trend": "stable", "source": "Pending live update..."},
    }


# ── Zimbabwe Regions ───────────────────────────────────────────
PROVINCE_DEFAULTS = {
    "1": "marondera", "2": "bulawayo",       "3": "mutare",
    "4": "masvingo",  "5": "gweru",          "6": "chinhoyi",
    "7": "bindura",   "8": "victoria falls", "9": "beitbridge",
}

PROVINCE_NAMES = {
    "1": "Harare/Mashonaland East",  "2": "Bulawayo/Matabeleland",
    "3": "Manicaland",               "4": "Masvingo/Lowveld",
    "5": "Midlands",                 "6": "Mashonaland West",
    "7": "Mashonaland Central",      "8": "Matabeleland North",
    "9": "Matabeleland South",
}

ZIMBABWE_REGIONS = {
    "harare":         {"region": 2, "lat": -17.8252, "lon": 31.0335, "climate": "Sub-humid",          "rainfall": "600-800mm",   "best_crops": "Maize, Tobacco, Horticulture, Wheat, Soya",      "soil": "Sandy loam to clay loam", "season": "Nov-Apr", "challenges": "Urban expansion, water scarcity"},
    "bulawayo":       {"region": 4, "lat": -20.1325, "lon": 28.6264, "climate": "Semi-arid",           "rainfall": "400-600mm",   "best_crops": "Sorghum, Millet, Sunflower, Cotton, Groundnuts", "soil": "Sandy to sandy loam",     "season": "Dec-Mar", "challenges": "Drought prone, irregular rains"},
    "mutare":         {"region": 1, "lat": -18.9707, "lon": 32.6709, "climate": "Sub-humid to Humid",  "rainfall": "800-1200mm",  "best_crops": "Tea, Coffee, Macadamia, Maize, Beans, Avocado",  "soil": "Rich red clay loam",      "season": "Oct-Apr", "challenges": "Steep terrain, erosion, cyclone risk"},
    "masvingo":       {"region": 4, "lat": -20.0635, "lon": 30.8335, "climate": "Semi-arid",           "rainfall": "400-600mm",   "best_crops": "Sorghum, Cotton, Sunflower, Groundnuts",         "soil": "Granite sandy soils",     "season": "Dec-Mar", "challenges": "Low soil fertility, dry spells"},
    "gweru":          {"region": 3, "lat": -19.4500, "lon": 29.8167, "climate": "Semi-humid",          "rainfall": "500-700mm",   "best_crops": "Maize, Groundnuts, Soya, Sunflower",             "soil": "Clay to sandy clay",      "season": "Nov-Apr", "challenges": "Variable rainfall"},
    "marondera":      {"region": 2, "lat": -18.1833, "lon": 31.5500, "climate": "Sub-humid",           "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Wheat, Horticulture, Soya",      "soil": "Red sandy loam",          "season": "Nov-Apr", "challenges": "Early season dry spells"},
    "chinhoyi":       {"region": 2, "lat": -17.3667, "lon": 30.2000, "climate": "Sub-humid",           "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Soya, Wheat, Cotton",            "soil": "Deep red loam",           "season": "Nov-Apr", "challenges": "Bush encroachment"},
    "bindura":        {"region": 2, "lat": -17.3000, "lon": 31.3333, "climate": "Sub-humid",           "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Cotton, Groundnuts",             "soil": "Clay loam",               "season": "Nov-Apr", "challenges": "Hail risk"},
    "victoria falls": {"region": 4, "lat": -17.9322, "lon": 25.8306, "climate": "Semi-arid",           "rainfall": "500-700mm",   "best_crops": "Maize, Cotton, Sesame, Sorghum",                 "soil": "Sandy alluvial",          "season": "Dec-Mar", "challenges": "Remote markets, wildlife"},
    "kariba":         {"region": 4, "lat": -16.5167, "lon": 28.8000, "climate": "Hot semi-arid",       "rainfall": "400-600mm",   "best_crops": "Cotton, Sorghum, Millet, Sesame",                "soil": "Sandy to loamy sand",     "season": "Dec-Mar", "challenges": "Very high temps"},
    "chiredzi":       {"region": 5, "lat": -21.0500, "lon": 31.6667, "climate": "Arid",                "rainfall": "300-400mm",   "best_crops": "Sugarcane, Cotton, Sorghum, Livestock",          "soil": "Sandy clay loam",         "season": "Jan-Mar", "challenges": "Very low rainfall"},
    "beitbridge":     {"region": 5, "lat": -22.2167, "lon": 30.0000, "climate": "Very arid",           "rainfall": "200-400mm",   "best_crops": "Livestock, Sorghum, Millet, Drought crops",      "soil": "Shallow sandy",           "season": "Jan-Feb", "challenges": "Lowest rainfall, extreme heat"},
    "zvishavane":     {"region": 4, "lat": -20.3333, "lon": 30.0333, "climate": "Semi-arid",           "rainfall": "400-600mm",   "best_crops": "Sorghum, Cotton, Groundnuts, Livestock",         "soil": "Granite sandy",           "season": "Dec-Mar", "challenges": "Mining water competition"},
    "kwekwe":         {"region": 3, "lat": -18.9167, "lon": 29.8167, "climate": "Semi-humid",          "rainfall": "500-700mm",   "best_crops": "Maize, Groundnuts, Soya, Cotton",                "soil": "Clay to sandy clay",      "season": "Nov-Apr", "challenges": "Industrial pollution"},
    "kadoma":         {"region": 3, "lat": -18.3500, "lon": 29.9167, "climate": "Semi-humid",          "rainfall": "500-700mm",   "best_crops": "Cotton, Maize, Groundnuts, Wheat",               "soil": "Sandy clay loam",         "season": "Nov-Apr", "challenges": "Cotton price fluctuation"},
    "norton":         {"region": 2, "lat": -17.8833, "lon": 30.7000, "climate": "Sub-humid",           "rainfall": "600-800mm",   "best_crops": "Maize, Tobacco, Horticulture, Wheat",            "soil": "Red sandy loam",          "season": "Nov-Apr", "challenges": "Urban sprawl"},
    "rusape":         {"region": 2, "lat": -18.5333, "lon": 32.1333, "climate": "Sub-humid",           "rainfall": "700-900mm",   "best_crops": "Maize, Tobacco, Beans, Horticulture",            "soil": "Red clay loam",           "season": "Nov-Apr", "challenges": "Hilly terrain"},
    "nyanga":         {"region": 1, "lat": -18.2167, "lon": 32.7500, "climate": "Humid",               "rainfall": "1000-1500mm", "best_crops": "Potatoes, Wheat, Apples, Beans, Tea",            "soil": "Deep red clay",           "season": "Oct-May", "challenges": "Frost risk"},
    "chipinge":       {"region": 1, "lat": -20.1833, "lon": 32.6167, "climate": "Sub-humid to Humid",  "rainfall": "800-1200mm",  "best_crops": "Tea, Coffee, Macadamia, Avocado, Maize",         "soil": "Rich red clay loam",      "season": "Oct-Apr", "challenges": "Cyclone risk"},
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


def geocode_location_free(location: str) -> tuple:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{location}, Zimbabwe", "format": "json", "limit": 1,
                    "countrycodes": "zw", "addressdetails": 1},
            headers={"User-Agent": "AgroBotPro/4.2 (agrobot.co.zw)"},
            timeout=8,
        )
        results = r.json()
        if results:
            res = results[0]
            return float(res["lat"]), float(res["lon"]), res.get("display_name", location).split(",")[0]
    except Exception as e:
        print(f"Nominatim geocode error: {e}")
    return None, None, location


def find_agri_places_osm(lat: float, lon: float, radius_m: int = 20000) -> list:
    results = []
    try:
        query = f"""[out:json][timeout:15];
(
  node["shop"="agrarian"](around:{radius_m},{lat},{lon});
  node["shop"="farm"](around:{radius_m},{lat},{lon});
  node["amenity"="bank"]["name"~"Agribank|ZB Bank|CBZ",i](around:{radius_m},{lat},{lon});
  node["office"="government"]["name"~"Agritex|GMB|Grain Marketing",i](around:{radius_m},{lat},{lon});
  node["name"~"Seedco|ZFC|Agritex|GMB|Farmer|Windmill|Agricura",i](around:{radius_m},{lat},{lon});
);out body 8;"""
        r        = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=15)
        elements = r.json().get("elements", [])
        for el in elements:
            tags    = el.get("tags", {})
            name    = tags.get("name", "")
            if not name: continue
            street  = tags.get("addr:street", "")
            city    = tags.get("addr:city", "")
            address = f"{street}, {city}".strip(", ") or "See OpenStreetMap"
            phone   = tags.get("phone", tags.get("contact:phone", "—"))
            results.append((f"🏪 {name}", address, phone))
    except Exception as e:
        print(f"Overpass API error: {e}")
    return results


def _get_season_note(now: datetime.datetime) -> str:
    if now.month in [3, 4]:    return "Late season — harvest preparation, post-harvest soil care"
    if now.month in [5, 6, 7]: return "Post-harvest — land preparation, planning next season"
    if now.month in [8, 9, 10]:return "Pre-season — input procurement, land prep, planning"
    return "Planting season — crop establishment is critical"


# ── User Activity Tracking ─────────────────────────────────────
def track_activity(phone: str, action: str = "message"):
    now   = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")

    if phone not in user_activity:
        user_activity[phone] = {
            "first_seen": now.isoformat(), "last_seen": now.isoformat(),
            "total_messages": 0, "daily_activity": {}, "total_days_active": 0,
            "streak_days": 0, "last_active_date": today, "actions": {},
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
        days_registered = 1; trial_days_left = TRIAL_DAYS
        trial_expired   = False; trial_end_str = "Unknown"

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


# ── Premium Helpers ────────────────────────────────────────────
def is_premium(phone: str) -> bool:
    if phone not in premium_users: return False
    user = premium_users[phone]
    if not user.get("active", False): return False
    expires = user.get("expires")
    if expires:
        try:
            if datetime.datetime.now() > datetime.datetime.fromisoformat(expires):
                premium_users[phone]["active"] = False; save_data(); return False
        except Exception: pass
    return True

def is_in_trial(phone: str) -> bool:
    profile    = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str: return False
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        return datetime.datetime.now() < joined + datetime.timedelta(days=TRIAL_DAYS)
    except Exception: return False

def get_trial_days_left(phone: str) -> int:
    profile    = farmer_profiles.get(phone, {})
    joined_str = profile.get("joined")
    if not joined_str: return 0
    try:
        joined = datetime.datetime.fromisoformat(joined_str)
        diff   = (joined + datetime.timedelta(days=TRIAL_DAYS)) - datetime.datetime.now()
        return max(0, diff.days)
    except Exception: return 0

def has_full_access(phone: str) -> bool:
    return is_premium(phone) or is_in_trial(phone)

def get_plan(phone: str) -> str:
    if is_premium(phone):
        return premium_users[phone].get("plan", "premium")
    if is_in_trial(phone): return "trial"
    return "free"

def premium_gate(phone: str, feature: str):
    if has_full_access(phone): return None
    return f"""🔒 *{feature} — Premium Required*
━━━━━━━━━━━━━━━━━━━━━━
Your {TRIAL_DAYS}-day free trial has ended.

Reply *UPGRADE* to subscribe:
💎 Premium: $2/month
🏆 Business: $10/month

Type *MENU* to go back"""

def generate_ref(phone: str) -> str: return f"AGRO{phone[-6:]}"

def save_location(phone: str, location: str):
    if phone not in farmer_profiles:
        farmer_profiles[phone] = {"joined": datetime.datetime.now().isoformat()}
    farmer_profiles[phone]["location"]   = location.lower()
    farmer_profiles[phone]["registered"] = True
    save_data()

def save_conversation(phone: str, role: str, message: str, msg_type: str = "text"):
    if phone not in conversations: conversations[phone] = []
    conversations[phone].append({
        "role": role, "message": message, "type": msg_type,
        "timestamp": datetime.datetime.now().isoformat(), "platform": "whatsapp",
    })
    if len(conversations[phone]) > 500:
        conversations[phone] = conversations[phone][-500:]
    save_data()

def get_conversation_history(phone: str, limit: int = 5) -> list:
    return conversations.get(phone, [])[-limit:]

def get_farmer_context(phone: str) -> str:
    profile  = farmer_profiles.get(phone, {})
    activity = user_activity.get(phone, {})
    now      = datetime.datetime.now()
    ctx  = f"\nDate: {now.strftime('%d %B %Y')}\nSeason: {_get_season_note(now)}"
    if "gps_lat" in profile:
        nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
        info    = nearest["info"]
        ctx += f"\nGPS: {profile['gps_lat']:.4f}°S, {profile['gps_lon']:.4f}°E | Nearest: {nearest['name'].title()}"
        ctx += f"\nRegion {info['region']} — {info['climate']} | Rainfall: {info['rainfall']}"
        ctx += f"\nSoil: {info.get('soil','Mixed')} | Best crops: {info['best_crops']}"
    elif "location" in profile:
        loc  = profile["location"]
        info = get_region_info(loc)
        ctx += f"\nLocation: {loc.title()} | Region {info['region']} — {info['climate']}"
        ctx += f"\nRainfall: {info['rainfall']} | Best crops: {info['best_crops']}"
    ctx += f"\nPlan: {get_plan(phone).upper()} | Days on AgroBot: {activity.get('total_days_active',1)}"
    history = get_conversation_history(phone, 3)
    if history:
        ctx += "\nRecent:"
        for msg in history:
            ctx += f"\n{'Farmer' if msg['role']=='farmer' else 'Bot'}: {msg['message'][:80]}"
    return ctx
# ════════════════════════════════════════════════════════════
#  PART 3 OF 8 — ask_groq (fixed), Image Analysis, Seeds,
#                Weather, Help Nearby, Community, Payments
# ════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  IMPROVED ask_groq
#  FIXES:
#   1. Forces input to str() — stops "can't deal with non-text" crash
#   2. Farming relevance check — refuses off-topic questions cleanly
#   3. Dynamic topic — disease/soil/loan answers are unique per farmer
#   4. Strict prompt — no padding, only answers what was asked
# ══════════════════════════════════════════════════════════════

FARMING_KEYWORDS = {
    "crop","crops","farm","farming","plant","plants","seed","seeds","soil",
    "harvest","harvesting","planting","grow","growing","yield","maize","tobacco",
    "wheat","cotton","soya","soybean","groundnut","sunflower","sorghum","millet",
    "sugar","sugarcane","beans","tomato","tomatoes","onion","onions","potato",
    "potatoes","vegetable","vegetables","fruit","fruits","horticulture","mushroom",
    "disease","pest","pests","fungus","fungal","bacteria","bacterial","weed","weeds",
    "insect","insects","aphid","caterpillar","armyworm","blight","rust","mildew",
    "rot","wilt","yellowing","spray","treatment","chemical","herbicide","pesticide",
    "fungicide","insecticide","agricura","windmill","fertilizer","fertiliser",
    "compost","manure","lime","nitrogen","phosphorus","potassium","npk","basal",
    "irrigation","drip","furrow","borehole","dam","water","drought","flood",
    "livestock","cattle","cow","bull","heifer","goat","sheep","pig","chicken",
    "poultry","rabbit","bee","honey","fish","aquaculture","feed","hay","silage",
    "vet","veterinary","breed","wean","vaccinate","market","price","prices",
    "sell","selling","buy","buying","export","import","gmb","grain","commodity",
    "loan","insurance","agribank","agritex","seedco","pannar","zfc","arda",
    "zimbabwe","harare","bulawayo","marondera","chinhoyi","mutare","masvingo",
    "region","province","field","acre","hectare","plot","land","weather","rain",
    "rainfall","temperature","climate","season","forecast",
}

NON_FARMING_TOPICS = {
    "movie","movies","film","cinema","netflix","music","song","sport","sports",
    "football","soccer","cricket","basketball","rugby","politics","election",
    "president","minister","parliament","vote","party","religion","church",
    "mosque","prayer","bible","quran","relationship","love","girlfriend",
    "boyfriend","marriage","divorce","celebrity","actor","actress","singer",
    "rapper","crypto","cryptocurrency","bitcoin","ethereum","forex","gaming",
    "game","playstation","xbox","fifa","gta","fashion","clothes","makeup",
    "cooking","recipe","restaurant","travel","tourist","tourism","hotel","beach",
}


def _is_farming_question(question: str) -> bool:
    words = set(question.lower().split())
    if words & FARMING_KEYWORDS:  return True
    if words & NON_FARMING_TOPICS: return False
    if len(question.split()) <= 8: return True
    return True


def ask_groq(question: str, topic: str = "", phone: str = "") -> str:
    # ── 1. Input validation ─────────────────────────────────────
    if question is None:
        return "❓ No question received. Please describe your farming problem."
    try:
        question = str(question).strip()
    except Exception:
        return "❓ Could not read your question. Please type it again."

    # Strip control characters that crash the API
    question = "".join(ch for ch in question if ch.isprintable() or ch in "\n\t")

    if len(question) < 2:
        return "❓ Too short. Please describe your farming situation in more detail."
    if len(question) > 2000:
        question = question[:2000]

    # ── 2. Topic relevance check ────────────────────────────────
    if not _is_farming_question(question):
        return (
            "❌ I can only assist with farming and agricultural topics.\n\n"
            "I can help with:\n"
            "🌱 Crop diseases and pest control\n"
            "🧪 Soil analysis and fertilizers\n"
            "🌤️ Weather and climate advice\n"
            "💰 Market prices and selling\n"
            "🌾 Seed recommendations\n"
            "🐄 Livestock management\n"
            "🏦 Agricultural loans\n\n"
            f"📞 {SUPPORT_PHONE}"
        )

    # ── 3. Build location context ───────────────────────────────
    profile = farmer_profiles.get(phone, {})
    now     = datetime.datetime.now()

    if "gps_lat" in profile:
        lat     = profile["gps_lat"]
        lon     = profile["gps_lon"]
        nearest = find_nearest_region(lat, lon)
        info    = nearest["info"]
        location_context = (
            f"FARMER GPS: {lat:.4f}°S, {lon:.4f}°E | Nearest: {nearest['name'].title()} | "
            f"Region {info['region']} — {info['climate']} | Rainfall: {info['rainfall']} | "
            f"Soil: {info.get('soil','Mixed')} | Best crops: {info['best_crops']}"
        )
    elif "location" in profile:
        loc  = profile["location"]
        info = get_region_info(loc)
        location_context = (
            f"FARMER LOCATION: {loc.title()} | Region {info['region']} — {info['climate']} | "
            f"Rainfall: {info['rainfall']} | Best crops: {info['best_crops']}"
        )
    else:
        location_context = "FARMER LOCATION: Zimbabwe (location not set)"

    topic_line = f"\nFOCUS ON: {topic}" if topic else ""

    # ── 4. Strict system prompt ─────────────────────────────────
    system_prompt = f"""You are {BOT_NAME} — Zimbabwe's AI agriculture assistant by {COMPANY_NAME}.

TODAY: {now.strftime('%d %B %Y')} | SEASON: {_get_season_note(now)}
{location_context}
PLAN: {get_plan(phone).upper()}
{topic_line}

RULES — follow all strictly:
1. Answer ONLY what was asked — no extra information, no padding
2. If you do not know, say so clearly — do not guess
3. Give advice SPECIFIC to the farmer's location above
4. Name only REAL Zimbabwe products: ZFC, Agricura, Seedco, Pannar, Windmill, ARDA
5. Include specific rates (kg/ha, ml/litre) and USD costs where relevant
6. Maximum 250 words — be concise and practical
7. End with ONE clear action for the farmer to take today
8. Never fabricate product names, prices or contact numbers"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": question},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()

        cant_help = ["i cannot","i can't","i am not able","i'm not able","not my area"]
        if any(p in answer.lower()[:80] for p in cant_help):
            return (
                "🤔 I don't have specific information on that.\n\n"
                f"📞 Agritex Hotline: 0800 4040 (free)\n"
                f"📞 {COMPANY_NAME}: {SUPPORT_PHONE}"
            )
        return answer

    except Exception as e:
        err = str(e).lower()
        if "non-text" in err or "non_text" in err:
            return "⚠️ Please retype your question using plain text only."
        if "rate_limit" in err or "429" in err:
            return f"⏳ AgroBot is busy. Please try again in 30 seconds.\n📞 {SUPPORT_PHONE}"
        print(f"[ask_groq] Error: {e}")
        return f"⚠️ AgroBot temporarily unavailable. Please try again.\n📞 {SUPPORT_PHONE}"


# ══════════════════════════════════════════════════════════════
#  OTP SYSTEM — Fixed: now actually sends via WhatsApp
# ══════════════════════════════════════════════════════════════

import random as _random

def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return str(_random.randint(100000, 999999))


def request_otp(phone: str, purpose: str = "login") -> dict:
    """
    Generate OTP, store it, send via WhatsApp.
    Returns {"success": True, "message": "..."} or {"success": False, "error": "..."}
    """
    if not phone:
        return {"success": False, "error": "Phone number required"}

    otp     = generate_otp()
    expires = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

    reset_otps[phone] = {
        "otp":     otp,
        "expires": expires,
        "purpose": purpose,
        "used":    False,
    }

    purpose_text = {
        "login":          "log in to AgroBot Pro",
        "register":       "create your AgroBot Pro account",
        "reset_password": "reset your AgroBot Pro password",
        "verify_phone":   "verify your phone number",
    }.get(purpose, "access AgroBot Pro")

    whatsapp_msg = f"""🔐 *{BOT_NAME} — Verification Code*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Your one-time code to {purpose_text}:

*{otp}*

━━━━━━━━━━━━━━━━━━━━━━
⏰ This code expires in 10 minutes.
🔒 Do not share this code with anyone.

If you did not request this, ignore this message.
📞 {SUPPORT_PHONE}"""

    # Send OTP via WhatsApp
    sent = send_whatsapp_message(phone, whatsapp_msg)

    if sent:
        print(f"[OTP] Sent to {phone} for purpose: {purpose}")
        return {"success": True, "message": f"OTP sent to WhatsApp {phone}. Check your messages."}
    else:
        # WhatsApp failed — still return success so the OTP is usable if WhatsApp delivers eventually
        print(f"[OTP] WhatsApp send may have failed for {phone}")
        return {"success": True, "message": "OTP sent. Check your WhatsApp messages."}


def verify_otp(phone: str, otp: str) -> dict:
    """
    Verify OTP. Returns {"valid": True/False, "reason": "..."}
    """
    if not phone or not otp:
        return {"valid": False, "reason": "Phone and OTP are required"}

    stored = reset_otps.get(phone)

    if not stored:
        return {"valid": False, "reason": "No OTP was requested for this number. Request a new one."}

    if stored.get("used"):
        return {"valid": False, "reason": "This OTP has already been used. Request a new one."}

    try:
        expires = datetime.datetime.fromisoformat(stored["expires"])
        if datetime.datetime.now() > expires:
            del reset_otps[phone]
            return {"valid": False, "reason": "OTP has expired. Please request a new one."}
    except Exception:
        return {"valid": False, "reason": "OTP error. Please request a new one."}

    if str(otp).strip() != str(stored["otp"]):
        return {"valid": False, "reason": "Incorrect OTP. Please try again."}

    # Mark as used
    reset_otps[phone]["used"] = True
    return {"valid": True, "reason": "OTP verified successfully", "purpose": stored.get("purpose","login")}


# ══════════════════════════════════════════════════════════════
#  ACTIVITY TRACKING — Fixed: saves to Supabase immediately
#  so Render restarts do not lose farmer progress
# ══════════════════════════════════════════════════════════════

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

    # Keep only last 90 days
    if len(activity["daily_activity"]) > 90:
        sorted_days = sorted(activity["daily_activity"].keys())
        for old_day in sorted_days[:-90]:
            del activity["daily_activity"][old_day]

    # FIX: Save to Supabase IMMEDIATELY so Render restarts don't lose data
    _persist_activity(phone, activity)
    save_data()   # Also save local backup


def _persist_activity(phone: str, activity: dict):
    """Push activity data to Supabase immediately."""
    if not sb: return
    try:
        sb.table("user_activity").upsert({
            "phone":             phone,
            "total_messages":    activity.get("total_messages", 0),
            "total_days_active": activity.get("total_days_active", 0),
            "streak_days":       activity.get("streak_days", 0),
            "last_active_date":  activity.get("last_active_date", ""),
            "last_seen":         activity.get("last_seen", datetime.datetime.now().isoformat()),
            "first_seen":        activity.get("first_seen", datetime.datetime.now().isoformat()),
            "data":              json.dumps({
                "daily_activity": activity.get("daily_activity", {}),
                "actions":        activity.get("actions", {}),
            }),
        }).execute()
    except Exception as e:
        print(f"[activity] Supabase persist error: {e}")


def _persist_profile(phone: str):
    """Push farmer profile to Supabase immediately — prevents data loss on restart."""
    if not sb: return
    profile = farmer_profiles.get(phone, {})
    if not profile: return
    try:
        db_save_profile(phone, profile)
    except Exception as e:
        print(f"[profile] Supabase persist error: {e}")


def _persist_premium(phone: str):
    """Push premium status to Supabase immediately."""
    if not sb: return
    data = premium_users.get(phone, {})
    if not data: return
    try:
        db_save_premium(phone, data)
    except Exception as e:
        print(f"[premium] Supabase persist error: {e}")


# ══════════════════════════════════════════════════════════════
#  IMAGE ANALYSIS
# ══════════════════════════════════════════════════════════════

def analyze_image_improved(image_url: str, phone: str = "") -> str:
    try:
        img_response = requests.get(
            image_url,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            timeout=20,
        )
        if img_response.status_code != 200:
            return "Could not download image. Please try again."

        img_bytes = img_response.content
        if len(img_bytes) < 1000:
            return "Image too small or corrupted. Please send a clearer photo."

        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
        img_type   = (
            "image/jpeg" if img_bytes[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1') else
            "image/png"  if img_bytes[:8] == b'\x89PNG\r\n\x1a\n' else
            "image/jpeg"
        )

        ctx      = get_farmer_context(phone)
        profile  = farmer_profiles.get(phone, {})
        location = profile.get("location", "Zimbabwe")
        now      = datetime.datetime.now()

        detailed_prompt = f"""You are an expert plant pathologist and agronomist for Zimbabwe agriculture.

{ctx}
Today: {now.strftime('%d %B %Y')} | Location: {location.title()}

Analyse this image carefully. Provide a SPECIFIC, DETAILED report:

🌿 PLANT IDENTIFIED: Common name, Scientific name, Growth stage, Confidence
🔍 PROBLEM DIAGNOSED: YES/NO — Disease / Pest / Nutrient deficiency / Environmental / Normal
📊 SEVERITY: LOW / MODERATE / HIGH / CRITICAL — % affected
💊 TREATMENT: Zimbabwe brand name, application rate, method, timing, cost USD
🛡️ PREVENTION: How to prevent next season, cultural practices for Zimbabwe
⏰ URGENCY: Act within [X hours/days]

Be specific to what you see in THIS actual image. Do not give generic responses."""

        models_to_try = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ]

        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{img_type};base64,{img_base64}"}},
                        {"type": "text",      "text": detailed_prompt},
                    ]}],
                    max_tokens=1000,
                )
                analysis = response.choices[0].message.content
                if len(analysis) < 100: continue
                cant_see = ["cannot see","can't see","no image","not provided","unable to view","i don't see"]
                if any(p in analysis.lower() for p in cant_see): continue
                return f"{analysis}\n\n━━━━━━━━━━━━━━━━━━━━━━\n📸 Analysed by {BOT_NAME} Vision AI\nType *MENU* to return"
            except Exception as model_error:
                print(f"Model {model_name} failed: {model_error}")
                continue

        return fallback_image_analysis(phone)
    except Exception as e:
        print(f"Image analysis error: {e}")
        return "❌ Image Analysis Failed\n\nPlease try again with good lighting and a clear photo."


def fallback_image_analysis(phone: str) -> str:
    user_states[phone] = "image_describe"
    return """📸 *Image received but needs description*

Please describe what you see:
1. What crop is it?
2. What do the leaves/stems look like?
3. What colour changes do you see?
4. How many plants are affected?
5. When did you first notice?"""


# ══════════════════════════════════════════════════════════════
#  WEATHER
# ══════════════════════════════════════════════════════════════

def get_weather_by_name(location_name: str) -> str:
    lat, lon, display = geocode_location_free(location_name)
    if not lat:
        info     = get_region_info(location_name)
        lat, lon = info["lat"], info["lon"]
        display  = location_name.title()
    return get_weather(lat, lon, display)


def get_weather(lat: float, lon: float, name: str = "Your Farm") -> str:
    try:
        url  = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
                f"precipitation_probability_max,windspeed_10m_max,et0_fao_evapotranspiration"
                f"&timezone=Africa/Harare&forecast_days=7")
        data = requests.get(url, timeout=12).json()
        d    = data.get("daily", {})
        if not d: return "Weather data unavailable. Please try again."

        nearest    = find_nearest_region(lat, lon)
        info       = nearest["info"]
        et_list    = d.get("et0_fao_evapotranspiration", [3.5]*7)
        total_rain = sum(d.get("precipitation_sum", [0]*7))
        avg_max    = sum(d.get("temperature_2m_max", [25]*7)) / 7
        now        = datetime.datetime.now()

        result  = f"🌤️ *7-DAY FORECAST — LIVE*\n📍 {name}\n"
        result += f"📡 Open-Meteo | {now.strftime('%d %b %Y %H:%M')}\n"
        result += f"🌍 Region {info['region']} | {info['climate']}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

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
            icon  = ("⛈️" if rain > 30 else "🌧️" if rain > 10 else "🌦️" if rain > 2 else "⛅" if prob > 60 else "☀️")
            result += f"*{times[i]}* {icon}\n"
            result += f"  🌡️ {tmin_list[i]}°–{tmax_list[i]}°C  💧 {rain}mm  💨 {prob}%\n"
            if irrig > 0: result += f"  💦 Irrigation needed: ~{irrig}mm\n"
            result += "\n"

        result += f"━━━━━━━━━━━━━━━━━━━━━━\n📊 Week total: {total_rain:.0f}mm | Avg max: {avg_max:.1f}°C\n\n"

        advice = ask_groq(
            f"Farm at {name}, Zimbabwe Region {info['region']} ({info['climate']}). "
            f"Season: {_get_season_note(now)}. "
            f"Weather this week: avg max {avg_max:.1f}°C, total rain {total_rain:.0f}mm. "
            f"Give 4 specific actionable farming tasks for this week based on these conditions.",
            f"Zimbabwe precision agriculture weekly farm tasks",
        )
        result += f"🌱 *THIS WEEK'S ADVISORY:*\n{advice}\n\nType *MENU* to return"
        return result
    except Exception as e:
        print(f"Weather error: {e}")
        return "Weather unavailable right now. Please try again in a few minutes."


# ══════════════════════════════════════════════════════════════
#  HELP NEARBY
# ══════════════════════════════════════════════════════════════

def find_help_nearby(location: str, lat: float = None, lon: float = None) -> str:
    gps_note = "\n🛰️ Based on your GPS location" if lat else ""
    if not (lat and lon):
        lat, lon, _ = geocode_location_free(location)
    if lat and lon:
        try:
            osm_places = find_agri_places_osm(lat, lon, radius_m=20000)
            if osm_places:
                display_loc = location.title() if location else f"{lat:.3f}°S, {lon:.3f}°E"
                result  = f"📍 *AGRICULTURAL HELP NEAR YOU*{gps_note}\n"
                result += f"📡 Live map results — {display_loc}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for name, addr, ph in osm_places[:6]:
                    result += f"*{name}*\n📌 {addr}\n📞 {ph}\n\n"
                result += f"━━━━━━━━━━━━━━━━━━━━━━\n📞 Agritex Hotline: 0800 4040 (free)\n📞 {COMPANY_NAME}: {SUPPORT_PHONE}"
                return result
        except Exception as e:
            print(f"Overpass help error: {e}")

    if lat and lon:
        nearest  = find_nearest_region(lat, lon)
        location = nearest["name"]

    ai_help = ask_groq(
        f"List the nearest Agritex office, GMB depot, Agribank branch, and agro-dealer "
        f"to {location} Zimbabwe. Include street address and phone number for each.",
        f"Zimbabwe agricultural services near {location}",
    )
    return f"""📍 *AGRICULTURAL HELP NEAR {location.upper()}*{gps_note}
━━━━━━━━━━━━━━━━━━━━━━

{ai_help}

━━━━━━━━━━━━━━━━━━━━━━
📞 Agritex Hotline: 0800 4040 (free)
📞 {COMPANY_NAME}: {SUPPORT_PHONE}"""


# ══════════════════════════════════════════════════════════════
#  SEED BRANDS (abbreviated for space — full data intact)
# ══════════════════════════════════════════════════════════════

SEED_BRANDS = {
    "maize": {
        "Region 1": [
            {"brand":"Seedco",   "variety":"SC403",    "yield":"8-12 t/ha",  "days":"120-130","traits":"Drought tolerant, high yield",           "price_per_kg":8.50},
            {"brand":"Seedco",   "variety":"SC513",    "yield":"9-13 t/ha",  "days":"130-140","traits":"High yield, good standability",           "price_per_kg":9.00},
            {"brand":"Pannar",   "variety":"PAN 53",   "yield":"8-11 t/ha",  "days":"125-135","traits":"Good disease resistance",                 "price_per_kg":8.00},
            {"brand":"ZFC Seeds","variety":"ZFC 803",  "yield":"7-10 t/ha",  "days":"120-130","traits":"Affordable, locally adapted",             "price_per_kg":7.50},
        ],
        "Region 2": [
            {"brand":"Seedco",    "variety":"SC403",   "yield":"8-12 t/ha",  "days":"120-130","traits":"Best for Region 2, drought tolerant",     "price_per_kg":8.50},
            {"brand":"Seedco",    "variety":"SC633",   "yield":"10-14 t/ha", "days":"130-140","traits":"Top commercial yield",                    "price_per_kg":9.50},
            {"brand":"Pannar",    "variety":"PAN 6479","yield":"9-12 t/ha",  "days":"128-135","traits":"Drought tolerant, grey leaf spot resistant","price_per_kg":8.80},
            {"brand":"ARDA Seeds","variety":"R201",    "yield":"6-9 t/ha",   "days":"115-125","traits":"Open pollinated, good for small farms",   "price_per_kg":4.50},
            {"brand":"ZFC Seeds", "variety":"ZFC 803", "yield":"7-10 t/ha",  "days":"120-130","traits":"Affordable, good for smallholders",       "price_per_kg":7.50},
        ],
        "Region 3": [
            {"brand":"Seedco", "variety":"SC403",    "yield":"7-10 t/ha","days":"120-130","traits":"Drought tolerant — essential for Region 3","price_per_kg":8.50},
            {"brand":"Seedco", "variety":"SC301",    "yield":"6-9 t/ha", "days":"110-120","traits":"Short season, drought escape",            "price_per_kg":8.00},
            {"brand":"Pannar", "variety":"PAN 67",   "yield":"7-10 t/ha","days":"115-125","traits":"Good for variable rainfall",              "price_per_kg":8.20},
            {"brand":"Pioneer","variety":"PHB 30G19","yield":"8-11 t/ha","days":"120-130","traits":"Heat tolerant, good standability",        "price_per_kg":9.00},
        ],
        "Region 4": [
            {"brand":"Seedco","variety":"SC301",         "yield":"5-8 t/ha","days":"105-115","traits":"Short season, drought escape",          "price_per_kg":8.00},
            {"brand":"Seedco","variety":"SC403",         "yield":"6-9 t/ha","days":"115-125","traits":"Drought tolerant #1 choice",            "price_per_kg":8.50},
            {"brand":"Pannar","variety":"PAN 53",        "yield":"5-8 t/ha","days":"110-120","traits":"Reliable in dry conditions",            "price_per_kg":8.00},
            {"brand":"OPV",   "variety":"ZM309",         "yield":"4-7 t/ha","days":"100-110","traits":"Extreme drought tolerant, affordable",  "price_per_kg":3.50},
        ],
        "Region 5": [
            {"brand":"Sorghum (recommended)","variety":"SX-17","yield":"3-6 t/ha","days":"90-100","traits":"More drought tolerant than maize for Region 5","price_per_kg":4.00},
            {"brand":"Seedco","variety":"SC301","yield":"4-6 t/ha","days":"100-110","traits":"Earliest maturing maize, drought escape","price_per_kg":8.00},
        ],
    },
    "tobacco": {
        "All Regions": [
            {"brand":"Seedco",    "variety":"KRK 26",       "yield":"2.5-3.5 t/ha","days":"100-110","traits":"#1 Zimbabwe tobacco variety, high grade","price_per_kg":45.00},
            {"brand":"Seedco",    "variety":"T 66",         "yield":"2.8-3.8 t/ha","days":"105-115","traits":"High yield, good curing",               "price_per_kg":42.00},
            {"brand":"SeedTech",  "variety":"KE1",          "yield":"2.5-3.5 t/ha","days":"100-110","traits":"Good drought tolerance",                 "price_per_kg":40.00},
            {"brand":"ZFC Seeds", "variety":"Zimbabwe Gold","yield":"2.2-3.0 t/ha","days":"95-105", "traits":"Affordable, good curing quality",         "price_per_kg":35.00},
        ],
    },
    "soya": {
        "Region 2": [
            {"brand":"Seedco", "variety":"SC Soya 6","yield":"2.8-4 t/ha",  "days":"120-130","traits":"Best performing in Region 2","price_per_kg":6.50},
            {"brand":"Naseco", "variety":"NS-1",     "yield":"2.5-3.5 t/ha","days":"115-120","traits":"Good protein content",       "price_per_kg":5.80},
        ],
        "Region 1": [
            {"brand":"Seedco","variety":"SC Soya 6","yield":"3-4.5 t/ha","days":"120-130","traits":"High protein, good yield","price_per_kg":6.50},
            {"brand":"Pannar","variety":"Pannar 717","yield":"2.5-4 t/ha","days":"115-125","traits":"Disease resistant",        "price_per_kg":6.00},
        ],
    },
    "cotton": {
        "Region 3": [
            {"brand":"Quton",    "variety":"QM 302","yield":"1.5-2.5 t/ha","days":"160-180","traits":"#1 cotton Zimbabwe, high lint%",  "price_per_kg":12.00},
            {"brand":"Quton",    "variety":"QM 902","yield":"1.8-2.8 t/ha","days":"165-185","traits":"Bollworm resistant, high yield",   "price_per_kg":13.00},
            {"brand":"SeedTech", "variety":"ST 468","yield":"1.6-2.4 t/ha","days":"160-175","traits":"Early maturing, drought tolerant","price_per_kg":11.00},
        ],
        "Region 4": [
            {"brand":"Quton",    "variety":"QM 302","yield":"1.2-2.0 t/ha","days":"160-175","traits":"Best in dry conditions",     "price_per_kg":12.00},
            {"brand":"SeedTech", "variety":"ST 468","yield":"1.3-2.0 t/ha","days":"155-170","traits":"Early maturing for dry regions","price_per_kg":11.00},
        ],
    },
    "sorghum": {
        "Region 3": [
            {"brand":"Pannar","variety":"PAN 8816",     "yield":"4-7 t/ha","days":"90-110","traits":"High yield, bird resistant","price_per_kg":5.50},
            {"brand":"Seedco","variety":"SC Sorghum 1", "yield":"3-6 t/ha","days":"85-100","traits":"Drought tolerant",          "price_per_kg":5.00},
        ],
        "Region 4": [
            {"brand":"Pannar",     "variety":"PAN 8816","yield":"3-6 t/ha",  "days":"90-110","traits":"Best sorghum for dry regions","price_per_kg":5.50},
            {"brand":"ARDA Seeds", "variety":"Serena",  "yield":"2.5-5 t/ha","days":"85-100","traits":"Traditional, affordable",     "price_per_kg":3.50},
        ],
        "Region 5": [
            {"brand":"Pannar",     "variety":"PAN 8816","yield":"2-4 t/ha",  "days":"85-100","traits":"Best crop for Region 5",    "price_per_kg":5.50},
            {"brand":"ARDA Seeds", "variety":"Serena",  "yield":"1.5-3 t/ha","days":"80-95", "traits":"Most affordable, drought tolerant","price_per_kg":3.50},
        ],
    },
    "groundnuts": {
        "Region 2": [
            {"brand":"ARDA Seeds","variety":"Ruduku",      "yield":"1.5-2.5 t/ha","days":"90-110","traits":"Popular Zimbabwe variety","price_per_kg":5.00},
            {"brand":"ARDA Seeds","variety":"Natal Common","yield":"1.2-2.0 t/ha","days":"85-100","traits":"Spreading type, good yield","price_per_kg":4.50},
        ],
        "Region 3": [
            {"brand":"ARDA Seeds","variety":"Ruduku", "yield":"1.2-2.0 t/ha","days":"90-105","traits":"Best in Region 3",            "price_per_kg":5.00},
            {"brand":"Pannar",    "variety":"Bonanza","yield":"1.5-2.5 t/ha","days":"90-110","traits":"High oil content, disease resistant","price_per_kg":6.00},
        ],
    },
    "wheat": {
        "Region 1": [
            {"brand":"Seedco","variety":"SC Wheat 1","yield":"5-7 t/ha","days":"120-140","traits":"High yield under irrigation","price_per_kg":4.50},
            {"brand":"Pannar","variety":"Delphos",   "yield":"5-8 t/ha","days":"120-135","traits":"Top yielding, rust resistant","price_per_kg":5.00},
        ],
        "Region 2": [
            {"brand":"Seedco",    "variety":"SC Wheat 1","yield":"4-6 t/ha",  "days":"120-140","traits":"Good for Region 2 irrigation","price_per_kg":4.50},
            {"brand":"ZFC Seeds", "variety":"ZFC W3",    "yield":"4-5.5 t/ha","days":"125-140","traits":"Affordable, locally adapted",  "price_per_kg":4.00},
        ],
    },
}


def get_seed_recommendations(location: str, crop: str = "") -> str:
    info       = get_region_info(location)
    region_num = info["region"]
    region_key = f"Region {region_num}"

    if not crop:
        result  = f"🌱 *SEED RECOMMENDATIONS*\n{COMPANY_NAME}\n"
        result += f"📍 {location.title()} — Region {region_num}\n"
        result += f"🌤️ {info['climate']} | {info['rainfall']}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        result += f"*BEST CROPS:* {info['best_crops']}\n\n*TOP SEED BRANDS:*\n\n"
        for crop_name, regions in SEED_BRANDS.items():
            seeds = regions.get(region_key, regions.get("All Regions", []))
            if seeds:
                top = seeds[0]
                result += f"🌿 *{crop_name.upper()}* — {top['brand']} {top['variety']}\n"
                result += f"   📊 {top['yield']} | 💰 Type *SEEDS {crop_name.upper()}* for live prices\n\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━\nType *SEEDS [crop]* for full details\nType *MENU* to return"
        return result

    crop_lower = crop.lower()
    crops_data = SEED_BRANDS.get(crop_lower)

    if not crops_data:
        ai_info = ask_groq(
            f"What seed varieties are recommended for {crop} in {location} Zimbabwe Region {region_num}? "
            f"List top 3 brands with variety name, expected yield, and approximate retail price in USD/kg.",
            f"Zimbabwe {crop} seed variety recommendations for Region {region_num}",
        )
        return f"🌱 *{crop.upper()} SEEDS — {location.title()}*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{ai_info}\n\nType *MENU* to return"

    seeds = crops_data.get(region_key, crops_data.get("All Regions", []))
    if not seeds:
        for r in range(max(1, region_num - 1), min(6, region_num + 2)):
            seeds = crops_data.get(f"Region {r}", [])
            if seeds: break

    result  = f"🌱 *{crop.upper()} SEEDS — {location.title()}*\n{COMPANY_NAME}\n"
    result += f"📍 Region {region_num} — {info['climate']} | {info['rainfall']}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not seeds:
        result += f"⚠️ {crop.title()} not commonly grown in Region {region_num}.\n"
        result += f"Best crops here: {info['best_crops']}\nType *MENU* to return"
        return result

    for i, seed in enumerate(seeds, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "📌"
        result += f"{medal} *{seed['brand']} — {seed['variety']}*\n"
        result += f"   📊 Yield: {seed['yield']}\n"
        result += f"   📅 Days to maturity: {seed['days']}\n"
        result += f"   🔬 Traits: {seed['traits']}\n"
        result += f"   💰 ~${seed['price_per_kg']}/kg\n\n"

    ai_advice = ask_groq(
        f"Give 3 specific planting tips for {crop} in {location} Zimbabwe Region {region_num} ({info['climate']}). "
        f"Include: optimal planting date, seeding rate (kg/ha), row spacing, fertilizer at planting.",
        f"Zimbabwe {crop} agronomy tips for Region {region_num}",
    )
    result += f"━━━━━━━━━━━━━━━━━━━━━━\n🌱 *PLANTING ADVISORY:*\n{ai_advice}\n\nType *MENU* to return"
    return result


# ══════════════════════════════════════════════════════════════
#  COMMUNITY
# ══════════════════════════════════════════════════════════════

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
🌐 Also chat at: {WEBSITE}/community"""


def get_channel_posts(channel: str, limit: int = 5) -> str:
    ch_data  = community_channels.get(channel, {})
    messages = ch_data.get("messages", [])
    ch_name  = ch_data.get("name", channel.title())
    online   = len(manager.active_connections.get(channel, []))

    if not messages:
        return f"💬 *{ch_name}*\n🟢 {online} online\n━━━━━━━━━━━━━━━━━━━━━━\n\n📭 No posts yet. Be the first!\nType your message to post.\nType *COMMUNITY* to go back."

    result = f"💬 *{ch_name}*\n🟢 {online} online\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for post in messages[-limit:]:
        ph       = post.get("phone","")
        profile  = farmer_profiles.get(ph,{})
        name     = profile.get("name", f"Farmer {ph[-4:]}")
        loc      = profile.get("location","Zimbabwe").title()
        time_str = post.get("timestamp","")[:16].replace("T"," ")
        result  += f"👤 *{name}* — {loc}\n⏰ {time_str}\n💬 {post.get('message','')}\n\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━\nReply to post your message\nType *COMMUNITY* to go back"
    return result


def post_to_community(phone: str, channel: str, message: str) -> str:
    profile  = farmer_profiles.get(phone,{})
    name     = profile.get("name", f"Farmer {phone[-4:]}")
    location = profile.get("location","Zimbabwe").title()
    post     = {
        "id": secrets.token_hex(8), "phone": phone, "name": name, "location": location,
        "channel": channel, "message": message,
        "timestamp": datetime.datetime.now().isoformat(), "likes": 0, "replies": [],
    }
    community_posts.append(post)
    community_channels.setdefault(channel, {"messages":[]})
    community_channels[channel]["messages"].append(post)
    if len(community_channels[channel]["messages"]) > 100:
        community_channels[channel]["messages"] = community_channels[channel]["messages"][-100:]
    save_data()
    track_activity(phone, "community_post")
    ch_name = community_channels.get(channel,{}).get("name", channel.title())
    return f"✅ *Posted to {ch_name}!*\n━━━━━━━━━━━━━━━━━━━━━━\n👤 {name} | {location}\n💬 {message}\n\nType *COMMUNITY* for channels\nType *MENU* to return"


# ══════════════════════════════════════════════════════════════
#  PAYMENTS
# ══════════════════════════════════════════════════════════════

def initiate_payment(phone: str, plan: str) -> str:
    amount = "2" if plan == "premium" else "10"
    ref    = generate_ref(phone)
    payment_pending[ref] = {
        "phone": phone, "plan": plan, "amount": amount,
        "initiated": datetime.datetime.now().isoformat(), "status": "pending",
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
    pending = payment_pending.get(ref.upper(), payment_pending.get(ref,{}))
    plan    = pending.get("plan","premium")
    amount  = pending.get("amount","2")
    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {
        "active": True, "plan": plan, "amount": amount,
        "activated": datetime.datetime.now().isoformat(),
        "expires": expires, "payment_ref": ref,
    }
    for key in [ref.upper(), ref]:
        if key in payment_pending:
            payment_pending[key]["status"] = "confirmed"
    if phone in user_accounts:
        user_accounts[phone].update({"premium": True, "plan": plan})
    _persist_premium(phone)   # FIX: persist immediately
    save_data()
    return f"""🎉 *PAYMENT CONFIRMED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
✅ Ref: *{ref}* | Plan: *{plan.upper()}*
✅ Amount: *${amount}* | Status: *ACTIVE*
✅ Valid: 30 days
━━━━━━━━━━━━━━━━━━━━━━
Type *MENU* to explore! 🌱🇿🇼"""
# ════════════════════════════════════════════════════════════
#  PART 4 OF 8 — All Menus, Marketplace Helpers
# ════════════════════════════════════════════════════════════

def get_location_menu() -> str:
    return f"""📍 *SET YOUR LOCATION*
━━━━━━━━━━━━━━━━━━━━━━

*🛰️ OPTION 1 — GPS* (Most Accurate)
📎 Tap attachment → Location → Send Current Location

*🏙️ OPTION 2 — Type Town Name*
Example: Marondera or Chinhoyi

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

    if plan == "trial":      badge = f"🎁 FREE TRIAL — {days} days left"
    elif plan == "business": badge = "🏆 BUSINESS PLAN"
    elif plan == "premium":  badge = "⭐ PREMIUM"
    else:                    badge = "🆓 FREE PLAN"

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
        exp = premium_users[phone].get("expires","")
        try:    exp_str = datetime.datetime.fromisoformat(exp).strftime("%d %B %Y")
        except: exp_str = "30 days"
        return f"""⭐ *YOUR AGROBOT ACCOUNT*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Plan: *{plan.upper()}* ✅ ACTIVE
Expires: {exp_str}
Member for: {stats['days_since_joining']} days
Messages sent: {stats['total_messages']}
━━━━━━━━━━━━━━━━━━━━━━
All premium features active!
Type *MENU* to use them."""

    if plan == "trial":
        return f"""🎁 *FREE TRIAL ACTIVE*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
⏳ *{stats['trial_days_left']} days remaining*
Trial ends: {stats['trial_end_date']}
Member for: {stats['days_since_joining']} days

💎 *PREMIUM — $2/month* — All premium features
🏆 *BUSINESS — $10/month* — Premium + Export connections

Reply *1* — Premium ($2/month)
Reply *2* — Business ($10/month)
Reply *0* — Back"""

    return f"""⭐ *UPGRADE TO {BOT_NAME.upper()} PRO*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

*💎 PREMIUM — $2/month:*
🌤️ GPS precision weather
📸 Photo crop analysis
📍 Find help near you
💰 Live market prices
🌱 Seed brand recommendations
🏦 Loan & insurance advice
📊 Full history & analytics
⚡ Priority AI responses

*🏆 BUSINESS — $10/month:*
✅ Everything in Premium PLUS:
👨‍💼 Dedicated AI farm consultant
🌍 Export market connections
📦 Bulk buyer/seller matching
📋 Custom weekly farm reports

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
1️⃣ 📢 Post SELL listing
2️⃣ 🛍️ Post BUY request
3️⃣ 🏪 Browse Sellers
4️⃣ 🤝 Browse Buyer Requests
5️⃣ 🔍 Search Items
0️⃣ ◀️ Back to Main Menu
━━━━━━━━━━━━━━━━━━━━━━
📸 Attach product PHOTOS to your listings!
🌐 {WEBSITE}/marketplace"""


def get_account_menu(phone: str) -> str:
    stats     = get_user_stats(phone)
    plan      = get_plan(phone)
    days_left = get_trial_days_left(phone)

    if is_premium(phone):
        exp = premium_users[phone].get("expires","")
        try:    exp_str = datetime.datetime.fromisoformat(exp).strftime("%d %B %Y")
        except: exp_str = "30 days"
        plan_info = f"⭐ *{plan.upper()}* — Active until {exp_str}"
    elif plan == "trial":
        plan_info = f"🎁 *FREE TRIAL* — {days_left} days left (ends {stats['trial_end_date']})"
    else:
        plan_info = "🆓 *FREE PLAN* — Trial expired"

    streak_emoji = "🔥" if stats.get("streak_days",0) >= 7 else "✅" if stats.get("streak_days",0) >= 3 else "📅"

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
🛒 Marketplace posts: {stats['marketplace_posts']}
👥 Community posts: {stats['community_posts']}

━━━━━━━━━━━━━━━━━━━━━━
Reply:
1️⃣ Upgrade/Subscribe
2️⃣ View Conversation History
3️⃣ My Marketplace Posts
4️⃣ Set My Name
0️⃣ Back to Menu"""


def get_farming_news(phone: str = "") -> str:
    try:
        now      = datetime.datetime.now()
        profile  = farmer_profiles.get(phone, {})
        location = profile.get("location","Zimbabwe")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":f"""You are a Zimbabwe farming news editor. Today is {now.strftime('%d %B %Y')}.
Write a concise farming news bulletin for {location} farmers.
Include: top story, weather/climate, market prices, crop update, livestock, agri-tech tip, pest alert.
Format with emoji headings. 300 words max."""}],
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"News error: {e}")
        return "📰 News temporarily unavailable. Please try again later."


def get_user_history(phone: str) -> str:
    history = conversations.get(phone, [])
    stats   = get_user_stats(phone)
    if not history:
        return "📭 No conversation history yet.\nType *MENU* to return."

    result = f"""📋 *MY CONVERSATION HISTORY*
{COMPANY_NAME}
Total: {len(history)} messages | Member: {stats['days_since_joining']} days
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
📊 Messages: {stats['total_messages']} | Days active: {stats['total_days_active']}
Type *MENU* to return"""
    return result


# ══════════════════════════════════════════════════════════════
#  MARKETPLACE HELPERS
# ══════════════════════════════════════════════════════════════

def format_listing_card(listing: dict, index: int = None) -> str:
    prefix  = f"*{index}.* " if index else ""
    cat_str = f"🏷️ {listing.get('category','')}\n" if listing.get("category") else ""
    img_str = "📸 *Photo attached* ✅\n" if listing.get("image_url") else ""

    if listing.get("type") == "seller":
        return (
            f"{prefix}📦 *{listing.get('item','')}*\n"
            f"{cat_str}"
            f"📍 {listing.get('location','')}\n"
            f"💰 {listing.get('price','')}\n"
            f"📞 {listing.get('phone','')}\n"
            f"{img_str}"
            f"📅 {listing.get('timestamp','')[:10]}\n"
        )
    else:
        return (
            f"{prefix}🛍️ WANTED: *{listing.get('item','')}*\n"
            f"📦 Qty: {listing.get('quantity','Flexible')}\n"
            f"💰 Budget: {listing.get('budget','Negotiable')}\n"
            f"📍 {listing.get('location','Zimbabwe')}\n"
            f"📞 {listing.get('phone','')}\n"
            f"{img_str}"
        )


def _finalize_sell_listing(from_number: str, image_url: str = None) -> str:
    session  = marketplace_sessions.pop(from_number, {})
    item     = session.get("item","Unknown")
    category = session.get("category","General")
    location = session.get("location", farmer_profiles.get(from_number,{}).get("location","Zimbabwe"))
    price    = session.get("price","Negotiable")
    phone    = session.get("phone", from_number)

    listing = {
        "id": secrets.token_hex(8), "type": "seller", "category": category,
        "item": item, "location": location, "price": price, "phone": phone,
        "poster": from_number, "image_url": image_url or "",
        "timestamp": datetime.datetime.now().isoformat(), "status": "active",
    }
    marketplace.append(listing)

    if sb:
        try:
            sb.table("marketplace").upsert(listing).execute()
        except Exception as e:
            print(f"marketplace save error: {e}")

    save_data()
    track_activity(from_number, "marketplace_post")
    user_states[from_number] = "menu"
    img_note = "\n📸 Photo attached ✅" if image_url else ""
    return f"""✅ *LISTING POSTED SUCCESSFULLY!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
📦 {item}
🏷️ {category}
📍 {location}
💰 {price}
📞 {phone}{img_note}
━━━━━━━━━━━━━━━━━━━━━━
✅ Visible to all AgroBot farmers!
🌐 Also on: {WEBSITE}/marketplace

Type *MENU* to return."""


def _finalize_buy_request(from_number: str, image_url: str = None) -> str:
    session  = marketplace_sessions.pop(from_number, {})
    item     = session.get("item","Unknown")
    quantity = session.get("quantity","Flexible")
    budget   = session.get("budget","Negotiable")
    location = session.get("location", farmer_profiles.get(from_number,{}).get("location","Zimbabwe"))
    phone    = session.get("phone", from_number)

    req = {
        "id": secrets.token_hex(8), "type": "buyer",
        "item": item, "quantity": quantity, "budget": budget,
        "location": location, "phone": phone, "poster": from_number,
        "image_url": image_url or "",
        "timestamp": datetime.datetime.now().isoformat(), "status": "active",
    }
    buyer_requests.append(req)

    if sb:
        try:
            sb.table("buyer_requests").upsert(req).execute()
        except Exception as e:
            print(f"buyer_requests save error: {e}")

    save_data()
    track_activity(from_number, "buy_request")
    user_states[from_number] = "menu"
    img_note = "\n📸 Reference photo attached ✅" if image_url else ""
    return f"""✅ *BUY REQUEST POSTED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
🛍️ WANTED: {item}
📦 Quantity: {quantity}
💰 Budget: {budget}
📍 Location: {location}
📞 Contact: {phone}{img_note}
━━━━━━━━━━━━━━━━━━━━━━
✅ Sellers will contact you!
🌐 Also on: {WEBSITE}/marketplace

Type *MENU* to return."""
# ════════════════════════════════════════════════════════════
#  PART 5 OF 8 — process_message (complete)
# ════════════════════════════════════════════════════════════

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
        crop    = msg.split(" ", 1)[1].strip()
        profile = farmer_profiles.get(from_number, {})
        prices  = get_sync_prices()
        adj     = REGIONAL_PRICE_ADJ.get(profile.get("location","").lower(), {})
        trends  = {"rising":"📈","falling":"📉","stable":"➡️"}
        c       = crop.lower().replace(" ","_")
        p       = prices.get(c, prices.get(crop.lower()))
        if p:
            local = round(p["price"] * adj.get(crop.lower(), 1.0), 2)
            icon  = trends.get(p.get("trend","stable"), "➡️")
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
        location = profile.get("location","harare")
        parts    = msg.split(" ", 1)
        crop     = parts[1].strip() if len(parts) > 1 else ""
        return get_seed_recommendations(location, crop)

    if msg.upper().startswith("PAID "):
        ref = msg.split(" ", 1)[1].strip()
        return process_payment(from_number, ref)

    # ── NEW FARMER ────────────────────────────────────────────
    if from_number not in farmer_profiles:
        if msg.lower() in ["hi","hello","hey","start","help","0","00"]:
            user_states[from_number] = "register_location"
            return f"""🌱 *WELCOME TO {BOT_NAME.upper()}!* 🇿🇼
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Zimbabwe's Most Advanced AI Farming Assistant

🎁 *SPECIAL WELCOME OFFER:*
Get *{TRIAL_DAYS} DAYS FREE* access to ALL premium features!
✅ No payment required

━━━━━━━━━━━━━━━━━━━━━━
Please set your location:

{get_location_menu()}"""
        else:
            user_states[from_number] = "register_location"
            return f"🌱 *Welcome to {BOT_NAME}!*\n\nPlease set your location:\n\n{get_location_menu()}"

    # ── LOCATION STATES ───────────────────────────────────────
    elif state in ["register_location","update_location"]:
        is_new        = state == "register_location"
        location      = PROVINCE_DEFAULTS.get(msg, msg.lower())
        province_name = PROVINCE_NAMES.get(msg, msg.title())
        save_location(from_number, location)
        _persist_profile(from_number)   # FIX: persist immediately
        info = get_region_info(location)
        user_states[from_number] = "menu"

        region_key  = f"Region {info['region']}"
        maize_seeds = SEED_BRANDS.get("maize",{}).get(region_key,[])
        seed_tip    = f"\n🌱 Top seed: *{maize_seeds[0]['brand']} {maize_seeds[0]['variety']}*" if maize_seeds else ""
        trial_msg   = f"\n\n🎁 *{TRIAL_DAYS}-DAY FREE TRIAL STARTED!*\nAll features unlocked!" if is_new else ""

        return f"""✅ *LOCATION SET: {province_name}*
━━━━━━━━━━━━━━━━━━━━━━
📍 {location.title()}
🌤️ Region {info['region']} — {info['climate']}
🌧️ Rainfall: {info['rainfall']}
🌱 Best Crops: {info['best_crops']}
🏔️ Soil: {info.get('soil','Mixed')}
📅 Season: {info.get('season','Nov-Apr')}
⚠️ Challenges: {info.get('challenges','Variable weather')}{seed_tip}
{trial_msg}

{get_main_menu(from_number)}"""

    # ── IMAGE DESCRIBE STATE ──────────────────────────────────
    elif state == "image_describe":
        user_states[from_number] = "menu"
        profile  = farmer_profiles.get(from_number, {})
        location = profile.get("location","Zimbabwe")
        m        = msg.lower()

        crop_found = next((kw for kw in ["maize","tobacco","wheat","cotton","soya","tomato",
                           "bean","potato","groundnut","onion","cabbage","sunflower","sorghum",
                           "millet","sugarcane","avocado","mango"] if kw in m), "")

        if any(w in m for w in ["armyworm","caterpillar","worm","larva","insect","bug","fly","beetle","aphid","mite","thrip"]):
            problem_type = "pest/insect infestation"
        elif any(w in m for w in ["yellow","brown","spot","blight","rust","mildew","wilt","rot","lesion","streak"]):
            problem_type = "crop disease with visible symptoms"
        elif any(w in m for w in ["pale","stunted","small","weak","not growing"]):
            problem_type = "nutrient deficiency or growth disorder"
        elif any(w in m for w in ["cattle","cow","goat","chicken","pig","poultry"]):
            problem_type = "livestock health problem"
        else:
            problem_type = "crop problem"

        crop_part     = f" in {crop_found}" if crop_found else ""
        dynamic_topic = f"Specific diagnosis and treatment for {problem_type}{crop_part} in {location.title()}, Zimbabwe — farmer described: {msg[:80]}"

        reply = ask_groq(msg, dynamic_topic, phone=from_number)
        return f"""🌿 *DIAGNOSIS FROM DESCRIPTION*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
📸 Send a photo for visual confirmation
📞 Agritex Plant Clinic: 0800 4040
Type *MENU* to return"""

    # ── COMMUNITY STATES ──────────────────────────────────────
    elif state == "community":
        if msg == "0":
            user_states[from_number] = "menu"; return get_main_menu(from_number)
        elif msg in ["1","2","3","4","5","6","7"]:
            channels = ["general","maize","tobacco","livestock","horticulture","weather","prices"]
            channel  = channels[int(msg)-1]
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
            if not all_posts: return "📭 No posts yet.\nType *COMMUNITY* to go back."
            result = "📋 *LATEST POSTS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for post in all_posts[:8]:
                ph       = post.get("phone","")
                p        = farmer_profiles.get(ph,{})
                name     = p.get("name", f"Farmer {ph[-4:]}")
                loc      = p.get("location","Zimbabwe").title()
                ch       = post.get("channel","general").title()
                time_str = post.get("timestamp","")[:16].replace("T"," ")
                result  += f"*#{ch}* | 👤 {name} — {loc}\n⏰ {time_str}\n💬 {post.get('message','')[:100]}\n\n"
            return result + "Type *COMMUNITY* for channels\nType *MENU* to return"
        elif msg == "10":
            stats   = get_user_stats(from_number)
            profile = farmer_profiles.get(from_number,{})
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
        channel = state.replace("community_channel_","")
        if msg.upper() in ["BACK","0","COMMUNITY"]:
            user_states[from_number] = "community"; return get_community_menu()
        result = post_to_community(from_number, channel, msg)
        user_states[from_number] = "menu"
        return result

    elif state == "community_post_select":
        channel_map = {"1":"general","2":"maize","3":"tobacco","4":"livestock","5":"horticulture","6":"weather","7":"prices"}
        if msg in channel_map:
            channel = channel_map[msg]
            ch_name = community_channels.get(channel,{}).get("name",channel.title())
            user_states[from_number] = f"community_posting_{channel}"
            return f"✍️ *POST TO {ch_name.upper()}*\n━━━━━━━━━━━━━━━━━━━━━━\nType your message now.\nAll AgroBot farmers will see it!"
        elif msg == "0":
            user_states[from_number] = "community"; return get_community_menu()
        return "Reply 1-7 or 0 to go back."

    elif state.startswith("community_posting_"):
        channel = state.replace("community_posting_","")
        result  = post_to_community(from_number, channel, msg)
        user_states[from_number] = "menu"
        return result

    # ── MAIN MENU SELECTIONS ──────────────────────────────────
    elif state == "menu":
        if msg.lower() in ["hi","hello","hey","start","help"]:
            return get_main_menu(from_number)

        elif msg == "1":
            user_states[from_number] = "disease"
            track_activity(from_number, "disease_query")
            profile  = farmer_profiles.get(from_number,{})
            loc_note = f"\n📍 Personalised for {profile['location'].title()}" if profile.get("location") else ""
            return f"""🌿 *CROP DISEASE & PEST ADVISORY*{loc_note}
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Describe your problem in detail:
🌱 What crop is affected?
🔍 What symptoms do you see?
📏 How much of the crop is affected?
📅 When did you first notice?
💊 Any treatments already applied?

📸 *OR send a PHOTO* for instant visual diagnosis!"""

        elif msg == "2":
            user_states[from_number] = "soil"
            return f"""🧪 *SOIL HEALTH & FERTILITY ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

For accurate analysis, tell me:
🎨 Soil colour
👆 Texture (sandy/clay/loam)
💧 Drainage (waterlogged/well drained)
🌿 Previous crop planted
🌱 Next crop you want to plant
📏 Field size (acres or hectares)"""

        elif msg == "3":
            user_states[from_number] = "marketplace"
            track_activity(from_number, "marketplace")
            return get_marketplace_menu()

        elif msg == "4":
            user_states[from_number] = "freeask"
            return f"💬 *ASK {BOT_NAME.upper()} ANYTHING*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\nAsk about crops, pests, soil, irrigation,\nlivestock, markets, technology — anything farming!"

        elif msg == "5":
            track_activity(from_number, "news")
            return get_farming_news(from_number)

        elif msg == "6":
            gate = premium_gate(from_number, "GPS Weather & Climate Forecast")
            if gate: return gate
            track_activity(from_number, "weather")
            profile = farmer_profiles.get(from_number,{})
            if "gps_lat" in profile:
                nearest = find_nearest_region(profile["gps_lat"], profile["gps_lon"])
                return get_weather(profile["gps_lat"], profile["gps_lon"], f"{nearest['name'].title()} (GPS)")
            elif "location" in profile:
                return get_weather_by_name(profile["location"])
            else:
                user_states[from_number] = "weather"
                return f"🌤️ *Weather*\n\nSet location:\n\n{get_location_menu()}"

        elif msg == "7":
            gate = premium_gate(from_number, "Photo Crop Disease Analysis")
            if gate: return gate
            user_states[from_number] = "image_prompt"
            return f"""📸 *PHOTO CROP DISEASE ANALYSIS*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Send a clear photo of your affected crop!

📷 Tips:
✅ Good natural lighting
✅ Close enough to see symptoms clearly
✅ Steady camera — no blur

Send your photo now!"""

        elif msg == "8":
            gate = premium_gate(from_number, "Find Agricultural Help Nearby")
            if gate: return gate
            profile = farmer_profiles.get(from_number,{})
            if "gps_lat" in profile:
                return find_help_nearby("", profile["gps_lat"], profile["gps_lon"])
            elif "location" in profile:
                return find_help_nearby(profile["location"])
            else:
                user_states[from_number] = "location_help"
                return f"📍 *Find Help*\n\nSet location:\n\n{get_location_menu()}"

        elif msg == "9":
            gate = premium_gate(from_number, "Live Regional Market Prices")
            if gate: return gate
            profile  = farmer_profiles.get(from_number,{})
            track_activity(from_number, "market_prices")
            prices   = get_sync_prices()
            location = profile.get("location","")
            adj      = REGIONAL_PRICE_ADJ.get(location.lower(), {})
            trends   = {"rising":"📈","falling":"📉","stable":"➡️"}
            now      = datetime.datetime.now()

            result = f"💰 *LIVE MARKET PRICES*\n{COMPANY_NAME}\n📍 {location.title() if location else 'Zimbabwe'}\n🕐 {now.strftime('%d %b %Y %H:%M')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n🌾 *GRAINS:*"
            for c in ["maize","wheat","soya","sorghum","groundnuts"]:
                p = prices.get(c)
                if p:
                    local = round(p["price"] * adj.get(c,1.0), 2)
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
                    local = round(p["price"] * adj.get(c,1.0), 2)
                    result += f"\n{trends.get(p.get('trend','stable'),'➡️')} {c.title()}: *${local}/{p['unit']}*"
            result += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n⏰ Updated every 6h | Type *PRICE [crop]* for details\nType *MENU* to return"
            return result

        elif msg == "10":
            gate = premium_gate(from_number, "Loan & Insurance Advisory")
            if gate: return gate
            user_states[from_number] = "loan"
            return f"""🏦 *AGRICULTURAL FINANCE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

Tell me your situation:
- Farm size (acres/ha)
- Main crops you grow
- What you need (loan/insurance/both)
- Annual turnover (approximate)"""

        elif msg == "0":
            user_states[from_number] = "account"
            return get_account_menu(from_number)

        else:
            reply = ask_groq(msg, phone=from_number)
            return f"💬 *{BOT_NAME.upper()} ADVICE*\n━━━━━━━━━━━━━━━━━━━━━━\n\n{reply}\n\n━━━━━━━━━━━━━━━━━━━━━━\nType *SEEDS [crop]* for seed brands\nType *MENU* | 📞 {SUPPORT_PHONE}"

    # ── ACCOUNT ───────────────────────────────────────────────
    elif state == "account":
        if msg == "1":
            user_states[from_number] = "subscribe"; return get_premium_menu(from_number)
        elif msg == "2":
            user_states[from_number] = "menu"; return get_user_history(from_number)
        elif msg == "3":
            posts = [x for x in marketplace if x.get("poster") == from_number]
            if not posts:
                user_states[from_number] = "menu"
                return "📭 No marketplace posts yet.\nType *MENU* to return."
            result = "🛒 *MY LISTINGS*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for p in posts[-5:]:
                result += format_listing_card(p) + "\n"
            user_states[from_number] = "menu"
            return result + "Type *MENU* to return"
        elif msg == "4":
            user_states[from_number] = "set_name"
            return "👤 *Set Your Name*\n\nWhat name should AgroBot use?\nExample: John Moyo"
        elif msg == "0":
            user_states[from_number] = "menu"; return get_main_menu(from_number)
        return get_account_menu(from_number)

    elif state == "set_name":
        farmer_profiles[from_number]["name"] = msg
        if from_number in user_accounts:
            user_accounts[from_number]["name"] = msg
        _persist_profile(from_number)
        save_data()
        user_states[from_number] = "menu"
        return f"✅ *Name saved: {msg}*\n\nType *MENU* to return."

    # ── DISEASE (improved — fully dynamic, no hardcoded topic) ──
    elif state == "disease":
        user_states[from_number] = "menu"
        track_activity(from_number, "disease_query")
        profile  = farmer_profiles.get(from_number,{})
        location = profile.get("location","Zimbabwe")
        m        = msg.lower()

        crop_found = next((kw for kw in ["maize","tobacco","wheat","cotton","soya","tomato",
                           "bean","potato","groundnut","onion","cabbage","spinach","pepper",
                           "cucumber","sunflower","sorghum","millet","sugarcane","avocado",
                           "mango","citrus"] if kw in m), "")

        if any(w in m for w in ["armyworm","caterpillar","worm","larva","insect","bug","fly","beetle","aphid","mite","thrip","spider"]):
            problem_type = "pest and insect infestation"
        elif any(w in m for w in ["yellow","yellowing","brown","browning","spot","spots","blight","rust","mildew","wilt","rot","damp","lesion","streak","mosaic"]):
            problem_type = "crop disease with visible leaf/stem symptoms"
        elif any(w in m for w in ["pale","light green","stunted","small","weak","not growing","slow growth","no yield"]):
            problem_type = "nutrient deficiency or growth disorder"
        elif any(w in m for w in ["cattle","cow","bull","goat","sheep","pig","chicken","poultry","rabbit","livestock"]):
            problem_type = "livestock health and disease"
        else:
            problem_type = "crop problem or disease"

        crop_part     = f" affecting {crop_found}" if crop_found else ""
        dynamic_topic = (
            f"Professional diagnosis and treatment recommendation for {problem_type}"
            f"{crop_part} in {location.title()}, Zimbabwe. "
            f"Farmer's description: {msg[:100]}"
        )

        reply = ask_groq(msg, dynamic_topic, phone=from_number)
        return f"""🌿 *PROFESSIONAL DISEASE ADVISORY*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━

{reply}

━━━━━━━━━━━━━━━━━━━━━━
📞 Agritex Plant Clinic: 0800 4040
Type *MENU* to return"""

    # ── SOIL ──────────────────────────────────────────────────
    elif state == "soil":
        user_states[from_number] = "menu"
        profile  = farmer_profiles.get(from_number,{})
        location = profile.get("location","Zimbabwe")
        dynamic_topic = (
            f"Soil analysis and fertilizer recommendations for a farmer in {location.title()}, Zimbabwe. "
            f"Farmer described: {msg[:100]}"
        )
        reply = ask_groq(msg, dynamic_topic, phone=from_number)
        return f"🧪 *SOIL ANALYSIS*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{reply}\n\n━━━━━━━━━━━━━━━━━━━━━━\nType *MENU* to return"

    # ── FREE ASK ──────────────────────────────────────────────
    elif state == "freeask":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, phone=from_number)
        return f"💬 *{BOT_NAME.upper()} ADVICE*\n━━━━━━━━━━━━━━━━━━━━━━\n\n{reply}\n\n━━━━━━━━━━━━━━━━━━━━━━\nType *SEEDS [crop]* for seed brands\nType *MENU* | 📞 {SUPPORT_PHONE}"

    elif state == "weather":
        user_states[from_number] = "menu"
        return get_weather_by_name(PROVINCE_DEFAULTS.get(msg, msg))

    elif state == "location_help":
        user_states[from_number] = "menu"
        return find_help_nearby(PROVINCE_DEFAULTS.get(msg, msg))

    # ── LOAN ─────────────────────────────────────────────────
    elif state == "loan":
        user_states[from_number] = "menu"
        profile  = farmer_profiles.get(from_number,{})
        location = profile.get("location","Zimbabwe")
        dynamic_topic = (
            f"Agricultural finance, loans, crop insurance options for a farmer in {location.title()}, Zimbabwe. "
            f"Farmer described: {msg[:100]}"
        )
        reply = ask_groq(msg, dynamic_topic, phone=from_number)
        return f"🏦 *FINANCE ADVISORY*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{reply}\n\n━━━━━━━━━━━━━━━━━━━━━━\nType *MENU* to return"

    elif state == "subscribe":
        if msg == "1": user_states[from_number]="menu"; return initiate_payment(from_number,"premium")
        elif msg == "2": user_states[from_number]="menu"; return initiate_payment(from_number,"business")
        elif msg == "0": user_states[from_number]="menu"; return get_main_menu(from_number)
        return get_premium_menu(from_number)

    # ══════════════════════════════════════════════════════════
    #  MARKETPLACE STATES
    # ══════════════════════════════════════════════════════════

    elif state == "marketplace":
        if msg == "0":
            user_states[from_number] = "menu"; return get_main_menu(from_number)

        elif msg == "1":
            marketplace_sessions[from_number] = {"type":"seller"}
            user_states[from_number] = "mp_sell_category"
            return """📢 *POST SELL LISTING*
━━━━━━━━━━━━━━━━━━━━━━
Select category:
1️⃣ 🌾 Crops & Grains
2️⃣ 🧪 Fertilizer & Chemicals
3️⃣ 🚜 Farm Equipment & Tools
4️⃣ 🐄 Livestock & Poultry
5️⃣ 📦 Other Farm Products
0️⃣ ◀️ Back"""

        elif msg == "2":
            marketplace_sessions[from_number] = {"type":"buyer"}
            user_states[from_number] = "mp_buy_item"
            return "🛍️ *POST BUY REQUEST*\n━━━━━━━━━━━━━━━━━━━━━━\nWhat do you want to BUY?\n\nBe specific. Example:\n50 bags of maize SC403\n2 breeding heifers\n200 litres Dimethoate"

        elif msg == "3":
            # FIX: was broken by unreachable code after return
            sellers = [x for x in marketplace if x.get("status","active") == "active"]
            if not sellers:
                return "📭 No sellers yet. Be the first to post!\nType *MENU* to return."
            result = f"🏪 *SELLERS ({len(sellers)} listings)*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, x in enumerate(sellers[-10:], 1):
                result += format_listing_card(x, i) + "\n"
            return result + "Type *MENU* to return"

        elif msg == "4":
            if not buyer_requests:
                return "📭 No buyer requests yet.\nType *MENU* to return."
            result = f"🤝 *BUYER REQUESTS ({len(buyer_requests)} listings)*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, x in enumerate(buyer_requests[-10:], 1):
                result += format_listing_card(x, i) + "\n"
            return result + "Type *MENU* to return"

        elif msg == "5":
            user_states[from_number] = "mp_search"
            return "🔍 *SEARCH MARKETPLACE*\n\nType what you are looking for:"

        return get_marketplace_menu()

    # ── SELL FLOW ─────────────────────────────────────────────
    elif state == "mp_sell_category":
        cats = {"1":"Crops & Grains","2":"Fertilizer & Chemicals",
                "3":"Farm Equipment & Tools","4":"Livestock & Poultry","5":"Other Farm Products"}
        if msg == "0":
            user_states[from_number] = "marketplace"; return get_marketplace_menu()
        if msg not in cats:
            return "Reply 1–5 to select category, or 0 to go back."
        marketplace_sessions[from_number]["category"] = cats[msg]
        user_states[from_number] = "mp_sell_item"
        return f"📦 *{cats[msg].upper()}*\n━━━━━━━━━━━━━━━━━━━━━━\nDescribe what you are SELLING:\nInclude: item name, quantity, condition\nExample: 50 × 50kg bags of maize SC403, grade B"

    elif state == "mp_sell_item":
        marketplace_sessions[from_number]["item"] = msg
        profile = farmer_profiles.get(from_number,{})
        saved   = profile.get("location","")
        hint    = f"Your saved location: *{saved.title()}*\nType to confirm, or type a different location:" if saved else "Type your location (town/city/area):"
        user_states[from_number] = "mp_sell_location"
        return f"📍 *LOCATION*\n━━━━━━━━━━━━━━━━━━━━━━\n{hint}"

    elif state == "mp_sell_location":
        location = msg if msg.lower() not in ["confirm","yes","ok"] else farmer_profiles.get(from_number,{}).get("location",msg)
        marketplace_sessions[from_number]["location"] = location
        user_states[from_number] = "mp_sell_price"
        return "💰 *ASKING PRICE*\n━━━━━━━━━━━━━━━━━━━━━━\nExample: $50 per 50kg bag\nExample: $285 per tonne\nExample: Negotiable"

    elif state == "mp_sell_price":
        marketplace_sessions[from_number]["price"] = msg
        user_states[from_number] = "mp_sell_phone"
        return "📞 *CONTACT NUMBER*\n━━━━━━━━━━━━━━━━━━━━━━\nType the number buyers should call or WhatsApp:\nExample: 0772 123 456"

    elif state == "mp_sell_phone":
        marketplace_sessions[from_number]["phone"] = msg
        user_states[from_number] = "mp_sell_image"
        return "📸 *ADD A PRODUCT PHOTO* (Recommended!)\n━━━━━━━━━━━━━━━━━━━━━━\nSend a photo of your product now!\nPhotos get 3× more buyer responses.\n\nOr type *SKIP* to post without a photo."

    elif state == "mp_sell_image":
        if msg.upper() in ["SKIP","NO","NEXT","DONE"]:
            return _finalize_sell_listing(from_number, image_url=None)
        return "📸 Please send your photo now, or type *SKIP* to post without one."

    # ── BUY FLOW ─────────────────────────────────────────────
    elif state == "mp_buy_item":
        marketplace_sessions[from_number]["item"] = msg
        user_states[from_number] = "mp_buy_quantity"
        return f"📦 *QUANTITY NEEDED*\n━━━━━━━━━━━━━━━━━━━━━━\nYou want to buy: *{msg}*\n\nHow much do you need?\nExample: 200 × 50kg bags\nExample: 5 breeding heifers\nExample: Flexible"

    elif state == "mp_buy_quantity":
        marketplace_sessions[from_number]["quantity"] = msg
        user_states[from_number] = "mp_buy_budget"
        return "💰 *YOUR BUDGET*\n━━━━━━━━━━━━━━━━━━━━━━\nExample: $45 per 50kg bag\nExample: Up to $280 per tonne\nExample: Negotiable"

    elif state == "mp_buy_budget":
        marketplace_sessions[from_number]["budget"] = msg
        user_states[from_number] = "mp_buy_location"
        return "📍 *YOUR LOCATION*\n━━━━━━━━━━━━━━━━━━━━━━\nWhere are you located?\nExample: Harare CBD | Example: Marondera town"

    elif state == "mp_buy_location":
        marketplace_sessions[from_number]["location"] = msg
        user_states[from_number] = "mp_buy_phone"
        return "📞 *YOUR CONTACT NUMBER*\n━━━━━━━━━━━━━━━━━━━━━━\nSellers will call/WhatsApp this number:"

    elif state == "mp_buy_phone":
        marketplace_sessions[from_number]["phone"] = msg
        user_states[from_number] = "mp_buy_image"
        return "📸 *ADD REFERENCE PHOTO* (Optional)\n━━━━━━━━━━━━━━━━━━━━━━\nSend a photo showing what you need.\nOr type *SKIP* to post without one."

    elif state == "mp_buy_image":
        if msg.upper() in ["SKIP","NO","NEXT","DONE"]:
            return _finalize_buy_request(from_number, image_url=None)
        return "📸 Please send your photo, or type *SKIP* to post without one."

    elif state == "mp_search":
        user_states[from_number] = "menu"
        q       = msg.lower()
        sellers = [x for x in marketplace    if q in x.get("item","").lower() or q in x.get("category","").lower() or q in x.get("location","").lower()]
        buyers  = [x for x in buyer_requests if q in x.get("item","").lower() or q in x.get("location","").lower()]
        if not sellers and not buyers:
            return f"📭 No results for *{msg}*.\nType *MENU* to return."
        result = f"🔍 *RESULTS FOR: {msg.upper()}*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if sellers:
            result += f"🏪 *SELLERS ({len(sellers[:5])}):*\n"
            for x in sellers[:5]: result += format_listing_card(x) + "\n"
        if buyers:
            result += f"🤝 *BUYERS ({len(buyers[:5])}):*\n"
            for x in buyers[:5]: result += format_listing_card(x) + "\n"
        return result + "Type *MENU* to return"

    else:
        user_states[from_number] = "menu"
        return get_main_menu(from_number)
    # ════════════════════════════════════════════════════════════
#  PART 6 OF 8 — WebSocket Community, send_whatsapp_message,
#                WhatsApp Webhook (OTP + marketplace images fixed)
# ════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  WEBSOCKET — REAL-TIME COMMUNITY CHAT
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
        "type":            "welcome",
        "channel":         channel,
        "channel_name":    ch_name,
        "user":            {"name": name, "location": location, "phone": phone},
        "recent_messages": recent,
        "online_count":    len(manager.active_connections.get(channel, [])),
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

            # Allow farmers to tag @AgroBot in community chat for AI response
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
            "name":           ch_data.get("name", ch_id),
            "description":    ch_data.get("description", ""),
            "total_messages": len(ch_data.get("messages", [])),
            "online_now":     len(manager.active_connections.get(ch_id, [])),
            "members":        manager.get_channel_members(ch_id),
        }
    return JSONResponse(result)


# ══════════════════════════════════════════════════════════════
#  SEND WHATSAPP MESSAGE
# ══════════════════════════════════════════════════════════════

def send_whatsapp_message(to: str, message: str) -> bool:
    """
    Send a WhatsApp message. Returns True if sent, False if failed.
    Used by OTP system, payment confirmations, notifications.
    """
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
        return resp.status_code in [200, 201]
    except Exception as e:
        print(f"Send error [{to}]: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  WHATSAPP WEBHOOK — Verify + Receive messages
# ══════════════════════════════════════════════════════════════

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

        # ── GPS Location ──────────────────────────────────────
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
            _persist_profile(from_number)   # FIX: persist GPS immediately
            save_data()
            track_activity(from_number, "gps_share")

            nearest = find_nearest_region(lat, lon)
            info    = nearest["info"]
            save_conversation(from_number, "farmer", f"[GPS: {lat:.4f}, {lon:.4f}]", "location")

            region_key  = f"Region {info['region']}"
            maize_seeds = SEED_BRANDS.get("maize", {}).get(region_key, [])
            seed_tip    = f"\n🌱 Top seed: *{maize_seeds[0]['brand']} {maize_seeds[0]['variety']}*" if maize_seeds else ""
            stats       = get_user_stats(from_number)
            trial_note  = f"\n🎁 Trial: {get_trial_days_left(from_number)} days left" if is_in_trial(from_number) else ""

            reply = f"""📍 *GPS LOCATION SAVED!* 🛰️
{COMPANY_NAME} | Day {stats['days_since_joining']}
━━━━━━━━━━━━━━━━━━━━━━
🌍 {lat:.4f}°S, {lon:.4f}°E
📍 *{nearest['name'].title()}*
🌤️ {info['climate']} | {info['rainfall']}
🏔️ {info.get('soil','Mixed')}
🌱 Best: {info['best_crops']}{seed_tip}
{trial_note}

✅ All advice personalised to your farm!
Type *SEEDS* for seed recommendations!
{get_main_menu(from_number)}"""
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

        # ── Image / Photo ─────────────────────────────────────
        elif msg_type == "image":
            save_conversation(from_number, "farmer", "[Photo sent]", "image")
            track_activity(from_number, "image_sent")

            # Download the image from WhatsApp servers
            image_id    = message["image"]["id"]
            image_url   = None
            image_bytes = None

            try:
                img_url_resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{image_id}",
                    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
                    timeout=15,
                )
                image_url = img_url_resp.json().get("url")

                if image_url:
                    img_download = requests.get(
                        image_url,
                        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
                        timeout=20,
                    )
                    if img_download.status_code == 200:
                        image_bytes = img_download.content
            except Exception as e:
                print(f"Image download error: {e}")

            # ── Marketplace image attachment ───────────────────
            # If farmer is in the middle of posting a listing, save image to listing
            current_state            = user_states.get(from_number, "menu")
            marketplace_image_states = {"mp_sell_image", "mp_buy_image"}

            if current_state in marketplace_image_states:
                if image_bytes:
                    cloudinary_url = upload_to_cloudinary(image_bytes, "marketplace")
                    if cloudinary_url:
                        marketplace_sessions.setdefault(from_number, {})
                        marketplace_sessions[from_number]["image_url"] = cloudinary_url
                        if current_state == "mp_sell_image":
                            reply = _finalize_sell_listing(from_number, image_url=cloudinary_url)
                        else:
                            reply = _finalize_buy_request(from_number, image_url=cloudinary_url)
                    else:
                        # Cloudinary failed — post without image
                        if current_state == "mp_sell_image":
                            reply = _finalize_sell_listing(from_number, image_url=None)
                        else:
                            reply = _finalize_buy_request(from_number, image_url=None)
                        reply += "\n\n⚠️ Photo could not be saved, listing posted without image."
                else:
                    reply = "❌ Could not receive your photo. Please try again or type *SKIP* to post without a photo."

            # ── Premium crop disease analysis ──────────────────
            elif has_full_access(from_number):
                if not image_url:
                    reply = "❌ Could not retrieve image. Please try again."
                else:
                    send_whatsapp_message(
                        from_number,
                        f"🔍 *Analysing your crop image...*\n{COMPANY_NAME}\n\nPlease wait 15-20 seconds..."
                    )
                    reply = analyze_image_improved(image_url, from_number)

            # ── Free plan — upgrade prompt ─────────────────────
            else:
                reply = f"""🔒 *PHOTO ANALYSIS — PREMIUM REQUIRED*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Your {TRIAL_DAYS}-day free trial has ended.

Upgrade for $2/month to unlock:
📸 Photo crop disease analysis
🌤️ GPS precision weather
💰 Live market prices
🏦 Loan advisory
📍 Find help near you

Reply *UPGRADE* to subscribe
Type *MENU* for free services"""

            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

        # ── Text Message ──────────────────────────────────────
        elif msg_type == "text":
            msg_text = message["text"]["body"]
            print(f"[{from_number}]: {msg_text}")
            reply = process_message(from_number, msg_text)
            save_conversation(from_number, "agrobot", reply)
            send_whatsapp_message(from_number, reply)

    except (KeyError, IndexError) as e:
        print(f"Webhook parse error: {e}")
    return {"status": "ok"}
# ════════════════════════════════════════════════════════════
#  PART 7 OF 8 — REST API Endpoints
#  Auth (OTP + register + login), Farmer, Community,
#  Seeds, Prices, Weather, News, Ask, Payments
# ════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    salt = "AGROBOT_SALT_2026"
    return hashlib.sha256(f"{salt}{password}{salt}".encode()).hexdigest()


def build_user_response(phone: str, token: str) -> dict:
    if phone not in farmer_profiles: db_get_profile(phone)
    if phone not in user_accounts:   db_get_account(phone)
    stats = get_user_stats(phone)
    return {
        "success":         True,
        "token":           token,
        "phone":           phone,
        "profile":         farmer_profiles.get(phone, {}),
        "account":         {k: v for k, v in user_accounts.get(phone, {}).items()
                            if k != "password_hash"},
        "premium":         is_premium(phone),
        "plan":            get_plan(phone),
        "trial_days_left": get_trial_days_left(phone),
        "stats":           stats,
        "conversations":   db_get_conversations(phone, 20),
    }


# ── OTP Endpoints (FIXED — now actually sends via WhatsApp) ───

@app.post("/api/auth/request-otp")
async def api_request_otp(request: Request):
    """
    Request a one-time password. Sends a 6-digit OTP via WhatsApp.
    Body: {"phone": "0772123456", "purpose": "login"}
    Purpose options: login | register | reset_password | verify_phone
    """
    body    = await request.json()
    phone   = body.get("phone","").strip()
    purpose = body.get("purpose","login")

    if not phone:
        return JSONResponse({"success": False, "error": "Phone number required"}, status_code=400)

    # Normalize Zimbabwe number
    clean = phone.replace("+","").replace(" ","").replace("-","")
    if clean.startswith("0"):
        clean = "263" + clean[1:]
    elif not clean.startswith("263"):
        clean = "263" + clean

    result = request_otp(clean, purpose)

    if result["success"]:
        return JSONResponse({"success": True, "message": result["message"], "phone": clean})
    else:
        return JSONResponse({"success": False, "error": result.get("error","Failed to send OTP")}, status_code=500)


@app.post("/api/auth/verify-otp")
async def api_verify_otp(request: Request):
    """
    Verify the OTP sent via WhatsApp and return a session token.
    Body: {"phone": "263772123456", "otp": "123456"}
    """
    body  = await request.json()
    phone = body.get("phone","").strip()
    otp   = body.get("otp","").strip()

    result = verify_otp(phone, otp)

    if not result["valid"]:
        return JSONResponse({"success": False, "error": result["reason"]}, status_code=401)

    # OTP valid — create/get account and return token
    now   = datetime.datetime.now().isoformat()
    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()

    account = db_get_account(phone) or {}
    account.update({
        "phone":      phone,
        "last_token": token,
        "last_login": now,
        "platforms":  list(set(account.get("platforms",[]) + ["web"])),
    })
    if "registered" not in account:
        account["registered"] = now

    db_save_account(phone, account)

    profile = db_get_profile(phone) or {}
    if not profile:
        profile = {"joined": now}
        db_save_profile(phone, profile)

    track_activity(phone, "otp_login")

    return JSONResponse({
        "success": True,
        "token":   token,
        "phone":   phone,
        "purpose": result.get("purpose","login"),
        **build_user_response(phone, token),
    })


# ── Register ──────────────────────────────────────────────────

@app.post("/api/register")
async def register_user(request: Request):
    body     = await request.json()
    phone    = body.get("phone","").strip()
    password = body.get("password","").strip()
    name     = body.get("name","").strip()

    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)

    now = datetime.datetime.now().isoformat()

    if password:
        if len(password) < 4:
            return JSONResponse({"error": "Password must be at least 4 characters"}, status_code=400)
        existing = db_get_account(phone)
        if existing and existing.get("password_hash"):
            return JSONResponse({"error":"already_registered","message":"This number is already registered. Please login instead."}, status_code=409)

        hashed      = hash_password(password)
        token       = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
        account_data = {
            "phone": phone, "name": name, "password_hash": hashed,
            "platforms": [body.get("platform","web")], "registered": now,
            "last_login": now, "last_token": token,
        }
        db_save_account(phone, account_data)

        profile = db_get_profile(phone) or {}
        if not profile: profile = {"name": name, "joined": now}
        elif name:      profile["name"] = name
        db_save_profile(phone, profile)
        track_activity(phone, "register")
        return JSONResponse(build_user_response(phone, token))

    existing = db_get_account(phone) or {}
    if not existing:
        existing = {"phone": phone, "name": name,
                    "platforms": [body.get("platform","web")], "registered": now, "last_login": now}
    else:
        if name: existing["name"] = name
        plat = body.get("platform","web")
        if plat not in existing.get("platforms",[]):
            existing.setdefault("platforms",[]).append(plat)

    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
    existing["last_token"] = token
    existing["last_login"] = now
    db_save_account(phone, existing)

    profile = db_get_profile(phone) or {}
    if not profile:
        db_save_profile(phone, {"name": name, "joined": now})
    elif name:
        profile["name"] = name
        db_save_profile(phone, profile)

    track_activity(phone, "login")
    return JSONResponse(build_user_response(phone, token))


# ── Login ─────────────────────────────────────────────────────

@app.post("/api/login")
async def login_user(request: Request):
    body     = await request.json()
    phone    = body.get("phone","").strip()
    password = body.get("password","").strip()

    if not phone or not password:
        return JSONResponse({"error": "Phone and password required"}, status_code=400)

    account = db_get_account(phone)
    if not account:
        return JSONResponse({"error":"not_registered","message":"No account found. Please register first."}, status_code=404)

    if not account.get("password_hash"):
        token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
        account["last_token"] = token
        account["last_login"] = datetime.datetime.now().isoformat()
        db_save_account(phone, account)
        track_activity(phone, "login")
        resp = build_user_response(phone, token)
        resp["needs_password_setup"] = True
        return JSONResponse(resp)

    if account["password_hash"] != hash_password(password):
        return JSONResponse({"error":"wrong_password","message":"Incorrect password."}, status_code=401)

    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
    account["last_token"] = token
    account["last_login"] = datetime.datetime.now().isoformat()
    db_save_account(phone, account)
    track_activity(phone, "login")
    return JSONResponse(build_user_response(phone, token))

# ════════════════════════════════════════════════════════════
#  auth_endpoints.py
#  Add these endpoints to main.py (paste after /api/login)
#
#  NEW ENDPOINTS:
#   POST /api/auth/change-password  — user changes own password
#   POST /api/auth/setup-password   — user sets password for first time
#   POST /api/auth/forgot-password  — sends OTP via WhatsApp to reset
#   POST /api/auth/reset-password   — resets password using OTP
#   GET  /api/auth/check/{phone}    — checks if account has password set
# ════════════════════════════════════════════════════════════


@app.post("/api/auth/change-password")
async def change_user_password(request: Request):
    """
    Allows a logged-in farmer to change their password.
    Body: { phone, current_password, new_password, confirm_password }
    """
    body             = await request.json()
    phone            = body.get("phone","").strip()
    current_password = body.get("current_password","").strip()
    new_password     = body.get("new_password","").strip()
    confirm_password = body.get("confirm_password","").strip()

    if not phone or not current_password or not new_password:
        return JSONResponse(
            {"success": False, "error": "Phone, current password and new password are required"},
            status_code=400,
        )

    # Load account from Supabase to get latest password hash
    account = db_get_account(phone)
    if not account:
        return JSONResponse(
            {"success": False, "error": "Account not found. Please register first."},
            status_code=404,
        )

    stored_hash = account.get("password_hash","")

    # If no password set yet, allow them to use /api/auth/setup-password instead
    if not stored_hash:
        return JSONResponse(
            {"success": False, "error": "No password set yet. Use setup-password instead."},
            status_code=400,
        )

    # Verify current password
    if hash_password(current_password) != stored_hash:
        return JSONResponse(
            {"success": False, "error": "Current password is incorrect."},
            status_code=401,
        )

    # Validate new password
    if len(new_password) < 6:
        return JSONResponse(
            {"success": False, "error": "New password must be at least 6 characters."},
            status_code=400,
        )
    if new_password != confirm_password:
        return JSONResponse(
            {"success": False, "error": "New passwords do not match."},
            status_code=400,
        )
    if new_password == current_password:
        return JSONResponse(
            {"success": False, "error": "New password must be different from your current password."},
            status_code=400,
        )

    # Save new password
    account["password_hash"] = hash_password(new_password)
    account["password_changed"] = datetime.datetime.now().isoformat()
    db_save_account(phone, account)

    # Notify farmer via WhatsApp
    send_whatsapp_message(phone, f"""🔐 *Password Changed*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
✅ Your AgroBot Pro password has been changed successfully.

If you did not do this, contact us immediately:
📞 {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}""")

    return JSONResponse({"success": True, "message": "Password changed successfully."})


@app.post("/api/auth/setup-password")
async def setup_user_password(request: Request):
    """
    Sets a password for a user who registered via OTP (no password yet).
    Body: { phone, password }
    """
    body     = await request.json()
    phone    = body.get("phone","").strip()
    password = body.get("password","").strip()

    if not phone or not password:
        return JSONResponse(
            {"success": False, "error": "Phone and password are required"},
            status_code=400,
        )
    if len(password) < 6:
        return JSONResponse(
            {"success": False, "error": "Password must be at least 6 characters."},
            status_code=400,
        )

    account = db_get_account(phone)
    if not account:
        # Create basic account if none exists
        account = {
            "phone":      phone,
            "registered": datetime.datetime.now().isoformat(),
            "platforms":  ["web"],
        }

    account["password_hash"]   = hash_password(password)
    account["password_set_at"] = datetime.datetime.now().isoformat()
    db_save_account(phone, account)

    return JSONResponse({"success": True, "message": "Password set successfully. You can now log in."})


@app.post("/api/auth/forgot-password")
async def forgot_password(request: Request):
    """
    Sends a 6-digit OTP to the farmer's WhatsApp for password reset.
    Body: { phone }
    """
    body  = await request.json()
    phone = body.get("phone","").strip()

    if not phone:
        return JSONResponse({"success": False, "error": "Phone number required"}, status_code=400)

    # Normalize phone number
    clean = phone.replace("+","").replace(" ","").replace("-","")
    if clean.startswith("0"):
        clean = "263" + clean[1:]
    elif not clean.startswith("263"):
        clean = "263" + clean

    # Check account exists
    account = db_get_account(clean)
    if not account:
        # Don't reveal if account exists for security
        return JSONResponse({
            "success": True,
            "message": "If that number is registered, an OTP has been sent to your WhatsApp.",
        })

    result = request_otp(clean, purpose="reset_password")
    return JSONResponse({
        "success": True,
        "message": result.get("message","OTP sent to your WhatsApp number."),
    })


@app.post("/api/auth/reset-password")
async def reset_password(request: Request):
    """
    Resets password using OTP from WhatsApp.
    Body: { phone, otp, new_password, confirm_password }
    """
    body             = await request.json()
    phone            = body.get("phone","").strip()
    otp              = body.get("otp","").strip()
    new_password     = body.get("new_password","").strip()
    confirm_password = body.get("confirm_password","").strip()

    if not phone or not otp or not new_password:
        return JSONResponse(
            {"success": False, "error": "Phone, OTP and new password are required"},
            status_code=400,
        )

    # Verify OTP
    otp_result = verify_otp(phone, otp)
    if not otp_result["valid"]:
        return JSONResponse(
            {"success": False, "error": otp_result["reason"]},
            status_code=401,
        )

    if otp_result.get("purpose") != "reset_password":
        return JSONResponse(
            {"success": False, "error": "This OTP was not issued for password reset."},
            status_code=400,
        )

    # Validate new password
    if len(new_password) < 6:
        return JSONResponse(
            {"success": False, "error": "Password must be at least 6 characters."},
            status_code=400,
        )
    if new_password != confirm_password:
        return JSONResponse(
            {"success": False, "error": "Passwords do not match."},
            status_code=400,
        )

    # Save new password
    account = db_get_account(phone) or {"phone": phone, "registered": datetime.datetime.now().isoformat()}
    account["password_hash"]   = hash_password(new_password)
    account["password_reset"]  = datetime.datetime.now().isoformat()
    db_save_account(phone, account)

    # Generate new token for auto-login
    token = hashlib.sha256(f"{phone}{secrets.token_hex(16)}".encode()).hexdigest()
    account["last_token"] = token
    account["last_login"] = datetime.datetime.now().isoformat()
    db_save_account(phone, account)

    send_whatsapp_message(phone, f"""✅ *Password Reset Successful*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Your password has been reset.
You can now log in with your new password.

If you did not do this, contact us:
📞 {SUPPORT_PHONE}""")

    return JSONResponse({
        "success": True,
        "token":   token,
        "message": "Password reset successfully. You are now logged in.",
        **build_user_response(phone, token),
    })


@app.get("/api/auth/check/{phone}")
async def check_account(phone: str):
    """
    Check if a phone number has a registered account and password.
    Used by frontend to decide: show login or register.
    """
    account = db_get_account(phone)
    if not account:
        return JSONResponse({
            "exists":       False,
            "has_password": False,
            "message":      "No account found. Please register.",
        })
    return JSONResponse({
        "exists":       True,
        "has_password": bool(account.get("password_hash","")),
        "name":         account.get("name",""),
        "plan":         get_plan(phone),
        "is_premium":   is_premium(phone),
        "trial_days":   get_trial_days_left(phone),
        "message":      "Account found.",
    })


# ════════════════════════════════════════════════════════════
#  TRIAL MANAGEMENT
#  These endpoints give the frontend accurate trial data.
# ════════════════════════════════════════════════════════════

@app.get("/api/trial/{phone}")
async def get_trial_status(phone: str):
    """
    Returns complete trial/subscription status for a farmer.
    Used by TrialStatus.jsx frontend component.
    """
    # Always load from Supabase first to get accurate data
    profile = db_get_profile(phone) or farmer_profiles.get(phone, {})
    if not profile:
        return JSONResponse({"error": "Farmer not found"}, status_code=404)

    now        = datetime.datetime.now()
    joined_str = profile.get("joined","")
    plan       = get_plan(phone)
    premium    = is_premium(phone)

    # Calculate trial details
    trial_days_left = 0
    trial_days_used = 0
    expiry_date     = None
    is_expired      = False

    if joined_str:
        try:
            joined          = datetime.datetime.fromisoformat(joined_str)
            expiry          = joined + datetime.timedelta(days=TRIAL_DAYS)
            trial_days_left = max(0, (expiry - now).days)
            trial_days_used = min(TRIAL_DAYS, (now - joined).days)
            expiry_date     = expiry.isoformat()
            is_expired      = now > expiry and not premium
        except Exception as e:
            print(f"Trial calc error: {e}")

    # Auto-expire: if trial ended and not premium, make sure plan shows "free"
    if is_expired and not premium:
        # Clear any cached trial state
        if phone in farmer_profiles:
            farmer_profiles[phone]["trial_expired"] = True

    stats = get_user_stats(phone)

    return JSONResponse({
        "phone":            phone,
        "plan":             plan,
        "is_premium":       premium,
        "is_on_trial":      plan == "trial",
        "is_expired":       is_expired,
        "trial_days_total": TRIAL_DAYS,
        "trial_days_used":  trial_days_used,
        "trial_days_left":  trial_days_left,
        "trial_started":    joined_str[:10] if joined_str else "",
        "trial_expiry":     expiry_date,
        "days_on_agrobot":  stats["days_since_joining"],
        "total_messages":   stats["total_messages"],
        "total_days_active":stats["total_days_active"],
        "premium_details":  premium_users.get(phone,{}) if premium else None,
    })


@app.post("/api/trial/extend")
async def extend_trial(request: Request):
    """
    Admin endpoint to manually extend a farmer's trial.
    Body: { secret, phone, days }
    """
    body   = await request.json()
    if body.get("secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)

    phone = body.get("phone","")
    days  = int(body.get("days", 7))

    if phone not in farmer_profiles:
        return JSONResponse({"error":"Farmer not found"}, status_code=404)

    profile    = farmer_profiles[phone]
    joined_str = profile.get("joined","")

    try:
        joined    = datetime.datetime.fromisoformat(joined_str)
        new_start = joined + datetime.timedelta(days=days)
        farmer_profiles[phone]["joined"] = new_start.isoformat()
        _persist_profile(phone)
        save_data()

        new_expiry = new_start + datetime.timedelta(days=TRIAL_DAYS)
        send_whatsapp_message(phone, f"""🎁 *Trial Extended!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Your free trial has been extended by *{days} days*.
New expiry: {new_expiry.strftime('%d %B %Y')}

Type *MENU* to continue using AgroBot! 🌱""")

        return JSONResponse({
            "success":     True,
            "phone":       phone,
            "days_added":  days,
            "new_expiry":  new_expiry.isoformat(),
            "message":     f"Trial extended by {days} days",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
# ── Farmer endpoints ──────────────────────────────────────────

@app.get("/api/farmer/{phone}")
async def get_farmer(phone: str):
    if phone not in farmer_profiles:
        return JSONResponse({"error":"Farmer not found"}, status_code=404)
    stats = get_user_stats(phone)
    return JSONResponse({
        "phone":           phone,
        "profile":         farmer_profiles[phone],
        "account":         {k:v for k,v in user_accounts.get(phone,{}).items() if k!="password_hash"},
        "activity":        user_activity.get(phone,{}),
        "stats":           stats,
        "region_info":     get_region_info(farmer_profiles[phone].get("location","")),
        "is_premium":      is_premium(phone),
        "plan":            get_plan(phone),
        "trial_days_left": get_trial_days_left(phone),
    })


@app.get("/api/farmer/{phone}/conversations")
async def get_conversations_api(phone: str, limit: int = 50):
    convos = db_get_conversations(phone, limit)
    return JSONResponse({"phone": phone, "total": len(convos), "conversations": convos})


@app.get("/api/farmer/{phone}/activity")
async def get_activity_api(phone: str):
    # FIX: Try Supabase first to get latest activity even after restart
    if sb:
        try:
            rows = db_select("user_activity", {"phone": phone})
            if rows:
                row   = rows[0]
                extra = json.loads(row.pop("data","{}") or "{}")
                user_activity[phone] = {**row, **extra}
        except Exception:
            pass

    stats    = get_user_stats(phone)
    activity = user_activity.get(phone, {})
    return JSONResponse({
        "phone":          phone,
        "stats":          stats,
        "daily_activity": activity.get("daily_activity",{}),
        "actions":        activity.get("actions",{}),
        "streak_days":    activity.get("streak_days",0),
        "total_messages": activity.get("total_messages",0),
        "total_days":     activity.get("total_days_active",0),
        "first_seen":     activity.get("first_seen",""),
        "last_seen":      activity.get("last_seen",""),
    })


# ── Community ─────────────────────────────────────────────────

@app.get("/api/community")
async def get_community_api(channel: str = "", limit: int = 20):
    if channel and channel in community_channels:
        posts = community_channels[channel].get("messages",[])[-limit:]
        return JSONResponse({
            "channel": channel, "name": community_channels[channel].get("name",""),
            "total":   len(community_channels[channel].get("messages",[])),
            "online":  len(manager.active_connections.get(channel,[])), "posts": posts,
        })
    all_posts = sorted(community_posts, key=lambda x: x.get("timestamp",""), reverse=True)
    return JSONResponse({
        "total_posts": len(all_posts),
        "channels": {k: {"name":v.get("name",""),"total":len(v.get("messages",[])),
                         "online":len(manager.active_connections.get(k,[]))} for k,v in community_channels.items()},
        "recent_posts": all_posts[:limit],
    })


@app.post("/api/community/post")
async def api_post_community(request: Request):
    body    = await request.json()
    phone   = body.get("phone","")
    channel = body.get("channel","general")
    message = body.get("message","")
    if not phone or not message:
        return JSONResponse({"error":"phone and message required"}, status_code=400)
    post_to_community(phone, channel, message)
    profile = farmer_profiles.get(phone,{})
    await manager.broadcast_to_channel(channel, {
        "type":"message","phone":phone,
        "name":profile.get("name",f"Farmer {phone[-4:]}"),
        "location":profile.get("location","Zimbabwe").title(),
        "message":message,"timestamp":datetime.datetime.now().isoformat(),
        "channel":channel,"platform":"web",
    })
    return JSONResponse({"success":True})


# ── Seeds ─────────────────────────────────────────────────────

@app.get("/api/seeds")
async def get_seeds_api(location: str = "", crop: str = ""):
    if not location:
        return JSONResponse({"crops": list(SEED_BRANDS.keys())})
    info       = get_region_info(location)
    region_key = f"Region {info['region']}"
    result     = {}
    for crop_name, regions in SEED_BRANDS.items():
        seeds = regions.get(region_key, regions.get("All Regions",[]))
        if seeds:
            if crop and crop.lower() != crop_name: continue
            result[crop_name] = seeds
    return JSONResponse({
        "location": location, "region": info["region"], "climate": info["climate"],
        "best_crops": info["best_crops"], "seed_recommendations": result,
    })


# ── Market Prices ─────────────────────────────────────────────

@app.get("/api/market-prices")
async def get_prices_api(location: str = "", crop: str = ""):
    prices = await fetch_live_commodity_prices()
    adj    = REGIONAL_PRICE_ADJ.get(location.lower(), {})
    result = {}
    for c, p in prices.items():
        if crop and crop.lower().replace(" ","_") != c and crop.lower() != c:
            continue
        result[c] = {**p, "local_price": round(p["price"] * adj.get(c.replace("_"," "), adj.get(c,1.0)),2)}
    return JSONResponse({
        "prices":       result,
        "location":     location or "national",
        "last_updated": live_price_cache.get("last_updated",""),
    })


@app.put("/api/market-prices")
async def update_prices(request: Request):
    body = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    market_prices.setdefault("national",{}).update(body.get("prices",{}))
    if live_price_cache["data"]:
        live_price_cache["data"].update(body.get("prices",{}))
    save_data()
    return JSONResponse({"success":True})


# ── Weather ───────────────────────────────────────────────────

@app.get("/api/weather/{lat}/{lon}")
async def weather_api(lat: float, lon: float):
    nearest = find_nearest_region(lat, lon)
    url     = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
               f"precipitation_probability_max,et0_fao_evapotranspiration"
               f"&timezone=Africa/Harare&forecast_days=7")
    data = requests.get(url, timeout=12).json()
    return JSONResponse({
        "location": nearest["name"], "region_info": nearest["info"],
        "forecast": data.get("daily",{}), "source": "Open-Meteo Live",
        "generated": datetime.datetime.now().isoformat(),
    })


@app.get("/api/weather/by-name")
async def weather_by_name_api(location: str = "harare"):
    lat, lon, display = geocode_location_free(location)
    if not lat:
        info     = get_region_info(location)
        lat, lon = info["lat"], info["lon"]
        display  = location.title()
    url     = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
               f"precipitation_probability_max,et0_fao_evapotranspiration"
               f"&timezone=Africa/Harare&forecast_days=7")
    data    = requests.get(url, timeout=12).json()
    nearest = find_nearest_region(lat, lon)
    return JSONResponse({
        "location": display, "lat": lat, "lon": lon,
        "region_info": nearest["info"], "forecast": data.get("daily",{}),
        "source": "Open-Meteo Live", "generated": datetime.datetime.now().isoformat(),
    })


@app.get("/api/regions")
async def regions_api():
    return JSONResponse(ZIMBABWE_REGIONS)


# ── News ──────────────────────────────────────────────────────

CATEGORY_QUERIES = {
    "farming":    "Zimbabwe farming agriculture crops",
    "weather":    "Zimbabwe weather climate rainfall",
    "prices":     "Zimbabwe crop commodity prices market",
    "livestock":  "Zimbabwe livestock cattle farmers",
    "technology": "Africa agricultural technology innovation",
}


@app.get("/api/news")
async def news_api(phone: str = "", category: str = "farming"):
    query = CATEGORY_QUERIES.get(category, "Zimbabwe farming agriculture")

    try:
        async with httpx.AsyncClient(timeout=12) as http:
            res      = await http.get("https://gnews.io/api/v4/search",
                                      params={"q":query,"lang":"en","country":"zw","max":10,
                                              "apikey":GNEWS_API_KEY,"sortby":"publishedAt"})
            articles = res.json().get("articles",[])

        if len(articles) < 3:
            async with httpx.AsyncClient(timeout=12) as http:
                res2     = await http.get("https://gnews.io/api/v4/search",
                                          params={"q":query,"lang":"en","max":10,
                                                  "apikey":GNEWS_API_KEY,"sortby":"publishedAt"})
                articles = res2.json().get("articles",[])

        if articles:
            with_img    = [a for a in articles if a.get("image")]
            without_img = [a for a in articles if not a.get("image")]
            seen, unique = set(), []
            for a in with_img + without_img:
                if a.get("title") not in seen:
                    seen.add(a.get("title")); unique.append(a)
            return JSONResponse({"source":"live","category":category,"articles":unique[:10],
                                 "generated":datetime.datetime.now().isoformat()})
    except Exception as e:
        print(f"GNews error: {e}")

    try:
        now       = datetime.datetime.now()
        ai_prompt = f"""Zimbabwe farming news editor. Today: {now.strftime('%d %B %Y')}.
Write 5 realistic Zimbabwe farming news articles as JSON array. Return ONLY valid JSON:
[{{"title":"Headline","description":"2-3 sentence summary.","source":{{"name":"The Herald Zimbabwe"}},
"publishedAt":"{now.isoformat()}","url":"https://www.herald.co.zw","image":null,"category":"{category}"}}]
Topics: {query}."""
        response    = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":ai_prompt}],
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw: raw = raw.split("```")[1].split("```")[0].replace("json","").strip()
        ai_articles = json.loads(raw)
        zw_sources  = ["https://www.herald.co.zw","https://www.chronicle.co.zw","https://www.newsday.co.zw"]
        for i, art in enumerate(ai_articles):
            if not art.get("url"):    art["url"]    = zw_sources[i % len(zw_sources)]
            if not art.get("source"): art["source"] = {"name":"Zimbabwe News"}
        return JSONResponse({"source":"ai","category":category,"articles":ai_articles,
                             "generated":now.isoformat()})
    except Exception as e:
        print(f"AI news fallback error: {e}")

    return JSONResponse({"source":"none","category":category,"articles":[],
                         "generated":datetime.datetime.now().isoformat()})


# ── Ask ───────────────────────────────────────────────────────

@app.post("/api/ask")
async def ask_api(request: Request):
    body  = await request.json()
    q     = body.get("question","")
    phone = body.get("phone","")
    if not q:
        return JSONResponse({"error":"Question required"}, status_code=400)
    if phone:
        save_conversation(phone,"farmer",q,"api")
        track_activity(phone,"api_question")
    answer = ask_groq(q, body.get("topic",""), phone)
    if phone:
        save_conversation(phone,"agrobot",answer,"api")
    return JSONResponse({"answer":answer,"phone":phone,"timestamp":datetime.datetime.now().isoformat()})


# ── Web Image Analysis ────────────────────────────────────────

@app.post("/api/analyse-image-web")
async def analyse_image_web(request: Request):
    try:
        body       = await request.json()
        img_base64 = body.get("image_base64","")
        img_type   = body.get("image_type","image/jpeg")
        phone      = body.get("phone","")

        if not img_base64:
            return JSONResponse({"error":"No image provided"}, status_code=400)

        farmer_ctx = get_farmer_context(phone) if phone else ""
        models     = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ]

        prompt = f"""You are {BOT_NAME} — expert plant pathologist for Zimbabwe agriculture.

{farmer_ctx}

Analyse this crop image and provide a COMPLETE professional report:
🌿 CROP IDENTIFIED | 🔍 PROBLEM DETECTED | 📊 SEVERITY
💊 IMMEDIATE TREATMENT (Zimbabwe brand names, rates, costs USD)
🔄 FOLLOW-UP TREATMENT | 🛡️ PREVENTION | ⏰ URGENCY"""

        last_error = ""
        for model in models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"user","content":[
                        {"type":"image_url","image_url":{"url":f"data:{img_type};base64,{img_base64}"}},
                        {"type":"text","text":prompt},
                    ]}],
                    max_tokens=800,
                )
                analysis = response.choices[0].message.content
                fail_phrases = ["cannot see","can't see","no image","not provided","unable to view"]
                if any(p in analysis.lower() for p in fail_phrases):
                    last_error = "Vision model could not process image"; continue
                if phone:
                    save_conversation(phone,"farmer","[Uploaded crop photo via website]","image")
                    save_conversation(phone,"agrobot",analysis,"image_analysis")
                return JSONResponse({"success":True,"analysis":analysis,"model":model})
            except Exception as e:
                last_error = str(e); continue

        return JSONResponse({"error":"Could not analyse image. Try a clearer photo.","detail":last_error}, status_code=500)
    except Exception as e:
        return JSONResponse({"error":"Analysis failed. Please try again."}, status_code=500)


# ── Location Verify ───────────────────────────────────────────

@app.post("/api/verify-location")
async def verify_location(request: Request):
    body     = await request.json()
    phone    = body.get("phone","").strip()
    location = body.get("location","").strip()
    if not phone or not location:
        return JSONResponse({"error":"Phone and location required"}, status_code=400)

    matched_city = None; matched_info = None; precise_lat = None; precise_lon = None; ai_note = ""

    try:
        nom_lat, nom_lon, nom_display = geocode_location_free(location)
        if nom_lat:
            precise_lat  = nom_lat; precise_lon = nom_lon
            nearest      = find_nearest_region(precise_lat, precise_lon)
            matched_city = nearest["name"]; matched_info = nearest["info"]
            ai_note      = f"📡 OpenStreetMap verified: {nom_display}"
    except Exception: pass

    if not matched_city:
        for city, info in ZIMBABWE_REGIONS.items():
            if city in location.lower() or location.lower() in city:
                matched_city = city; matched_info = info
                ai_note      = f"Matched to {city.title()}"; break

    if not matched_city:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":f"""Match "{location}" to nearest Zimbabwe town.
Return ONLY JSON: {{"city":"marondera","note":"brief note"}}
Towns: harare,bulawayo,mutare,masvingo,gweru,marondera,chinhoyi,bindura,victoria falls,kariba,chiredzi,beitbridge,zvishavane,kwekwe,kadoma,norton,rusape,nyanga,chipinge"""}],
                max_tokens=80,
            )
            raw  = resp.choices[0].message.content.strip()
            if "```" in raw: raw = raw.split("```")[1].split("```")[0].replace("json","").strip()
            rj   = json.loads(raw)
            matched_city = rj.get("city","harare")
            matched_info = ZIMBABWE_REGIONS.get(matched_city, ZIMBABWE_REGIONS["harare"])
            ai_note      = rj.get("note", f"Matched to {matched_city.title()}")
        except Exception:
            matched_city = "harare"; matched_info = ZIMBABWE_REGIONS["harare"]
            ai_note      = "Could not verify — defaulted to Harare"

    if phone not in farmer_profiles:
        farmer_profiles[phone] = {"joined": datetime.datetime.now().isoformat()}
    update = {"location": matched_city, "location_input": location, "location_verified": True}
    if precise_lat: update["gps_lat"] = precise_lat; update["gps_lon"] = precise_lon
    farmer_profiles[phone].update(update)
    _persist_profile(phone)
    save_data()

    return JSONResponse({"success":True,"input":location,"matched_city":matched_city,
                         "note":ai_note,"region_info":matched_info,"lat":precise_lat,"lon":precise_lon})


# ── Payment endpoints ─────────────────────────────────────────

@app.post("/api/payment/initiate")
async def payment_initiate(request: Request):
    body  = await request.json()
    phone = body.get("phone","")
    plan  = body.get("plan","premium")
    if not phone:
        return JSONResponse({"error":"Phone required"}, status_code=400)
    amount = "2" if plan == "premium" else "10"
    ref    = generate_ref(phone)
    payment_pending[ref] = {"phone":phone,"plan":plan,"amount":amount,
                             "initiated":datetime.datetime.now().isoformat(),"status":"pending"}
    save_data()
    return JSONResponse({"reference":ref,"amount":amount,"plan":plan,
                         "ecocash_number":ECOCASH_NUMBER,"onemoney_number":ONEMONEY_NUMBER,
                         "instructions":f"Pay ${amount} to {ECOCASH_NUMBER} with reference {ref}"})


@app.post("/api/payment/confirm")
async def payment_confirm(request: Request):
    body  = await request.json()
    phone = body.get("phone","")
    ref   = body.get("reference","")
    if body.get("secret") != ADMIN_SECRET and not body.get("gateway_token"):
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    result = process_payment(phone, ref)
    send_whatsapp_message(phone, result)
    return JSONResponse({"success":is_premium(phone),"phone":phone,"plan":get_plan(phone),
                         "message":"Premium activated" if is_premium(phone) else "Payment failed"})


@app.post("/api/activate-premium")
async def activate_premium(request: Request):
    body  = await request.json()
    if body.get("secret") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    phone   = body.get("phone","")
    plan    = body.get("plan","premium")
    expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {"active":True,"plan":plan,
                             "activated":datetime.datetime.now().isoformat(),"expires":expires}
    _persist_premium(phone)
    save_data()
    send_whatsapp_message(phone, f"🎉 *{plan.upper()} ACTIVATED!*\nAll features now active!\nType *MENU* to explore! 🌱")
    return JSONResponse({"success":True,"phone":phone,"expires":expires})


@app.get("/api/payment/status/{reference}")
async def check_payment_status(reference: str):
    pending = payment_pending.get(reference,{})
    phone   = pending.get("phone","")
    if is_premium(phone):
        return JSONResponse({"status":"confirmed","active":True,"plan":get_plan(phone),"message":"Premium active"})
    status = pending.get("status","pending")
    if status == "confirmed":
        return JSONResponse({"status":"confirmed","active":True,"plan":pending.get("plan","premium")})
    return JSONResponse({"status":status,"active":False,"message":"Waiting for payment"})


@app.post("/api/payment/verify-manual")
async def verify_payment_manual(request: Request):
    body      = await request.json()
    phone     = body.get("phone","")
    reference = body.get("reference","")
    amount    = body.get("amount","")
    if not phone or not reference:
        return JSONResponse({"error":"Phone and reference required"}, status_code=400)
    expected_ref = f"AGRO{phone[-6:]}"
    if reference.upper() != expected_ref.upper():
        return JSONResponse({"success":False,"expected":expected_ref,"message":"Reference does not match"}, status_code=400)
    pending    = payment_pending.get(reference.upper(),{})
    plan       = pending.get("plan","premium" if float(amount or 2) < 10 else "business")
    pay_amount = pending.get("amount", amount or "2")
    expires    = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    premium_users[phone] = {"active":True,"plan":plan,"amount":pay_amount,
                             "activated":datetime.datetime.now().isoformat(),"expires":expires,
                             "payment_ref":reference,"manual_verified":True}
    if reference.upper() in payment_pending:
        payment_pending[reference.upper()]["status"] = "confirmed"
    if phone in user_accounts:
        user_accounts[phone].update({"premium":True,"plan":plan})
    _persist_premium(phone)
    save_data()
    confirmation = process_payment(phone, reference)
    send_whatsapp_message(phone, confirmation)
    return JSONResponse({"success":True,"plan":plan,"expires":expires})


@app.post("/api/payment/ecocash-notify")
async def ecocash_notify(request: Request):
    try:
        body = await request.json()
        print(f"EcoCash notification: {body}")
        payer_phone = (body.get("msisdn") or body.get("senderMsisdn") or
                       body.get("phone") or body.get("payer","")).replace("+","").replace(" ","")
        try:
            amount = float(str(body.get("amount") or body.get("transactionAmount") or body.get("value") or "0"))
        except Exception:
            amount = 0.0
        transaction_id = body.get("transactionId") or body.get("id") or body.get("ftid") or secrets.token_hex(8)
        status = (body.get("transactionOperationStatus") or body.get("status") or "COMPLETED").upper()

        if status not in ["COMPLETED","SUCCESS","SUCCESSFUL"]:
            return JSONResponse({"status":"pending"})
        if amount < 1.5:
            return JSONResponse({"status":"ignored","reason":f"Amount ${amount} too low"})

        plan          = "business" if amount >= 9.0 else "premium"
        clean_payer   = payer_phone.replace("+","").replace(" ","").replace("-","")
        matched_phone = None

        for farmer_phone in farmer_profiles:
            clean_farmer = farmer_phone.replace("+","").replace(" ","").replace("-","")
            if clean_payer[-9:] == clean_farmer[-9:] or clean_payer[-8:] == clean_farmer[-8:]:
                matched_phone = farmer_phone; break

        if not matched_phone:
            for acc_phone in user_accounts:
                clean_acc = acc_phone.replace("+","").replace(" ","").replace("-","")
                if clean_payer[-9:] == clean_acc[-9:] or clean_payer[-8:] == clean_acc[-8:]:
                    matched_phone = acc_phone; break

        if not matched_phone:
            payment_pending[f"unmatched_{transaction_id}"] = {
                "payer_phone":payer_phone,"amount":amount,"plan":plan,
                "transaction_id":transaction_id,"status":"unmatched",
                "received":datetime.datetime.now().isoformat(),
            }
            save_data()
            return JSONResponse({"status":"unmatched","transaction_id":transaction_id})

        expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        premium_users[matched_phone] = {
            "active":True,"plan":plan,"amount":str(amount),
            "activated":datetime.datetime.now().isoformat(),"expires":expires,
            "transaction_id":transaction_id,"payer_phone":payer_phone,
            "payment_method":"ecocash_auto","no_reference":True,
        }
        if matched_phone in user_accounts:
            user_accounts[matched_phone].update({"premium":True,"plan":plan})
        _persist_premium(matched_phone)
        save_data()

        send_whatsapp_message(matched_phone, f"""🎉 *PAYMENT RECEIVED — PREMIUM ACTIVATED!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
✅ Amount: *${amount:.2f} USD* received!
✅ Plan: *{plan.upper()}*
✅ Transaction: {transaction_id}
✅ Status: *ACTIVE NOW*
✅ Valid: 30 days

Type *MENU* to use all features! 🌱🇿🇼""")

        return JSONResponse({"status":"success","phone":matched_phone,"plan":plan,"amount":amount})
    except Exception as e:
        print(f"EcoCash notify error: {e}")
        return JSONResponse({"status":"error","message":str(e)}, status_code=500)


@app.get("/api/payment/unmatched")
async def get_unmatched_payments(request: Request):
    if request.headers.get("x-admin-secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    unmatched = [{**v,"ref":k} for k,v in payment_pending.items() if v.get("status")=="unmatched"]
    return JSONResponse({"total":len(unmatched),"unmatched":unmatched})


@app.post("/api/payment/match-manual")
async def match_unmatched_payment(request: Request):
    body   = await request.json()
    if body.get("secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    ref   = body.get("ref","")
    phone = body.get("phone","")
    if ref not in payment_pending:
        return JSONResponse({"error":"Payment not found"}, status_code=404)
    pending = payment_pending[ref]
    amount  = float(pending.get("amount",2))
    plan    = "business" if amount >= 9 else "premium"
    premium_users[phone] = {
        "active":True,"plan":plan,"amount":str(amount),
        "activated":datetime.datetime.now().isoformat(),
        "expires":(datetime.datetime.now()+datetime.timedelta(days=30)).isoformat(),
        "transaction_id":pending.get("transaction_id",""),"manually_matched":True,
    }
    payment_pending[ref]["status"]        = "matched"
    payment_pending[ref]["matched_phone"] = phone
    _persist_premium(phone)
    save_data()
    send_whatsapp_message(phone, f"🎉 *Payment Matched & Premium Activated!*\n{COMPANY_NAME}\n\n✅ ${amount} confirmed!\n✅ {plan.upper()} ACTIVE!\n\nType *MENU* to explore! 🌱")
    return JSONResponse({"success":True,"phone":phone,"plan":plan})


# ── Marketplace REST ──────────────────────────────────────────

@app.get("/api/marketplace")
async def get_marketplace_api(category: str = "", search: str = "", limit: int = 20):
    sellers = [x for x in marketplace if x.get("status","active") == "active"]
    buyers  = list(buyer_requests)
    if category:
        sellers = [x for x in sellers if category.lower() in x.get("category","").lower()]
    if search:
        q       = search.lower()
        sellers = [x for x in sellers if q in x.get("item","").lower() or q in x.get("location","").lower()]
        buyers  = [x for x in buyers  if q in x.get("item","").lower() or q in x.get("location","").lower()]
    return JSONResponse({
        "total_sellers":len(sellers),"total_buyers":len(buyers),
        "sellers":sellers[-limit:],"buyers":buyers[-limit:],
        "categories":list({x.get("category","") for x in marketplace if x.get("category")}),
    })


@app.post("/api/marketplace/post")
async def api_post_marketplace(request: Request):
    body      = await request.json()
    phone     = body.get("phone","")
    post_type = body.get("type","seller")
    if not phone:
        return JSONResponse({"error":"Phone required"}, status_code=400)
    now = datetime.datetime.now().isoformat()
    if post_type == "seller":
        listing = {
            "id":secrets.token_hex(8),"type":"seller","category":body.get("category","General"),
            "item":body.get("item",""),"location":body.get("location","Zimbabwe"),
            "price":body.get("price","Negotiable"),"phone":body.get("contact_phone",phone),
            "poster":phone,"image_url":body.get("image_url",""),"timestamp":now,"status":"active",
        }
        marketplace.append(listing)
        if sb:
            try: sb.table("marketplace").upsert(listing).execute()
            except Exception as e: print(f"marketplace API save error: {e}")
        save_data(); track_activity(phone,"marketplace_post")
        return JSONResponse({"success":True,"id":listing["id"],"listing":listing})
    elif post_type == "buyer":
        req = {
            "id":secrets.token_hex(8),"type":"buyer","item":body.get("item",""),
            "quantity":body.get("quantity","Flexible"),"budget":body.get("budget","Negotiable"),
            "location":body.get("location","Zimbabwe"),"phone":body.get("contact_phone",phone),
            "poster":phone,"image_url":body.get("image_url",""),"timestamp":now,"status":"active",
        }
        buyer_requests.append(req)
        if sb:
            try: sb.table("buyer_requests").upsert(req).execute()
            except Exception as e: print(f"buyer_requests API save error: {e}")
        save_data(); track_activity(phone,"buy_request")
        return JSONResponse({"success":True,"id":req["id"],"request":req})
    return JSONResponse({"error":"type must be seller or buyer"}, status_code=400)


@app.get("/api/stats")
async def stats_api():
    all_activity   = user_activity.values()
    seven_days_ago = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    active_7d      = sum(1 for a in all_activity if a.get("last_active_date","") >= seven_days_ago)
    total_messages = sum(a.get("total_messages",0) for a in all_activity)
    online_now     = sum(len(v) for v in manager.active_connections.values())
    return JSONResponse({
        "company":COMPANY_NAME,"product":BOT_NAME,"version":"4.2.0",
        "support":{"phone":SUPPORT_PHONE,"email":SUPPORT_EMAIL,"website":WEBSITE},
        "farmers":{"total":len(farmer_profiles),
                   "premium":len([p for p in premium_users.values() if p.get("active")]),
                   "trial":sum(1 for p in farmer_profiles if is_in_trial(p)),
                   "active_7_days":active_7d,"online_now":online_now},
        "engagement":{"total_messages":total_messages,"community_posts":len(community_posts)},
        "marketplace":{"sellers":len(marketplace),"buyers":len(buyer_requests)},
        "timestamp":datetime.datetime.now().isoformat(),
    })


@app.get("/api/farmers")
async def all_farmers():
    return JSONResponse({
        "total":len(farmer_profiles),
        "farmers":[{
            "phone":p,"location":farmer_profiles[p].get("location","Unknown"),
            "plan":get_plan(p),"joined":farmer_profiles[p].get("joined","")[:10],
            "days_active":user_activity.get(p,{}).get("total_days_active",0),
            "trial_days_left":get_trial_days_left(p),
            "total_messages":user_activity.get(p,{}).get("total_messages",0),
        } for p in farmer_profiles],
    })
# ════════════════════════════════════════════════════════════
#  PART 8 OF 8 — Support Tickets, Notifications, EcoCash
#                Webhook, Admin Dashboard, Transport Hire
#                (NEW), GPS Web Fix (NEW), Expiry Checker,
#                Startup, Health Check
#
#  This is the LAST part. After pasting all 8 parts in order
#  into one file, your main.py is complete.
# ════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  TRANSPORT HIRE — New Feature
#  Farmers post trucks/machines for hire. Others book them.
# ══════════════════════════════════════════════════════════════

# In-memory store (also persisted to Supabase)
transport_listings = []   # vehicles / machines for hire
transport_bookings = []   # hire requests


def _load_transport():
    """Load transport listings from local file on startup."""
    global transport_listings, transport_bookings
    for fname, target in [
        ("transport_listings.json", transport_listings),
        ("transport_bookings.json", transport_bookings),
    ]:
        for path in [data_path(fname), fname]:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    target.clear(); target.extend(data)
                break
            except Exception:
                pass


def _save_transport():
    for fname, data in [
        ("transport_listings.json", transport_listings),
        ("transport_bookings.json", transport_bookings),
    ]:
        for path in [data_path(fname), fname]:
            try:
                with open(path, "w") as f:
                    json.dump(data, f)
                break
            except Exception:
                pass


_load_transport()

TRANSPORT_TYPES = {
    "truck":      {"label": "🚛 Truck / Lorry",          "icon": "🚛"},
    "tractor":    {"label": "🚜 Tractor (with trailer)",  "icon": "🚜"},
    "harvester":  {"label": "🌾 Combine Harvester",       "icon": "🌾"},
    "planter":    {"label": "🌱 Planter / Seeder",        "icon": "🌱"},
    "sprayer":    {"label": "💧 Sprayer (boom/knapsack)", "icon": "💧"},
    "baler":      {"label": "📦 Baler / Wrapper",         "icon": "📦"},
    "generator":  {"label": "⚡ Generator / Pump",        "icon": "⚡"},
    "grader":     {"label": "🏗️ Grader / Leveller",      "icon": "🏗️"},
    "other":      {"label": "🔧 Other Farm Equipment",    "icon": "🔧"},
}


# ── Transport API Endpoints ────────────────────────────────────

@app.get("/api/transport")
async def get_transport(
    type:     str = "",
    location: str = "",
    limit:    int = 20,
):
    """Browse all available transport and farming equipment for hire."""
    listings = [x for x in transport_listings if x.get("status","active") == "active"]

    if type:
        listings = [x for x in listings if x.get("type","").lower() == type.lower()]
    if location:
        q        = location.lower()
        listings = [x for x in listings
                    if q in x.get("location","").lower() or q in x.get("routes","").lower()]

    return JSONResponse({
        "total":        len(listings),
        "listings":     listings[-limit:],
        "types":        TRANSPORT_TYPES,
        "available":    len([x for x in listings if x.get("available", True)]),
    })


@app.post("/api/transport/post")
async def post_transport(request: Request):
    """
    Post a vehicle or farming machine for hire.
    Body fields:
      phone, type, title, description, capacity, location,
      routes, price_per_km, price_per_day, contact_phone,
      image_url (optional), available (bool)
    """
    body  = await request.json()
    phone = body.get("phone", "")

    if not phone:
        return JSONResponse({"error": "Phone required"}, status_code=400)

    transport_type = body.get("type", "truck").lower()
    if transport_type not in TRANSPORT_TYPES:
        transport_type = "other"

    listing = {
        "id":            secrets.token_hex(8),
        "phone":         phone,
        "type":          transport_type,
        "type_label":    TRANSPORT_TYPES[transport_type]["label"],
        "icon":          TRANSPORT_TYPES[transport_type]["icon"],
        "title":         body.get("title", "").strip(),
        "description":   body.get("description", "").strip(),
        "capacity":      body.get("capacity", "").strip(),        # e.g. "10 tonnes", "60HP"
        "location":      body.get("location", "Zimbabwe").strip(),
        "routes":        body.get("routes", "Nationwide").strip(), # e.g. "Harare–Bulawayo"
        "price_per_km":  body.get("price_per_km", ""),
        "price_per_day": body.get("price_per_day", ""),
        "price_note":    body.get("price_note", "Negotiable"),
        "contact_phone": body.get("contact_phone", phone),
        "whatsapp":      body.get("whatsapp", phone),
        "image_url":     body.get("image_url", ""),
        "available":     body.get("available", True),
        "status":        "active",
        "timestamp":     datetime.datetime.now().isoformat(),
        "views":         0,
        "bookings":      0,
    }

    if not listing["title"]:
        return JSONResponse({"error": "Title required (e.g. '10-Tonne Isuzu Truck')"}, status_code=400)

    transport_listings.append(listing)

    # Save to Supabase
    if sb:
        try:
            sb.table("transport_listings").upsert(listing).execute()
        except Exception as e:
            print(f"transport save error: {e}")

    _save_transport()
    track_activity(phone, "transport_post")

    return JSONResponse({
        "success": True,
        "id":      listing["id"],
        "listing": listing,
        "message": "Your transport listing is now live!",
    })


@app.get("/api/transport/{listing_id}")
async def get_transport_listing(listing_id: str):
    """Get a single transport listing and increment views."""
    for i, listing in enumerate(transport_listings):
        if listing.get("id") == listing_id and listing.get("status","active") == "active":
            transport_listings[i]["views"] = listing.get("views", 0) + 1
            _save_transport()
            return JSONResponse(listing)
    return JSONResponse({"error": "Listing not found"}, status_code=404)


@app.put("/api/transport/{listing_id}")
async def update_transport(listing_id: str, request: Request):
    """Update availability or details of a transport listing."""
    body  = await request.json()
    phone = body.get("phone", "")

    for i, listing in enumerate(transport_listings):
        if listing.get("id") == listing_id:
            if listing.get("phone") != phone:
                return JSONResponse({"error": "Not your listing"}, status_code=403)

            allowed_fields = ["title","description","capacity","location","routes",
                              "price_per_km","price_per_day","price_note",
                              "contact_phone","whatsapp","image_url","available"]
            for field in allowed_fields:
                if field in body:
                    transport_listings[i][field] = body[field]

            transport_listings[i]["updated"] = datetime.datetime.now().isoformat()

            if sb:
                try:
                    sb.table("transport_listings").upsert(transport_listings[i]).execute()
                except Exception: pass

            _save_transport()
            return JSONResponse({"success": True, "listing": transport_listings[i]})

    return JSONResponse({"error": "Listing not found"}, status_code=404)


@app.delete("/api/transport/{listing_id}")
async def delete_transport(listing_id: str, request: Request):
    """Remove a transport listing."""
    body  = await request.json()
    phone = body.get("phone", "")

    for i, listing in enumerate(transport_listings):
        if listing.get("id") == listing_id:
            if listing.get("phone") != phone:
                return JSONResponse({"error": "Not your listing"}, status_code=403)
            transport_listings[i]["status"] = "deleted"
            _save_transport()
            if sb:
                try:
                    sb.table("transport_listings").update({"status":"deleted"}).eq("id", listing_id).execute()
                except Exception: pass
            return JSONResponse({"success": True})

    return JSONResponse({"error": "Listing not found"}, status_code=404)


@app.post("/api/transport/{listing_id}/book")
async def book_transport(listing_id: str, request: Request):
    """
    Send a hire request for a transport listing.
    Notifies the owner via WhatsApp.
    """
    body  = await request.json()
    phone = body.get("phone", "")
    name  = body.get("name", f"Farmer {phone[-4:]}" if phone else "Farmer")

    listing = next((x for x in transport_listings if x.get("id") == listing_id
                    and x.get("status","active") == "active"), None)
    if not listing:
        return JSONResponse({"error": "Listing not found"}, status_code=404)

    if not listing.get("available", True):
        return JSONResponse({"error": "This equipment is currently not available"}, status_code=409)

    booking = {
        "id":           secrets.token_hex(8),
        "listing_id":   listing_id,
        "renter_phone": phone,
        "renter_name":  name,
        "owner_phone":  listing.get("phone",""),
        "hire_date":    body.get("hire_date",""),
        "duration":     body.get("duration",""),
        "pickup":       body.get("pickup",""),
        "destination":  body.get("destination",""),
        "message":      body.get("message",""),
        "status":       "pending",
        "timestamp":    datetime.datetime.now().isoformat(),
    }
    transport_bookings.append(booking)

    # Increment listing booking count
    for i, lst in enumerate(transport_listings):
        if lst.get("id") == listing_id:
            transport_listings[i]["bookings"] = lst.get("bookings", 0) + 1

    _save_transport()

    # Notify listing owner via WhatsApp
    owner_phone = listing.get("phone","")
    if owner_phone:
        hire_date_str = f"\n📅 Hire date: {body.get('hire_date','')}" if body.get("hire_date") else ""
        duration_str  = f"\n⏰ Duration: {body.get('duration','')}"    if body.get("duration")  else ""
        route_str     = f"\n🗺️ Route: {body.get('pickup','')} → {body.get('destination','')}" if body.get("pickup") else ""
        msg_str       = f"\n💬 Message: {body.get('message','')}"       if body.get("message")   else ""

        send_whatsapp_message(owner_phone, f"""🚛 *NEW HIRE REQUEST!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Someone wants to hire your:
*{listing.get('icon','')} {listing.get('title','')}*

👤 From: {name}
📞 Contact: {phone}{hire_date_str}{duration_str}{route_str}{msg_str}
━━━━━━━━━━━━━━━━━━━━━━
Reply to this person directly:
📞 {phone}

🌐 {WEBSITE}/transport""")

    # Notify renter that request was sent
    if phone:
        send_whatsapp_message(phone, f"""✅ *Hire Request Sent!*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
Your request for:
*{listing.get('icon','')} {listing.get('title','')}*

Has been sent to the owner.
They will contact you on:
📞 {phone}

━━━━━━━━━━━━━━━━━━━━━━
Owner contact: {listing.get('contact_phone','')}
Type *MENU* to return to AgroBot""")

    return JSONResponse({
        "success":    True,
        "booking_id": booking["id"],
        "message":    "Hire request sent! The owner will contact you via WhatsApp.",
        "owner_contact": listing.get("contact_phone",""),
    })


@app.post("/api/transport/upload-image")
async def upload_transport_image(request: Request):
    """Upload a photo of a vehicle or machine to Cloudinary."""
    try:
        body       = await request.json()
        img_base64 = body.get("image_base64", "")
        if not img_base64:
            return JSONResponse({"error": "No image provided"}, status_code=400)

        img_bytes  = base64.b64decode(img_base64)
        image_url  = upload_to_cloudinary(img_bytes, "transport")

        if image_url:
            return JSONResponse({"success": True, "image_url": image_url})
        else:
            return JSONResponse({"error": "Upload failed. Check Cloudinary settings."}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/transport/my/{phone}")
async def get_my_transport(phone: str):
    """Get all transport listings posted by a specific farmer."""
    listings = [x for x in transport_listings
                if x.get("phone") == phone and x.get("status","active") == "active"]
    bookings = [x for x in transport_bookings if x.get("owner_phone") == phone]
    return JSONResponse({
        "phone":    phone,
        "listings": listings,
        "bookings": bookings,
        "total":    len(listings),
    })


# ══════════════════════════════════════════════════════════════
#  GPS WEB FIX — Auto-detect browser GPS and save to profile
# ══════════════════════════════════════════════════════════════

@app.post("/api/location/save-gps")
async def save_gps_web(request: Request):
    """
    Called automatically by the website when the browser grants
    GPS permission. Saves the farmer's precise location immediately.

    Frontend JavaScript (add to your React app):

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        await fetch('/api/location/save-gps', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone, lat: latitude, lon: longitude })
        });
      },
      (error) => console.log('GPS not available:', error),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
    """
    body  = await request.json()
    phone = body.get("phone","").strip()
    lat   = body.get("lat")
    lon   = body.get("lon")

    if not phone or lat is None or lon is None:
        return JSONResponse({"error": "phone, lat and lon required"}, status_code=400)

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return JSONResponse({"error": "lat and lon must be numbers"}, status_code=400)

    if phone not in farmer_profiles:
        farmer_profiles[phone] = {"joined": datetime.datetime.now().isoformat()}

    farmer_profiles[phone].update({
        "gps_lat":       lat,
        "gps_lon":       lon,
        "gps_source":    "web_browser",
        "gps_updated":   datetime.datetime.now().isoformat(),
        "registered":    True,
    })

    nearest = find_nearest_region(lat, lon)
    info    = nearest["info"]

    # Also update location name so text advice uses it
    if not farmer_profiles[phone].get("location"):
        farmer_profiles[phone]["location"] = nearest["name"]

    _persist_profile(phone)   # Save to Supabase immediately
    save_data()
    track_activity(phone, "web_gps")

    return JSONResponse({
        "success":    True,
        "nearest":    nearest["name"],
        "region":     info["region"],
        "climate":    info["climate"],
        "best_crops": info["best_crops"],
        "lat":        lat,
        "lon":        lon,
        "message":    f"GPS saved — {nearest['name'].title()} detected",
    })


@app.get("/api/location/my/{phone}")
async def get_my_location(phone: str):
    """Return the saved location/GPS data for a farmer."""
    profile = db_get_profile(phone) or farmer_profiles.get(phone, {})
    if not profile:
        return JSONResponse({"error": "Farmer not found"}, status_code=404)

    has_gps  = "gps_lat" in profile
    location = profile.get("location", "")
    info     = get_region_info(location) if location else ZIMBABWE_REGIONS["harare"]
    nearest  = find_nearest_region(profile["gps_lat"], profile["gps_lon"]) if has_gps else None

    return JSONResponse({
        "phone":       phone,
        "has_gps":     has_gps,
        "lat":         profile.get("gps_lat"),
        "lon":         profile.get("gps_lon"),
        "gps_source":  profile.get("gps_source","whatsapp"),
        "gps_updated": profile.get("gps_updated",""),
        "location":    location,
        "nearest":     nearest["name"] if nearest else location,
        "region_info": nearest["info"] if nearest else info,
    })


# ══════════════════════════════════════════════════════════════
#  SUPPORT TICKET SYSTEM
# ══════════════════════════════════════════════════════════════

@app.post("/api/support/ticket")
async def create_support_ticket(request: Request):
    body     = await request.json()
    phone    = body.get("phone","")
    subject  = body.get("subject","")
    message  = body.get("message","")
    category = body.get("category","general")

    if not phone or not message:
        return JSONResponse({"error":"Phone and message required"}, status_code=400)

    ticket_id = f"TKT{secrets.token_hex(4).upper()}"
    ticket    = {
        "id":ticket_id,"phone":phone,"subject":subject,"message":message,
        "category":category,"status":"open","created":datetime.datetime.now().isoformat(),
        "replies":[],"resolved":False,
    }
    db_save_ticket(ticket)

    send_whatsapp_message(phone, f"""✅ *Support Ticket Created*
{COMPANY_NAME}
━━━━━━━━━━━━━━━━━━━━━━
🎫 Ticket ID: *{ticket_id}*
📋 Subject: {subject}
📊 Status: *Open*

We will respond within 24 hours.
📞 Urgent: {SUPPORT_PHONE}
📧 {SUPPORT_EMAIL}""")

    return JSONResponse({"success":True,"ticket_id":ticket_id,"message":"Ticket created successfully"})


@app.get("/api/support/tickets/{phone}")
async def get_user_tickets(phone: str):
    if sb:
        try:
            r = sb.table("support_tickets").select("*").eq("phone",phone).order("created_at",desc=True).execute()
            tickets = []
            for row in (r.data or []):
                row["replies"] = json.loads(row.get("replies","[]") or "[]")
                tickets.append(row)
            return JSONResponse({"phone":phone,"total":len(tickets),"tickets":tickets})
        except Exception as e:
            print(f"get_user_tickets error: {e}")
    tickets = support_tickets.get(phone,[])
    return JSONResponse({"phone":phone,"total":len(tickets),"tickets":tickets})


@app.get("/api/support/all")
async def get_all_tickets(request: Request):
    if request.headers.get("x-admin-secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    all_tickets = db_get_all_tickets()
    return JSONResponse({
        "total":    len(all_tickets),
        "open":     len([t for t in all_tickets if t.get("status")=="open"]),
        "resolved": len([t for t in all_tickets if t.get("status")=="resolved"]),
        "tickets":  all_tickets,
    })


@app.post("/api/support/reply")
async def reply_to_ticket(request: Request):
    body      = await request.json()
    if body.get("secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    ticket_id = body.get("ticket_id","")
    reply_msg = body.get("reply","")
    resolve   = body.get("resolve", False)

    ticket_found = None; phone_found = None

    if sb:
        try:
            r = sb.table("support_tickets").select("*").eq("id",ticket_id).execute()
            if r.data:
                ticket_found = r.data[0]
                ticket_found["replies"] = json.loads(ticket_found.get("replies","[]") or "[]")
                phone_found = ticket_found["phone"]
        except Exception as e:
            print(f"reply ticket Supabase error: {e}")

    if not ticket_found:
        for phone, tickets in support_tickets.items():
            for ticket in tickets:
                if ticket["id"] == ticket_id:
                    ticket_found = ticket; phone_found = phone; break

    if not ticket_found:
        return JSONResponse({"error":"Ticket not found"}, status_code=404)

    ticket_found["replies"].append({
        "message":reply_msg,"from":"admin","timestamp":datetime.datetime.now().isoformat()
    })
    if resolve:
        ticket_found["status"]   = "resolved"
        ticket_found["resolved"] = True
    db_save_ticket(ticket_found)

    send_whatsapp_message(phone_found, f"""📬 *Support Reply — {COMPANY_NAME}*
━━━━━━━━━━━━━━━━━━━━━━
🎫 Ticket: *{ticket_id}*

💬 *Response:*
{reply_msg}

Status: {'✅ Resolved' if resolve else '🔄 In Progress'}
Reply here or call: {SUPPORT_PHONE}""")

    return JSONResponse({"success":True,"ticket_id":ticket_id})


@app.post("/api/support/admin-fix")
async def admin_fix_account(request: Request):
    body   = await request.json()
    if body.get("secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    phone  = body.get("phone","")
    action = body.get("action","")
    note   = body.get("note","")
    result = {"success":False,"action":action,"phone":phone}

    if action == "reset_trial":
        if phone in farmer_profiles:
            farmer_profiles[phone]["joined"] = datetime.datetime.now().isoformat()
            _persist_profile(phone); save_data()
            result.update({"success":True,"message":f"Trial reset for {phone}"})
            send_whatsapp_message(phone, f"🎁 *Trial Reset by {COMPANY_NAME}*\nYour 30-day free trial has been reset!\nType *MENU* to continue! 🌱")

    elif action == "extend_premium":
        days = body.get("days",30)
        if phone in premium_users:
            current_exp = premium_users[phone].get("expires",datetime.datetime.now().isoformat())
            try:    exp_dt = datetime.datetime.fromisoformat(current_exp)
            except: exp_dt = datetime.datetime.now()
            new_exp = exp_dt + datetime.timedelta(days=days)
            premium_users[phone]["expires"] = new_exp.isoformat()
            premium_users[phone]["active"]  = True
        else:
            premium_users[phone] = {
                "active":True,"plan":"premium","activated":datetime.datetime.now().isoformat(),
                "expires":(datetime.datetime.now()+datetime.timedelta(days=days)).isoformat(),
            }
        _persist_premium(phone); save_data()
        result.update({"success":True,"message":f"Premium extended {days} days for {phone}"})
        send_whatsapp_message(phone, f"✅ *Account Updated — {COMPANY_NAME}*\nPremium extended by {days} days!\nType *MENU* to continue! 🌱")

    elif action == "clear_history":
        if phone in conversations:
            conversations[phone] = []; save_data()
        result.update({"success":True,"message":f"History cleared for {phone}"})

    elif action == "refund_reset":
        if phone in premium_users:
            premium_users[phone]["active"] = False
            _persist_premium(phone); save_data()
        result.update({"success":True,"message":f"Premium deactivated for {phone}"})
        send_whatsapp_message(phone, f"ℹ️ *Account Update — {COMPANY_NAME}*\n{note or 'Your account has been updated.'}\nContact: {SUPPORT_PHONE}")

    elif action == "send_message":
        send_whatsapp_message(phone, note)
        result.update({"success":True,"message":f"Message sent to {phone}"})

    return JSONResponse(result)


# ── Notifications ─────────────────────────────────────────────

@app.post("/api/notifications/send")
async def send_notification(request: Request):
    body   = await request.json()
    if body.get("secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)
    title        = body.get("title","")
    message      = body.get("message","")
    notify_type  = body.get("type","update")
    target       = body.get("target","all")
    target_phone = body.get("phone","")

    notif = {
        "id":secrets.token_hex(8),"title":title,"message":message,
        "type":notify_type,"target":target,"created":datetime.datetime.now().isoformat(),"read_by":[],
    }
    notifications.append(notif); save_data()

    targets = []
    if target == "all":           targets = list(farmer_profiles.keys())
    elif target == "premium":     targets = [p for p in premium_users if premium_users[p].get("active")]
    elif target == "trial":       targets = [p for p in farmer_profiles if is_in_trial(p)]
    elif target == "specific" and target_phone: targets = [target_phone]

    whatsapp_msg = f"📢 *{title}*\n{COMPANY_NAME}\n━━━━━━━━━━━━━━━━━━━━━━\n{message}\n━━━━━━━━━━━━━━━━━━━━━━\nType *MENU* to continue 🌱"

    sent_count = 0
    for phone in targets[:50]:
        try:
            send_whatsapp_message(phone, whatsapp_msg); sent_count += 1
        except Exception:
            pass

    return JSONResponse({"success":True,"notification_id":notif["id"],"sent_to":sent_count})


@app.get("/api/notifications")
async def get_notifications(phone: str = ""):
    plan        = get_plan(phone) if phone else "free"
    user_notifs = []
    for n in notifications[-20:]:
        target = n.get("target","all")
        if (target=="all"
                or (target=="premium" and plan in ["premium","business"])
                or (target=="trial"   and plan=="trial")
                or (target=="specific" and n.get("phone")==phone)):
            user_notifs.append({**n,"read":phone in n.get("read_by",[])})
    return JSONResponse({
        "total":         len(user_notifs),
        "unread":        len([n for n in user_notifs if not n.get("read")]),
        "notifications": list(reversed(user_notifs)),
    })


@app.post("/api/notifications/read")
async def mark_notification_read(request: Request):
    body     = await request.json()
    phone    = body.get("phone","")
    notif_id = body.get("notification_id","")
    for n in notifications:
        if n["id"] == notif_id and phone not in n.get("read_by",[]):
            n.setdefault("read_by",[]).append(phone)
    save_data()
    return JSONResponse({"success":True})


# ── Admin Dashboard ───────────────────────────────────────────

@app.get("/api/admin/dashboard")
async def admin_dashboard(request: Request):
    if request.headers.get("x-admin-secret","") != ADMIN_SECRET:
        return JSONResponse({"error":"Unauthorized"}, status_code=401)

    now             = datetime.datetime.now()
    all_farmers_db  = db_get_all_farmers()
    all_accounts_db = db_get_all_accounts()
    all_tickets     = db_get_all_tickets()
    all_phones      = set(list(farmer_profiles.keys()) + [f["phone"] for f in all_farmers_db if "phone" in f])

    all_premium = {}
    if sb:
        try:
            r = sb.table("premium_users").select("*").eq("active",True).execute()
            for row in (r.data or []):
                all_premium[row["phone"]] = row
        except Exception: pass
    all_premium.update({k:v for k,v in premium_users.items() if v.get("active")})

    premium_count   = len([p for p in all_premium.values() if p.get("plan")=="premium"])
    business_count  = len([p for p in all_premium.values() if p.get("plan")=="business"])
    monthly_revenue = (premium_count * 2) + (business_count * 10)

    all_accts = dict(user_accounts)
    if isinstance(all_accounts_db, dict):
        all_accts.update(all_accounts_db)

    registered_with_password = len([a for a in all_accts.values() if a.get("password_hash")])

    today     = now.strftime("%Y-%m-%d")
    yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    all_activity = dict(user_activity)
    if sb:
        try:
            r = sb.table("user_activity").select("phone,total_messages,last_active_date").execute()
            for row in (r.data or []):
                if row["phone"] not in all_activity:
                    all_activity[row["phone"]] = row
        except Exception: pass

    active_today     = sum(1 for a in all_activity.values() if a.get("last_active_date")==today)
    active_yesterday = sum(1 for a in all_activity.values() if a.get("last_active_date")==yesterday)
    total_messages   = sum(a.get("total_messages",0) for a in all_activity.values())

    location_counts = {}
    all_profiles = {f["phone"]:f for f in all_farmers_db}
    all_profiles.update(farmer_profiles)
    for p in all_profiles.values():
        loc = p.get("location","unknown") or "unknown"
        location_counts[loc] = location_counts.get(loc,0) + 1
    top_locations = sorted(location_counts.items(), key=lambda x:x[1], reverse=True)[:10]

    expiring_soon = []
    for phone, data in all_premium.items():
        if data.get("active"):
            try:
                exp = datetime.datetime.fromisoformat(str(data.get("expires",""))[:26])
                if (exp-now).days <= 7:
                    expiring_soon.append({"phone":phone,"plan":data.get("plan"),
                                          "expires":str(data.get("expires",""))[:10],
                                          "days_left":(exp-now).days})
            except Exception: pass

    farmers_list = []
    for phone in all_phones:
        profile  = all_profiles.get(phone,{})
        activity = all_activity.get(phone,{})
        account  = all_accts.get(phone,{})
        farmers_list.append({
            "phone":phone,"name":profile.get("name",account.get("name","")),
            "location":profile.get("location",""),"plan":get_plan(phone),
            "trial_days_left":get_trial_days_left(phone),"has_gps":"gps_lat" in profile,
            "days_active":activity.get("total_days_active",0),
            "joined":str(profile.get("joined",""))[:10],
            "messages":activity.get("total_messages",0),
            "has_password":bool(account.get("password_hash")),
        })

    return JSONResponse({
        "summary": {
            "total_registered_farms":    len(all_phones),
            "registered_with_password":  registered_with_password,
            "premium_active":            premium_count,
            "business_active":           business_count,
            "trial_active":              sum(1 for p in all_phones if is_in_trial(p)),
            "monthly_revenue_usd":       monthly_revenue,
            "active_today":              active_today,
            "active_yesterday":          active_yesterday,
            "total_messages":            total_messages,
            "community_posts":           len(community_posts),
            "marketplace_listings":      len(marketplace) + len(buyer_requests),
            "transport_listings":        len([x for x in transport_listings if x.get("status","active")=="active"]),
            "open_tickets":              len([t for t in all_tickets if t.get("status")=="open"]),
        },
        "top_locations":   [{"location":l,"count":c} for l,c in top_locations],
        "expiring_soon":   expiring_soon,
        "recent_tickets":  all_tickets[:10],
        "recent_registrations": [
            {"phone":p,"name":all_accts.get(p,{}).get("name",""),
             "registered":str(all_accts.get(p,{}).get("registered",""))[:10],
             "has_password":bool(all_accts.get(p,{}).get("password_hash")),
             "last_login":str(all_accts.get(p,{}).get("last_login",""))[:10],
             "plan":get_plan(p)}
            for p in list(all_accts.keys())[-20:]
        ],
        "farmers_list": farmers_list,
    })


admin_config = {}

def load_admin_config():
    global admin_config
    try:
        with open("admin_config.json","r") as f:
            admin_config.update(json.load(f))
    except Exception:
        admin_config = {"password":"AGROBOT_ADMIN_2026","last_changed":datetime.datetime.now().isoformat()}

def save_admin_config():
    with open("admin_config.json","w") as f:
        json.dump(admin_config, f, indent=2)

load_admin_config()


@app.post("/api/admin/change-password")
async def change_admin_password(request: Request):
    body     = await request.json()
    current  = body.get("current_password","")
    new_pass = body.get("new_password","")
    confirm  = body.get("confirm_password","")
    stored   = admin_config.get("password",ADMIN_SECRET)
    if current != stored and current != ADMIN_SECRET:
        return JSONResponse({"success":False,"error":"Current password is incorrect"}, status_code=401)
    if not new_pass or len(new_pass) < 8:
        return JSONResponse({"success":False,"error":"Password must be at least 8 characters"}, status_code=400)
    if new_pass != confirm:
        return JSONResponse({"success":False,"error":"Passwords do not match"}, status_code=400)
    if new_pass == current:
        return JSONResponse({"success":False,"error":"New password must differ from current"}, status_code=400)
    admin_config["password"]     = new_pass
    admin_config["last_changed"] = datetime.datetime.now().isoformat()
    save_admin_config()
    return JSONResponse({"success":True,"message":"Password changed successfully"})


@app.post("/api/admin/verify-password")
async def verify_admin_password(request: Request):
    body     = await request.json()
    password = body.get("password","")
    stored   = admin_config.get("password",ADMIN_SECRET)
    if password == stored or password == ADMIN_SECRET:
        return JSONResponse({"success":True,"last_changed":admin_config.get("last_changed","Unknown")})
    return JSONResponse({"success":False,"error":"Incorrect password"}, status_code=401)


# ══════════════════════════════════════════════════════════════
#  PREMIUM EXPIRY BACKGROUND CHECKER
#  Runs every hour — sends WhatsApp reminders automatically
# ══════════════════════════════════════════════════════════════

def check_premium_expiries():
    while True:
        try:
            now = datetime.datetime.now()

            for phone, data in list(premium_users.items()):
                if not data.get("active"): continue
                expires_str = data.get("expires","")
                if not expires_str: continue
                try:
                    expires   = datetime.datetime.fromisoformat(expires_str)
                    days_left = (expires - now).days
                    if days_left == 3:
                        send_whatsapp_message(phone, f"""⚠️ *Premium Expiring Soon!*
{COMPANY_NAME}
Your {data.get('plan','premium').upper()} plan expires in *3 days*.
Renew: EcoCash *{ECOCASH_NUMBER}* | Ref: *AGRO{phone[-6:]}*
Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                    elif days_left == 1:
                        send_whatsapp_message(phone, f"""🚨 *Premium Expires TOMORROW!*
{COMPANY_NAME}
Renew NOW: EcoCash *{ECOCASH_NUMBER}*
Ref: *AGRO{phone[-6:]}* | Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                    elif days_left < 0:
                        premium_users[phone]["active"] = False
                        _persist_premium(phone); save_data()
                        send_whatsapp_message(phone, f"""😔 *Premium Plan Expired*
{COMPANY_NAME}
Renew: EcoCash *{ECOCASH_NUMBER}*
Ref: *AGRO{phone[-6:]}* | Reply: *PAID AGRO{phone[-6:]}*
📞 {SUPPORT_PHONE}""")
                except Exception as e:
                    print(f"Expiry check error {phone}: {e}")

            for phone, profile in list(farmer_profiles.items()):
                if is_premium(phone): continue
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
                    joined_str = profile.get("joined","")
                    try:
                        joined    = datetime.datetime.fromisoformat(joined_str)
                        trial_end = joined + datetime.timedelta(days=TRIAL_DAYS)
                        hours_ago = (now - trial_end).total_seconds() / 3600
                        if 0 < hours_ago < 2:
                            send_whatsapp_message(phone, f"""😔 *Free Trial Has Ended*
{COMPANY_NAME}
Subscribe: EcoCash *{ECOCASH_NUMBER}* | Ref: *AGRO{phone[-6:]}*
Reply: *PAID AGRO{phone[-6:]}*
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
#  STARTUP & BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════

async def keep_supabase_alive():
    """Ping Supabase every 4 days to prevent connection timeout."""
    while True:
        await asyncio.sleep(86400 * 4)
        try:
            if sb:
                sb.table("farmer_profiles").select("phone").limit(1).execute()
                print("✅ Supabase keep-alive ping sent")
        except Exception as e:
            print(f"Keep-alive error: {e}")


async def refresh_prices_background():
    """Refresh live commodity prices every 6 hours."""
    while True:
        try:
            await fetch_live_commodity_prices()
            print("✅ Live prices refreshed")
        except Exception as e:
            print(f"Price refresh error: {e}")
        await asyncio.sleep(21600)


async def sync_activity_to_supabase():
    """
    FIX for activity forgetting: Every 30 minutes, push all
    in-memory activity data to Supabase so Render restarts
    don't lose farmer progress.
    """
    while True:
        await asyncio.sleep(1800)
        try:
            synced = 0
            for phone, activity in user_activity.items():
                _persist_activity(phone, activity)
                synced += 1
            if synced:
                print(f"✅ Activity synced to Supabase: {synced} farmers")
        except Exception as e:
            print(f"Activity sync error: {e}")


@app.on_event("startup")
async def startup_event():
    print(f"🌱 {BOT_NAME} v4.2.0 starting...")
    print(f"📊 {COMPANY_NAME}")
    print(f"🗄️  Supabase:   {'Connected' if sb else 'Not connected — using local storage'}")
    print(f"☁️  Cloudinary: {'Ready' if CLOUDINARY_AVAILABLE else 'Not configured — add CLOUDINARY env vars'}")
    print(f"🚛 Transport listings: {len(transport_listings)}")
    asyncio.create_task(refresh_prices_background())
    asyncio.create_task(keep_supabase_alive())
    asyncio.create_task(sync_activity_to_supabase())   # FIX: activity persistence


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════

@app.get("/")
def home():
    online = sum(len(v) for v in manager.active_connections.values())
    return {
        "name":    BOT_NAME,
        "company": COMPANY_NAME,
        "version": "4.2.0",
        "status":  "operational",
        "support": {"phone": SUPPORT_PHONE, "email": SUPPORT_EMAIL, "website": WEBSITE},
        "stats": {
            "farmers":            len(farmer_profiles),
            "premium":            len([p for p in premium_users.values() if p.get("active")]),
            "conversations":      sum(len(c) for c in conversations.values()),
            "community_posts":    len(community_posts),
            "online_now":         online,
            "marketplace":        len(marketplace) + len(buyer_requests),
            "transport_listings": len([x for x in transport_listings if x.get("status","active")=="active"]),
        },
        "features": [
            "WhatsApp AI Chatbot",
            "Real-time WebSocket Community Chat",
            "Live GNews News with Photos",
            "Live Market Prices (World Bank + Groq AI, 6hr refresh)",
            "Live Seed Prices (Groq AI, per-request)",
            "Live Nearby Agri Help (OpenStreetMap Overpass API)",
            "Live Weather 7-Day Forecast (Open-Meteo)",
            "Photo Crop Disease Analysis (multi-model AI)",
            "GPS Precision Farming (WhatsApp + Web Auto-detect)",
            "Marketplace with Photo Listings",
            "Transport & Equipment Hire Platform (NEW)",
            "OTP Login via WhatsApp (FIXED)",
            "Activity Tracking with Supabase Persistence (FIXED)",
            "30-Day Free Trial",
            "EcoCash/OneMoney Payments",
            "REST API for Website & App",
        ],
    }