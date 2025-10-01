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
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE")
}
ELITEDIAS_CHECKID_URL = "https://api.elitedias.com/checkid"
ELITEDIAS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01", "Accept-Language": "en-SG,en;q=0.9",
    "Content-Type": "application/json; charset=utf-8", "Origin": "https://elitedias.com",
    "Referer": "https://elitedias.com/", "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site"
}
BIGO_NATIVE_VALIDATE_URL = "https://mobile.bigo.tv/pay-bigolive-tv/quicklyPay/getUserDetail"
BIGO_NATIVE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*", "Origin": "https://www.gamebar.gg", "Referer": "https://www.gamebar.gg/",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "cross-site"
}
ENJOYGM_BASE_URL = "https://www.enjoygm.com/portal/supplier/api"
ENJOYGM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*", "Referer": "https://www.enjoygm.com/", "X-Requested-With": "XMLHttpRequest"
}
RMTGAMESHOP_VALIDATE_URL = "https://rmtgameshop.com/game/checkid"
RMTGAMESHOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*", "Content-Type": "application/json", "Origin": "https://rmtgameshop.com",
    "Referer": "https://rmtgameshop.com/", "X-Auth-Token": "5a9cbf0b303b57f12e3da444f5d42c59"
}


# --- Helper Functions for ID Validation ---

def perform_ml_check(user_id, zone_id):
    try:
        logging.info(f"Attempting primary ML API (caliph.dev) for user: {user_id}")
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success" and response_data.get("result", {}).get("nickname"):
                nickname = response_data["result"]["nickname"]
                country_name = response_data["result"].get("country")
                country_code = "N/A"
                if country_name:
                    try:
                        country = pycountry.countries.get(name=country_name)
                        if country: country_code = country.alpha_2
                    except Exception: pass
                logging.info(f"Primary ML API Success! Nickname: {nickname}, Region: {country_code}")
                return {'status': 'success', 'username': nickname, 'region': country_code}
        logging.warning("Primary ML API failed. Proceeding to fallback.")
    except Exception as e:
        logging.error(f"Primary ML API exception: {e}. Proceeding to fallback.")
    logging.info(f"Attempting fallback ML API (Smile.One) for user: {user_id}")
    fallback_result = check_smile_one_api("mobilelegends", user_id, zone_id)
    if fallback_result.get("status") == "success": fallback_result['region'] = 'N/A'
    return fallback_result

def check_smile_one_api(game_code_for_smileone, uid, server_id=None):
    endpoints = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole"}
    if game_code_for_smileone not in endpoints: return {"status": "error", "message": f"Game '{game_code_for_smileone}' not configured for SmileOne."}
    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends", "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike"}
    current_headers["Referer"] = referer_map.get(game_code_for_smileone)
    default_pids_map = {"mobilelegends": "25", "bloodstrike": "20295"}
    pid_to_use = default_pids_map.get(game_code_for_smileone)
    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code_for_smileone == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone == "bloodstrike": params.update({"uid": uid, "sid": "-1"})
    logging.info(f"Sending SmileOne: Game='{game_code_for_smileone}', URL='{url}', PID='{pid_to_use}', Params={params}")
    try:
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10, verify=certifi.where())
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 200:
            username = data.get("username") or data.get("nickname")
            if username and isinstance(username, str) and username.strip(): return {"status": "success", "username": username.strip()}
            return {"status": "error", "message": "Username not found in API response"}
        error_message = data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))
        if "não existe" in error_message: error_message = "Invalid User ID."
        return {"status": "error", "message": error_message}
    except Exception: return {"status": "error", "message": "API Error (SmileOne)"}

def check_elitedias_api(game_code_for_api, role_id):
    payload = {"game": game_code_for_api, "userid": str(role_id)}
    logging.info(f"Sending EliteDias API: URL='{ELITEDIAS_CHECKID_URL}', Payload='{json.dumps(payload)}'")
    try:
        response = requests.post(ELITEDIAS_CHECKID_URL, json=payload, headers=ELITEDIAS_HEADERS, timeout=12, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("valid") == "valid":
            username = data.get("name") or data.get("username")
            if username and username.lower() != 'na': return {"status": "success", "username": username.strip()}
            return {"status": "success", "message": "Role ID Verified."}
        return {"status": "error", "message": data.get("message", "Invalid Role ID.")}
    except Exception: return {"status": "error", "message": "API Error (EliteDias)"}

def check_bigo_native_api(uid):
    params = {"isFromApp": "0", "bigoId": uid}
    logging.info(f"Sending Bigo Native API: URL='{BIGO_NATIVE_VALIDATE_URL}', Params={params}")
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params=params, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where())
        response.raise_for_status()
        data = response.json()
        if data.get("result") == 0 and data.get("data", {}).get("nick_name"):
            return {"status": "success", "username": data["data"]["nick_name"].strip()}
        return {"status": "error", "message": data.get("errorMsg", "Invalid Bigo ID.")}
    except Exception: return {"status": "error", "message": "API Error (Bigo)"}

