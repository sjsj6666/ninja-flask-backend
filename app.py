# app.py

import os
import logging
import time
import uuid
import json
import base64
import requests
import certifi
import pycountry
import pytz
from flask import Flask, jsonify, request, g, Response
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode
import random

from i18n import i18n, gettext as _

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[os.environ.get("RATELIMIT_DEFAULT", "20 per minute")],
    storage_uri="memory://"
)

allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', "http://127.0.0.1:5500,http://localhost:5500")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

@app.before_request
def before_request():
    g.language = i18n.get_user_language()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("CRITICAL: Supabase credentials must be set as environment variables.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BASE_URL = "https://www.gameuniverse.co"

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
GARENA_LOGIN_URL = "https://shop.garena.sg/api/auth/player_id_login"
GARENA_ROLES_URL = "https://shop.garena.sg/api/shop/apps/roles"
GARENA_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-SG,en-GB;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://shop.garena.sg',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15',
}

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
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike",
        "loveanddeepspace": "https://www.smile.one/merchant/loveanddeepspace/checkrole/",
        "magicchessgogo": "https://www.smile.one/br/merchant/game/checkrole?product=magicchessgogo"
    }
    pids = {"mobilelegends": "25", "bloodstrike": "20294"}
    if game_code not in endpoints: return {"status": "error", "message": _("game_not_configured", game=game_code)}
    pid_to_use = pids.get(game_code)
    sid_to_use = server_id
    params = {"checkrole": "1"}
    if game_code == "loveanddeepspace":
        pid_to_use = "18762"
        server_sid_map = {"Asia": "81", "America": "82", "Europe": "83"}
        sid_to_use = server_sid_map.get(str(server_id))
        if not sid_to_use: return {"status": "error", "message": _("invalid_server")}
        params.update({"uid": uid, "pid": pid_to_use, "sid": sid_to_use})
    elif game_code == "mobilelegends":
        if not pid_to_use: return {"status": "error", "message": _("invalid_server")}
        params.update({"user_id": uid, "zone_id": server_id, "pid": pid_to_use})
    elif game_code == "bloodstrike":
        if not pid_to_use: return {"status": "error", "message": _("invalid_server")}
        params.update({"uid": uid, "sid": "-1", "pid": pid_to_use})
    elif game_code == "magicchessgogo":
        params.update({"uid": uid, "sid": server_id})
    else:
        params.update({"uid": uid, "sid": sid_to_use, "pid": pid_to_use})
    logging.info(f"Sending SmileOne API: Game='{game_code}', URL='{endpoints[game_code]}', Params={params}")
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
                return {"status": "error", "message": _("api_format_error")}
        else:
            data = response.json()
        if data.get("code") == 200:
            username = data.get("username") or data.get("nickname")
            if username: return {"status": "success", "username": username.strip()}
        error_message = data.get("message", data.get("info", _("invalid_id")))
        if "não existe" in str(error_message): error_message = _("invalid_user_id")
        return {"status": "error", "message": error_message}
    except Exception as e:
        logging.error(f"SmileOne API exception for {game_code}: {e}")
        return {"status": "error", "message": _("api_error", service=game_code)}

def check_bigo_native_api(uid):
    params = {"isFromApp": "0", "bigoId": uid}
    logging.info(f"Sending Bigo API: Params={params}")
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params=params, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("result") == 0 and data.get("data", {}).get("nick_name"):
            return {"status": "success", "username": data["data"]["nick_name"].strip()}
        return {"status": "error", "message": data.get("errorMsg", "Invalid Bigo ID.")}
    except Exception: return {"status": "error", "message": _("api_error", service="Bigo")}

def check_gamingnp_api(game_code, uid):
    game_params = {
        "hok": {"categoryId": "3898", "referer": "https://gaming.com.np/topup/honor-of-kings"},
        "pubgm": {"categoryId": "3920", "referer": "https://gaming.com.np/topup/pubg-mobile-global"}
    }
    if game_code not in game_params:
        return {"status": "error", "message": "Game not configured for this API."}
    payload = { "userid": uid, "game": game_code, "categoryId": game_params[game_code]["categoryId"] }
    headers = GAMINGNP_HEADERS.copy()
    headers["Referer"] = game_params[game_code]["referer"]
    logging.info(f"Sending Gaming.com.np API: Payload={payload}")
    try:
        response = requests.post(GAMINGNP_VALIDATE_URL, data=payload, headers=headers, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("success") and data.get("detail", {}).get("valid") == "valid":
            username = data["detail"].get("name")
            if username: return {"status": "success", "username": username.strip()}
        return {"status": "error", "message": "Invalid Player ID."}
    except Exception as e:
        logging.error(f"Gaming.com.np API Error for {game_code}: {e}")
        return {"status": "error", "message": _("api_error", service=game_code)}

def check_spacegaming_api(game_id, uid):
    payload = {"username": uid, "game_id": game_id}
    logging.info(f"Sending SpaceGaming API: Payload={json.dumps(payload)}")
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json=payload, headers=SPACEGAMING_HEADERS, timeout=10, verify=certifi.where())
        data = response.json()
        if data.get("status") == "true" and data.get("message"):
            return {"status": "success", "username": data["message"].strip()}
        return {"status": "error", "message": "Invalid Player ID."}
    except Exception: return {"status": "error", "message": _("api_error", service=game_id)}

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
    except Exception: return {"status": "error", "message": _("api_error", service="Netease")}

