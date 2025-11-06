# app.py (Updated with Garena Delta Force Validation)

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
import pytz
from flask import Flask, jsonify, request, Response, g
from flask_cors import CORS, cross_origin
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode
import random

# Import your new modules
from error_handler import error_handler, log_execution_time, AppError, ValidationError, ExternalAPIError, PaymentError
from redis_cache import cached, invalidate_cache
from i18n import i18n, gettext

app = Flask(__name__)

# --- Configuration ---
app.config['JSON_AS_ASCII'] = False

allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://coxx.netlify.app"
]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

port = int(os.environ.get("PORT", 10000))

# --- Service Initialization ---
try:
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("CRITICAL: Supabase credentials must be set as environment variables.")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception as e:
    logging.critical(f"Could not initialize Supabase client: {e}")
    exit()

BASE_URL = "https://www.gameuniverse.co"

# --- API Headers and Constants ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one", "X-Requested-With": "XMLHttpRequest", "Cookie": os.environ.get("SMILE_ONE_COOKIE")
}
BIGO_NATIVE_VALIDATE_URL = "https://mobile.bigo.tv/pay-bigolive-tv/quicklyPay/getUserDetail"
BIGO_NATIVE_HEADERS = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15", "Accept": "*/*", "Origin": "https://www.gamebar.gg", "Referer": "https://www.gamebar.gg/" }
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
RAZER_RO_ORIGIN_VALIDATE_URL = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users"
RAZER_RO_ORIGIN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin"
}
GAMINGNP_VALIDATE_URL = "https://gaming.com.np/ajaxCheckId"
GAMINGNP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://gaming.com.np",
    "X-Requested-With": "XMLHttpRequest"
}
# NEW: Garena API Constants
GARENA_VALIDATE_URL = "https://shop.garena.sg/api/auth/player_id_login"
GARENA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://shop.garena.sg",
    "Referer": "https://shop.garena.sg/"
}


# --- Flask Hooks ---
@app.before_request
def before_request():
    g.language = i18n.get_user_language()
    g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())


# --- Business Logic / Helper Functions ---
@cached(key_pattern="game_servers::ragnarok_origin", expire_seconds=86400) # Cache for 1 day
def get_ro_origin_servers():
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

@log_execution_time("perform_ml_check")
def perform_ml_check(user_id, zone_id):
    try:
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

@log_execution_time("check_smile_one_api")
def check_smile_one_api(game_code, uid, server_id=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike",
        "loveanddeepspace": "https://www.smile.one/merchant/loveanddeepspace/checkrole/",
        "magicchessgogo": "https://www.smile.one/br/merchant/game/checkrole?product=magicchessgogo"
    }
    pids = {"mobilelegends": "25", "bloodstrike": "20294"}
    
    if game_code not in endpoints: 
        raise ValidationError(gettext("game_not_configured", game=game_code))
    
    pid_to_use = pids.get(game_code)
    sid_to_use = server_id
    params = {"checkrole": "1"}
    
    if game_code == "loveanddeepspace":
        pid_to_use = "18762"
        server_sid_map = {"Asia": "81", "America": "82", "Europe": "83"}
        sid_to_use = server_sid_map.get(str(server_id))
        if not sid_to_use: 
            raise ValidationError(gettext("invalid_server"))
        params.update({"uid": uid, "pid": pid_to_use, "sid": sid_to_use})
    elif game_code == "mobilelegends":
        if not pid_to_use: 
            raise ValidationError(gettext("invalid_server"))
        params.update({"user_id": uid, "zone_id": server_id, "pid": pid_to_use})
    elif game_code == "bloodstrike":
        if not pid_to_use: 
            raise ValidationError(gettext("invalid_server"))
        params.update({"uid": uid, "sid": "-1", "pid": pid_to_use})
    elif game_code == "magicchessgogo":
        params.update({"uid": uid, "sid": server_id})
    else:
        params.update({"uid": uid, "sid": sid_to_use, "pid": pid_to_use})
    
    try:
        response = requests.post(endpoints[game_code], data=params, headers=SMILE_ONE_HEADERS, timeout=10, verify=certifi.where())
        data = {}
        if "text/html" in response.headers.get('content-type', ''):
            try:
                json_text = response.text
                start = json_text.find('{')
                end = json_text.rfind('}') + 1
                if start != -1 and end != -1: data = json.loads(json_text[start:end])
                else: raise ValueError("No JSON object found in HTML response")
            except (json.JSONDecodeError, ValueError):
                raise ExternalAPIError(gettext("api_format_error"), "SmileOne")
        else:
            data = response.json()
        
        if data.get("code") == 200:
            username = data.get("username") or data.get("nickname")
            if username: return {"status": "success", "username": username.strip()}
        
        error_message = data.get("message", data.get("info", gettext("invalid_id")))
        if "não existe" in str(error_message): error_message = gettext("invalid_user_id")
        raise ValidationError(error_message)
        
    except requests.exceptions.RequestException as e:
        logging.error(f"SmileOne API exception for {game_code}: {e}")
        raise ExternalAPIError(gettext("api_error", service=game_code), "SmileOne")

@log_execution_time("check_bigo_native_api")
def check_bigo_native_api(uid):
    params = {"isFromApp": "0", "bigoId": uid}
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params=params, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("result") == 0 and data.get("data", {}).get("nick_name"):
            return {"status": "success", "username": data["data"]["nick_name"].strip()}
        raise ValidationError(data.get("errorMsg", gettext("invalid_bigo_id")))
    except requests.exceptions.RequestException as e:
        logging.error(f"Bigo API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="Bigo"), "Bigo")

@log_execution_time("check_gamingnp_api")
def check_gamingnp_api(game_code, uid):
    game_params = {
        "hok": {"categoryId": "3898", "referer": "https://gaming.com.np/topup/honor-of-kings"},
        "pubgm": {"categoryId": "3920", "referer": "https://gaming.com.np/topup/pubg-mobile-global"}
    }
    if game_code not in game_params:
        raise ValidationError(gettext("game_not_configured", game=game_code))
    
    payload = { "userid": uid, "game": game_code, "categoryId": game_params[game_code]["categoryId"] }
    headers = GAMINGNP_HEADERS.copy()
    headers["Referer"] = game_params[game_code]["referer"]
    
    try:
        response = requests.post(GAMINGNP_VALIDATE_URL, data=payload, headers=headers, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("success") and data.get("detail", {}).get("valid") == "valid":
            username = data["detail"].get("name")
            if username: return {"status": "success", "username": username.strip()}
        raise ValidationError(gettext("invalid_player_id"))
    except requests.exceptions.RequestException as e:
        logging.error(f"Gaming.com.np API Error for {game_code}: {e}")
        raise ExternalAPIError(gettext("api_error", service="Gaming.com.np"), "Gaming.com.np")

@log_execution_time("check_spacegaming_api")
def check_spacegaming_api(game_id, uid):
    payload = {"username": uid, "game_id": game_id}
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json=payload, headers=SPACEGAMING_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("status") == "true" and data.get("message"):
            return {"status": "success", "username": data["message"].strip()}
        raise ValidationError(gettext("invalid_player_id"))
    except requests.exceptions.RequestException as e:
        logging.error(f"SpaceGaming API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="SpaceGaming"), "SpaceGaming")

@log_execution_time("check_netease_api")
def check_netease_api(game_path, server_id, role_id):
    if not server_id:
        raise ValidationError(gettext("server_required"))
    params = { "deviceid": "156032181698579111", "traceid": str(uuid.uuid4()), "timestamp": int(time.time() * 1000), "gc_client_version": "1.11.4", "roleid": role_id, "client_type": "gameclub" }
    current_headers = NETEASE_HEADERS.copy()
    current_headers['X-TASK-ID'] = f"transid={params['traceid']},uni_transaction_id=default"
    try:
        response = requests.get(f"{NETEASE_BASE_URL}/{game_path}/{server_id}/login-role", params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == "0000":
            username = data.get("data", {}).get("rolename")
            if username: return {"status": "success", "username": username.strip()}
        raise ValidationError(gettext("invalid_id_or_server"))
    except requests.exceptions.RequestException as e:
        logging.error(f"Netease API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="Netease"), "Netease")

@log_execution_time("check_razer_hoyoverse_api")
def check_razer_hoyoverse_api(api_path, referer_slug, server_id_map, uid, server_name):
    razer_server_id = server_id_map.get(server_name)
    if not razer_server_id:
        raise ValidationError(gettext("invalid_server"))
    
    url = f"{RAZER_BASE_URL}/{api_path}/users/{uid}"
    params = {"serverId": razer_server_id}
    current_headers = RAZER_HEADERS.copy()
    current_headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{referer_slug}"
    
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("username"):
            return {"status": "success", "username": data["username"].strip()}
        raise ValidationError(data.get("message", gettext("invalid_id_or_server")))
    except requests.exceptions.RequestException as e:
        logging.error(f"Razer Hoyoverse API Error for {api_path}: {e}")
        raise ExternalAPIError(gettext("api_error", service="Razer"), "Razer")

@log_execution_time("check_razer_api")
def check_razer_api(game_path, uid, server_id):
    if not server_id:
        raise ValidationError(gettext("server_required"))
    params = {"serverId": server_id}
    current_headers = RAZER_HEADERS.copy()
    current_headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{game_path.split('/')[-1]}"
    try:
        response = requests.get(f"{RAZER_BASE_URL}/{game_path}/users/{uid}", params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("username"):
            return {"status": "success", "username": data["username"].strip()}
        raise ValidationError(data.get("message", gettext("invalid_id_or_server")))
    except requests.exceptions.RequestException as e:
        logging.error(f"Razer API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="Razer"), "Razer")

@log_execution_time("check_nuverse_api")
def check_nuverse_api(aid, role_id):
    params = {"tab": "purchase", "aid": aid, "role_id": role_id}
    try:
        response = requests.get(NUVERSE_VALIDATE_URL, params=params, headers=NUVERSE_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == 0 and data.get("message", "").lower() == "success":
            role_info = data.get("data", [{}])[0]
            username = role_info.get("role_name")
            server_name = role_info.get("server_name")
            if username and server_name: return {"status": "success", "username": f"{username} ({server_name})"}
        raise ValidationError(gettext("invalid_player_id"))
    except requests.exceptions.RequestException as e:
        logging.error(f"Nuverse API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="Nuverse"), "Nuverse")

@log_execution_time("check_rom_xd_api")
def check_rom_xd_api(role_id):
    params = {"source": "webpay", "appId": "2079001", "serverId": "50001", "roleId": role_id}
    try:
        response = requests.get(ROM_XD_VALIDATE_URL, params=params, headers=ROM_XD_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("code") == 200:
            username = data.get("data", {}).get("name")
            if username: return {"status": "success", "username": username.strip()}
        raise ValidationError(data.get("msg", gettext("invalid_player_id")))
    except requests.exceptions.RequestException as e:
        logging.error(f"ROM XD API exception: {e}")
        raise ExternalAPIError(gettext("api_error", service="ROM XD"), "ROM XD")
        
@log_execution_time("check_ro_origin_razer_api")
def check_ro_origin_razer_api(uid, server_id):
    if not server_id:
        raise ValidationError(gettext("server_required"))
    url = f"{RAZER_RO_ORIGIN_VALIDATE_URL}/{uid}"
    params = {"serverId": server_id}
    try:
        response = requests.get(url, params=params, headers=RAZER_RO_ORIGIN_HEADERS, timeout=10, verify=certifi.where())
        if response.status_code == 200:
            data = response.json()
            if data.get("roles") and isinstance(data["roles"], list):
                transformed_roles = [{"roleId": r.get("CharacterId"), "roleName": r.get("Name")} for r in data["roles"]]
                return {"status": "success", "roles": transformed_roles}
        raise ValidationError(gettext("invalid_code_or_server"))
    except requests.exceptions.RequestException as e:
        logging.error(f"Razer RO Origin API Error: {e}")
        raise ExternalAPIError(gettext("api_error", service="Ragnarok Origin"), "Razer")

# NEW: Garena Delta Force validation function
@log_execution_time("check_garena_api")
def check_garena_api(app_id, uid):
    payload = {
        "app_id": app_id,
        "login_id": uid
    }
    try:
        response = requests.post(GARENA_VALIDATE_URL, json=payload, headers=GARENA_HEADERS, timeout=10)
        response.raise_for_status() # Will raise an exception for 4xx/5xx status codes
        data = response.json()
        
        # Garena's API is a bit inconsistent. Sometimes it's 'nickname', sometimes 'username'.
        username = data.get("nickname") or data.get("username")
        
        if username:
            return {"status": "success", "username": username.strip()}
        else:
            # Check for a specific error message if available
            error_msg = data.get("error_msg", gettext("invalid_player_id"))
            raise ValidationError(error_msg)
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Garena API exception for app_id {app_id}: {e}")
        raise ExternalAPIError(gettext("api_error", service="Garena"), "Garena")


# --- API Routes ---

@app.route('/')
def home():
    return gettext("welcome_message")

@app.route('/health')
@error_handler
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.1" # Incremented version
    }), 200

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@cross_origin(origins=allowed_origins, supports_credentials=True)
@error_handler
def check_game_id(game_slug, uid, server_id):
    if not uid: 
        raise ValidationError(gettext("user_id_required"))
    
    if game_slug == "ragnarok-origin":
        result = check_ro_origin_razer_api(uid, server_id)
        return jsonify(result), 200
    
    genshin_servers = {"Asia": "os_asia", "America": "os_usa", "Europe": "os_euro", "TW,HK,MO": "os_cht"}
    hsr_servers = {"Asia": "prod_official_asia", "America": "prod_official_usa", "Europe": "prod_official_eur", "TW/HK/MO": "prod_official_cht"}
    zzz_servers = {"Asia": "prod_gf_jp", "America": "prod_gf_us", "Europe": "prod_gf_eu", "TW/HK/MO": "prod_gf_sg"}
    snowbreak_servers = {"Asia": "225", "SEA": "215", "Americas": "235", "Europe": "245"}
    
    handlers = {
        "pubg-mobile": lambda: check_gamingnp_api("pubgm", uid),
        "genshin-impact": lambda: check_razer_hoyoverse_api("genshinimpact", "genshin-impact", genshin_servers, uid, server_id),
        "honkai-star-rail": lambda: check_razer_hoyoverse_api("mihoyo-honkai-star-rail", "hsr", hsr_servers, uid, server_id),
        "zenless-zone-zero": lambda: check_razer_hoyoverse_api("cognosphere-zenless-zone-zero", "zenless-zone-zero", zzz_servers, uid, server_id),
        "arena-breakout": lambda: check_spacegaming_api("arena_breakout", uid),
        "blood-strike": lambda: check_smile_one_api("bloodstrike", uid),
        "love-and-deepspace": lambda: check_smile_one_api("loveanddeepspace", uid, server_id),
        "ragnarok-m-classic": lambda: check_rom_xd_api(uid),
        "honor-of-kings": lambda: check_gamingnp_api("hok", uid),
        "magic-chess-go-go": lambda: check_smile_one_api("magicchessgogo", uid, server_id),
        "bigo-live": lambda: check_bigo_native_api(uid),
        "mobile-legends": lambda: perform_ml_check(uid, server_id),
        "identity-v": lambda: check_netease_api("identityv", {"Asia": "2001", "NA-EU": "2011"}.get(server_id), uid),
        "marvel-rivals": lambda: check_netease_api("marvelrivals", "11001", uid),
        "ragnarok-x-next-generation": lambda: check_nuverse_api("3402", uid),
        "snowbreak-containment-zone": lambda: check_razer_api("seasun-games-snowbreak-containment-zone", uid, snowbreak_servers.get(server_id)),
        # NEW: Added handler for Delta Force
        "delta-force": lambda: check_garena_api("100151", uid),
    }
    
    handler = handlers.get(game_slug)
    if not handler:
        raise ValidationError(gettext("validation_not_configured", game=game_slug))
    
    result = handler()
    if result.get("status") == "success" and "roles" in result and len(result["roles"]) == 1:
        result["username"] = result["roles"][0].get("roleName")
        del result["roles"]
    
    return jsonify(result), 200

@app.route('/ro-origin/get-servers', methods=['GET'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
@error_handler
def handle_ro_origin_get_servers():
    result = get_ro_origin_servers()
    return jsonify(result), 200

@app.route('/create-paynow-qr', methods=['POST'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
@error_handler
@log_execution_time("create_paynow_qr")
def create_paynow_qr():
    data = request.get_json()
    if not data or 'amount' not in data or 'order_id' not in data:
        raise ValidationError(gettext("amount_order_id_required"))
    
    try:
        expiry_minutes = 15
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = supabase.table('settings').select('value').eq('key', 'qr_code_expiry_minutes').single().execute()
                if response.data and response.data.get('value'):
                    expiry_minutes = int(response.data['value'])
                break 
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} to fetch expiry setting failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    logging.error(f"Could not fetch expiry setting after {max_retries} attempts, using default. Error: {e}")

        paynow_uen = os.environ.get('PAYNOW_UEN')
        if not paynow_uen:
            raise PaymentError(gettext("paynow_uen_not_configured"))

        amount = f"{float(data['amount']):.2f}"
        order_id = str(data['order_id'])
        
        sgt_timezone = pytz.timezone('Asia/Singapore')
        expiry_time_sgt = datetime.now(sgt_timezone) + timedelta(minutes=expiry_minutes)
        expiry_timestamp = int(expiry_time_sgt.timestamp() * 1000)

        maybank_url = "https://sslsecure.maybank.com.sg/scripts/mbb_qrcode/mbb_qrcode.jsp"
        numeric_ref = str(int(order_id.replace('-', '')[:15], 16))[-8:]

        params = { 'proxyValue': paynow_uen, 'proxyType': 'UEN', 'merchantName': 'NA', 'amount': amount, 'reference': numeric_ref, 'amountInd': 'N', 'expiryDate': '', 'rnd': random.random() }
        headers = { 'User-Agent': 'Mozilla/5.0...', 'Referer': 'https://sslsecure.maybank.com.sg/...' }
        
        response = requests.get(maybank_url, params=params, headers=headers, timeout=20, verify=True)
        response.raise_for_status()

        if 'image/png' in response.headers.get('Content-Type', ''):
            encoded_string = base64.b64encode(response.content).decode('utf-8')
            qr_code_data_uri = f"data:image/png;base64,{encoded_string}"
            return jsonify({
                'qr_code_data': qr_code_data_uri, 
                'expiry_timestamp': expiry_timestamp,
                'reference_id': numeric_ref,
                'message': gettext("qr_generated_successfully")
            })
        
        raise ExternalAPIError(gettext("invalid_qr_service_response"), "MaybankQR")
        
    except requests.exceptions.RequestException as e:
        raise ExternalAPIError(gettext("qr_service_connection_error"), "MaybankQR")
    except Exception as e:
        raise PaymentError(str(e) or gettext("qr_generation_error"))


# --- Main Execution ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
