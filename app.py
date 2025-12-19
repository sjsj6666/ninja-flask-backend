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
import random
import pandas as pd
import io
from functools import wraps
from flask import Flask, jsonify, request, g, Response, send_file, stream_with_context
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, quote_plus
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Local Module Imports
from i18n import i18n, gettext as _
from gamepoint_service import GamePointService
from error_handler import error_handler, log_execution_time
from redis_cache import cache
from email_service import send_order_update

app = Flask(__name__)

# --- CORE CONFIGURATION ---
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

# --- API HEADERS ---
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

# --- MIDDLEWARE & UTILS ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[os.environ.get("RATELIMIT_DEFAULT", "60 per minute")],
    storage_uri="memory://"
)

allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', "https://www.gameuniverse.co,http://localhost:5173")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

@app.before_request
def before_request():
    g.language = i18n.get_user_language()

@cache.cached("exchange_rate_myr_sgd", expire_seconds=3600)
def get_myr_to_sgd_rate():
    try:
        rate_setting = supabase.table('settings').select('value').eq('key', 'myr_sgd_rate').single().execute()
        if rate_setting.data and rate_setting.data.get('value'):
            return float(rate_setting.data['value'])
    except Exception: pass
    return 0.31

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header: return jsonify({"status": "error", "message": "Missing Auth"}), 401
        try:
            token = auth_header.split(" ")[1]
            user = supabase.auth.get_user(token)
            profile = supabase.table('profiles').select('role').eq('id', user.user.id).single().execute()
            if profile.data and profile.data['role'] in ['admin', 'owner']:
                return f(*args, **kwargs)
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        except: return jsonify({"status": "error", "message": "Invalid Token"}), 401
    return decorated_function

def get_hitpay_config():
    keys = ['hitpay_mode', 'hitpay_api_key_sandbox', 'hitpay_salt_sandbox', 'hitpay_api_key_live', 'hitpay_salt_live']
    res = supabase.table('settings').select('key, value').in_('key', keys).execute()
    s = {item['key']: item['value'] for item in res.data}
    if s.get('hitpay_mode') == 'live':
        return {'url': 'https://api.hit-pay.com/v1/payment-requests', 'key': s.get('hitpay_api_key_live'), 'salt': s.get('hitpay_salt_live')}
    return {'url': 'https://api.sandbox.hit-pay.com/v1/payment-requests', 'key': s.get('hitpay_api_key_sandbox'), 'salt': s.get('hitpay_salt_sandbox')}

# --- VALIDATION ENGINE FUNCTIONS ---
def perform_ml_check(user_id, zone_id):
    try:
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7, proxies=None)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("result", {}).get("nickname"):
                return {'status': 'success', 'username': data["result"]["nickname"]}
    except: pass
    return check_smile_one_api("mobilelegends", user_id, zone_id)