def check_razer_hoyoverse_api(api_path, referer_slug, server_id_map, uid, server_name):
    razer_server_id = server_id_map.get(server_name)
    if not razer_server_id:
        return {"status": "error", "message": _("invalid_server")}
    if api_path == "genshinimpact":
        url = f"https://gold.razer.com/api/ext/{api_path}/users/{uid}"
    else:
        url = f"{RAZER_BASE_URL}/{api_path}/users/{uid}"
    params = {"serverId": razer_server_id}
    current_headers = RAZER_HEADERS.copy()
    current_headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{referer_slug}"
    logging.info(f"Sending Razer Hoyoverse API: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200 and data.get("username"):
            return {"status": "success", "username": data["username"].strip()}
        else:
            message = data.get("message", "Invalid ID or Server.")
            return {"status": "error", "message": message}
    except Exception as e:
        logging.error(f"Razer Hoyoverse API Error for {api_path}: {e}")
        return {"status": "error", "message": "API Error"}

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
    except Exception: return {"status": "error", "message": _("api_error", service="Razer")}

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
    except Exception: return {"status": "error", "message": _("api_error", service="Nuverse")}

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
    except Exception: return {"status": "error", "message": _("api_error", service="ROM")}

def check_ro_origin_razer_api(uid, server_id):
    url = f"{RAZER_RO_ORIGIN_VALIDATE_URL}/{uid}"
    params = {"serverId": server_id}
    logging.info(f"Sending Razer RO Origin API: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=RAZER_RO_ORIGIN_HEADERS, timeout=10, verify=certifi.where())
        if response.status_code == 200:
            data = response.json()
            if data.get("roles") and isinstance(data["roles"], list):
                transformed_roles = []
                for role in data["roles"]:
                    transformed_roles.append({
                        "roleId": role.get("CharacterId"),
                        "roleName": role.get("Name")
                    })
                return {"status": "success", "roles": transformed_roles}
        return {"status": "error", "message": "Invalid Secret Code or no characters on this server."}
    except Exception as e:
        logging.error(f"Razer RO Origin API Error: {e}")
        return {"status": "error", "message": "API Error"}

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
    
def check_garena_api(app_id, uid):
    with requests.Session() as s:
        s.headers.update(GARENA_HEADERS)
        login_payload = {"app_id": int(app_id), "login_id": uid}
        try:
            s.headers["Referer"] = f"https://shop.garena.sg/?app={app_id}"
            login_response = s.post(GARENA_LOGIN_URL, json=login_payload, timeout=10)
            if login_response.status_code != 200:
                logging.warning(f"Garena login failed with status {login_response.status_code}")
                return {"status": "error", "message": "Invalid Player ID."}
            roles_params = {'app_id': app_id, 'region': 'SG', 'language': 'en', 'source': 'pc'}
            roles_response = s.get(GARENA_ROLES_URL, params=roles_params, timeout=10)
            roles_response.raise_for_status()
            roles_data = roles_response.json()
            app_roles = roles_data.get(str(app_id))
            if app_roles and isinstance(app_roles, list) and len(app_roles) > 0:
                username = app_roles[0].get("role")
                if username:
                    return {"status": "success", "username": username.strip()}
            return {"status": "error", "message": "Could not find player name."}
        except requests.exceptions.RequestException as e:
            logging.error(f"Garena API connection exception for app_id {app_id}: {e}")
            return {"status": "error", "message": _("api_error", service="Garena")}

@app.route('/')
def home():
    return _("welcome_message")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@cross_origin(origins=allowed_origins, supports_credentials=True)
@limiter.limit("10/minute")
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": _("user_id_required")}), 400
    if game_slug == "ragnarok-origin":
        result = check_ro_origin_razer_api(uid, server_id)
        status_code = 200 if result.get("status") == "success" else 400
        return jsonify(result), status_code
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
        "mobile-legends-sg": lambda: perform_ml_check(uid, server_id),
        "mobile-legends-my": lambda: perform_ml_check(uid, server_id),
        "identity-v": lambda: check_netease_api("identityv", {"Asia": "2001", "NA-EU": "2011"}.get(server_id), uid),
        "marvel-rivals": lambda: check_netease_api("marvelrivals", "11001", uid),
        "ragnarok-x-next-generation": lambda: check_nuverse_api("3402", uid),
        "snowbreak-containment-zone": lambda: check_razer_api("seasun-games-snowbreak-containment-zone", uid, snowbreak_servers.get(server_id)),
        "delta-force": lambda: check_garena_api("100151", uid),
    }
    handler = handlers.get(game_slug)
    if handler:
        result = handler()
        if result.get("status") == "success" and "roles" in result and len(result["roles"]) == 1:
            result["username"] = result["roles"][0].get("roleName")
            del result["roles"]
    else:
        result = {"status": "error", "message": _("validation_not_configured", game=game_slug)}
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code

@app.route('/ro-origin/get-servers', methods=['GET', 'OPTIONS'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def handle_ro_origin_get_servers():
    result = get_ro_origin_servers()
    return jsonify(result), 200 if result.get("status") == "success" else 400

@app.route('/ro-origin/get-roles', methods=['POST', 'OPTIONS'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def handle_ro_origin_get_roles():
    data = request.get_json()
    uid = data.get('userId')
    server_id = data.get('serverId')
    if not uid or not server_id:
        return jsonify({"status": "error", "message": "Secret Code and Server ID are required."}), 400
    result = check_ro_origin_razer_api(uid, server_id)
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
@cross_origin(origins=allowed_origins, supports_credentials=True)
@limiter.limit("5/minute")
def create_paynow_qr():
    data = request.get_json()
    if not data or 'amount' not in data or 'order_id' not in data:
        return jsonify({'error': _("amount_order_id_required")}), 400
    try:
        # --- CHANGED: Default expiry is now 5 minutes to reduce matching collisions ---
        expiry_minutes = 5
        try:
            response = supabase.table('settings').select('value').eq('key', 'qr_code_expiry_minutes').single().execute()
            if response.data and response.data.get('value'):
                expiry_minutes = int(response.data['value'])
        except Exception as e:
            logging.error(f"Could not fetch expiry setting from Supabase, using default. Error: {e}")

        paynow_uen = os.environ.get('PAYNOW_UEN')
        if not paynow_uen:
            raise ValueError(_("paynow_uen_not_configured"))

        amount = f"{float(data['amount']):.2f}"
        order_id = str(data['order_id'])
        
        sgt_timezone = pytz.timezone('Asia/Singapore')
        now_in_sgt = datetime.now(sgt_timezone)
        expiry_time_sgt = now_in_sgt + timedelta(minutes=expiry_minutes)
        expiry_timestamp = int(expiry_time_sgt.timestamp() * 1000)

        maybank_url = "https://sslsecure.maybank.com.sg/scripts/mbb_qrcode/mbb_qrcode.jsp"
        
        numeric_ref = str(int(order_id.replace('-', '')[:15], 16))[-8:]

        params = {
            'proxyValue': paynow_uen,
            'proxyType': 'UEN',
            'merchantName': 'NA',
            'amount': amount,
            'reference': numeric_ref,
            'amountInd': 'N',
            'expiryDate': '',
            'rnd': random.random()
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15',
            'Referer': 'https://sslsecure.maybank.com.sg/cgi-bin/mbs/scripts/mbb_cas/mbb_cas_qrcodegen_mbs.jsp'
        }
        
        logging.info(f"Requesting Maybank QR with params: {params}")
        response = requests.get(maybank_url, params=params, headers=headers, timeout=20, verify=True)
        response.raise_for_status()

        if 'image/png' in response.headers.get('Content-Type', ''):
            encoded_string = base64.b64encode(response.content).decode('utf-8')
            qr_code_data_uri = f"data:image/png;base64,{encoded_string}"
            return jsonify({
                'qr_code_data': qr_code_data_uri, 
                'expiry_timestamp': expiry_timestamp,
                'reference_id': numeric_ref,
                'message': _("qr_generated_successfully")
            })
        
        logging.error(f"Maybank API returned non-image content. Status: {response.status_code}, Content: {response.text[:200]}")
        return jsonify({'error': _("invalid_qr_service_response")}), 502

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP Request to Maybank failed: {e}")
        return jsonify({"error": _("qr_service_connection_error")}), 504
    except Exception as e:
        logging.error(f"An unexpected error occurred during QR generation: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
