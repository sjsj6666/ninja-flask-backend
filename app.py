import os
import logging
import time
import uuid
import json
import base64
import requests
import certifi
import pycountry
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# --- Configuration ---
allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://coxx.netlify.app"
]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

# --- Supabase Client Initialization ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("CRITICAL: Supabase credentials must be set as environment variables.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- Your Website's Domain ---
BASE_URL = "https://www.gameuniverse.co" 

# --- API Headers & Constants ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one", "X-Requested-With": "XMLHttpRequest", "Cookie": os.environ.get("SMILE_ONE_COOKIE")
}
BIGO_NATIVE_VALIDATE_URL = "https://mobile.bigo.tv/pay-bigolive-tv/quicklyPay/getUserDetail"
BIGO_NATIVE_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "*/*", "Origin": "https://www.gamebar.gg", "Referer": "https://www.gamebar.gg/" }
ENJOYGM_BASE_URL = "https://www.enjoygm.com/portal/supplier/api"
ENJOYGM_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "*/*", "Referer": "https://www.enjoygm.com/" }
RMTGAMESHOP_VALIDATE_URL = "https://rmtgameshop.com/game/checkid"
RMTGAMESHOP_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "*/*", "Content-Type": "application/json", "Origin": "https://rmtgameshop.com", "Referer": "https://rmtgameshop.com/", "X-Auth-Token": "5a9cbf0b303b57f12e3da444f5d42c59" }
SPACEGAMING_VALIDATE_URL = "https://spacegaming.sg/wp-json/endpoint/validate_v2"
SPACEGAMING_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "*/*", "Content-Type": "application/json", "Origin": "https://spacegaming.sg", "Referer": "https://spacegaming.sg/" }
NETEASE_BASE_URL = "https://pay.neteasegames.com/gameclub"
NETEASE_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "application/json, text/plain, */*", "Referer": "https://pay.neteasegames.com/"}
RAZER_BASE_URL = "https://gold.razer.com/api/ext/custom"
RAZER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "application/json, text/plain, */*"}
NUVERSE_VALIDATE_URL = "https://pay.nvsgames.com/web/payment/validate"
NUVERSE_HEADERS = {"User-Agent": "Mozilla/5.0"}
ROM_XD_VALIDATE_URL = "https://xdsdk-intnl-6.xd.com/product/v1/query/game/role"
ROM_XD_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "application/json, text/plain, */*", "Origin": "https://webpay.xd.com", "Referer": "https://webpay.xd.com/" }


# --- Helper Functions for ID Validation ---

def perform_ml_check(user_id, zone_id):
    # ... (code is unchanged) ...

def check_smile_one_api(game_code, uid, server_id=None):
    # ... (code is unchanged) ...

def check_bigo_native_api(uid):
    # ... (code is unchanged) ...

def check_enjoygm_api(game_path, uid, server_id=None):
    # ... (code is unchanged) ...

def check_rmtgameshop_api(game_code, uid, server_id=None):
    # ... (code is unchanged) ...

def check_spacegaming_api(game_id, uid):
    # ... (code is unchanged) ...

def check_netease_api(game_path, server_id, role_id):
    # ... (code is unchanged) ...

