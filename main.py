from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import requests
import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Store conversation states and marketplace listings
user_states = {}
marketplace = []

# ── Load marketplace from file ─────────────────────────────────
def load_marketplace():
    global marketplace
    try:
        with open("marketplace.json", "r") as f:
            marketplace = json.load(f)
    except:
        marketplace = []

def save_marketplace():
    with open("marketplace.json", "w") as f:
        json.dump(marketplace, f)

load_marketplace()

# ── Ask Groq AI ────────────────────────────────────────────────
def ask_groq(question: str, topic: str = "") -> str:
    try:
        system_prompt = f"""You are AgroBot, an expert agriculture 
        assistant helping smallholder farmers across Zimbabwe.
        {f'Focus on: {topic}' if topic else ''}
        Answer in simple clear language under 150 words.
        Give practical advice using locally available resources.
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

# ── Main Menu ──────────────────────────────────────────────────
def get_main_menu():
    return """🌱 *Welcome to AgroBot!*
Zimbabwe's Smart Farming Assistant

Reply with a number:
1️⃣ Crop Disease & Pest Advice
2️⃣ Soil Health Analysis
3️⃣ Weather & Irrigation Advice
4️⃣ Market Prices & Yield Tips
5️⃣ 🛒 Marketplace - Buy & Sell
6️⃣ Ask Any Farming Question

Type *MENU* anytime to return here."""

# ── Marketplace Menu ───────────────────────────────────────────
def get_marketplace_menu():
    return """🛒 *AGROBOT MARKETPLACE*
Buy & Sell Crops, Fertilizer & Equipment

Reply with a number:
1️⃣ Post item for SALE
2️⃣ Search for BUYERS
3️⃣ Search for SELLERS
4️⃣ View all listings
0️⃣ Back to main menu"""

# ── View All Listings ──────────────────────────────────────────
def get_all_listings():
    if not marketplace:
        return "📭 No listings yet. Be the first to post!"
    
    result = "📋 *Current Marketplace Listings:*\n\n"
    for i, item in enumerate(marketplace[-10:], 1):
        result += f"*{i}. {item['type'].upper()}*\n"
        result += f"📦 {item['item']}\n"
        result += f"📍 {item['location']}\n"
        result += f"💰 {item['price']}\n"
        result += f"📞 {item['phone']}\n\n"
    return result

# ── Search Listings ────────────────────────────────────────────
def search_listings(search_type: str, query: str = ""):
    results = [x for x in marketplace if x['type'] == search_type]
    if query:
        results = [x for x in results if query.lower() in x['item'].lower()]
    
    if not results:
        return f"📭 No {search_type}s found. Try a different search!"
    
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
        return get_main_menu()

    # ── MENU STATE ──────────────────────────────────────────────
    if state == "menu":
        if msg in ["hi", "hello", "hey", "start", "help", "0"]:
            return get_main_menu()
        elif msg == "1":
            user_states[from_number] = "disease"
            return "🌿 *Crop Disease & Pest Advice*\n\nDescribe your crop problem or send a photo of the affected plant. What crop is affected and what symptoms do you see?"
        elif msg == "2":
            user_states[from_number] = "soil"
            return "🧪 *Soil Health Analysis*\n\nTell me about your soil:\n- What color is it?\n- Is it sandy, clay or loam?\n- What crop do you want to grow?\n- Any previous crops grown there?"
        elif msg == "3":
            user_states[from_number] = "weather"
            return "🌧️ *Weather & Irrigation Advice*\n\nTell me:\n- Your location (district/province)\n- What crop are you growing?\n- What stage is your crop at?\n- What is your current weather like?"
        elif msg == "4":
            user_states[from_number] = "market"
            return "📈 *Market Prices & Yield Tips*\n\nWhat crop would you like market information about? (e.g. maize, tobacco, soya, wheat, cotton, tomatoes)"
        elif msg == "5":
            user_states[from_number] = "marketplace"
            return get_marketplace_menu()
        elif msg == "6":
            user_states[from_number] = "freeask"
            return "💬 *Ask Any Farming Question*\n\nWhat would you like to know? Ask me anything about farming!"
        else:
            return get_main_menu()

    # ── DISEASE STATE ───────────────────────────────────────────
    elif state == "disease":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, "crop disease, pest identification and treatment in Zimbabwe")
        return f"🌿 *AgroBot Disease Advice:*\n\n{reply}\n\nType *MENU* to return to main menu."

    # ── SOIL STATE ──────────────────────────────────────────────
    elif state == "soil":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, "soil health analysis and fertilizer recommendations for Zimbabwe")
        return f"🧪 *AgroBot Soil Advice:*\n\n{reply}\n\nType *MENU* to return to main menu."

    # ── WEATHER STATE ───────────────────────────────────────────
    elif state == "weather":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, "irrigation and weather advice for Zimbabwe farming")
        return f"🌧️ *AgroBot Irrigation Advice:*\n\n{reply}\n\nType *MENU* to return to main menu."

    # ── MARKET STATE ────────────────────────────────────────────
    elif state == "market":
        user_states[from_number] = "menu"
        reply = ask_groq(msg, "crop market prices, selling tips and yield improvement in Zimbabwe")
        return f"📈 *AgroBot Market Advice:*\n\n{reply}\n\nType *MENU* to return to main menu."

    # ── FREE ASK STATE ──────────────────────────────────────────
    elif state == "freeask":
        user_states[from_number] = "menu"
        reply = ask_groq(msg)
        return f"💬 *AgroBot Answer:*\n\n{reply}\n\nType *MENU* to return to main menu."

    # ── MARKETPLACE STATE ───────────────────────────────────────
    elif state == "marketplace":
        if msg == "0":
            user_states[from_number] = "menu"
            return get_main_menu()
        elif msg == "1":
            user_states[from_number] = "post_type"
            return """📢 *Post an Item for Sale*

