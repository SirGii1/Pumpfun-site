import os
import asyncio
import json
import httpx
import websockets
from flask import Flask
from threading import Thread

# =================================================================
# 1. CONFIGURATION
# =================================================================
BOT_TOKEN = "8579945497:AAG2rxeNscB9mo--d2F1l3dWvwqiUlFuEz8"
CHAT_ID = "-1003566409395"

RPC_URL = "https://api.mainnet-beta.solana.com" 
WS_URL = "wss://pumpportal.fun/api/data"

app = Flask('')
@app.route('/')
def home(): return "<h1>Bot Status: 🟢 Live Feed Active</h1>"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

# =================================================================
# 2. DATA FETCHING
# =================================================================
async def get_wallet_stats(address):
    async with httpx.AsyncClient() as client:
        try:
            b_p = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
            h_p = {"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress", "params": [address, {"limit": 50}]}
            
            b_res, h_res = await asyncio.gather(
                client.post(RPC_URL, json=b_p, timeout=5.0),
                client.post(RPC_URL, json=h_p, timeout=5.0)
            )
            
            sol = round(b_res.json().get("result", {}).get("value", 0) / 1_000_000_000, 2)
            activity = len(h_res.json().get("result", []))
            return sol, activity
        except: return 0.0, 0

async def fetch_token_metadata(uri):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(uri, timeout=5.0)
            return res.json() if res.status_code == 200 else {}
        except: return {}

# =================================================================
# 3. MESSAGE ENGINE (SENDS ALL TOKENS)
# =================================================================
async def process_event(data):
    mint, dev, uri = data.get("mint"), data.get("trader"), data.get("uri")
    name, symbol = data.get("name", "Unknown"), data.get("symbol", "TOKEN")
    
    # Fetch Metadata
    meta = await fetch_token_metadata(uri) if uri else {}
    tg_link = meta.get("telegram") or data.get("telegram")
    twitter = meta.get("twitter") or data.get("twitter")

    # Fetch Wallet Stats
    sol_bal, tx_count = await get_wallet_stats(dev)
    
    # Determine Social Status for the message
    social_text = ""
    links_list = []
    if tg_link: links_list.append(f'✈️ <a href="{tg_link}">Telegram</a>')
    if twitter: links_list.append(f'🐦 <a href="{twitter}">Twitter</a>')
    
    if links_list:
        social_text = "  |  ".join(links_list)
    else:
        social_text = "❌ No Socials Found"

    # Message Construction
    text = (
        f"🆕 <b>NEW TOKEN CREATED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>{name}</b> (${symbol})\n"
        f"📝 <code>{mint}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Dev Wallet:</b>\n"
        f"💰 <b>Balance:</b> {sol_bal} SOL\n"
        f"📊 <b>Activity:</b> {tx_count} Txs\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 {social_text}\n\n"
        f"💊 <a href='https://pump.fun/{mint}'><b>TRADE ON PUMP.FUN</b></a>"
    )

    # Trading Buttons
    keyboard = {"inline_keyboard": [
        [{"text": "🛡️ Buy Trojan", "url": f"https://t.me/pumptrojanbot?start=r-user-{mint}"},
         {"text": "🐶 Buy BonkBot", "url": f"https://t.me/bonkbot?start={mint}"}],
        [{"text": "📊 Dexscreener", "url": f"https://dexscreener.com/solana/{mint}"},
         {"text": "🕵️ Dev Wallet", "url": f"https://solscan.io/account/{dev}"}]
    ]}

    # Send Message
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard), "disable_web_page_preview": True
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(api_url, json=payload)
        except Exception as e:
            print(f"Error sending to TG: {e}")

# =================================================================
# 4. RUNNER
# =================================================================
async def main():
    print("🚀 Sniper Live Feed Started. Sending ALL tokens...")
    async for websocket in websockets.connect(WS_URL):
        try:
            await websocket.send(json.dumps({"method": "subscribeNewToken"}))
            async for message in websocket:
                response = json.loads(message)
                if response.get("txType") == "create":
                    asyncio.create_task(process_event(response))
        except Exception as e:
            print(f"WebSocket error: {e}. Reconnecting...")
            await asyncio.sleep(2)
            continue

if __name__ == "__main__":
    Thread(target=run_web_server).start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