def check_smile_one_api(game_code, uid, server_id=None):
    endpoints = { "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike", "loveanddeepspace": "https://www.smile.one/merchant/loveanddeepspace/checkrole/", "magicchessgogo": "https://www.smile.one/br/merchant/game/checkrole?product=magicchessgogo" }
    target_endpoint = endpoints.get(game_code) or f"https://www.smile.one/merchant/{game_code}/checkrole"
    params = {"checkrole": "1"}
    if game_code == "loveanddeepspace":
        sid = {"Asia": "81", "America": "82", "Europe": "83"}.get(str(server_id))
        if not sid: return {"status": "error", "message": "Invalid Server"}
        params.update({"uid": uid, "pid": "18762", "sid": sid})
    elif game_code == "mobilelegends":
        params.update({"user_id": uid, "zone_id": server_id, "pid": "25"})
    else:
        params.update({"uid": uid, "sid": server_id})
    try:
        response = requests.post(target_endpoint, data=params, headers=SMILE_ONE_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("code") == 200: return {"status": "success", "username": (data.get("username") or data.get("nickname")).strip()}
        return {"status": "error", "message": data.get("message", "Invalid ID")}
    except: return {"status": "error", "message": "API Error"}

def check_bigo_native_api(uid):
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params={"isFromApp": "0", "bigoId": uid}, headers=BIGO_NATIVE_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("result") == 0: return {"status": "success", "username": data.get("data", {}).get("nick_name")}
        return {"status": "error", "message": "Invalid Bigo ID"}
    except: return {"status": "error", "message": "API Error"}

def check_gamingnp_api(game_code, uid):
    params = { "hok": {"id": "3898", "url": "https://gaming.com.np/topup/honor-of-kings"}, "pubgm": {"id": "3920", "url": "https://gaming.com.np/topup/pubg-mobile-global"} }
    config = params.get(game_code, {"id": "0", "url": "https://gaming.com.np"})
    headers = GAMINGNP_HEADERS.copy()
    headers["Referer"] = config["url"]
    try:
        response = requests.post(GAMINGNP_VALIDATE_URL, data={"userid": uid, "game": game_code, "categoryId": config["id"]}, headers=headers, timeout=10, proxies=PROXY_DICT)
        data = response.json()
        if data.get("success") and data.get("detail", {}).get("valid") == "valid": return {"status": "success", "username": data["detail"].get("name")}
        return {"status": "error", "message": "Invalid ID"}
    except: return {"status": "error", "message": "API Error"}

def check_spacegaming_api(game_id, uid):
    try:
        response = requests.post(SPACEGAMING_VALIDATE_URL, json={"username": uid, "game_id": game_id}, headers=SPACEGAMING_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("status") == "true": return {"status": "success", "username": data.get("message").strip()}
        return {"status": "error", "message": "Invalid ID"}
    except: return {"status": "error", "message": "API Error"}

def check_netease_api(game_path, server_id, role_id):
    try:
        params = {"deviceid": str(uuid.uuid4()), "traceid": str(uuid.uuid4()), "timestamp": int(time.time()*1000), "roleid": role_id, "client_type": "gameclub"}
        headers = NETEASE_HEADERS.copy()
        headers["Referer"] = f"https://pay.neteasegames.com/{game_path}/topup"
        response = requests.get(f"{NETEASE_BASE_URL}/{game_path}/{server_id}/login-role", params=params, headers=headers, timeout=10, proxies=PROXY_DICT)
        data = response.json()
        if data.get("code") == "0000": return {"status": "success", "username": data.get("data", {}).get("rolename")}
        return {"status": "error", "message": "Invalid ID"}
    except: return {"status": "error", "message": "API Error"}

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
    except: return {"status": "error", "message": "API Error"}

def check_nuverse_api(aid, role_id):
    try:
        response = requests.get(NUVERSE_VALIDATE_URL, params={"tab": "purchase", "aid": aid, "role_id": role_id}, headers=NUVERSE_HEADERS, timeout=10, proxies=None)
        data = response.json()
        if data.get("code") == 0: return {"status": "success", "username": f"{data.get('data', [{}])[0].get('role_name')}"}
        return {"status": "error", "message": "Invalid ID"}
    except: return {"status": "error", "message": "API Error"}

def check_ro_origin_razer_api(uid, server_id):
    try:
        response = requests.get(f"{RAZER_RO_ORIGIN_VALIDATE_URL}/{uid}", params={"serverId": server_id}, headers=RAZER_RO_ORIGIN_HEADERS, timeout=10, proxies=None)
        if response.status_code == 200:
            data = response.json()
            if data.get("roles"): return {"status": "success", "roles": [{"roleId": r.get("CharacterId"), "roleName": r.get("Name")} for r in data["roles"]]}
        return {"status": "error", "message": "Invalid ID"}
    except: return {"status": "error", "message": "API Error"}

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
        except: return {"status": "error", "message": "API Error"}

# --- VALIDATION HANDLERS MAP ---
genshin_servers = {"Asia": "os_asia", "America": "os_usa", "Europe": "os_euro", "TW,HK,MO": "os_cht"}
hsr_servers = {"Asia": "prod_official_asia", "America": "prod_official_usa", "Europe": "prod_official_eur", "TW/HK/MO": "prod_official_cht"}
zzz_servers = {"Asia": "prod_gf_jp", "America": "prod_gf_us", "Europe": "prod_gf_eu", "TW/HK/MO": "prod_gf_sg"}

VALIDATION_HANDLERS = {
    "universal_mlbb": lambda uid, sid, cfg: perform_ml_check(uid, sid),
    "universal_netease": lambda uid, sid, cfg: check_netease_api(cfg.get('target_id'), sid, uid),
    "universal_smile_one": lambda uid, sid, cfg: check_smile_one_api(cfg.get('target_id'), uid, sid),
    "universal_gamingnp": lambda uid, sid, cfg: check_gamingnp_api(cfg.get('target_id'), uid),
    "universal_spacegaming": lambda uid, sid, cfg: check_spacegaming_api(cfg.get('target_id'), uid),
    "pubgm_global": lambda uid, sid, cfg: check_gamingnp_api("pubgm", uid),
    "genshin_impact": lambda uid, sid, cfg: check_razer_hoyoverse_api("genshinimpact", "genshin-impact", genshin_servers, uid, sid),
    "honkai_star_rail": lambda uid, sid, cfg: check_razer_hoyoverse_api("mihoyo-honkai-star-rail", "hsr", hsr_servers, uid, sid),
    "zenless_zone_zero": lambda uid, sid, cfg: check_razer_hoyoverse_api("cognosphere-zenless-zone-zero", "zenless-zone-zero", zzz_servers, uid, sid),
    "blood_strike": lambda uid, sid, cfg: check_smile_one_api("bloodstrike", uid),
    "love_and_deepspace": lambda uid, sid, cfg: check_smile_one_api("loveanddeepspace", uid, sid),
    "ragnarok_origin": lambda uid, sid, cfg: check_ro_origin_razer_api(uid, sid),
    "honor_of_kings": lambda uid, sid, cfg: check_gamingnp_api("hok", uid),
    "bigo_live": lambda uid, sid, cfg: check_bigo_native_api(uid),
    "ragnarok_x_next_gen": lambda uid, sid, cfg: check_nuverse_api("3402", uid),
    "delta_force": lambda uid, sid, cfg: check_garena_api("100151", uid),
}

# --- PRIMARY ROUTES ---

@app.route('/')
def home():
    return _("welcome_message")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@limiter.limit("20/minute")
@error_handler
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": _("user_id_required")}), 400
    if game_slug == "ragnarok-origin": return jsonify(check_ro_origin_razer_api(uid, server_id))
    
    res = supabase.table('games').select('*').eq('game_key', game_slug).single().execute()
    if not res.data: return jsonify({"status": "error", "message": "Game not found"}), 404
    
    game = res.data
    if game.get('requires_user_id') == False: return jsonify({"status": "success", "username": "Voucher"})
    
    handler_key = game.get('api_handler')
    if handler_key in VALIDATION_HANDLERS:
        target = game.get('validation_param') or game.get('supplier_pid')
        result = VALIDATION_HANDLERS[handler_key](uid, server_id, {'target_id': target})
        return jsonify(result), 200 if result.get("status") == "success" else 400
    
    if game.get('supplier') == 'gamepoint':
        gp = GamePointService(supabase_client=supabase)
        resp = gp.validate_id(game.get('supplier_pid'), {"input1": uid, "input2": server_id} if server_id else {"input1": uid})
        if resp.get('code') == 200: return jsonify({"status": "success", "username": "Validated", "validation_token": resp.get('validation_token')})
        return jsonify({"status": "error", "message": resp.get('message')}), 400

    return jsonify({"status": "error", "message": "Validation not configured"}), 400

# --- ADMIN ROUTES ---

@app.route('/api/admin/gamepoint/catalog', methods=['GET'])
@admin_required
@error_handler
def admin_get_gp_catalog():
    cached = cache.get("admin_gp_full_catalog")
    if cached: return jsonify(cached)
    gp = GamePointService(supabase_client=supabase)
    full_catalog = gp.get_full_catalog() # Assumes ThreadPool inside service
    cache.set("admin_gp_full_catalog", full_catalog, expire_seconds=3600)
    return jsonify(full_catalog)

@app.route('/api/admin/gamepoint/download-csv', methods=['GET'])
@admin_required
def admin_download_gp_csv():
    gp = GamePointService(supabase_client=supabase)
    token = gp.get_token()
    products = gp._request("product/list", {"token": token}).get('detail', [])
    def generate_csv():
        yield u'\ufeffProduct ID,Product Name,Package ID,Package Name,Cost Price\n'
        for p in products:
            details = gp._request("product/detail", {"token": token, "productid": p['id']})
            if details.get('code') == 200:
                for pkg in details.get('package', []):
                    yield f"{p['id']},{p['name'].replace(',',' ')},{pkg['id']},{pkg['name'].replace(',',' ')},{pkg['price']}\n"
    return Response(stream_with_context(generate_csv()), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=gp_catalog.csv"})

# --- PAYMENT & WEBHOOKS ---

@app.route('/api/create-payment', methods=['POST'])
def create_hitpay_payment():
    data = request.get_json()
    order_id, redirect_url = data.get('order_id'), data.get('redirect_url')
    order_res = supabase.table('orders').select('*').eq('id', order_id).single().execute()
    if not order_res.data: return jsonify({'status': 'error', 'message': 'Order not found'}), 404
    
    config = get_hitpay_config()
    payload = {
        'amount': float(order_res.data['total_amount']), 'currency': 'SGD', 'reference_number': order_id,
        'redirect_url': redirect_url, 'webhook': f"{BACKEND_URL}/api/webhook-handler",
        'purpose': data.get('product_name', 'Top-up'), 'email': data.get('email', 'customer@gameuniverse.co')
    }
    res = requests.post(config['url'], headers={'X-BUSINESS-API-KEY': config['key'], 'Content-Type': 'application/json'}, json=payload)
    return jsonify(res.json())

@app.route('/api/webhook-handler', methods=['POST'])
@cross_origin()
def hitpay_webhook_handler():
    try:
        form_data = request.form.to_dict()
        status, order_id = form_data.get('status'), form_data.get('reference_number')
        if status == 'completed' and order_id:
            # Atomic lock
            lock = supabase.table('orders').update({'status': 'processing'}).eq('id', order_id).in_('status', ['pending', 'verifying']).execute()
            if not lock.data: return Response(status=200)

            order = supabase.table('orders').select('*, order_items(*, products(*, games(*)))').eq('id', order_id).single().execute().data
            if not order: return Response(status=200)

            product = order['order_items'][0]['products']
            game = product.get('games', {})
            gp_api = GamePointService(supabase_client=supabase)
            
            # Handle Bundles (supplier_config)
            supplier_config = product.get('supplier_config')
            inputs = {"input1": order.get('game_uid') if game.get('requires_user_id') != False else "GIFT_CARD"}
            if order.get('server_region'): inputs["input2"] = order.get('server_region')

            if supplier_config:
                all_success, failed_items, supplier_refs = True, [], []
                for item in supplier_config:
                    try:
                        val_resp = gp_api.validate_id(item.get('gameId'), inputs)
                        v_token = val_resp.get('validation_token')
                        if v_token:
                            merchant_ref = f"{order_id[:8]}-{int(time.time())}-{random.randint(100,999)}"
                            create_resp = gp_api.create_order(item.get('packageId'), v_token, merchant_ref)
                            if create_resp.get('code') in [100, 101]:
                                supplier_refs.append(create_resp.get('referenceno'))
                                if create_resp.get('code') == 101: all_success = False
                            else: all_success, _ = False, failed_items.append(f"{item.get('name')} Fail")
                        else: all_success, _ = False, failed_items.append(f"{item.get('name')} Val Fail")
                    except: all_success, _ = False, failed_items.append(f"{item.get('name')} Err")
                
                final_status = 'completed' if all_success else ('manual_review' if failed_items else 'processing')
                supabase.table('orders').update({'status': final_status, 'supplier_ref': ', '.join(supplier_refs), 'notes': f"Issues: {'; '.join(failed_items)}"}).eq('id', order_id).execute()
                if final_status == 'completed': send_order_update(order, product['name'], game['name'], order['email'], order['remitter_name'])
            
            else:
                # Handle Single GamePoint Product
                gp_prod_id, gp_pack_id = product.get('gamepoint_product_id'), product.get('gamepoint_package_id')
                if gp_prod_id and gp_pack_id:
                    try:
                        val_resp = gp_api.validate_id(gp_prod_id, inputs)
                        v_token = val_resp.get('validation_token')
                        if v_token:
                            merchant_ref = f"{order_id[:8]}-{int(time.time())}"
                            create_resp = gp_api.create_order(gp_pack_id, v_token, merchant_ref)
                            gp_code = create_resp.get('code')
                            if gp_code in [100, 101]:
                                final_s = 'completed' if gp_code == 100 else 'processing'
                                supabase.table('orders').update({'status': final_s, 'supplier_ref': create_resp.get('referenceno')}).eq('id', order_id).execute()
                                if final_s == 'completed': send_order_update(order, product['name'], game['name'], order['email'], order['remitter_name'])
                            else: supabase.table('orders').update({'status': 'manual_review', 'notes': create_resp.get('message')}).eq('id', order_id).execute()
                    except: supabase.table('orders').update({'status': 'manual_review'}).eq('id', order_id).execute()

        return Response(status=200)
    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return Response(status=200)

@app.route('/api/callbacks/gamepoint', methods=['POST'])
@cross_origin()
def gamepoint_callback():
    """Returns plain text 'OK' as required by GamePoint V1.93"""
    try:
        data = request.form.to_dict() or request.get_json() or {}
        merchant_code, status_code = data.get('merchantcode'), str(data.get('code'))
        
        # Order lookup
        order_res = supabase.table('orders').select('*').ilike('supplier_ref', f"%{data.get('referenceno')}%").execute()
        if not order_res.data and merchant_code:
            order_res = supabase.table('orders').select('*').ilike('id', f"{merchant_code.split('-')[0]}%").execute()
        
        if order_res.data:
            order = order_res.data[0]
            if status_code == '100':
                v_data = {"pin1": data.get('pin1'), "pin2": data.get('pin2'), "message": data.get('message')}
                supabase.table('orders').update({'status': 'completed', 'voucher_codes': v_data, 'updated_at': datetime.utcnow().isoformat()}).eq('id', order['id']).execute()
            elif status_code not in ['101', '102']:
                supabase.table('orders').update({'status': 'manual_review', 'notes': f"Callback: {data.get('message')}"}).eq('id', order['id']).execute()
        
        return Response("OK", mimetype="text/plain")
    except Exception as e:
        logging.error(f"Callback Error: {e}")
        return Response("OK", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