What are you selling?
1️⃣ Crops (maize, tomatoes, etc.)
2️⃣ Fertilizer & Chemicals
3️⃣ Equipment & Tools
4️⃣ Livestock"""
        elif msg == "2":
            user_states[from_number] = "search_buyer"
            return "🔍 *Search for Buyers*\n\nWhat item are you looking to sell? (e.g. maize, tomatoes, tobacco)"
        elif msg == "3":
            user_states[from_number] = "search_seller"
            return "🔍 *Search for Sellers*\n\nWhat item are you looking to buy? (e.g. fertilizer, maize, equipment)"
        elif msg == "4":
            user_states[from_number] = "menu"
            return get_all_listings()
        else:
            return get_marketplace_menu()

    # ── POST TYPE STATE ─────────────────────────────────────────
    elif state == "post_type":
        types = {"1": "Crops", "2": "Fertilizer & Chemicals",
                 "3": "Equipment & Tools", "4": "Livestock"}
        if msg in types:
            user_states[from_number] = f"post_item_{types[msg]}"
            return f"📦 What *{types[msg]}* are you selling?\n\nType the item name and quantity.\nExample: 10 bags of maize"
        else:
            return "Please reply with 1, 2, 3 or 4"

    # ── POST ITEM STATE ─────────────────────────────────────────
    elif state.startswith("post_item_"):
        category = state.replace("post_item_", "")
        user_states[from_number] = f"post_location_{category}_{msg}"
        return "📍 What is your *location*?\n\nExample: Marondera, Mashonaland East"

    # ── POST LOCATION STATE ─────────────────────────────────────
    elif state.startswith("post_location_"):
        parts = state.replace("post_location_", "").split("_", 1)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        user_states[from_number] = f"post_price_{category}_{item}_{msg}"
        return "💰 What is your *price*?\n\nExample: $50 per bag or negotiable"

    # ── POST PRICE STATE ────────────────────────────────────────
    elif state.startswith("post_price_"):
        parts = state.replace("post_price_", "").split("_", 2)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        location = parts[2] if len(parts) > 2 else "Unknown"
        user_states[from_number] = f"post_phone_{category}_{item}_{location}_{msg}"
        return "📞 What is your *contact phone number*?\n\nExample: 0771234567"

    # ── POST PHONE STATE ────────────────────────────────────────
    elif state.startswith("post_phone_"):
        parts = state.replace("post_phone_", "").split("_", 3)
        category = parts[0]
        item = parts[1] if len(parts) > 1 else "Unknown"
        location = parts[2] if len(parts) > 2 else "Unknown"
        price = parts[3] if len(parts) > 3 else "Negotiable"

        # Save listing
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
        save_marketplace()
        user_states[from_number] = "menu"

        return f"""✅ *Listing Posted Successfully!*

📦 Item: {item}
📍 Location: {location}
💰 Price: {price}
📞 Contact: {msg}

Your listing is now visible to all AgroBot users across Zimbabwe!

Type *MENU* to return to main menu."""

    # ── SEARCH BUYER STATE ──────────────────────────────────────
    elif state == "search_buyer":
        user_states[from_number] = "menu"
        results = search_listings("buyer", msg)
        return f"{results}\nType *MENU* to return to main menu."

    # ── SEARCH SELLER STATE ─────────────────────────────────────
    elif state == "search_seller":
        user_states[from_number] = "menu"
        results = search_listings("seller", msg)
        return f"{results}\nType *MENU* to return to main menu."

    else:
        user_states[from_number] = "menu"
        return get_main_menu()

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
        msg_text = message["text"]["body"]
        print(f"Message from {from_number}: {msg_text}")
        reply = process_message(from_number, msg_text)
        send_whatsapp_message(from_number, reply)
    except (KeyError, IndexError):
        pass
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
    print(f"Message sent: {response.status_code}")

@app.get("/")
def home():
    return {"message": "AgroBot with Marketplace is running!"}