def check_razer_api(game_path, uid, server_id):
    url = f"{RAZER_BASE_URL}/{game_path}/users/{uid}"
    params = {"serverId": server_id}
    # THE FIX IS HERE: Create a copy of the base headers and add the specific Referer
    current_headers = RAZER_HEADERS.copy()
    current_headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{game_path.split('/')[-1]}"
    
    logging.info(f"Sending Razer API: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("username"):
            return {"status": "success", "username": data["username"].strip()}
        else:
            return {"status": "error", "message": data.get("message", "Invalid ID or Server.")}
    except Exception: return {"status": "error", "message": "API Error (Razer)"}

def check_nuverse_api(aid, role_id):
    # ... (code is unchanged) ...

def check_rom_xd_api(role_id):
    # ... (code is unchanged) ...


# --- Flask Routes ---
@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": "User ID is required."}), 400
    
    handlers = {
        "pubg-mobile": lambda: check_enjoygm_api("pubg", uid),
        "genshin-impact": lambda: check_enjoygm_api("genshin-impact", uid, server_id),
        "honkai-star-rail": lambda: check_enjoygm_api("honkai", uid, server_id),
        "zenless-zone-zero": lambda: check_enjoygm_api("zenless-zone-zero", uid, server_id),
        "arena-breakout": lambda: check_spacegaming_api("arena_breakout", uid),
        "bloodstrike": lambda: check_smile_one_api("bloodstrike", uid),
        "love-and-deepspace": lambda: check_smile_one_api("loveanddeepspace", uid, server_id),
        "ragnarok-m-classic": lambda: check_rom_xd_api(uid),
        "honor-of-kings": lambda: check_rmtgameshop_api("HOK", uid),
        "magic-chess-go-go": lambda: check_rmtgameshop_api("MCGG", uid, server_id),
        "bigo-live": lambda: check_bigo_native_api(uid),
        "mobile-legends": lambda: perform_ml_check(uid, server_id),
        "mobile-legends-sg": lambda: perform_ml_check(uid, server_id),
        "identity-v": lambda: check_netease_api("identityv", {"Asia": "2001", "NA-EU": "2011"}.get(server_id), uid),
        "marvel-rivals": lambda: check_netease_api("marvelrivals", "11001", uid),
        "ragnarok-x-next-generation": lambda: check_nuverse_api("3402", uid),
        "snowbreak-containment-zone": lambda: check_razer_api("seasun-games-snowbreak-containment-zone", uid, server_id)
    }
    
    handler = handlers.get(game_slug)
    if handler:
        result = handler()
    else:
        result = {"status": "error", "message": f"Validation not configured for: {game_slug}"}
    
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code

@app.route('/sitemap.xml')
def generate_sitemap():
    try:
        response = supabase.from_('games').select('slug').eq('is_active', True).execute()
        games = response.data
        static_pages = ['/', '/about.html', '/contact.html', '/reviews.html', '/past-transactions.html', '/faq.html', '/login.html', '/signup.html']
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for page in static_pages: xml_parts.append(f'  <url><loc>{BASE_URL}{page}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
        for game in games:
            if game.get('slug'): xml_parts.append(f'  <url><loc>{BASE_URL}/topup.html?game={game["slug"]}</loc><changefreq>monthly</changefreq><priority>0.9</priority></url>')
        xml_parts.append('</urlset>')
        return Response("\n".join(xml_parts), mimetype='application/xml')
    except Exception as e: return jsonify({"error": "Could not generate sitemap"}), 500

@app.route('/create-paynow-qr', methods=['POST'])
def create_paynow_qr():
    data = request.get_json()
    if not data or 'amount' not in data or 'order_id' not in data: return jsonify({'error': 'Amount and order_id are required.'}), 400
    try:
        amount = f"{float(data['amount']):.2f}"; order_id = str(data['order_id'])
        paynow_uen = os.environ.get('PAYNOW_UEN'); company_name = os.environ.get('PAYNOW_COMPANY_NAME')
        if not paynow_uen or not company_name: raise ValueError("PAYNOW_UEN and PAYNOW_COMPANY_NAME must be set.")
        maybank_url = "https://sslsecure.maybank.com.sg/scripts/mbb_qrcode/mbb_qrcode.jsp"
        expiry_date = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
        params = {'proxyValue': paynow_uen, 'proxyType': 'UEN', 'merchantName': company_name, 'amount': amount, 'reference': order_id, 'amountInd': 'N', 'expiryDate': expiry_date, 'rnd': random.random()}
        headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': 'https://sslsecure.maybank.com.sg/'}
        response = requests.get(maybank_url, params=params, headers=headers, timeout=20, verify=True)
        response.raise_for_status()
        if 'image/png' in response.headers.get('Content-Type', ''):
            encoded_string = base64.b64encode(response.content).decode('utf-8')
            qr_code_data_uri = f"data:image/png;base64,{encoded_string}"
            return jsonify({'qr_code_data': qr_code_data_uri, 'message': 'QR code generated successfully.'})
        return jsonify({'error': 'Invalid response from QR service.'}), 502
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
