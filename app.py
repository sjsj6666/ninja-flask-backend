import os
import logging
import time
import uuid
import json
import base64
import requests
import certifi
import pycountry
import hashlib
from flask import Flask, jsonify, request, Response
from flask_cors import CORS, cross_origin
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
RO_ORIGIN_ONEONE_BASE_URL = "https://games.oneone.com/games/ro-global/api"
RO_ORIGIN_ONEONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://games.oneone.com",
    "Referer": "https://games.oneone.com/games/ragnarok-origin-global"
}


# --- Helper Functions for ID Validation ---

def perform_ml_check(user_id, zone_id):
    try:
        logging.info(f"Attempting primary ML API for user: {user_id}")
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("result", {}).get("nickname"):
                nickname = data["result"]["nickname"]
                country_code = "N/A"
                try:
                    country = pycountry.countries.get(name=data["result"].get("country"))
                    if country: country_code = country.alpha_2
                except Exception: pass
                return {'status': 'success', 'username': nickname, 'region': country_code}
        logging.warning("Primary ML API failed. Proceeding to fallback.")
    except Exception:
        logging.error("Primary ML API exception. Proceeding to fallback.")
    fallback_result = check_smile_one_api("mobilelegends", user_id, zone_id)
    if fallback_result.get("status") == "success": fallback_result['region'] = 'N/A'
    return fallback_result

def check_smile_one_api(game_code, uid, server_id=None):
    endpoints = { "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/"}
    pids = {"mobilelegends": "25", "bloodstrike": "20295"}
    if game_code not in endpoints: return {"status": "error", "message": f"Game not configured: {game_code}"}
    
    pid_to_use = pids.get(game_code)
    if game_code == "loveanddeepspace":
        server_pid_map = {"America": "18760", "Asia": "18762", "Europe": "18762"}
        pid_to_use = server_pid_map.get(str(server_id))
    if not pid_to_use: return {"status": "error", "message": "Invalid server for this game."}
        
    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code == "bloodstrike": params.update({"uid": uid, "sid": "-1"})
    else: params.update({"uid": uid, "sid": server_id})
    
    logging.info(f"Sending SmileOne API: Game='{game_code}', Params={params}")
    try:
        response = requests.post(endpoints[game_code], data=params, headers=SMILE_ONE_HEADERS, timeout=10, verify=certifi.where())
        if "nickname" in response.text and "text/html" in response.headers.get('content-type', ''):
            try:
                start_idx = response.text.find('{"nickname":"') + len('{"nickname":"')
                end_idx = response.text.find('"', start_idx)
                return {"status": "success", "username": response.text[start_idx:end_idx]}
            except Exception: pass
        data = response.json()
        if data.get("code") == 200:
            username = data.get("username") or data.get("nickname")
            if username: return {"status": "success", "username": username.strip()}
        error_message = data.get("message", data.get("info", "Invalid ID."))
        if "não existe" in error_message: error_message = "Invalid User ID."
        return {"status": "error", "message": error_message}
    except Exception: return {"status": "error", "message": "API Error (SmileOne)"}

def check_bigo_native_api(uid):
    params = {"isFromApp": "0", "bigoId": uid}
    logging.info(f"Sending Bigo API: Params={params}")
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params=params, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("result") == 0 and data.get("data", {}).get("nick_name"):
            return {"status": "success", "username": data["data"]["nick_name"].strip()}
        return {"status": "error", "message": data.get("errorMsg", "Invalid Bigo ID.")}
    except Exception: return {"status": "error", "message": "API Error (Bigo)"}

