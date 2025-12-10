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
from flask import Flask, jsonify, request, g, Response, send_file
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse
import random
import pandas as pd
import io
from i18n import i18n, gettext as _

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[os.environ.get("RATELIMIT_DEFAULT", "60 per minute")],
    storage_uri="memory://"
)

allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', "http://127.0.0.1:5173,http://localhost:5173,https://www.gameuniverse.co")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
BACKEND_URL = os.environ.get('RENDER_EXTERNAL_URL')
PROXY_URL = os.environ.get('PROXY_URL')

PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
} if PROXY_URL else None

if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY, BACKEND_URL]):
    raise ValueError("CRITICAL: Supabase credentials and BACKEND_URL must be set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

@app.before_request
def before_request():
    g.language = i18n.get_user_language()

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
        return {
            'url': 'https://api.hit-pay.com/v1/payment-requests',
            'key': settings.get('hitpay_api_key_live'),
            'salt': settings.get('hitpay_salt_live')
        }
    else:
        return {
            'url': 'https://api.sandbox.hit-pay.com/v1/payment-requests',
            'key': settings.get('hitpay_api_key_sandbox'),
            'salt': settings.get('hitpay_salt_sandbox')
        }

class GamePointAPI:
    def __init__(self):
        settings = get_settings_from_db(['gamepoint_mode', 'gamepoint_partner_id', 'gamepoint_secret_key'])
        self.mode = settings.get('gamepoint_mode', 'sandbox')
        self.partner_id = settings.get('gamepoint_partner_id')
        self.secret_key = settings.get('gamepoint_secret_key')
        
        if self.mode == 'live':
            self.base_url = "https://api.gamepointclub.net"
        else:
            self.base_url = "https://sandbox.gamepointclub.net"
            
        self.headers = {
            'Content-Type': 'application/json',
            'partnerid': self.partner_id
        }

    def _generate_payload(self, data_dict):
        data_dict['timestamp'] = int(time.time())
        token = jwt.encode(data_dict, self.secret_key, algorithm='HS256')
        return json.dumps({"payload": token})

    def _make_request(self, endpoint, payload_data):
        url = f"{self.base_url}/{endpoint}"
        body = self._generate_payload(payload_data)
        try:
            response = requests.post(
                url, 
                data=body, 
                headers=self.headers, 
                proxies=PROXIES, 
                timeout=20,
                verify=certifi.where()
            )
            return response.json()
        except Exception as e:
            logging.error(f"GamePoint Request Error: {e}")
            return None

    def get_token(self):
        resp = self._make_request("merchant/token", {})
        if resp and resp.get('code') == 200:
            return resp.get('token')
        return None

    def get_full_catalog(self):
        token = self.get_token()
        if not token: return []
        
        list_resp = self._make_request("product/list", {"token": token})
        if not list_resp or list_resp.get('code') != 200: return []
        
        products = list_resp.get('detail', [])
        full_catalog = []
        
        for p in products:
            p_id = p['id']
            detail_resp = self._make_request("product/detail", {"token": token, "productid": p_id})
            if detail_resp and detail_resp.get('code') == 200:
                p_data = {
                    "id": p_id,
                    "name": p['name'],
                    "fields": detail_resp.get('fields', []),
                    "packages": detail_resp.get('package', [])
                }
                full_catalog.append(p_data)
        return full_catalog

    def place_order(self, gp_product_id, gp_package_id, user_id, zone_id=None, server_id=None):
        token = self.get_token()
        if not token:
            return {"status": "error", "message": "Failed to authenticate with GamePoint."}

        fields = {"input1": user_id}
        if zone_id:
            fields["input2"] = zone_id
        elif server_id:
            fields["input2"] = server_id

        validate_payload = {
            "token": token,
            "productid": gp_product_id,
            "fields": fields
        }

        val_resp = self._make_request("order/validate", validate_payload)
        
        if not val_resp or val_resp.get('code') != 200:
            return {"status": "error", "message": f"GP Validation Failed: {val_resp.get('message')}"}

        validation_token = val_resp.get('validation_token')
        merchant_ref = f"GV-{int(time.time())}-{random.randint(1000,9999)}"
        
        create_payload = {
            "token": token,
            "packageid": gp_package_id,
            "validate_token": validation_token,
            "merchantcode": merchant_ref
        }

        create_resp = self._make_request("order/create", create_payload)
        code = create_resp.get('code')
        
        if code == 100 or code == 101:
            return {
                "status": "success", 
                "supplier_ref": create_resp.get('referenceno'),
                "message": create_resp.get('message')
            }
        
        return {
            "status": "error", 
            "message": f"GP Order Failed {code}: {create_resp.get('message')}"
        }

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

def perform_ml_check(user_id, zone_id):
    try:
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7, proxies=PROXIES)
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
    if game_code not in endpoints: return {"status": "error", "message": "Game not configured"}
    pid_to_use = pids.get(game_code)
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
        response = requests.post(endpoints[game_code], data=params, headers=SMILE_ONE_HEADERS, timeout=10, verify=certifi.where(), proxies=PROXIES)
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
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params={"isFromApp": "0", "bigoId": uid}, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where(), proxies=PROXIES)
        data = response.json()
        if data.get("result") == 0: return {"status": "success", "username": data.get("data", {}).get("nick_name")}
        return {"status": "error", "message": "Invalid Bigo ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_gamingnp_api(game_code, uid):
    params = { "hok": {"id": "3898", "url": "https://gaming.com.np/topup/honor-of-kings"}, "pubgm": {"id": "3920", "url": "https://gaming.com.np/topup/pubg-mobile-global"} }
    if game_code not in params: return {"status": "error", "message": "Config Error"}
    headers = GAMINGNP_HEADERS.copy()
    headers["Referer"] = params[game_code]["url"]
    try:
        response = requests.post(GAMINGNP_VALIDATE_URL, data={"userid": uid, "game": game_code, "categoryId": params[game_code]["id"]}, headers=headers, timeout=10, proxies=PROXIES)
        data = response.json()
        if data.get("success") and data.get("detail", {}).get("valid") == "valid":
            return {"status": "success", "username": data["detail"].get("name")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_spacegaming_api(game_id, uid):
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json={"username": uid, "game_id": game_id}, headers=SPACEGAMING_HEADERS, timeout=10, proxies=PROXIES)
        data = response.json()
        if data.get("status") == "true": return {"status": "success", "username": data.get("message").strip()}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_netease_api(game_path, server_id, role_id):
    try:
        params = {"deviceid": "1", "traceid": str(uuid.uuid4()), "timestamp": int(time.time()*1000), "roleid": role_id, "client_type": "gameclub"}
        response = requests.get(f"{NETEASE_BASE_URL}/{game_path}/{server_id}/login-role", params=params, headers=NETEASE_HEADERS, timeout=10, proxies=PROXIES)
        data = response.json()
        if data.get("code") == "0000": return {"status": "success", "username": data.get("data", {}).get("rolename")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_razer_hoyoverse_api(api_path, referer, server_map, uid, server_name):
    sid = server_map.get(server_name)
    if not sid: return {"status": "error", "message": "Invalid Server"}
    url = f"https://gold.razer.com/api/ext/{api_path}/users/{uid}" if api_path == "genshinimpact" else f"{RAZER_BASE_URL}/{api_path}/users/{uid}"
    headers = RAZER_HEADERS.copy()
    headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{referer}"
    try:
        response = requests.get(url, params={"serverId": sid}, headers=headers, timeout=10, proxies=PROXIES)
        data = response.json()
        if response.status_code == 200 and data.get("username"): return {"status": "success", "username": data.get("username")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_razer_api(game_path, uid, server_id):
    headers = RAZER_HEADERS.copy()
    headers["Referer"] = f"https://gold.razer.com/my/en/gold/catalog/{game_path.split('/')[-1]}"
    try:
        response = requests.get(f"{RAZER_BASE_URL}/{game_path}/users/{uid}", params={"serverId": server_id}, headers=headers, timeout=10, proxies=PROXIES)
        data = response.json()
        if response.status_code == 200 and data.get("username"): return {"status": "success", "username": data.get("username")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_nuverse_api(aid, role_id):
    try:
        response = requests.get(NUVERSE_VALIDATE_URL, params={"tab": "purchase", "aid": aid, "role_id": role_id}, headers=NUVERSE_HEADERS, timeout=10, proxies=PROXIES)
        data = response.json()
        if data.get("code") == 0:
            info = data.get("data", [{}])[0]
            return {"status": "success", "username": f"{info.get('role_name')} ({info.get('server_name')})"}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_rom_xd_api(role_id):
    try:
        response = requests.get(ROM_XD_VALIDATE_URL, params={"source": "webpay", "appId": "2079001", "serverId": "50001", "roleId": role_id}, headers=ROM_XD_HEADERS, timeout=10, proxies=PROXIES)
        data = response.json()
        if data.get("code") == 200: return {"status": "success", "username": data.get("data", {}).get("name")}
        return {"status": "error", "message": "Invalid ID"}
    except Exception: return {"status": "error", "message": "API Error"}

def check_ro_origin_razer_api(uid, server_id):
    try:
        response = requests.get(f"{RAZER_RO_ORIGIN_VALIDATE_URL}/{uid}", params={"serverId": server_id}, headers=RAZER_RO_ORIGIN_HEADERS, timeout=10, proxies=PROXIES)
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
        if PROXIES: s.proxies.update(PROXIES)
        try:
            s.headers["Referer"] = f"https://shop.garena.sg/?app={app_id}"
            login = s.post(GARENA_LOGIN_URL, json={"app_id": int(app_id), "login_id": uid}, timeout=10)
            if login.status_code != 200: return {"status": "error", "message": "Invalid ID"}
            roles = s.get(GARENA_ROLES_URL, params={'app_id': app_id, 'region': 'SG', 'language': 'en', 'source': 'pc'}, timeout=10)
            data = roles.json().get(str(app_id), [])
            if data: return {"status": "success", "username": data[0].get("role")}
            return {"status": "error", "message": "No player found"}
        except Exception: return {"status": "error", "message": "API Error"}

@app.route('/')
def home():
    return _("welcome_message")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/admin/gamepoint/catalog', methods=['GET'])
def admin_get_gp_catalog():
    gp = GamePointAPI()
    catalog = gp.get_full_catalog()
    return jsonify(catalog)

@app.route('/api/admin/gamepoint/download-csv', methods=['GET'])
def admin_download_gp_csv():
    gp = GamePointAPI()
    catalog = gp.get_full_catalog()
    
    rows = []
    for product in catalog:
        p_name = product['name']
        p_id = product['id']
        for pkg in product['packages']:
            rows.append({
                "Product ID": p_id,
                "Product Name": p_name,
                "Package ID": pkg['id'],
                "Package Name": pkg['name'],
                "Cost Price": pkg['price']
            })
            
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="gamepoint_products.csv"
    )

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
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
    
    return jsonify(result), 200 if result.get("status") == "success" else 400

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
    amount = data.get('amount')
    order_id = data.get('order_id')
    redirect_url = data.get('redirect_url')
    product_name = data.get('product_name', 'GameVault Order')

    if not all([amount, order_id, redirect_url]):
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    config = get_hitpay_config()
    if not config or not config['key']:
        return jsonify({'status': 'error', 'message': 'Payment gateway not configured.'}), 500

    try:
        webhook_url = f"{BACKEND_URL}/api/webhook-handler"
        payload = {
            'amount': float(amount),
            'currency': 'SGD',
            'reference_number': order_id,
            'redirect_url': redirect_url,
            'webhook': webhook_url,
            'purpose': product_name,
            'channel': 'api_custom',
            'email': data.get('email', 'customer@example.com'),
            'name': data.get('name', 'GameVault Customer')
        }
        
        headers = {'X-BUSINESS-API-KEY': config['key'], 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        response = requests.post(config['url'], headers=headers, json=payload, timeout=15, proxies=PROXIES)
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
                supabase.table('orders').update({'status': 'processing', 'payment_id': payment_id}).eq('id', order_id).execute()
                
                order_data = supabase.table('orders').select('*, order_items(*, products(*))').eq('id', order_id).single().execute()
                order = order_data.data
                
                if order and order.get('order_items'):
                    product = order['order_items'][0]['products']
                    gp_prod_id = product.get('gp_product_id')
                    gp_pack_id = product.get('gp_package_id')

                    if gp_prod_id and gp_pack_id:
                        gp_api = GamePointAPI()
                        result = gp_api.place_order(
                            gp_product_id=gp_prod_id,
                            gp_package_id=gp_pack_id,
                            user_id=order.get('game_uid'),
                            zone_id=order.get('server_region')
                        )

                        if result['status'] == 'success':
                            supabase.table('orders').update({'status': 'completed', 'supplier_ref': result.get('supplier_ref')}).eq('id', order_id).execute()
                        else:
                            supabase.table('orders').update({'status': 'manual_review'}).eq('id', order_id).execute()

            elif status == 'failed':
                supabase.table('orders').update({'status': 'failed', 'updated_at': datetime.utcnow().isoformat()}).eq('id', order_id).execute()

        return Response(status=200)

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return Response(status=200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
