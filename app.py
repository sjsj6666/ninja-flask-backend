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
import hmac
import hashlib
import jwt
import concurrent.futures
from functools import wraps
from flask import Flask, jsonify, request, g, Response, send_file, stream_with_context
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, quote_plus
import random
import pandas as pd
import io
from i18n import i18n, gettext as _
from gamepoint_service import GamePointService
from error_handler import error_handler, log_execution_time
from redis_cache import cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email_service import send_order_update

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[os.environ.get("RATELIMIT_DEFAULT", "60 per minute")],
    storage_uri="memory://"
)

allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', "http://127.0.1:5173,http://localhost:5173,https://www.gameuniverse.co")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
BACKEND_URL = os.environ.get('RENDER_EXTERNAL_URL')
PROXY_URL = os.environ.get('PROXY_URL')

PROXY_DICT = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY, BACKEND_URL]):
    raise ValueError("CRITICAL: Supabase credentials and BACKEND_URL must be set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

PRICE_CHECK_TOLERANCE = 0.05

BASE_URL = "https://www.gameuniverse.co"
SMILE_ONE_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://www.smile.one", "Cookie": os.environ.get("SMILE_ONE_COOKIE") }
BIGO_NATIVE_VALIDATE_URL = "https://mobile.bigo.tv/pay-bigolive-tv/quicklyPay/getUserDetail"
BIGO_NATIVE_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "*/*", "Origin": "https://www.gamebar.gg", "Referer": "https://www.gamebar.gg/" }
SPACEGAMING_VALIDATE_URL = "https://spacegaming.sg/wp-json/endpoint/validate_v2"
SPACEGAMING_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "*/*", "Content-Type": "application/json", "Origin": "https://spacegaming.sg", "Referer": "https://spacegaming.sg/" }
NETEASE_BASE_URL = "https://pay.neteasegames.com/gameclub"
NETEASE_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
RAZER_BASE_URL = "https://gold.razer.com/api/ext/custom"
RAZER_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
NUVERSE_VALIDATE_URL = "https://pay.nvsgames.com/web/payment/validate"
NUVERSE_HEADERS = {"User-Agent": "Mozilla/5.0"}
ROM_XD_VALIDATE_URL = "https://xdsdk-intnl-6.xd.com/product/v1/query/game/role"
ROM_XD_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://webpay.xd.com", "Referer": "https://webpay.xd.com/" }
RAZER_RO_ORIGIN_VALIDATE_URL = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users"
RAZER_RO_ORIGIN_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin" }
GAMINGNP_VALIDATE_URL = "https://gaming.com.np/ajaxCheckId"
GAMINGNP_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://gaming.com.np", "X-Requested-With": "XMLHttpRequest" }
GARENA_LOGIN_URL = "https://shop.garena.sg/api/auth/player_id_login"
GARENA_ROLES_URL = "https://shop.garena.sg/api/shop/apps/roles"
GARENA_HEADERS = { 'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0' }

@app.before_request
def before_request():
    g.language = i18n.get_user_language()

@cache.cached("exchange_rate_myr_sgd", expire_seconds=3600)
def get_myr_to_sgd_rate():
    try:
        rate_setting = supabase.table('settings').select('value').eq('key', 'myr_sgd_rate').single().execute()
        if rate_setting.data and rate_setting.data.get('value'):
            return float(rate_setting.data['value'])
    except Exception:
        pass
    logging.warning("MYR_SGD_RATE not found in settings. Using default 0.31 for price check.")
    return 0.31

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"status": "error", "message": "Missing Authorization Header"}), 401
        try:
            token = auth_header.split(" ")[1]
            user = supabase.auth.get_user(token)
            user_id = user.user.id
            profile = supabase.table('profiles').select('role').eq('id', user_id).single().execute()
            if profile.data and profile.data['role'] in ['admin', 'owner']:
                return f(*args, **kwargs)
            else:
                return jsonify({"status": "error", "message": "Unauthorized"}), 403
        except Exception:
            return jsonify({"status": "error", "message": "Invalid Token"}), 401
    return decorated_function

def get_settings_from_db(keys):
    try:
        response = supabase.table('settings').select('key, value').in_('key', keys).execute()
        return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        logging.error(f"Error fetching settings: {e}")
        return {}