def check_enjoygm_api(game_path, uid, server_id=None):
    params = {"account": uid}
    if server_id: params["serverid"] = server_id
    logging.info(f"Sending EnjoyGM API: Game='{game_path}', Params={params}")
    try:
        response = requests.get(f"{ENJOYGM_BASE_URL}/{game_path}/userinfo", params=params, headers=ENJOYGM_HEADERS, timeout=10, verify=certifi.where())
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
    if server_id: payload["server"] = server_id
    logging.info(f"Sending RMTGameShop API: Payload={json.dumps(payload)}")
    try:
        response = requests.post(RMTGAMESHOP_VALIDATE_URL, json=payload, headers=RMTGAMESHOP_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if not data.get("error") and data.get("code") == 200:
            nickname = data.get("data", {}).get("nickname")
            if nickname: return {"status": "success", "username": nickname.strip()}
        return {"status": "error", "message": data.get("message", "Invalid Player ID.")}
    except Exception: return {"status": "error", "message": f"API Error ({game_code})"}

def check_spacegaming_api(game_id, uid):
    payload = {"username": uid, "game_id": game_id}
    logging.info(f"Sending SpaceGaming API: Payload={json.dumps(payload)}")
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json=payload, headers=SPACEGAMING_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("status") == "true" and data.get("message"):
            return {"status": "success", "username": data["message"].strip()}
        return {"status": "error", "message": "Invalid Player ID."}
    except Exception: return {"status": "error", "message": f"API Error ({game_id})"}

def check_netease_api(game_path, server_id, role_id):
    params = { "deviceid": "156032181698579111", "traceid": str(uuid.uuid4()), "timestamp": int(time.time() * 1000), "gc_client_version": "1.11.4", "roleid": role_id, "client_type": "gameclub" }
    current_headers = NETEASE_HEADERS.copy()
    current_headers['X-TASK-ID'] = f"transid={params['traceid']},uni_transaction_id=default"
    logging.info(f"Sending Netease API: Game='{game_path}', Params={params}")
    try:
        response = requests.get(f"{NETEASE_BASE_URL}/{game_path}/{server_id}/login-role", params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == "0000":
            username = data.get("data", {}).get("rolename")
            if username: return {"status": "success", "username": username.strip()}
        return {"status": "error", "message": "Invalid ID or Server."}
    except Exception: return {"status": "error", "message": "API Error (Netease)"}

def check_razer_api(game_path, uid, server_id):
    params = {"serverId": server_id}
    current_headers = RAZER_HEADERS.copy()
    current_headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{game_path.split('/')[-1]}"
    logging.info(f"Sending Razer API: Game='{game_path}', Params={params}")
    try:
        response = requests.get(f"{RAZER_BASE_URL}/{game_path}/users/{uid}", params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("username"):
            return {"status": "success", "username": data["username"].strip()}
        else:
            return {"status": "error", "message": data.get("message", "Invalid ID or Server.")}
    except Exception: return {"status": "error", "message": "API Error (Razer)"}

def check_nuverse_api(aid, role_id):
    params = {"tab": "purchase", "aid": aid, "role_id": role_id}
    logging.info(f"Sending Nuverse API: Params={params}")
    try:
        response = requests.get(NUVERSE_VALIDATE_URL, params=params, headers=NUVERSE_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == 0 and data.get("message", "").lower() == "success":
            role_info = data.get("data", [{}])[0]
            username = role_info.get("role_name")
            server_name = role_info.get("server_name")
            if username and server_name: return {"status": "success", "username": f"{username} ({server_name})"}
        return {"status": "error", "message": "Invalid Player ID."}
    except Exception: return {"status": "error", "message": "API Error (Nuverse)"}

def check_rom_xd_api(role_id):
    params = {"source": "webpay", "appId": "2079001", "serverId": "50001", "roleId": role_id}
    logging.info(f"Sending ROM XD API: Params={params}")
    try:
        response = requests.get(ROM_XD_VALIDATE_URL, params=params, headers=ROM_XD_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == 200:
            username = data.get("data", {}).get("name")
            if username: return {"status": "success", "username": username.strip()}
        return {"status": "error", "message": data.get("msg", "Invalid Player ID.")}
    except Exception: return {"status": "error", "message": "API Error (ROM)"}

def get_ro_origin_oneone_servers():
    logging.info("Returning hardcoded RO Origin server list.")
    servers_list = [
        {"server_id": 1, "server_name": "Prontera-(1~3)/Izlude-9(-10)/Morroc-(1~10)"},
        {"server_id": 4, "server_name": "Prontera-(4~6)/Prontera-10/Izlude-(1~8)"},
        {"server_id": 7, "server_name": "Prontera-(7~9)/Geffen-(1~10)/Payon-(1~10)"},
        {"server_id": 51, "server_name": "Poring Island-(1~10)/Orc Village-(1~10)/Shipwreck-(1~9)/Memoria/Awakening/Ant Hell-(1~10)/Goblin Forest-1(-2-4)/Valentine"},
        {"server_id": 95, "server_name": "Lasagna/1st-Anniversary/Goblin Forest-7/For Honor/Sakura Vows/Goblin Forest-10/Garden-1"},
        {"server_id": 102, "server_name": "1.5th Anniversary/Vicland"},
        {"server_id": 104, "server_name": "2025"},
        {"server_id": 105, "server_name": "Timeless Love"},
        {"server_id": 106, "server_name": "2nd Anniversary"},
        {"server_id": 107, "server_name": "Hugel"}
    ]
    return {"status": "success", "servers": servers_list}

# *** MODIFIED FUNCTION TO HANDLE CSRF TOKEN ***
def get_ro_origin_oneone_roles(uid, server_id):
    url = f"{RO_ORIGIN_ONEONE_BASE_URL}/getRoles"
    payload = {"userId": uid, "serverId": server_id}
    logging.info(f"Sending RO Origin Get Roles API (oneone): URL='{url}', Payload={json.dumps(payload)}")
    
    try:
        # Use a session to persist cookies
        with requests.Session() as s:
            # First, visit the main page to get the necessary session cookies
            s.get("https://games.oneone.com/games/ragnarok-origin-global", headers=RO_ORIGIN_ONEONE_HEADERS, timeout=10)
            
            # Now, make the POST request. The session will automatically include the cookies.
            # We need to find the X-CSRF-TOKEN from the cookies.
            xsrf_token = s.cookies.get('XSRF-TOKEN')
            if not xsrf_token:
                # If the cookie isn't found, we might need a fallback or to raise an error
                logging.error("Could not retrieve XSRF-TOKEN cookie.")
                return {"status": "error", "message": "Could not initiate session."}
            
            # Add the CSRF token to the headers for the POST request
            post_headers = RO_ORIGIN_ONEONE_HEADERS.copy()
            post_headers['X-CSRF-TOKEN'] = requests.utils.unquote(xsrf_token)

            response = s.post(url, json=payload, headers=post_headers, timeout=10, verify=certifi.where())
            
            # Check for a successful response
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return {"status": "success", "roles": data}
                # Check if the response contains the CSRF error message
                elif 'message' in data and 'CSRF token mismatch' in data['message']:
                     return {"status": "error", "message": "CSRF token mismatch."}
                else:
                    return {"status": "error", "message": data.get("message", "Could not fetch roles.")}
            else:
                # Handle non-200 responses
                logging.error(f"RO Origin API returned status {response.status_code}: {response.text}")
                return {"status": "error", "message": "API returned an error status."}
            
    except Exception as e:
        logging.error(f"Exception in get_ro_origin_oneone_roles: {e}")
        return {"status": "error", "message": "API Error"}


# --- Flask Routes ---
@app.route('/')
def home():
    return "NinjaTopUp API Backend is Live!"

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@cross_origin(origins=allowed_origins, supports_credentials=True)
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

@app.route('/ro-origin/get-servers', methods=['POST', 'OPTIONS'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def handle_ro_origin_get_servers():
    result = get_ro_origin_oneone_servers()
    return jsonify(result), 200 if result.get("status") == "success" else 400

@app.route('/ro-origin/get-roles', methods=['POST', 'OPTIONS'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def handle_ro_origin_get_roles():
    data = request.get_json()
    uid = data.get('userId')
    server_id = data.get('serverId')
    if not uid or not server_id:
        return jsonify({"status": "error", "message": "Secret Code and Server ID are required."}), 400
    result = get_ro_origin_oneone_roles(uid, server_id)
    return jsonify(result), 200 if result.get("status") == "success" else 400

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
