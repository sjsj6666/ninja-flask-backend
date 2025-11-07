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
from flask import Flask, jsonify, request, Response
from flask_cors import CORS, cross_origin
from supabase import create_client, Client
from datetime import datetime, timedelta
from urllib.parse import urlencode
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://coxx.netlify.app"
]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 10000))

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
        api_url = "https://cekidml.caliph.dev/api/validasi"
        params = {'id': user_id, 'serverid': zone_id}
        response = requests.get(api_url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("result", {}).get("nickname"):
                return {'status': 'success', 'username': data["result"]["nickname"], 'region': 'N/A'}
    except Exception as e:
        logging.error(f"Primary ML check failed: {e}")
    return check_smile_one_api("mobilelegends", user_id, zone_id)

def check_smile_one_api(game_code, uid, server_id=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike",
        "loveanddeepspace": "https://www.smile.one/merchant/loveanddeepspace/checkrole/",
        "magicchessgogo": "https://www.smile.one/br/merchant/game/checkrole?product=magicchessgogo"
    }
    pids = {"mobilelegends": "25", "bloodstrike": "20294"}
    if game_code not in endpoints: return {"status": "error", "message": f"Game not configured: {game_code}"}
    pid_to_use = pids.get(game_code)
    params = {"checkrole": "1"}
    if game_code == "loveanddeepspace":
        params.update({"uid": uid, "pid": "18762", "sid": {"Asia": "81", "America": "82", "Europe": "83"}.get(str(server_id))})
    elif game_code == "mobilelegends":
        params.update({"user_id": uid, "zone_id": server_id, "pid": pid_to_use})
    elif game_code == "bloodstrike":
        params.update({"uid": uid, "sid": "-1", "pid": pid_to_use})
    else:
        params.update({"uid": uid, "sid": server_id})
    try:
        response = requests.post(endpoints[game_code], data=params, headers=SMILE_ONE_HEADERS, timeout=10)
        data = response.json()
        if data.get("code") == 200 and (data.get("username") or data.get("nickname")):
            return {"status": "success", "username": (data.get("username") or data.get("nickname")).strip()}
        return {"status": "error", "message": data.get("message", "Invalid ID.")}
    except Exception as e:
        logging.error(f"Smile.One API error for {game_code}: {e}")
        return {"status": "error", "message": "API Error"}

def check_garena_api(app_id, uid):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(f"https://shop.garena.sg/?app={app_id}")
        time.sleep(2)
        script = """
            const loginPayload = { app_id: parseInt(arguments[0], 10), login_id: arguments[1] };
            const rolesParams = new URLSearchParams({ app_id: arguments[0], region: 'SG', language: 'en', source: 'pc' });
            return fetch('https://shop.garena.sg/api/auth/player_id_login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(loginPayload)
            }).then(loginRes => {
                if (!loginRes.ok) throw new Error('Login failed');
                return fetch('https://shop.garena.sg/api/shop/apps/roles?' + rolesParams);
            }).then(rolesRes => rolesRes.json());
        """
        result = driver.execute_script(script, app_id, uid)
        app_roles = result.get(str(app_id))
        if app_roles and app_roles[0].get("role"):
            return {"status": "success", "username": app_roles[0]["role"].strip()}
        return {"status": "error", "message": "Invalid Player ID."}
    except Exception as e:
        logging.error(f"Selenium/Garena error: {e}")
        return {"status": "error", "message": "API validation failed."}
    finally:
        if driver:
            driver.quit()

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

@app.route('/')
def home():
    return "API is live."

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/check-id/<game_slug>/<uid>/', defaults={'server_id': None})
@app.route('/check-id/<game_slug>/<uid>/<server_id>')
@cross_origin(origins=allowed_origins, supports_credentials=True)
def check_game_id(game_slug, uid, server_id):
    if not uid:
        return jsonify({"status": "error", "message": "User ID is required."}), 400
    
    handlers = {
        "delta-force": lambda: check_garena_api("100151", uid),
        "blood-strike": lambda: check_smile_one_api("bloodstrike", uid),
        "mobile-legends": lambda: perform_ml_check(uid, server_id),
    }

    handler = handlers.get(game_slug)
    if handler:
        result = handler()
    else:
        result = {"status": "error", "message": f"Validation not configured for: {game_slug}"}

    status_code = 200 if result and result.get("status") == "success" else 400
    return jsonify(result), status_code

@app.route('/ro-origin/get-servers', methods=['GET'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def handle_ro_origin_get_servers():
    return jsonify(get_ro_origin_servers()), 200

@app.route('/create-paynow-qr', methods=['POST'])
@cross_origin(origins=allowed_origins, supports_credentials=True)
def create_paynow_qr():
    data = request.get_json()
    if not data or 'amount' not in data or 'order_id' not in data:
        return jsonify({'error': 'Amount and order_id are required.'}), 400
    try:
        expiry_minutes = 15
        try:
            response = supabase.table('settings').select('value').eq('key', 'qr_code_expiry_minutes').single().execute()
            if response.data and response.data.get('value'):
                expiry_minutes = int(response.data['value'])
        except Exception as e:
            logging.error(f"Could not fetch expiry setting: {e}")

        paynow_uen = os.environ.get('PAYNOW_UEN')
        if not paynow_uen:
            raise ValueError("PAYNOW_UEN not set.")

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
                'message': 'QR code generated successfully.'
            })
        raise Exception("Invalid response from QR service.")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Could not connect to QR service."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