def get_hitpay_config():
    settings = get_settings_from_db(['hitpay_mode', 'hitpay_api_key_sandbox', 'hitpay_salt_sandbox', 'hitpay_api_key_live', 'hitpay_salt_live'])
    mode = settings.get('hitpay_mode', 'sandbox')
    if mode == 'live':
        return {'url': 'https://api.hit-pay.com/v1/payment-requests', 'key': settings.get('hitpay_api_key_live'), 'salt': settings.get('hitpay_salt_live')}
    else:
        return {'url': 'https://api.sandbox.hit-pay.com/v1/payment-requests', 'key': settings.get('hitpay_api_key_sandbox'), 'salt': settings.get('hitpay_salt_sandbox')}

def perform_ml_check(user_id, zone_id):
    try:
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7, proxies=None)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("result", {}).get("nickname"):
                return {'status': 'success', 'username': data["result"]["nickname"], 'region': 'N/A'}
    except Exception:
        pass
    return check_smile_one_api("mobilelegends", user_id, zone_id)

def check_smile_one_api(game_code, uid, server_id=None):
    endpoints = { "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike", "loveanddeepspace": "https://www.smile.one/merchant/loveanddeepspace/checkrole/", "magicchessgogo": "https://www.smile.one/br/merchant/game/checkrole?product=magicchessgogo" }
    pids = {"mobilelegends": "25", "bloodstrike": "20294"}
    target_endpoint = endpoints.get(game_code)
    if not target_endpoint:
        target_endpoint = f"https://www.smile.one/merchant/{game_code}/checkrole"
    pid_to_use = pids.get(game_code, "0")
    params = {"checkrole": "1"}
    if game_code == "loveanddeepspace":
        server_sid_map = {"Asia": "81", "America": "82", "Europe": "83"}
        sid = server_sid_map.get(str(server_id))
        if not sid: return {"status": "error", "message": "Invalid Server"}
        params.update({"uid": uid, "pid": "18762", "sid": sid})
    elif game_code == "mobilelegends":
        params.update({"user_id": uid, "zone_id": server_id, "pid": pid_to_use})
    elif game_code == "bloodstrike":
        params.update({"uid": uid, "sid": "-1", "pid": pid_to_use})
    elif game_code == "magicchessgogo":
        params.update({"uid": uid, "sid": server_id})
    else:
        params.update({"uid": uid, "sid": server_id, "pid": pid_to_use})
    try:
        response = requests.post(target_endpoint, data=params, headers=SMILE_ONE_HEADERS, timeout=10, verify=certifi.where(), proxies=None)
        if "text/html" in response.headers.get('content-type', ''):
             return {"status": "error", "message": "API Format Error"}
        data = response.json()
        if data.get("code") == 200:
            username = data.get("username") or data.get("nickname")
            if username: return {"status": "success", "username": username.strip()}
        return {"status": "error", "message": data.get("message", "Invalid ID")}
    except Exception:
        return {"status": "error", "message": "API Error"}

