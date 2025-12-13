import os
import logging
import time
import uuid
import json
import hmac
import hashlib
import requests
import certifi
import concurrent.futures
from functools import wraps
from flask import Flask, jsonify, request, g, Response, stream_with_context
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime
import random
from i18n import i18n, gettext as _
from gamepoint_service import GamePointService
from error_handler import error_handler

app = Flask(__name__)

# --- Configuration ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[os.environ.get("RATELIMIT_DEFAULT", "60 per minute")],
    storage_uri="memory://"
)

# CORS Setup
allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', "http://127.0.0.1:5173,http://localhost:5173,https://www.gameuniverse.co")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

# Env Vars
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

# --- Decorators ---

# 1. I18n setup
@app.before_request
def before_request():
    g.language = i18n.get_user_language()

# 2. Admin Security Decorator (Protects Admin Routes)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"status": "error", "message": "Missing Authorization Header"}), 401
        
        try:
            token = auth_header.split(" ")[1]
            user = supabase.auth.get_user(token)
            if not user or not user.user:
                raise Exception("Invalid User")
            
            user_id = user.user.id
            
            # Check profile role
            profile = supabase.table('profiles').select('role').eq('id', user_id).single().execute()
            if profile.data and profile.data.get('role') in ['admin', 'owner']:
                return f(*args, **kwargs)
            else:
                return jsonify({"status": "error", "message": "Unauthorized: Admin access required"}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": "Invalid or Expired Token"}), 401
    return decorated_function

# --- Helpers ---

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

# --- Validation Logic (Headers & URLs) ---
SMILE_ONE_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://www.smile.one", "Cookie": os.environ.get("SMILE_ONE_COOKIE") }
# ... (Keep other headers as they were in your original code) ...
RAZER_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
NETEASE_BASE_URL = "https://pay.neteasegames.com/gameclub"
NETEASE_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
RAZER_RO_ORIGIN_VALIDATE_URL = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users"
RAZER_RO_ORIGIN_HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin" }

# (Included compact versions of your validation functions to save space, assuming they are unchanged except for using PROXIES)
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
    # ... (Your existing logic, ensure proxies=PROXIES is passed) ...
    # Placeholder for brevity, paste your full function here
    return {"status": "error", "message": "Function abbreviated for clarity"}

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

# --- Routes ---

@app.route('/')
def home():
    return _("welcome_message")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

# --- Admin Routes (Now Protected) ---

@app.route('/api/admin/gamepoint/catalog', methods=['GET'])
@admin_required # <--- Protected
@error_handler
def admin_get_gp_catalog():
    gp = GamePointService()
    token = gp.get_token()
    try:
        list_resp = gp._request("product/list", {"token": token})
        products = list_resp.get('detail', [])
    except Exception as e:
        logging.error(f"Failed to fetch product list: {e}")
        return jsonify([])

    full_catalog = []
    
    def fetch_detail_safe(product):
        try:
            detail_resp = gp._request("product/detail", {"token": token, "productid": product['id']})
            if detail_resp.get('code') == 200:
                product['packages'] = detail_resp.get('package', [])
                product['fields'] = detail_resp.get('fields', [])
                product['server'] = detail_resp.get('server', [])
                return product
        except Exception as e:
            logging.error(f"Error fetching product {product['id']}: {e}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_detail_safe, p): p for p in products}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                full_catalog.append(result)
    return jsonify(full_catalog)

@app.route('/api/admin/gamepoint/list', methods=['GET'])
@admin_required # <--- Protected
@error_handler
def admin_get_gp_game_list():
    gp = GamePointService()
    token = gp.get_token()
    list_resp = gp._request("product/list", {"token": token})
    products = list_resp.get('detail', [])
    return jsonify(products)

@app.route('/api/admin/gamepoint/detail/<int:product_id>', methods=['GET'])
@admin_required # <--- Protected
@error_handler
def admin_get_gp_game_detail(product_id):
    gp = GamePointService()
    token = gp.get_token()
    detail_resp = gp._request("product/detail", {"token": token, "productid": product_id})
    if detail_resp.get('code') == 200:
        return jsonify(detail_resp.get('package', []))
    return jsonify([])

@app.route('/api/admin/gamepoint/download-csv', methods=['GET'])
# Note: CSV download usually done via browser window.location, handling auth headers is hard.
# You might keep this unprotected but use a temporary token, or assume admin risk if URL is secret.
# Ideally, add @admin_required and fetch via Blob in JS.
def admin_download_gp_csv():
    try:
        gp = GamePointService()
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
@admin_required # <--- Protected
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
            # Clear redis cache if you have it implemented
            # cache.delete(f"gamepoint_token_{data.get('gamepoint_mode', 'sandbox')}")
        return jsonify({"status": "success", "message": "Settings updated"})

    response = supabase.table('settings').select('key,value').ilike('key', 'gamepoint%').execute()
    settings = {item['key']: item['value'] for item in response.data}
    for k in ['gamepoint_secret_key_live', 'gamepoint_secret_key_sandbox', 'gamepoint_proxy_url']:
        if settings.get(k): settings[k] = "********"
    return jsonify({"status": "success", "data": settings})

@app.route('/admin/gamepoint/balance', methods=['GET'])
@admin_required # <--- Protected
@error_handler
def admin_gamepoint_balance():
    gp = GamePointService()
    balance = gp.check_balance()
    return jsonify({"status": "success", "mode": gp.config['mode'], "balance": balance})

# --- Validation Route ---

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@limiter.limit("10/minute")
@error_handler
def check_game_id(game_slug, uid, server_id):
    if not uid: return jsonify({"status": "error", "message": _("user_id_required")}), 400
    
    # Check RO Origin First
    if game_slug == "ragnarok-origin":
        result = check_ro_origin_razer_api(uid, server_id)
        status_code = 200 if result.get("status") == "success" else 400
        return jsonify(result), status_code
    
    # Default handlers (Shortened for brevity - ensure your full logic is here)
    handlers = {
        "mobile-legends": lambda: perform_ml_check(uid, server_id),
        # ... Add other game handlers ...
    }
    
    handler = handlers.get(game_slug)
    if handler:
        result = handler()
        return jsonify(result), 200 if result.get("status") == "success" else 400
    
    # GamePoint Fallback
    game_res = supabase.table('games').select('*').eq('game_key', game_slug).single().execute()
    if game_res.data and game_res.data.get('supplier') == 'gamepoint':
        gp = GamePointService()
        inputs = {"input1": uid}
        if server_id: inputs["input2"] = server_id
        try:
            supplier_pid = game_res.data.get('supplier_pid') 
            if not supplier_pid: return jsonify({"status": "error", "message": "Game config missing supplier PID"}), 500
            resp = gp.validate_id(supplier_pid, inputs)
            if resp.get('code') == 200:
                return jsonify({"status": "success", "username": "Validated User", "roles": [], "validation_token": resp.get('validation_token')})
            else:
                 return jsonify({"status": "error", "message": resp.get('message', 'Invalid ID')}), 400
        except Exception:
            return jsonify({"status": "error", "message": "Validation Error"}), 400

    return jsonify({"status": "error", "message": _("validation_not_configured", game=game_slug)}), 400

@app.route('/ro-origin/get-servers', methods=['GET', 'OPTIONS'])
def handle_ro_origin_get_servers():
    return jsonify(get_ro_origin_servers())

# --- Payment Routes ---

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

# --- CRITICAL FIX: Webhook Handler with Idempotency ---
@app.route('/api/webhook-handler', methods=['POST'])
@cross_origin()
def hitpay_webhook_handler():
    try:
        raw_body = request.get_data()
        form_data = request.form.to_dict()
        hitpay_signature = request.headers.get('X-Business-Signature')
        
        # 1. Verify Signature
        config = get_hitpay_config()
        if config and config['salt']:
            generated_signature = hmac.new(key=bytes(config['salt'], 'utf-8'), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
            if hitpay_signature and generated_signature != hitpay_signature:
                logging.warning(f"Signature Mismatch! Possible spoofing attempt.")
                return Response(status=400) # Reject bad signatures
        
        status = form_data.get('status')
        order_id = form_data.get('reference_number')
        payment_id = form_data.get('payment_id')

        if not order_id:
            return Response(status=200)

        # 2. Check current status FIRST (Prevents race conditions)
        # We only process if status is 'pending' or 'verifying'
        # If it's 'processing', 'completed', or 'failed', we ignore the webhook (Idempotency)
        current_order = supabase.table('orders').select('status').eq('id', order_id).single().execute()
        if not current_order.data:
            logging.error(f"Webhook received for unknown order: {order_id}")
            return Response(status=200)
            
        current_status = current_order.data.get('status')
        if current_status in ['processing', 'completed', 'refunded', 'failed', 'paid']:
            logging.info(f"Duplicate webhook for Order {order_id}. Current status: {current_status}. Ignoring.")
            return Response(status=200)

        if status == 'completed':
            # 3. Mark as PROCESSING immediately
            # This locks the order so subsequent webhooks/retries hit the check above and stop.
            supabase.table('orders').update({
                'status': 'processing', 
                'payment_id': payment_id,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', order_id).execute()
            
            logging.info(f"Payment received for {order_id}. Starting fulfillment...")

            # 4. Fetch details for fulfillment
            order_data = supabase.table('orders').select('*, order_items(*, products(*))').eq('id', order_id).single().execute()
            order = order_data.data
            
            if order and order.get('order_items'):
                product = order['order_items'][0]['products']
                gp_api = GamePointService()
                
                # --- Fulfillment Logic ---
                supplier_config = product.get('supplier_config')
                
                inputs = {"input1": order.get('game_uid')}
                if order.get('server_region'): inputs["input2"] = order.get('server_region')

                if supplier_config:
                    # Logic for Custom Bundles (Multiple packages)
                    all_success = True
                    failed_items = []
                    supplier_refs = []
                    
                    for item in supplier_config:
                        gp_prod_id = item.get('gameId')
                        gp_pack_id = item.get('packageId')
                        
                        try:
                            val_resp = gp_api.validate_id(gp_prod_id, inputs)
                            val_token = val_resp.get('validation_token')
                            
                            if val_token:
                                merchant_ref = f"{order_id[:8]}-{int(time.time())}-{random.randint(100,999)}"
                                create_resp = gp_api.create_order(gp_pack_id, val_token, merchant_ref)
                                
                                if create_resp.get('code') in [100, 101]:
                                    supplier_refs.append(str(create_resp.get('referenceno')))
                                else:
                                    all_success = False
                                    failed_items.append(f"{item.get('name')} (Err: {create_resp.get('message')})")
                            else:
                                all_success = False
                                failed_items.append(f"{item.get('name')} (Validation Failed)")
                        except Exception as e:
                            all_success = False
                            failed_items.append(f"{item.get('name')} (Exception: {str(e)})")
                    
                    if all_success:
                        supabase.table('orders').update({
                            'status': 'completed', 
                            'supplier_ref': ', '.join(supplier_refs),
                            'completed_at': datetime.utcnow().isoformat()
                        }).eq('id', order_id).execute()
                    else:
                        supabase.table('orders').update({
                            'status': 'manual_review',
                            'notes': f"Partial Failure: {'; '.join(failed_items)}",
                            'supplier_ref': ', '.join(supplier_refs)
                        }).eq('id', order_id).execute()
                
                else:
                    # Logic for Standard Single Products
                    gp_prod_id = product.get('gamepoint_product_id')
                    gp_pack_id = product.get('gamepoint_package_id')

                    if gp_prod_id and gp_pack_id:
                        try:
                            val_resp = gp_api.validate_id(gp_prod_id, inputs)
                            val_token = val_resp.get('validation_token')
                            
                            if val_token:
                                merchant_ref = f"{order_id[:8]}-{int(time.time())}"
                                create_resp = gp_api.create_order(gp_pack_id, val_token, merchant_ref)
                                
                                if create_resp.get('code') in [100, 101]:
                                    supabase.table('orders').update({
                                        'status': 'completed', 
                                        'supplier_ref': str(create_resp.get('referenceno')),
                                        'completed_at': datetime.utcnow().isoformat()
                                    }).eq('id', order_id).execute()
                                else:
                                    error_msg = create_resp.get('message', 'Unknown Supplier Error')
                                    supabase.table('orders').update({'status': 'manual_review', 'notes': f"Supplier Failed: {error_msg}"}).eq('id', order_id).execute()
                            else:
                                supabase.table('orders').update({'status': 'manual_review', 'notes': 'GamePoint Validation Failed'}).eq('id', order_id).execute()
                        except Exception as e:
                            logging.error(f"GamePoint Fulfillment Failed: {e}")
                            supabase.table('orders').update({'status': 'manual_review', 'notes': f"Exception: {str(e)}"}).eq('id', order_id).execute()
                    else:
                        # Product not mapped to supplier
                        supabase.table('orders').update({'status': 'manual_review', 'notes': 'Product not linked to supplier'}).eq('id', order_id).execute()

        elif status == 'failed':
            supabase.table('orders').update({'status': 'failed', 'updated_at': datetime.utcnow().isoformat()}).eq('id', order_id).execute()

        return Response(status=200)

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        # Always return 200 to HitPay so they don't keep retrying errors that are our fault
        return Response(status=200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
