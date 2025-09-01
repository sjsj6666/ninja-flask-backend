# app.py (Final, Complete, Unabridged, and Corrected Version)

import os
import logging
import time
import uuid
import json
import io
import segno
import requests
import crcmod.predefined
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)

# --- CONFIGURATION ---
allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://coxx.netlify.app"
]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 5001))

# --- SUPABASE CLIENT INITIALIZATION (using secure service key) ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- API HEADERS & CONSTANTS ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE")
}
NETEASE_IDV_BASE_URL_TEMPLATE = "https://pay.neteasegames.com/gameclub/identityv/{server_code}/login-role"
NETEASE_IDV_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15", "Accept": "application/json, text/plain, */*", "Referer": "https://pay.neteasegames.com/identityv/topup", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}
NETEASE_IDV_STATIC_PARAMS = { "gc_client_version": "1.9.111", "client_type": "gameclub" }
IDV_SERVER_CODES = { "asia": "2001", "na-eu": "2011" }
RAZER_GOLD_COMMON_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15", "Accept": "application/json, text/plain, */*", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact"
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero"
RAZER_ZZZ_SERVER_ID_MAP = {"prod_official_asia": "prod_gf_jp","prod_official_usa": "prod_gf_us","prod_official_eur": "prod_gf_eu","prod_official_cht": "prod_gf_sg"}
RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin"
RAZER_GOLD_SNOWBREAK_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/seasun-games-snowbreak-containment-zone/users/{user_id}"
RAZER_GOLD_SNOWBREAK_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_SNOWBREAK_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/snowbreak-containment-zone"
RAZER_SNOWBREAK_SERVER_ID_MAP = {"sea": "215","asia": "225","americas": "235","europe": "245"}
NUVERSE_ROX_VALIDATE_URL = "https://pay.nvsgames.com/web/payment/validate"
NUVERSE_ROX_AID = "3402"
NUVERSE_ROX_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15", "Accept": "*/*", "Referer": f"https://pay.nvsgames.com/topup/{NUVERSE_ROX_AID}/sg-en", "x-appid": NUVERSE_ROX_AID, "x-language": "en", "x-scene": "0", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}
ELITEDIAS_MSA_VALIDATE_URL = "https://api.elitedias.com/checkid"
ELITEDIAS_MSA_GAME_ID = "metal_slug"
ELITEDIAS_MSA_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15", "Accept": "application/json, text/plain, */*", "Content-Type": "application/json; charset=utf-8", "Origin": "https://elitedias.com", "Referer": "https://elitedias.com/", "X-Requested-With": "XMLHttpRequest", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site"}
MSA_SERVER_ID_TO_NAME_MAP = {"49": "MSA SEA Server 49"}


# --- FLASK ROUTES ---
@app.route('/')
def home():
    return "NinjaTopUp Validation & Services Backend is Live!"