def check_bigo_native_api(uid):
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params={"isFromApp": "0", "bigoId": uid}, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where(), proxies=None)
        data = response.json()
        if data.get("result") == 0: return {"status": "success", "username": data.get("data", {}).get("nick_name")}
        return {"status": "error", "message": "Invalid Bigo ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_gamingnp_api(game_code, uid):
    params = { "hok": {"id": "3898", "url": "https://gaming.com.np/topup/honor-of-kings"}, "pubgm": {"id": "3920", "url": "https://gaming.com.np/topup/pubg-mobile-global"} }
    target_id = "0"
    target_url = "https://gaming.com.np"
    if game_code in params:
        target_id = params[game_code]["id"]
        target_url = params[game_code]["url"]
    headers = GAMINGNP_HEADERS.copy()
    headers["Referer"] = target_url
    try:
        response = requests.post(GAMINGNP_VALIDATE_URL, data={"userid": uid, "game": game_code, "categoryId": target_id}, headers=headers, timeout=10, proxies=PROXY_DICT)
        data = response.json()
        if data.get("success") and data.get("detail", {}).get("valid") == "valid":
            return {"status": "success", "username": data["detail"].get("name")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_spacegaming_api(game_id, uid):
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json={"username": uid, "game_id": game_id}, headers=SPACEGAMING_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("status") == "true": return {"status": "success", "username": data.get("message").strip()}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_netease_api(game_path, server_id, role_id):
    try:
        params = {"deviceid": str(uuid.uuid4()), "traceid": str(uuid.uuid4()), "timestamp": int(time.time()*1000), "roleid": role_id, "client_type": "gameclub"}
        headers = NETEASE_HEADERS.copy()
        headers["Referer"] = f"https://pay.neteasegames.com/{game_path}/topup"
        url = f"{NETEASE_BASE_URL}/{game_path}/{server_id}/login-role"
        response = requests.get(url, params=params, headers=headers, timeout=10, proxies=PROXY_DICT)
        data = response.json()
        if data.get("code") == "0000": 
            return {"status": "success", "username": data.get("data", {}).get("rolename")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_razer_hoyoverse_api(api_path, referer, server_map, uid, server_name):
    sid = server_map.get(server_name)
    if not sid: return {"status": "error", "message": "Invalid Server"}
    url = f"https://gold.razer.com/api/ext/{api_path}/users/{uid}" if api_path == "genshinimpact" else f"{RAZER_BASE_URL}/{api_path}/users/{uid}"
    headers = RAZER_HEADERS.copy()
    headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{referer}"
    try:
        response = requests.get(url, params={"serverId": sid}, headers=headers, timeout=10, proxies=None)
        data = response.json()
        if response.status_code == 200 and data.get("username"): return {"status": "success", "username": data.get("username")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_razer_api(game_path, uid, server_id):
    headers = RAZER_HEADERS.copy()
    headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{game_path.split('/')[-1]}"
    try:
        response = requests.get(f"{RAZER_BASE_URL}/{game_path}/users/{uid}", params={"serverId": server_id}, headers=headers, timeout=10, proxies=None)
        data = response.json()
        if response.status_code == 200 and data.get("username"): return {"status": "success", "username": data.get("username")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_nuverse_api(aid, role_id):
    try:
        response = requests.get(NUVERSE_VALIDATE_URL, params={"tab": "purchase", "aid": aid, "role_id": role_id}, headers=NUVERSE_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("code") == 0:
            info = data.get("data", [{}])[0]
            return {"status": "success", "username": f"{info.get('role_name')} ({info.get('server_name')})"}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_rom_xd_api(role_id):
    try:
        response = requests.get(ROM_XD_VALIDATE_URL, params={"source": "webpay", "appId": "2079001", "serverId": "50001", "roleId": role_id}, headers=ROM_XD_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("code") == 200: return {"status": "success", "username": data.get("data", {}).get("name")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_ro_origin_razer_api(uid, server_id):
    try:
        response = requests.get(f"{RAZER_RO_ORIGIN_VALIDATE_URL}/{uid}", params={"serverId": server_id}, headers=RAZER_RO_ORIGIN_HEADERS, timeout=10, proxies=None)
        if response.status_code == 200:
            data = response.json()
            if data.get("roles"):
                return {"status": "success", "roles": [{"roleId": r.get("CharacterId"), "roleName": r.get("Name")} for r in data["roles"]]}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def get_ro_origin_servers():
    return {"status": "success", "servers": [
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
    ]}

def check_garena_api(app_id, uid):
    with requests.Session() as s:
        s.headers.update(GARENA_HEADERS)
        try:
            s.headers["Referer"] = f"https://shop.garena.sg/?app={app_id}"
            login = s.post(GARENA_LOGIN_URL, json={"app_id": int(app_id), "login_id": uid}, timeout=10)
            if login.status_code != 200: return {"status": "error", "message": "Invalid ID"}
            roles = s.get(GARENA_ROLES_URL, params={'app_id': app_id, 'region': 'SG', 'language': 'en', 'source': 'pc'}, timeout=10)
            data = roles.json().get(str(app_id), [])
            if data: return {"status": "success", "username": data[0].get("role")}
            return {"status": "error", "message": "No player found"}
        except Exception: return {"status": "error", "message": "API Error"}

genshin_servers = {"Asia": "os_asia", "America": "os_usa", "Europe": "os_euro", "TW,HK,MO": "os_cht"}
hsr_servers = {"Asia": "prod_official_asia", "America": "prod_official_usa", "Europe": "prod_official_eur", "TW/HK/MO": "prod_official_cht"}
zzz_servers = {"Asia": "prod_gf_jp", "America": "prod_gf_us", "Europe": "prod_gf_eu", "TW/HK/MO": "prod_gf_sg"}
snowbreak_servers = {"Asia": "225", "SEA": "215", "Americas": "235", "Europe": "245"}

VALIDATION_HANDLERS = {
    "universal_mlbb": lambda uid, sid, cfg: perform_ml_check(uid, sid),
    "universal_netease": lambda uid, sid, cfg: check_netease_api(cfg.get('target_id'), sid, uid),
    "universal_smile_one": lambda uid, sid, cfg: check_smile_one_api(cfg.get('target_id'), uid, sid),
    "universal_gamingnp": lambda uid, sid, cfg: check_gamingnp_api(cfg.get('target_id'), uid),
    "universal_spacegaming": lambda uid, sid, cfg: check_spacegaming_api(cfg.get('target_id'), uid),
    "universal_razer": lambda uid, sid, cfg: check_razer_api(cfg.get('target_id'), uid, sid),
    "pubgm_global": lambda uid, sid, cfg: check_gamingnp_api("pubgm", uid),
    "genshin_impact": lambda uid, sid, cfg: check_razer_hoyoverse_api("genshinimpact", "genshin-impact", genshin_servers, uid, sid),
    "honkai_star_rail": lambda uid, sid, cfg: check_razer_hoyoverse_api("mihoyo-honkai-star-rail", "hsr", hsr_servers, uid, sid),
    "zenless_zone_zero": lambda uid, sid, cfg: check_razer_hoyoverse_api("cognosphere-zenless-zone-zero", "zenless-zone-zero", zzz_servers, uid, sid),
    "arena_breakout": lambda uid, sid, cfg: check_spacegaming_api("arena_breakout", uid),
    "blood_strike": lambda uid, sid, cfg: check_smile_one_api("bloodstrike", uid),
    "love_and_deepspace": lambda uid, sid, cfg: check_smile_one_api("loveanddeepspace", uid, sid),
    "ragnarok_m_classic": lambda uid, sid, cfg: check_rom_xd_api(uid),
    "ragnarok_origin": lambda uid, sid, cfg: check_ro_origin_razer_api(uid, sid),
    "honor_of_kings": lambda uid, sid, cfg: check_gamingnp_api("hok", uid),
    "magic_chess_gogo": lambda uid, sid, cfg: check_smile_one_api("magicchessgogo", uid, sid),
    "bigo_live": lambda uid, sid, cfg: check_bigo_native_api(uid),
    "mobile_legends_global": lambda uid, sid, cfg: perform_ml_check(uid, sid),
    "mobile_legends_brazil": lambda uid, sid, cfg: perform_ml_check(uid, sid),
    "identity_v": lambda uid, sid, cfg: check_netease_api("identityv", {"Asia": "2001", "NA-EU": "2011"}.get(sid), uid),
    "marvel_rivals": lambda uid, sid, cfg: check_netease_api("marvelrivals", "11001", uid),
    "ragnarok_x_next_gen": lambda uid, sid, cfg: check_nuverse_api("3402", uid),
    "snowbreak": lambda uid, sid, cfg: check_razer_api("seasun-games-snowbreak-containment-zone", uid, snowbreak_servers.get(sid)),
    "delta_force": lambda uid, sid, cfg: check_garena_api("100151", uid),
    "ace_racer": lambda uid, sid, cfg: check_netease_api("aceracer", sid, uid),
}

@app.route('/')
def home():
    return _("welcome_message")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/admin/gamepoint/catalog', methods=['GET'])
@admin_required
@error_handler
def admin_get_gp_catalog():
    cached_catalog = cache.get("admin_gp_full_catalog")
    if cached_catalog:
        return jsonify(cached_catalog)
    gp = GamePointService(supabase_client=supabase)
    token = gp.get_token()
    try:
        list_resp = gp._request("product/list", {"token": token})
        products = list_resp.get('detail', [])
    except Exception as e:
        logging.error(f"Failed to fetch product list: {e}")
        return jsonify([])
    full_catalog = []
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=Retry(total=3, backoff_factor=0.5))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({'Content-Type': 'application/json', 'partnerid': gp.partner_id, 'User-Agent': 'GameVault/1.0'})
    proxies = gp.proxies
    base_url = gp.base_url
    secret_key = gp.secret_key
    def fetch_detail_optimized(product):
        try:
            payload = {"token": token, "productid": product['id'], "timestamp": int(time.time())}
            encoded_payload = jwt.encode(payload, secret_key, algorithm='HS256')
            body = json.dumps({"payload": encoded_payload})
            resp = session.post(f"{base_url}/product/detail", data=body, proxies=proxies, timeout=15, verify=certifi.where())
            detail_data = resp.json()
            if detail_data.get('code') == 200:
                product['packages'] = detail_data.get('package', [])
                product['fields'] = detail_data.get('fields', [])
                product['server'] = detail_data.get('server', [])
                return product
        except Exception as e:
            logging.error(f"Error fetching product {product['id']}: {e}")
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(fetch_detail_optimized, p): p for p in products}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                full_catalog.append(result)
    cache.set("admin_gp_full_catalog", full_catalog, expire_seconds=3600)
    return jsonify(full_catalog)

@app.route('/api/admin/gamepoint/list', methods=['GET'])
@admin_required
@error_handler
def admin_get_gp_game_list():
    gp = GamePointService(supabase_client=supabase)
    token = gp.get_token()
    list_resp = gp._request("product/list", {"token": token})
    products = list_resp.get('detail', [])
    return jsonify(products)

@app.route('/api/admin/gamepoint/detail/<int:product_id>', methods=['GET'])
@admin_required
@error_handler
def admin_get_gp_game_detail(product_id):
    gp = GamePointService(supabase_client=supabase)
    token = gp.get_token()
    detail_resp = gp._request("product/detail", {"token": token, "productid": product_id})
    if detail_resp.get('code') == 200:
        return jsonify(detail_resp.get('package', []))
    return jsonify([])

@app.route('/api/admin/gamepoint/download-csv', methods=['GET'])
@admin_required
def admin_download_gp_csv():
    try:
        gp = GamePointService(supabase_client=supabase)
        token = gp.get_token()
        list_resp = gp._request("product/list", {"token": token})
        products = list_resp.get('detail', [])
        if not products:
            return jsonify({"status": "error", "message": "No products found"}), 404
        def fetch_detail_safe(product):
            try:
                detail_resp = gp._request("product/detail", {"token": token, "productid": product['id']})
                if detail_resp.get('code') == 200:
                    return { "parent": product, "packages": detail_resp.get('package', []) }
            except Exception as e:
                logging.error(f"Error fetching product {product['id']}: {e}")
            return None
        def generate_csv():
            yield u'\ufeff' 
            yield "Product ID,Product Name,Package ID,Package Name,Cost Price\n"
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(fetch_detail_safe, p): p for p in products}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        p = result['parent']
                        p_name = p['name'].replace(',', ' ')
                        for pkg in result['packages']:
                            row = [str(p['id']), p_name, str(pkg['id']), pkg['name'].replace(',', ' '), str(pkg['price'])]
                            yield ",".join(row) + "\n"
        return Response(stream_with_context(generate_csv()), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=gamepoint_catalog_{gp.config['mode']}.csv", "Cache-Control": "no-cache"})
    except Exception as e:
        logging.error(f"CSV Download Failed: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/gamepoint/config', methods=['GET', 'POST'])
@admin_required
@error_handler
def admin_gamepoint_config():
    if request.method == 'POST':
        data = request.get_json()
        updates = []
        allowed_keys = ['gamepoint_mode', 'gamepoint_partner_id_sandbox', 'gamepoint_secret_key_sandbox', 'gamepoint_partner_id_live', 'gamepoint_secret_key_live', 'gamepoint_proxy_url']
        for key, val in data.items():
            if key in allowed_keys:
                updates.append({'key': key, 'value': val})
        if updates:
            supabase.table('settings').upsert(updates, on_conflict='key').execute()
            from redis_cache import cache
            cache.delete(f"gamepoint_token_{data.get('gamepoint_mode', 'sandbox')}")
        return jsonify({"status": "success", "message": "Settings updated"})
    response = supabase.table('settings').select('key,value').ilike('key', 'gamepoint%').execute()
    settings = {item['key']: item['value'] for item in response.data}
    for k in ['gamepoint_secret_key_live', 'gamepoint_secret_key_sandbox', 'gamepoint_proxy_url']:
        if settings.get(k): settings[k] = "********"
    return jsonify({"status": "success", "data": settings})

@app.route('/admin/gamepoint/balance', methods=['GET'])
@admin_required
@error_handler
def admin_gamepoint_balance():
    gp = GamePointService(supabase_client=supabase)
    balance = gp.check_balance()
    return jsonify({"status": "success", "mode": gp.config['mode'], "balance": balance})

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@limiter.limit("10/minute")
@error_handler
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": _("user_id_required")}), 400
    if game_slug == "ragnarok-origin":
        result = check_ro_origin_razer_api(uid, server_id)
        status_code = 200 if result.get("status") == "success" else 400
        return jsonify(result), status_code
    try:
        game_res = supabase.table('games').select('api_handler, supplier, supplier_pid, validation_param, requires_user_id').eq('game_key', game_slug).single().execute()
        if game_res.data:
            game_data = game_res.data
            if game_data.get('requires_user_id') == False:
                return jsonify({"status": "success", "username": "Voucher/GiftCard", "roles": []})
            api_handler_key = game_data.get('api_handler')
            if api_handler_key and api_handler_key in VALIDATION_HANDLERS:
                handler_func = VALIDATION_HANDLERS[api_handler_key]
                target_id = game_data.get('validation_param') or game_data.get('supplier_pid')
                config_for_handler = {'target_id': target_id}
                result = handler_func(uid, server_id, config_for_handler)
                if result.get("status") == "success" and "roles" in result and len(result["roles"]) == 1:
                    result["username"] = result["roles"][0].get("roleName")
                    del result["roles"]
                return jsonify(result), 200 if result.get("status") == "success" else 400
            if game_data.get('supplier') == 'gamepoint':
                gp = GamePointService(supabase_client=supabase)
                inputs = {"input1": uid}
                if server_id: inputs["input2"] = server_id
                supplier_pid = game_data.get('supplier_pid') 
                if not supplier_pid: return jsonify({"status": "error", "message": "Game config missing supplier PID"}), 500
                resp = gp.validate_id(supplier_pid, inputs)
                if resp.get('code') == 200:
                    return jsonify({"status": "success", "username": "Validated User", "roles": [], "validation_token": resp.get('validation_token')})
                else:
                    return jsonify({"status": "error", "message": resp.get('message', 'Invalid ID')}), 400
    except Exception as e:
        logging.error(f"Error checking game ID: {e}")
        return jsonify({"status": "error", "message": "Validation Error"}), 500
    return jsonify({"status": "error", "message": _("validation_not_configured", game=game_slug)}), 400

@app.route('/ro-origin/get-servers', methods=['GET', 'OPTIONS'])
def handle_ro_origin_get_servers():
    return jsonify(get_ro_origin_servers())

@app.route('/ro-origin/get-roles', methods=['POST', 'OPTIONS'])
def handle_ro_origin_get_roles():
    data = request.get_json()
    return jsonify(check_ro_origin_razer_api(data.get('userId'), data.get('serverId')))
    
@app.route('/api/create-payment', methods=['POST'])
@limiter.limit("10/minute")
def create_hitpay_payment():
    data = request.get_json()
    order_id = data.get('order_id')
    redirect_url = data.get('redirect_url')
    email = data.get('email')
    if not order_id or not redirect_url:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400
    try:
        order_res = supabase.table('orders').select('total_amount, status').eq('id', order_id).single().execute()
        order_data = order_res.data
        if not order_data:
            return jsonify({'status': 'error', 'message': 'Order not found'}), 404
        if order_data['status'] in ['completed', 'processing', 'paid']:
             return jsonify({'status': 'error', 'message': 'Order already paid'}), 400
        real_amount = float(order_data['total_amount']) 
if email:
            try:
                supabase.table('orders').update({'email': email}).eq('id', order_id).execute()
            except Exception as email_err:
                # Log the error but don't stop the payment process
                logging.warning(f"Could not save email to order: {email_err}")
    except Exception as e:
        logging.error(f"DB Error fetching order price: {e}")
        return jsonify({'status': 'error', 'message': 'Server Error'}), 500
    config = get_hitpay_config()
    if not config or not config['key']:
        return jsonify({'status': 'error', 'message': 'Payment gateway not configured.'}), 500
    try:
        webhook_url = f"{BACKEND_URL}/api/webhook-handler"
        payload = {
            'amount': real_amount, 'currency': 'SGD', 'reference_number': order_id,
            'redirect_url': redirect_url, 'webhook': webhook_url, 'purpose': data.get('product_name', 'GameVault Order'),
            'channel': 'api_custom', 'email': email or 'customer@example.com', 'name': data.get('name', 'GameVault Customer')
        }
        headers = {'X-BUSINESS-API-KEY': config['key'], 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        response = requests.post(config['url'], headers=headers, json=payload, timeout=15, proxies=None)
        response_data = response.json()
        if response.status_code == 201:
            return jsonify({'status': 'success', 'payment_url': response_data['url']})
        else:
            return jsonify({'status': 'error', 'message': response_data.get('message', 'Failed to create payment')}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/webhook-handler', methods=['POST'])
@cross_origin()
def hitpay_webhook_handler():
    try:
        raw_body = request.get_data()
        form_data = request.form.to_dict()
        hitpay_signature = request.headers.get('X-Business-Signature')
        config = get_hitpay_config()
        if config and config['salt']:
            generated_signature = hmac.new(key=bytes(config['salt'], 'utf-8'), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
            if hitpay_signature and generated_signature != hitpay_signature:
                logging.warning(f"Signature Mismatch!")
        status = form_data.get('status')
        order_id = form_data.get('reference_number')
        payment_id = form_data.get('payment_id')
        if order_id:
            if status == 'completed':
                try:
                    result = supabase.table('orders').update({'status': 'processing', 'payment_id': payment_id}).eq('id', order_id).in_('status', ['pending', 'verifying']).execute()
                    if not result.data or len(result.data) == 0:
                        logging.info(f"Duplicate Webhook or Invalid Order: Order {order_id} already processed.")
                        return Response(status=200)
                except Exception as e:
                    logging.error(f"Error locking order {order_id}: {e}")
                    return Response(status=500)
                order_data = supabase.table('orders').select('*, order_items(*, products(*, games(*)))').eq('id', order_id).single().execute()
                order = order_data.data
                if order and order.get('order_items'):
                    product = order['order_items'][0]['products']
                    game = product.get('games', {})
                    product_name = product.get('name')
                    game_name = game.get('name', 'GameVault Product')
                    customer_email = order.get('email') or form_data.get('customer_email')
                    customer_name = order.get('remitter_name') or form_data.get('customer_name')
                    gp_api = GamePointService(supabase_client=supabase)
                    supplier_config = product.get('supplier_config')
                    if supplier_config:
                        all_success, failed_items, supplier_refs = True, [], []
                        # Check if game requires ID
                        inputs = {}
                        if game.get('requires_user_id') != False:
                            inputs["input1"] = order.get('game_uid')
                            if order.get('server_region'): inputs["input2"] = order.get('server_region')
                        else:
                            inputs["input1"] = "GIFT_CARD"
                        for item in supplier_config:
                            gp_pack_id = item.get('packageId')
                            try:
                                live_cost_myr_str = cache.get(f"gp_price:{gp_pack_id}")
                                if live_cost_myr_str:
                                    live_cost_myr, db_cost_sgd = float(live_cost_myr_str), float(product.get('original_price'))
                                    exchange_rate = get_myr_to_sgd_rate()
                                    if exchange_rate == 0: raise ValueError("Exchange rate cannot be zero.")
                                    db_cost_in_myr = db_cost_sgd / exchange_rate
                                    if live_cost_myr > db_cost_in_myr * (1 + PRICE_CHECK_TOLERANCE):
                                        logging.warning(f"PRICE MISMATCH DETECTED for Order {order_id}, Package {gp_pack_id}. DB Cost (MYR): {db_cost_in_myr:.2f}, Live Cost (MYR): {live_cost_myr:.2f}")
                                        all_success, _ = False, failed_items.append(f"{item.get('name')} (Price Mismatch)")
                                        continue
                            except Exception as price_check_error:
                                logging.error(f"Price check failed for Order {order_id}, Package {gp_pack_id}: {price_check_error}")
                                all_success, _ = False, failed_items.append(f"{item.get('name')} (Price Check Error)")
                                continue
                            try:
                                val_resp = gp_api.validate_id(item.get('gameId'), inputs)
                                val_token = val_resp.get('validation_token')
                                if val_token:
                                    merchant_ref = f"{order_id[:8]}-{int(time.time())}-{random.randint(100,999)}"
                                    create_resp = gp_api.create_order(gp_pack_id, val_token, merchant_ref)
                                    if create_resp.get('code') in [100, 101]:
                                        supplier_refs.append(create_resp.get('referenceno'))
                                    else:
                                        all_success, _ = False, failed_items.append(f"{item.get('name')} (Err: {create_resp.get('message')})")
                                else:
                                    all_success, _ = False, failed_items.append(f"{item.get('name')} (Validation Failed)")
                            except Exception as e:
                                all_success, _ = False, failed_items.append(f"{item.get('name')} (Exception: {str(e)})")
                        if all_success:
                            supabase.table('orders').update({'status': 'completed', 'supplier_ref': ', '.join(supplier_refs)}).eq('id', order_id).execute()
                            updated_order = {**order, 'status': 'completed'}
                            send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
                        else:
                            supabase.table('orders').update({'status': 'manual_review', 'notes': f"Partial/Full Failure: {'; '.join(failed_items)}", 'supplier_ref': ', '.join(supplier_refs)}).eq('id', order_id).execute()
                            updated_order = {**order, 'status': 'manual_review'}
                            send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
                    else:
                        gp_prod_id, gp_pack_id = product.get('gamepoint_product_id'), product.get('gamepoint_package_id')
                        if gp_prod_id and gp_pack_id:
                            try:
                                inputs = {}
                                if game.get('requires_user_id') != False:
                                    inputs["input1"] = order.get('game_uid')
                                    if order.get('server_region'): inputs["input2"] = order.get('server_region')
                                else:
                                    inputs["input1"] = "GIFT_CARD"
                                val_resp = gp_api.validate_id(gp_prod_id, inputs)
                                val_token = val_resp.get('validation_token')
                                if val_token:
                                    merchant_ref = f"{order_id[:8]}-{int(time.time())}"
                                    create_resp = gp_api.create_order(gp_pack_id, val_token, merchant_ref)
                                    if create_resp.get('code') in [100, 101]:
                                        supabase.table('orders').update({'status': 'completed', 'supplier_ref': create_resp.get('referenceno')}).eq('id', order_id).execute()
                                        updated_order = {**order, 'status': 'completed'}
                                        send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
                                    else:
                                        error_msg = create_resp.get('message', 'Unknown Supplier Error')
                                        supabase.table('orders').update({'status': 'manual_review', 'notes': f"Supplier Failed: {error_msg}"}).eq('id', order_id).execute()
                                        updated_order = {**order, 'status': 'manual_review'}
                                        send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
                                else:
                                    supabase.table('orders').update({'status': 'manual_review'}).eq('id', order_id).execute()
                                    updated_order = {**order, 'status': 'manual_review'}
                                    send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
                            except Exception as e:
                                logging.error(f"GamePoint Fulfillment Failed: {e}")
                                supabase.table('orders').update({'status': 'manual_review'}).eq('id', order_id).execute()
                                updated_order = {**order, 'status': 'manual_review'}
                                send_order_update(updated_order, product_name, game_name, customer_email, customer_name)
            elif status == 'failed':
                supabase.table('orders').update({'status': 'failed', 'updated_at': datetime.utcnow().isoformat()}).eq('id', order_id).execute()
                order_data = supabase.table('orders').select('*, order_items(*, products(*, games(*)))').eq('id', order_id).single().execute()
                order = order_data.data
                if order:
                    product = order['order_items'][0]['products']
                    game = product.get('games', {})
                    product_name = product.get('name')
                    game_name = game.get('name', 'GameVault Product')
                    customer_email = order.get('email') or form_data.get('customer_email')
                    customer_name = order.get('remitter_name') or form_data.get('customer_name')
                    send_order_update(order, product_name, game_name, customer_email, customer_name)
        return Response(status=200)
    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return Response(status=200)

@app.route('/api/callbacks/gamepoint', methods=['POST'])
@cross_origin()
def gamepoint_callback():
    try:
        data = request.form.to_dict() if request.form else request.get_json()
        logging.info(f"Received GamePoint Callback: {data}")
        merchant_code = data.get('merchantcode')
        status_code = str(data.get('code'))
        pin1 = data.get('pin1')
        pin2 = data.get('pin2')
        message = data.get('message')
        if not merchant_code:
            return jsonify({"status": "error", "message": "Missing merchantcode"}), 400
        order_res = supabase.table('orders').select('*').ilike('supplier_ref', f"%{merchant_code}%").execute()
        if not order_res.data:
            possible_id = merchant_code.split('-')[0]
            order_res = supabase.table('orders').select('*').ilike('id', f"{possible_id}%").execute()
        if not order_res.data:
            logging.error(f"Callback received for unknown order: {merchant_code}")
            return jsonify({"status": "error", "message": "Order not found"}), 404
        order = order_res.data[0]
        order_id = order['id']
        if status_code == '100': 
            voucher_data = {"pin1": pin1, "pin2": pin2, "message": message}
            supabase.table('orders').update({'status': 'completed', 'voucher_codes': voucher_data, 'updated_at': datetime.utcnow().isoformat()}).eq('id', order_id).execute()
            logging.info(f"Order {order_id} updated with Voucher Codes.")
        elif status_code in ['101', '102']:
            logging.info(f"Order {order_id} is still pending.")
        else:
            logging.warning(f"Order {order_id} failed via Callback. Code: {status_code}")
            supabase.table('orders').update({'status': 'manual_review', 'notes': f"Callback Failure: {message}"}).eq('id', order_id).execute()
        return jsonify({"code": 200, "message": "Callback received"}), 200
    except Exception as e:
        logging.error(f"Callback processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
