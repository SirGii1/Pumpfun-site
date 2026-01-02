import asyncio
import json
import httpx
import websockets
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
BOT_TOKEN = "8579945497:AAG2rxeNscB9mo--d2F1l3dWvwqiUlFuEz8"
CHAT_ID = "-1003566409395"
HELIUS_API_KEY = "YOUR_HELIUS_API_KEY"  # Get this free at helius.dev
WS_URL = "wss://pumpportal.fun/api/data"

# --- KEEP-ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Advanced Monitor is Online"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

# --- ANALYSIS TOOLS ---
async def get_dev_history(dev_address):
    """Checks how many tokens this dev has created previously."""
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "id": "dev-check",
        "method": "getAssetsByCreator",
        "params": {
            "creatorAddress": dev_address,
            "onlyVerified": False,
            "page": 1,
            "limit": 100
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=5.0)
            data = response.json()
            items = data.get("result", {}).get("items", [])
            return len(items)
        except: return 0

async def fetch_metadata(uri):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(uri, timeout=5.0)
            return res.json() if res.status_code == 200 else {}
        except: return {}

# --- PROCESSING ---
async def process_token(data):
    mint = data.get("mint")
    trader = data.get("trader") # The dev wallet address
    uri = data.get("uri")
    
    # 1. Fetch Socials
    metadata = await fetch_metadata(uri) if uri else {}
    telegram = metadata.get("telegram") or data.get("telegram")

    # 2. Strict TG Filter
    if not telegram:
        return

    # 3. Dev Wallet Analysis
    prev_tokens_count = await get_dev_history(trader)
    
    # Analysis Logic
    risk_level = "🟢 LOW" if prev_tokens_count < 3 else "⚠️ HIGH (Serial Launcher)"
    dev_summary = f"👤 <b>Dev Wallet:</b> <code>{trader[:6]}...{trader[-4:]}</code>\n"
    dev_summary += f"📊 <b>Previous Launches:</b> {prev_tokens_count}\n"
    dev_summary += f"🛡️ <b>Risk:</b> {risk_level}"

    # 4. Format Message
    name = data.get("name", "Unknown")
    symbol = data.get("symbol", "TOKEN")
    twitter = metadata.get("twitter") or data.get("twitter")
    website = metadata.get("website") or data.get("website")

    links = [f'✈️ <a href="{telegram}">Telegram</a>']
    if twitter: links.append(f'🐦 <a href="{twitter}">Twitter</a>')
    if website: links.append(f'🌐 <a href="{website}">Website</a>')
    
    message = (
        f"🚀 <b>NEW TOKEN WITH TELEGRAM</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>{name}</b> (${symbol})\n"
        f"📝 <code>{mint}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{dev_summary}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Links:</b> {' | '.join(links)}\n\n"
        f"💊 <a href='https://pump.fun/{mint}'><b>BUY ON PUMP.FUN</b></a>"
    )

    # 5. Send to Telegram
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def main():
    print("🟢 Tracking Live: Socials + Dev Analysis Active...")
    async for websocket in websockets.connect(WS_URL):
        try:
            await websocket.send(json.dumps({"method": "subscribeNewToken"}))
            async for message in websocket:
                token_data = json.loads(message)
                if token_data.get("txType") == "create":
                    asyncio.create_task(process_token(token_data))
        except: continue

if __name__ == "__main__":
    Thread(target=run_web_server).start()
    asyncio.run(main())