@app.route('/get-rates', methods=['GET'])
def get_rates():
    try:
        response = supabase.table('site_settings').select('setting_value').eq('setting_key', 'exchangerate_api_key').single().execute()
        api_key_data = response.data
        if not api_key_data or not api_key_data.get('setting_value'):
            logging.error("ExchangeRate-API key is missing or not set in the database.")
            return jsonify({"error": "Currency service API key is not configured in the admin panel."}), 500
        
        API_KEY = api_key_data['setting_value']
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/SGD"
        
        api_response = requests.get(url, timeout=10)
        api_response.raise_for_status()
        data = api_response.json()
        
        if data.get('result') == 'success':
            return jsonify(data.get('conversion_rates', {}))
        else:
            api_error_type = data.get('error-type', 'Unknown API error')
            logging.error(f"ExchangeRate-API returned an error: {api_error_type}")
            return jsonify({"error": api_error_type}), 400

    except requests.exceptions.RequestException as e:
        logging.error(f"Could not connect to ExchangeRate-API: {e}")
        return jsonify({"error": "Could not connect to the currency service."}), 503
    except Exception as e:
        logging.exception(f"An unexpected error occurred in get_rates: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/generate-paynow-qr', methods=['GET'])
def generate_paynow_qr():
    PAYNOW_UEN = os.environ.get("PAYNOW_UEN") 
    PAYNOW_MERCHANT_NAME = os.environ.get("PAYNOW_MERCHANT_NAME", "NinjaTopUp")
    if not PAYNOW_UEN:
        logging.error("PAYNOW_UEN is not set in environment variables.")
        return jsonify({"error": "Payment configuration is missing on the server."}), 500

    amount = request.args.get('amount')
    reference = request.args.get('ref')

    # More robust validation
    if not reference or not reference.strip() or len(reference.strip()) > 25:
        return jsonify({"error": "A valid reference (1-25 chars) is required."}), 400
    
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            return jsonify({"error": "Amount must be positive."}), 400
        amount = f"{amount_float:.2f}"
    except (ValueError, TypeError):
        return jsonify({"error": "A valid numeric amount is required."}), 400

    payload_parts = {
        '00': '01', '01': '12',
        '26': {'00': 'sg.com.paynow', '01': '2', '02': PAYNOW_UEN},
        '52': '0000', '53': '702', '54': amount, '58': 'SG', '59': PAYNOW_MERCHANT_NAME,
        '62': {'01': reference}
    }
    def build_payload(parts):
        result = ""
        for tag in sorted(parts.keys()):
            value = parts[tag]
            if isinstance(value, dict):
                sub_payload = build_payload(value)
                result += f"{tag}{len(sub_payload):02d}{sub_payload}"
            else:
                result += f"{tag}{len(value):02d}{value}"
        return result
    
    payload_string = build_payload(payload_parts)
    
    payload_with_crc_placeholder = payload_string + '6304'
    crc16_func = crcmod.predefined.mkCrcFun('crc-ccitt-false')
    checksum = crc16_func(payload_with_crc_placeholder.encode('utf-8'))
    checksum_hex = f'{checksum:04X}'
    final_payload = payload_with_crc_placeholder + checksum_hex
    
    try:
        buffer = io.BytesIO()
        qrcode = segno.make_qr(final_payload, error='h')
        qrcode.save(buffer, kind='png', scale=8, border=2)
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png', as_attachment=False)
    except Exception as e:
        logging.error(f"Failed to generate QR code: {e}")
        return jsonify({"error": "Failed to generate QR code image."}), 500

@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    game_lower = game_slug_from_frontend.lower()
    result = {}
    if not uid: return jsonify({"status": "error", "message": "User ID/Role ID is required."}), 400
    if game_lower == "metal-slug-awakening": result = check_elitedias_msa_api(uid)
    elif game_lower == "ragnarok-x-next-generation": result = check_nuverse_rox_api(uid)
    elif game_lower == "mobile-legends-sg": result = check_smile_one_api("mobilelegends", uid, server_id, os.environ.get("SMILE_ONE_PID_MLBB_SG_CHECKROLE"))
    elif game_lower == "mobile-legends": result = check_smile_one_api("mobilelegends", uid, server_id, "25")
    elif game_lower in ["genshin-impact", "zenless-zone-zero", "ragnarok-origin", "snowbreak-containment-zone"]:
        razer_game_slug = "snowbreak" if game_lower == "snowbreak-containment-zone" else game_lower
        result = check_razer_api(razer_game_slug, uid, server_id)
    elif game_lower == "identity-v": result = check_identityv_api(server_id, uid)
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        smileone_game_code = {"honkai-star-rail": "honkaistarrail", "bloodstrike": "bloodstrike", "ragnarok-m-classic": "ragnarokmclassic", "love-and-deepspace": "loveanddeepspace", "bigo-live": "bigolive"}.get(game_lower)
        result = check_smile_one_api(smileone_game_code, uid, server_id)
    else: return jsonify({"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}), 400
    
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


# --- API CHECK FUNCTIONS ---
def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole", "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/", "bigolive": "https://www.smile.one/sg/merchant/bigo/checkrole"}
    if game_code_for_smileone not in endpoints: return {"status": "error", "message": f"Game '{game_code_for_smileone}' not configured for SmileOne."}
    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends", "honkaistarrail": "https://www.smile.one/br/merchant/honkai", "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike", "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic", "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace", "bigolive": "https://www.smile.one/sg/merchant/bigo"}
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, f"https://www.smile.one/merchant/{game_code_for_smileone}")
    pid_to_use = specific_smileone_pid
    if not pid_to_use:
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" }
        default_pids_map = {"mobilelegends": os.environ.get("SMILE_ONE_PID_MLBB_DEFAULT", "25"), "honkaistarrail": os.environ.get("SMILE_ONE_PID_HSR_DEFAULT", "18356"), "bloodstrike": os.environ.get("SMILE_ONE_PID_BLOODSTRIKE", "20294"), "ragnarokmclassic": os.environ.get("SMILE_ONE_PID_ROM_DEFAULT", "23026"), "bigolive": os.environ.get("SMILE_ONE_PID_BIGO", "20580")}
        pid_to_use = love_deepspace_pids_map.get(str(server_id)) if game_code_for_smileone == "loveanddeepspace" else default_pids_map.get(game_code_for_smileone)
    if pid_to_use is None: return {"status": "error", "message": f"Product ID (PID) could not be resolved for '{game_code_for_smileone}'."}
    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code_for_smileone == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace", "bloodstrike"]: params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bigolive": params.update({"uid": uid, "product": "bigosg"})
    logging.info(f"Sending SmileOne: Game='{game_code_for_smileone}', URL='{url}', PID='{pid_to_use}', Params={params}")
    raw_text = ""
    try:
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status(); raw_text = response.text
        logging.info(f"SmileOne Raw Response (Game: {game_code_for_smileone}, UID:{uid}): {raw_text}")
        data = response.json(); logging.info(f"SmileOne Parsed JSON (Game: {game_code_for_smileone}): {data}")
        if data.get("code") == 200:
            name_key = "username" if game_code_for_smileone == "mobilelegends" else "message" if game_code_for_smileone == "bigolive" else "nickname"
            username = data.get(name_key)
            if not username or not isinstance(username, str) or not username.strip():
                for alt_key in ["username", "nickname", "role_name", "name", "char_name", "message"]:
                    if alt_key == name_key: continue
                    username = data.get(alt_key)
                    if username and isinstance(username, str) and username.strip(): break
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            if game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]: return {"status": "success", "message": "Account Verified (Username N/A from API)"}
            return {"status": "error", "message": "Username not found in API response (Code 200)"}
        return {"status": "error", "message": data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))}
    except ValueError:
        if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
            try:
                start_idx = raw_text.find("<span class=\"name\">") + len("<span class=\"name\">"); end_idx = raw_text.find("</span>", start_idx)
                if start_idx > len("<span class=\"name\">") -1 and end_idx != -1:
                    username_from_html = raw_text[start_idx:end_idx].strip()
                    if username_from_html: logging.info(f"Parsed username '{username_from_html}' from L&D HTML."); return {"status": "success", "username": username_from_html}
            except Exception as ex_parse: logging.error(f"HTML parse error for L&D: {ex_parse}")
        logging.error(f"JSON Parse Error (SmileOne {game_code_for_smileone}). Raw: {raw_text}")
        return {"status": "error", "message": "Invalid API response format (Not JSON)"}
    except requests.Timeout: logging.warning(f"API Timeout (SmileOne {game_code_for_smileone})"); return {"status": "error", "message": "API Request Timed Out"}
    except requests.RequestException as e: logging.error(f"API Connection Error (SmileOne {game_code_for_smileone}): {e}"); return {"status": "error", "message": f"API Connection Error (Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp: logging.exception(f"Unexpected error in SmileOne API call for {game_code_for_smileone}: {e_unexp}"); return {"status": "error", "message": "Unexpected server error (SmileOne)"}

def check_identityv_api(server_frontend_key, roleid):
    server_code = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code: return {"status": "error", "message": "Invalid server for Identity V."}
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    params = {"roleid": roleid, "timestamp": int(time.time() * 1000), "traceid": str(uuid.uuid4()), "deviceid": os.environ.get("NETEASE_DEVICE_ID"), **NETEASE_IDV_STATIC_PARAMS}
    current_headers = NETEASE_IDV_HEADERS.copy(); current_headers["X-TASK-ID"] = f"transid={params['traceid']},uni_transaction_id=default"
    logging.info(f"Sending Netease IDV: URL='{url}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10)
        raw_text = response.text; logging.info(f"Netease IDV Raw Response (Server: {server_frontend_key}, Role: {roleid}): {raw_text}")
        data = response.json(); logging.info(f"Netease IDV Parsed JSON: {data}")
        api_code = data.get("code"); api_msg = (data.get("message", "") or data.get("msg", "")).strip()
        if api_code == "0000":
            username = data.get("data", {}).get("rolename")
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            return {"status": "success", "message": "Role Verified"} if "ok" in api_msg.lower() or "success" in api_msg.lower() else {"status": "error", "message": f"Player found, but username unavailable ({api_msg or 'No details'})"}
        if "role not exist" in api_msg.lower() or api_code == "40004": return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details'}, Code: {api_code})"}
    except ValueError: logging.error(f"JSON Parse Error (IDV). Raw: {raw_text}"); return {"status": "error", "message": "Netease API check potentially blocked."}
    except requests.Timeout: logging.warning(f"API Timeout (IDV)"); return {"status": "error", "message": "API Request Timed Out (IDV)"}
    except requests.RequestException as e: logging.error(f"API Connection Error (IDV): {e}"); return {"status": "error", "message": f"Netease API Connection Error"}
    except Exception as e_unexp: logging.exception(f"Unexpected error in IDV API call: {e_unexp}"); return {"status": "error", "message": "Unexpected server error (IDV)"}

def check_razer_api(game_slug, user_id, server_id_frontend_key):
    api_details = {"genshin-impact": {"url_template": RAZER_GOLD_GENSHIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_GENSHIN_HEADERS, "server_map": None, "name": "Genshin Impact"}, "zenless-zone-zero": {"url_template": RAZER_GOLD_ZZZ_API_URL_TEMPLATE, "headers": RAZER_GOLD_ZZZ_HEADERS, "server_map": RAZER_ZZZ_SERVER_ID_MAP, "name": "Zenless Zone Zero"}, "ragnarok-origin": {"url_template": RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_RO_ORIGIN_HEADERS, "server_map": None, "name": "Ragnarok Origin"}, "snowbreak": {"url_template": RAZER_GOLD_SNOWBREAK_API_URL_TEMPLATE, "headers": RAZER_GOLD_SNOWBREAK_HEADERS, "server_map": RAZER_SNOWBREAK_SERVER_ID_MAP, "name": "Snowbreak"}}
    if game_slug not in api_details: return {"status": "error", "message": f"Razer API config not found for: {game_slug}"}
    config = api_details[game_slug]; api_server_id_param_value = None
    if config["server_map"]:
        api_server_id_param_value = config["server_map"].get(server_id_frontend_key)
        if not api_server_id_param_value: return {"status": "error", "message": f"Invalid server key for {config['name']}: '{server_id_frontend_key}'"}
    elif game_slug in ["genshin-impact", "ragnarok-origin"]: api_server_id_param_value = server_id_frontend_key
    url = config["url_template"].format(user_id=user_id)
    params = {"serverId": api_server_id_param_value} if api_server_id_param_value else {}
    logging.info(f"Sending Razer {config['name']}: URL='{url}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(url, params=params, headers=config["headers"], timeout=10)
        raw_text = response.text; logging.info(f"Razer {config['name']} Raw Response: {raw_text}")
        data = response.json(); logging.info(f"Razer {config['name']} Parsed JSON: {data}")
        if response.status_code == 200:
            username = data.get("username") or data.get("name") if game_slug != "ragnarok-origin" else data.get("roles", [{}])[0].get("Name") if "roles" in data and data["roles"] else None
            if username and isinstance(username, str) and username.strip(): return {"status": "success", "username": username.strip()}
            if data.get("code") == 77003: return {"status": "error", "message": f"Invalid User ID or Server ({config['name']})"}
            if data.get("code") == 0: return {"status": "success", "message": f"Account Verified ({config['name']})"}
            return {"status": "error", "message": data.get("message", "Unknown success response format")}
        return {"status": "error", "message": data.get("message", f"Razer API HTTP Error: {response.status_code}")}
    except ValueError: logging.error(f"JSON Parse Error (Razer {config['name']}). Raw: {raw_text}"); return {"status": "error", "message": f"Invalid API response (Razer)"}
    except requests.Timeout: logging.warning(f"API Timeout (Razer {config['name']})"); return {"status": "error", "message": f"API Request Timed Out (Razer)"}
    except requests.RequestException as e: logging.error(f"API Connection Error (Razer {config['name']}): {e}"); return {"status": "error", "message": f"Razer API Connection Error"}
    except Exception as e_unexp: logging.exception(f"Unexpected error in Razer API call for {config['name']}: {e_unexp}"); return {"status": "error", "message": f"Unexpected server error (Razer)"}

def check_nuverse_rox_api(role_id):
    params = {"tab": "purchase", "aid": NUVERSE_ROX_AID, "role_id": role_id}
    current_headers = NUVERSE_ROX_HEADERS.copy()
    tea_payload_data = {"role_id": role_id, "user_unique_id": None, "environment": "online", "payment_channel": "out_pay_shop", "pay_way": "out_app_pay", "aid": NUVERSE_ROX_AID, "session_id": str(uuid.uuid4()), "page_instance":"game", "geo":"SG", "url": f"https://pay.nvsgames.com/topup/{NUVERSE_ROX_AID}/sg-en", "language":"en", "x-scene":0, "req_id": str(uuid.uuid4()), "timestamp": int(time.time() * 1000)}
    current_headers["x-tea-payload"] = json.dumps(tea_payload_data)
    logging.info(f"Sending Nuverse ROX: URL='{NUVERSE_ROX_VALIDATE_URL}', Params={params}")
    try:
        response = requests.get(NUVERSE_ROX_VALIDATE_URL, params=params, headers=current_headers, timeout=10)
        data = response.json()
        if data.get("code") == 0 and data.get("message", "").lower() == "success":
            if "data" in data and data["data"]:
                role_info = data["data"][0]; username = role_info.get("role_name"); server_name = role_info.get("server_name")
                if username: return {"status": "success", "username": username.strip(), "server_name_from_api": server_name}
                return {"status": "success", "message": "Role ID Verified", "server_name_from_api": server_name}
            return {"status": "error", "message": "Role ID not found"}
        error_message = data.get("message", "Unknown error")
        if data.get("code") == 20012: error_message = "Invalid Role ID (Nuverse)"
        return {"status": "error", "message": error_message}
    except Exception as e: logging.error(f"Error in Nuverse ROX API call: {e}"); return {"status": "error", "message": "API Error (Nuverse)"}

def check_elitedias_msa_api(role_id):
    payload = {"game": ELITEDIAS_MSA_GAME_ID, "userid": str(role_id)}
    logging.info(f"Sending EliteDias MSA: URL='{ELITEDIAS_MSA_VALIDATE_URL}', Payload='{json.dumps(payload)}'")
    try:
        response = requests.post(ELITEDIAS_MSA_VALIDATE_URL, json=payload, headers=ELITEDIAS_MSA_HEADERS, timeout=12)
        data = response.json()
        if response.status_code == 200 and data.get("valid") == "valid":
            username = data.get("username") or data.get("nickname") or data.get("name")
            server_name = MSA_SERVER_ID_TO_NAME_MAP.get(str(data.get("serverid")), f"Server {data.get('serverid')}")
            if username: return {"status": "success", "username": username.strip(), "server_name_from_api": server_name}
            return {"status": "success", "message": "Role ID Verified.", "server_name_from_api": server_name}
        error_message = data.get("message", "Invalid Role ID (EliteDias).")
        return {"status": "error", "message": error_message}
    except Exception as e: logging.error(f"Error in EliteDias MSA API call: {e}"); return {"status": "error", "message": "API Error (EliteDias)"}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True)
