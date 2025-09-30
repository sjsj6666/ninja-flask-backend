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
from bs4 import BeautifulSoup
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
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_SNOWBREAK_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/seasun-games-snowbreak-containment-zone/users/{user_id}"
RAZER_GOLD_SNOWBREAK_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_SNOWBREAK_SERVER_ID_MAP = {"sea": "215","asia": "225","americas": "235","europe": "245"}
NUVERSE_ROX_VALIDATE_URL = "https://pay.nvsgames.com/web/payment/validate"
NUVERSE_ROX_AID = "3402"
NUVERSE_ROX_HEADERS = {"User-Agent": "Mozilla/5.0"}

ELITEDIAS_CHECKID_URL = "https://api.elitedias.com/checkid"
ELITEDIAS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-SG,en;q=0.9",
    "Content-Type": "application/json; charset=utf-8",
    "Origin": "https://elitedias.com",
    "Referer": "https://elitedias.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}
BIGO_NATIVE_VALIDATE_URL = "https://mobile.bigo.tv/pay-bigolive-tv/quicklyPay/getUserDetail"
BIGO_NATIVE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*",
    "Origin": "https://www.gamebar.gg",
    "Referer": "https://www.gamebar.gg/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site"
}
# NEW: PUBG Mobile API constants
PUBGM_VALIDATE_URL = "https://www.enjoygm.com/portal/supplier/api/pubg/userinfo"
PUBGM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept": "*/*",
    "Referer": "https://www.enjoygm.com/top-up/pubg-mobile",
    "X-Requested-With": "XMLHttpRequest"
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
    if fallback_result.get("status") == "success":
        fallback_result['region'] = 'N/A'
    return fallback_result

def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole", "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole", "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/"}
    if game_code_for_smileone not in endpoints: return {"status": "error", "message": f"Game '{game_code_for_smileone}' not configured for SmileOne."}
    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = {"mobilelegends": "https://www.smile.one/merchant/mobilelegends", "honkaistarrail": "https://www.smile.one/br/merchant/honkai", "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike", "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic", "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace"}
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, f"https://www.smile.one/merchant/{game_code_for_smileone}")
    pid_to_use = specific_smileone_pid
    if not pid_to_use:
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" }
        default_pids_map = {"mobilelegends": os.environ.get("SMILE_ONE_PID_MLBB_DEFAULT", "25"), "honkaistarrail": os.environ.get("SMILE_ONE_PID_HSR_DEFAULT", "18356"), "bloodstrike": "20295", "ragnarokmclassic": os.environ.get("SMILE_ONE_PID_ROM_DEFAULT", "23026")}
        pid_to_use = love_deepspace_pids_map.get(str(server_id)) if game_code_for_smileone == "loveanddeepspace" else default_pids_map.get(game_code_for_smileone)
    if pid_to_use is None: return {"status": "error", "message": f"Product ID (PID) could not be resolved for '{game_code_for_smileone}'."}
    params = {"pid": pid_to_use, "checkrole": "1"}
    
    if game_code_for_smileone == "mobilelegends":
        params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone == "bloodstrike":
        params.update({"uid": uid, "sid": "-1"})
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace"]:
        params.update({"uid": uid, "sid": server_id})

    logging.info(f"Sending SmileOne: Game='{game_code_for_smileone}', URL='{url}', PID='{pid_to_use}', Params={params}")
    raw_text = ""
    try:
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10, verify=certifi.where())
        response.raise_for_status(); raw_text = response.text
        data = response.json()
        if data.get("code") == 200:
            name_key = "username" if game_code_for_smileone == "mobilelegends" else "nickname"
            username = data.get(name_key)
            if username and isinstance(username, str) and username.strip(): return {"status": "success", "username": username.strip()}
            if game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]: return {"status": "success", "message": "Account Verified (Username N/A from API)"}
            return {"status": "error", "message": "Username not found in API response (Code 200)"}
        
        error_message = data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))
        if "não existe" in error_message:
            error_message = "Invalid User ID."
        return {"status": "error", "message": error_message}

    except ValueError:
        if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
            try:
                start_idx = raw_text.find("<span class=\"name\">") + len("<span class=\"name\">"); end_idx = raw_text.find("</span>", start_idx)
                if start_idx > len("<span class=\"name\">") -1 and end_idx != -1:
                    username_from_html = raw_text[start_idx:end_idx].strip()
                    if username_from_html: return {"status": "success", "username": username_from_html}
            except Exception as ex_parse: logging.error(f"HTML parse error for L&D: {ex_parse}")
        return {"status": "error", "message": "Invalid API response format (Not JSON)"}
    except requests.RequestException as e: return {"status": "error", "message": f"API Connection Error (Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp: return {"status": "error", "message": "Unexpected server error (SmileOne)"}

def check_identityv_api(server_frontend_key, roleid):
    server_code = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code: return {"status": "error", "message": "Invalid server for Identity V."}
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    params = {"roleid": roleid, "timestamp": int(time.time() * 1000), "traceid": str(uuid.uuid4()), "deviceid": os.environ.get("NETEASE_DEVICE_ID"), **NETEASE_IDV_STATIC_PARAMS}
    current_headers = NETEASE_IDV_HEADERS.copy(); current_headers["X-TASK-ID"] = f"transid={params['traceid']},uni_transaction_id=default"
    logging.info(f"Sending Netease IDV: URL='{url}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10, verify=certifi.where())
        raw_text = response.text
        data = response.json()
        api_code = data.get("code"); api_msg = (data.get("message", "") or data.get("msg", "")).strip()
        if api_code == "0000":
            username = data.get("data", {}).get("rolename")
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            return {"status": "success", "message": "Role Verified"} if "ok" in api_msg.lower() or "success" in api_msg.lower() else {"status": "error", "message": f"Player found, but username unavailable ({api_msg or 'No details'})"}
        if "role not exist" in api_msg.lower() or api_code == "40004": return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details'}, Code: {api_code})"}
    except ValueError: return {"status": "error", "message": "Netease API check potentially blocked."}
    except requests.RequestException: return {"status": "error", "message": f"Netease API Connection Error"}
    except Exception as e_unexp: return {"status": "error", "message": "Unexpected server error (IDV)"}

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
    try:
        response = requests.get(url, params=params, headers=config["headers"], timeout=10, verify=certifi.where())
        data = response.json()
        if response.status_code == 200:
            username = data.get("username") or data.get("name") if game_slug != "ragnarok-origin" else data.get("roles", [{}])[0].get("Name") if "roles" in data and data["roles"] else None
            if username and isinstance(username, str) and username.strip(): return {"status": "success", "username": username.strip()}
            if data.get("code") == 77003: return {"status": "error", "message": f"Invalid User ID or Server ({config['name']})"}
            if data.get("code") == 0: return {"status": "success", "message": f"Account Verified ({config['name']})"}
            return {"status": "error", "message": data.get("message", "Unknown success response format")}
        return {"status": "error", "message": data.get("message", f"Razer API HTTP Error: {response.status_code}")}
    except ValueError: return {"status": "error", "message": f"Invalid API response (Razer)"}
    except requests.RequestException: return {"status": "error", "message": f"Razer API Connection Error"}
    except Exception as e_unexp: return {"status": "error", "message": f"Unexpected server error (Razer)"}

def check_nuverse_rox_api(role_id):
    params = {"tab": "purchase", "aid": NUVERSE_ROX_AID, "role_id": role_id}
    current_headers = NUVERSE_ROX_HEADERS.copy()
    tea_payload_data = {"role_id": role_id, "user_unique_id": None, "environment": "online", "payment_channel": "out_pay_shop", "pay_way": "out_app_pay", "aid": NUVERSE_ROX_AID, "session_id": str(uuid.uuid4()), "page_instance":"game", "geo":"SG", "url": f"https://pay.nvsgames.com/topup/{NUVERSE_ROX_AID}/sg-en", "language":"en", "x-scene":0, "req_id": str(uuid.uuid4()), "timestamp": int(time.time() * 1000)}
    current_headers["x-tea-payload"] = json.dumps(tea_payload_data)
    logging.info(f"Sending Nuverse ROX: URL='{NUVERSE_ROX_VALIDATE_URL}', Params={params}")
    try:
        response = requests.get(NUVERSE_ROX_VALIDATE_URL, params=params, headers=current_headers, timeout=10, verify=certifi.where())
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
    except Exception as e: return {"status": "error", "message": "API Error (Nuverse)"}

def check_elitedias_api(game_code_for_api, role_id):
    payload = {"game": game_code_for_api, "userid": str(role_id)}
    logging.info(f"Sending EliteDias API: URL='{ELITEDIAS_CHECKID_URL}', Payload='{json.dumps(payload)}'")
    try:
        response = requests.post(ELITEDIAS_CHECKID_URL, json=payload, headers=ELITEDIAS_HEADERS, timeout=12, verify=certifi.where())
        data = response.json()
        
        if response.status_code == 200 and data.get("valid") == "valid":
            username = data.get("name") or data.get("username") or data.get("nickname")
            if username and username.lower() != 'na':
                return {"status": "success", "username": username.strip()}
            return {"status": "success", "message": "Role ID Verified."}
            
        error_message = data.get("message", f"Invalid Role ID ({game_code_for_api}).")
        return {"status": "error", "message": error_message}
    except requests.RequestException as e:
        logging.error(f"EliteDias API connection error for {game_code_for_api}: {e}")
        return {"status": "error", "message": f"API Connection Error (EliteDias)"}
    except Exception as e:
        logging.error(f"Unexpected error in EliteDias check for {game_code_for_api}: {e}")
        return {"status": "error", "message": "API Error (EliteDias)"}

def check_bigo_native_api(uid):
    params = {"isFromApp": "0", "bigoId": uid}
    logging.info(f"Sending Bigo Native API: URL='{BIGO_NATIVE_VALIDATE_URL}', Params={params}")
    try:
        response = requests.get(BIGO_NATIVE_VALIDATE_URL, params=params, headers=BIGO_NATIVE_HEADERS, timeout=10, verify=certifi.where())
        response.raise_for_status()
        data = response.json()
        if data.get("result") == 0 and "data" in data and data["data"].get("nick_name"):
            username = data["data"]["nick_name"]
            return {"status": "success", "username": username.strip()}
        else:
            error_message = data.get("errorMsg", "Invalid Bigo ID or API error.")
            return {"status": "error", "message": error_message}
    except requests.RequestException as e:
        logging.error(f"Bigo Native API connection error: {e}")
        return {"status": "error", "message": "API Connection Error (Bigo)"}
    except Exception as e:
        logging.error(f"Unexpected error in Bigo Native check: {e}")
        return {"status": "error", "message": "API Error (Bigo)"}

# NEW: PUBG Mobile API validation function
def check_enjoygm_pubg_api(uid):
    params = {"account": uid}
    logging.info(f"Sending EnjoyGM PUBG API: URL='{PUBGM_VALIDATE_URL}', Params={params}")
    try:
        response = requests.get(PUBGM_VALIDATE_URL, params=params, headers=PUBGM_HEADERS, timeout=10, verify=certifi.where())
        response.raise_for_status()
        outer_data = response.json()

        if outer_data.get("code") == 200 and outer_data.get("data"):
            inner_data_str = outer_data["data"]
            inner_data = json.loads(inner_data_str) # Parse the inner JSON string

            if inner_data.get("exist") == 1 and inner_data.get("accountName"):
                username = inner_data["accountName"]
                return {"status": "success", "username": username.strip()}
            else:
                return {"status": "error", "message": "Invalid Player ID."}
        else:
            return {"status": "error", "message": outer_data.get("message", "Invalid Player ID.")}

    except requests.RequestException as e:
        logging.error(f"EnjoyGM PUBG API connection error: {e}")
        return {"status": "error", "message": "API Connection Error (PUBG)"}
    except json.JSONDecodeError as e:
        logging.error(f"EnjoyGM PUBG API JSON decode error: {e}")
        return {"status": "error", "message": "Invalid API response format (PUBG)."}
    except Exception as e:
        logging.error(f"Unexpected error in EnjoyGM PUBG check: {e}")
        return {"status": "error", "message": "API Error (PUBG)"}

# --- Flask Routes ---

@app.route('/')
def home():
    return "NinjaTopUp API Backend is Live!"

@app.route('/sitemap.xml')
def generate_sitemap():
    try:
        logging.info("Generating sitemap...")
        response = supabase.from_('games').select('slug').eq('is_active', True).execute()
        games = response.data
        
        static_pages = [
            '/', '/about.html', '/contact.html', '/reviews.html',
            '/past-transactions.html', '/faq.html', '/login.html', '/signup.html'
        ]

        xml_parts = []
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

        for page in static_pages:
            xml_parts.append('  <url>')
            xml_parts.append(f'    <loc>{BASE_URL}{page}</loc>')
            xml_parts.append('    <changefreq>weekly</changefreq>')
            xml_parts.append('    <priority>0.8</priority>')
            xml_parts.append('  </url>')

        for game in games:
            game_slug = game.get('slug')
            if game_slug:
                xml_parts.append('  <url>')
                xml_parts.append(f'    <loc>{BASE_URL}/topup.html?game={game_slug}</loc>')
                xml_parts.append('    <changefreq>monthly</changefreq>')
                xml_parts.append('    <priority>0.9</priority>')
                xml_parts.append('  </url>')
        
        xml_parts.append('</urlset>')
        
        xml_sitemap = "\n".join(xml_parts)
        logging.info("Sitemap generated successfully.")
        return Response(xml_sitemap, mimetype='application/xml')

    except Exception as e:
        logging.error(f"Sitemap generation error: {e}")
        return jsonify({"error": "Could not generate sitemap"}), 500

@app.route('/create-paynow-qr', methods=['POST'])
def create_paynow_qr():
    data = request.get_json()
    if not data or 'amount' not in data or 'order_id' not in data:
        return jsonify({'error': 'Amount and order_id are required.'}), 400
    try:
        amount = f"{float(data['amount']):.2f}"
        order_id = str(data['order_id'])
        paynow_uen = os.environ.get('PAYNOW_UEN')
        company_name = os.environ.get('PAYNOW_COMPANY_NAME')
        if not paynow_uen or not company_name:
            raise ValueError("PAYNOW_UEN and PAYNOW_COMPANY_NAME must be set.")
        maybank_url = "https://sslsecure.maybank.com.sg/scripts/mbb_qrcode/mbb_qrcode.jsp"
        expiry_date = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
        params = {'proxyValue': paynow_uen, 'proxyType': 'UEN', 'merchantName': company_name, 'amount': amount, 'reference': order_id, 'amountInd': 'N', 'expiryDate': expiry_date, 'rnd': random.random()}
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15', 'Referer': 'https://sslsecure.maybank.com.sg/'}
        response = requests.get(maybank_url, params=params, headers=headers, timeout=20, verify=True)
        response.raise_for_status()
        if 'image/png' in response.headers.get('Content-Type', ''):
            encoded_string = base64.b64encode(response.content).decode('utf-8')
            qr_code_data_uri = f"data:image/png;base64,{encoded_string}"
            return jsonify({'qr_code_data': qr_code_data_uri, 'message': 'QR code generated successfully.'})
        return jsonify({'error': 'Invalid response from QR service.'}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Could not connect to the QR code generation service."}), 504
    except Exception as e:
        logging.error(f"QR proxy error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/check-ml-region', methods=['POST'])
def check_ml_region():
    data = request.get_json()
    if not data or 'userId' not in data or 'zoneId' not in data:
        return jsonify({'status': 'error', 'message': 'User ID and Zone ID are required.'}), 400
    user_id = data['userId']
    zone_id = data['zoneId']
    result = perform_ml_check(user_id, zone_id)
    return jsonify(result), 200

@app.route('/get-rates', methods=['GET'])
def get_rates():
    try:
        response = supabase.table('site_settings').select('setting_value').eq('setting_key', 'exchangerate_api_key').single().execute()
        API_KEY = response.data['setting_value']
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/SGD"
        api_response = requests.get(url, timeout=10, verify=certifi.where())
        api_response.raise_for_status()
        data = api_response.json()
        if data.get('result') == 'success':
            return jsonify(data.get('conversion_rates', {}))
        return jsonify({"error": "API error"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    game_lower = game_slug_from_frontend.lower()
    if not uid:
        return jsonify({"status": "error", "message": "User ID/Role ID is required."}), 400

    smileone_games_map = {
        "honkai-star-rail": "honkaistarrail",
        "ragnarok-m-classic": "ragnarokmclassic", "love-and-deepspace": "loveanddeepspace"
    }
    razer_games_map = {
        "genshin-impact": "genshin-impact", "zenless-zone-zero": "zenless-zone-zero",
        "ragnarok-origin": "ragnarok-origin", "snowbreak-containment-zone": "snowbreak"
    }
    elitedias_games_map = {
        "metal-slug-awakening": "metal_slug",
        "arena-breakout": "arena_breakout"
    }
    game_handlers = {
        "pubg-mobile": lambda: check_enjoygm_pubg_api(uid),
        "bigo-live": lambda: check_bigo_native_api(uid),
        "bloodstrike": lambda: check_smile_one_api("bloodstrike", uid),
        "ragnarok-x-next-generation": lambda: check_nuverse_rox_api(uid),
        "mobile-legends-sg": lambda: perform_ml_check(uid, server_id),
        "mobile-legends": lambda: perform_ml_check(uid, server_id),
        "identity-v": lambda: check_identityv_api(server_id, uid),
    }

    if game_lower in razer_games_map:
        handler = lambda: check_razer_api(razer_games_map[game_lower], uid, server_id)
    elif game_lower in smileone_games_map:
        handler = lambda: check_smile_one_api(smileone_games_map[game_lower], uid, server_id)
    elif game_lower in elitedias_games_map:
        handler = lambda: check_elitedias_api(elitedias_games_map[game_lower], uid)
    else:
        handler = game_handlers.get(game_lower)

    if handler:
        result = handler()
    else:
        result = {"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}
    
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