def check_enjoygm_api(game_path, uid, server_id=None):
    url = f"{ENJOYGM_BASE_URL}/{game_path}/userinfo"
    params = {"account": uid}
    if server_id: params["serverid"] = server_id
    headers = ENJOYGM_HEADERS.copy()
    headers["Referer"] = f"https://www.enjoygm.com/top-up/{game_path}"
    logging.info(f"Sending EnjoyGM API: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10, verify=certifi.where())
        response.raise_for_status()
        outer_data = response.json()
        if outer_data.get("code") == 200 and outer_data.get("data"):
            inner_data = json.loads(outer_data["data"])
            username = inner_data.get("accountName") or inner_data.get("username")
            if (inner_data.get("exist") == 1 or inner_data.get("username")) and username:
                return {"status": "success", "username": username.strip()}
        return {"status": "error", "message": "Invalid ID or Server."}
    except Exception: return {"status": "error", "message": "API Error (EnjoyGM)"}

def check_rmtgameshop_api(game_code, uid, server_id=None):
    payload = {"game": game_code, "id": uid}
    if server_id:
        payload["server"] = server_id
    logging.info(f"Sending RMTGameShop API: URL='{RMTGAMESHOP_VALIDATE_URL}', Payload={json.dumps(payload)}")
    try:
        response = requests.post(RMTGAMESHOP_VALIDATE_URL, json=payload, headers=RMTGAMESHOP_HEADERS, timeout=10, verify=certifi.where())
        response.raise_for_status()
        data = response.json()
        if not data.get("error") and data.get("code") == 200:
            nickname = data.get("data", {}).get("nickname")
            if nickname:
                return {"status": "success", "username": nickname.strip()}
            else:
                return {"status": "error", "message": "Player found, but name is unavailable."}
        return {"status": "error", "message": data.get("message", "Invalid Player ID.")}
    except Exception as e:
        logging.error(f"RMTGameShop API error for {game_code}: {e}")
        return {"status": "error", "message": f"API Error ({game_code})"}


# --- Flask Routes ---
@app.route('/')
def home(): return "NinjaTopUp API Backend is Live!"

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": "User ID is required."}), 400
    
    enjoygm_map = {
        "pubg-mobile": "pubg", "genshin-impact": "genshin-impact",
        "honkai-star-rail": "honkai", "zenless-zone-zero": "zenless-zone-zero"
    }
    elitedias_map = {"metal-slug-awakening": "metal_slug", "arena-breakout": "arena_breakout"}
    smileone_map = {"bloodstrike": "bloodstrike"}
    rmtgameshop_map = {"honor-of-kings": "HOK", "magic-chess-go-go": "MCGG"}
    
    handler = None
    if game_slug in enjoygm_map:
        handler = lambda: check_enjoygm_api(enjoygm_map[game_slug], uid, server_id)
    elif game_slug in elitedias_map:
        handler = lambda: check_elitedias_api(elitedias_map[game_slug], uid)
    elif game_slug in smileone_map:
        handler = lambda: check_smile_one_api(smileone_map[game_slug], uid)
    elif game_slug in rmtgameshop_map:
        handler = lambda: check_rmtgameshop_api(rmtgameshop_map[game_slug], uid, server_id)
    elif game_slug == "bigo-live":
        handler = lambda: check_bigo_native_api(uid)
    elif "mobile-legends" in game_slug:
        handler = lambda: perform_ml_check(uid, server_id)
        
    if handler:
        result = handler()
    else:
        result = {"status": "error", "message": f"Validation not configured for: {game_slug}"}
    
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code

# Other routes like /sitemap.xml, /create-paynow-qr, etc. remain the same...

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
