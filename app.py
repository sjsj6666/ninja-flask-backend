from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid # For Netease traceid
import json # For Nuverse x-tea-payload and Gamepoint

app = Flask(__name__)

# Define allowed origins
allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://coxx.netlify.app"
]
CORS(app, resources={r"/check-id/*": {"origins": allowed_origins}}, supports_credentials=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 5000))


# --- Smile One Config ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "YOUR_SMILE_ONE_COOKIE_PLACEHOLDER_IF_ANY")
}

# --- Netease Identity V Config ---
NETEASE_IDV_BASE_URL_TEMPLATE = "https://pay.neteasegames.com/gameclub/identityv/{server_code}/login-role"
NETEASE_IDV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pay.neteasegames.com/identityv/topup",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
}
NETEASE_IDV_STATIC_PARAMS = { "gc_client_version": "1.9.111", "client_type": "gameclub" }
IDV_SERVER_CODES = { "asia": "2001", "na-eu": "2011" }

# --- Razer Gold API Config ---
RAZER_GOLD_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
}
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact"
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero"
RAZER_ZZZ_SERVER_ID_MAP = {"prod_official_asia": "prod_gf_jp","prod_official_usa": "prod_gf_us","prod_official_eur": "prod_gf_eu","prod_official_cht": "prod_gf_sg"}
RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin"
RAZER_GOLD_SNOWBREAK_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/seasun-games-snowbreak-containment-zone/users/{user_id}"
RAZER_GOLD_SNOWBREAK_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_SNOWBREAK_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/snowbreak-containment-zone"
RAZER_SNOWBREAK_SERVER_ID_MAP = {"sea": "215","asia": "225","americas": "235","europe": "245"}


# --- Nuverse API Config (ROX) ---
NUVERSE_ROX_VALIDATE_URL = "https://pay.nvsgames.com/web/payment/validate"
NUVERSE_ROX_AID = "3402"
NUVERSE_ROX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "*/*",
    "Referer": f"https://pay.nvsgames.com/topup/{NUVERSE_ROX_AID}/sg-en",
    "x-appid": NUVERSE_ROX_AID,
    "x-language": "en",
    "x-scene": "0",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
}

# --- Gamepoint.club Metal Slug: Awakening Config ---
GAMEPOINT_MSA_VALIDATE_URL = "https://gamepoint.club/product2.aspx/ValidateUserAsync"
GAMEPOINT_MSA_PRODUCT_ID = "147" # Static Product ID for MSA on Gamepoint
GAMEPOINT_MSA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json; charset=utf-8",
    "Origin": "https://gamepoint.club",
    "Referer": "https://gamepoint.club/metal-slug-ruby", # Or your specific product page on gamepoint
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"
}

# --- API Check Functions ---

def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole",
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/",
        "bigolive": "https://www.smile.one/sg/merchant/bigo/checkrole"
    }
    if game_code_for_smileone not in endpoints:
        return {"status": "error", "message": f"Game '{game_code_for_smileone}' not configured for SmileOne."}

    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai",
        "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike",
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace",
        "bigolive": "https://www.smile.one/sg/merchant/bigo"
    }
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, f"https://www.smile.one/merchant/{game_code_for_smileone}")

    pid_to_use = specific_smileone_pid
    if not pid_to_use:
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" }
        default_pids_map = {
            "mobilelegends": os.environ.get("SMILE_ONE_PID_MLBB_DEFAULT", "25"),
            "honkaistarrail": os.environ.get("SMILE_ONE_PID_HSR_DEFAULT", "18356"),
            "bloodstrike": os.environ.get("SMILE_ONE_PID_BLOODSTRIKE", "20294"),
            "ragnarokmclassic": os.environ.get("SMILE_ONE_PID_ROM_DEFAULT", "23026"),
            "bigolive": os.environ.get("SMILE_ONE_PID_BIGO", "20580")
        }
        pid_to_use = love_deepspace_pids_map.get(str(server_id)) if game_code_for_smileone == "loveanddeepspace" else default_pids_map.get(game_code_for_smileone)

    if pid_to_use is None: return {"status": "error", "message": f"Product ID (PID) could not be resolved for '{game_code_for_smileone}'."}

    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code_for_smileone == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace"]: params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bloodstrike": params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bigolive": params.update({"uid": uid, "product": "bigosg"})

    logging.info(f"Sending SmileOne: Game='{game_code_for_smileone}', URL='{url}', PID='{pid_to_use}', Params={params}")
    raw_text = ""
    try:
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        logging.info(f"SmileOne Raw Response (Game: {game_code_for_smileone}, UID:{uid}): {raw_text}")
        data = response.json()
        logging.info(f"SmileOne Parsed JSON (Game: {game_code_for_smileone}): {data}")

        if data.get("code") == 200:
            name_key = "username" if game_code_for_smileone == "mobilelegends" else \
                       "message" if game_code_for_smileone == "bigolive" else "nickname"
            username = data.get(name_key)
            if not username or not isinstance(username, str) or not username.strip():
                for alt_key in ["username", "nickname", "role_name", "name", "char_name", "message"]:
                    if alt_key == name_key: continue
                    username = data.get(alt_key)
                    if username and isinstance(username, str) and username.strip(): break
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            if game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]:
                 return {"status": "success", "message": "Account Verified (Username N/A from API)"}
            return {"status": "error", "message": "Username not found in API response (Code 200)"}
        return {"status": "error", "message": data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))}
    except ValueError:
        if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
            try:
                start_idx = raw_text.find("<span class=\"name\">") + len("<span class=\"name\">")
                end_idx = raw_text.find("</span>", start_idx)
                if start_idx > len("<span class=\"name\">") -1 and end_idx != -1:
                    username_from_html = raw_text[start_idx:end_idx].strip()
                    if username_from_html:
                        logging.info(f"Successfully parsed username '{username_from_html}' from L&D HTML fallback.")
                        return {"status": "success", "username": username_from_html}
            except Exception as ex_parse: logging.error(f"HTML parse error for L&D: {ex_parse}")
        logging.error(f"JSON Parse Error (SmileOne {game_code_for_smileone}). Raw: {raw_text}")
        return {"status": "error", "message": "Invalid API response format (Not JSON)"}
    except requests.Timeout:
        logging.warning(f"API Timeout (SmileOne {game_code_for_smileone})")
        return {"status": "error", "message": "API Request Timed Out"}
    except requests.RequestException as e:
        logging.error(f"API Connection Error (SmileOne {game_code_for_smileone}): {e}")
        return {"status": "error", "message": f"API Connection Error (Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp:
        logging.exception(f"Unexpected error during SmileOne API call for {game_code_for_smileone}: {e_unexp}")
        return {"status": "error", "message": "Unexpected server error (SmileOne)"}

def check_identityv_api(server_frontend_key, roleid):
    server_code = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code: return {"status": "error", "message": "Invalid server specified for Identity V."}

    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    params = {
        "roleid": roleid, "timestamp": int(time.time() * 1000),
        "traceid": str(uuid.uuid4()),
        "deviceid": os.environ.get("NETEASE_DEVICE_ID", "YOUR_FALLBACK_NETEASE_DEVICE_ID_HERE"),
        **NETEASE_IDV_STATIC_PARAMS
    }
    current_headers = NETEASE_IDV_HEADERS.copy()
    current_headers["X-TASK-ID"] = f"transid={params['traceid']},uni_transaction_id=default"

    logging.info(f"Sending Netease IDV: URL='{url}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10)
        raw_text = response.text
        logging.info(f"Netease IDV Raw Response (Server: {server_frontend_key}, Role: {roleid}): {raw_text}")
        data = response.json()
        logging.info(f"Netease IDV Parsed JSON: {data}")
        api_code = data.get("code")
        api_msg = (data.get("message", "") or data.get("msg", "")).strip()

        if api_code == "0000":
            username = data.get("data", {}).get("rolename")
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            return {"status": "success", "message": "Role Verified (Username not provided by API)"} if "ok" in api_msg.lower() or "success" in api_msg.lower() else {"status": "error", "message": f"Player found, but username unavailable ({api_msg or 'No details from API'})"}
        if "role not exist" in api_msg.lower() or api_code == "40004":
            return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details from API'}, Code: {api_code})"}
    except ValueError:
        logging.error(f"JSON Parse Error (IDV). Status: {response.status_code if 'response' in locals() else 'N/A'}. Raw: {raw_text}")
        if 'response' in locals() and response.status_code >= 500: return {"status": "error", "message": "Netease Server Error (Remote)"}
        return {"status": "error", "message": "Netease API check potentially blocked or returned non-JSON."}
    except requests.Timeout:
        logging.warning(f"API Timeout (IDV {server_frontend_key}/{roleid})")
        return {"status": "error", "message": "API Request Timed Out (IDV)"}
    except requests.RequestException as e:
        logging.error(f"API Connection Error (IDV {server_frontend_key}/{roleid}): {e}")
        return {"status": "error", "message": f"Netease API Connection Error (Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp:
        logging.exception(f"Unexpected error during Identity V API call: {e_unexp}")
        return {"status": "error", "message": "Unexpected server error (IDV)"}

def check_razer_api(game_slug, user_id, server_id_frontend_key):
    api_details = {
        "genshin-impact": {"url_template": RAZER_GOLD_GENSHIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_GENSHIN_HEADERS, "server_map": None, "name": "Genshin Impact"},
        "zenless-zone-zero": {"url_template": RAZER_GOLD_ZZZ_API_URL_TEMPLATE, "headers": RAZER_GOLD_ZZZ_HEADERS, "server_map": RAZER_ZZZ_SERVER_ID_MAP, "name": "Zenless Zone Zero"},
        "ragnarok-origin": {"url_template": RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_RO_ORIGIN_HEADERS, "server_map": None, "name": "Ragnarok Origin"},
        "snowbreak": {"url_template": RAZER_GOLD_SNOWBREAK_API_URL_TEMPLATE, "headers": RAZER_GOLD_SNOWBREAK_HEADERS, "server_map": RAZER_SNOWBREAK_SERVER_ID_MAP, "name": "Snowbreak"}
    }
    if game_slug not in api_details: return {"status": "error", "message": f"Razer API configuration not found for game: {game_slug}"}

    config = api_details[game_slug]
    api_server_id_param_value = None

    if config["server_map"]:
        api_server_id_param_value = config["server_map"].get(server_id_frontend_key)
        if not api_server_id_param_value:
            return {"status": "error", "message": f"Invalid server configuration for {config['name']} using frontend key '{server_id_frontend_key}'"}
    elif game_slug in ["genshin-impact", "ragnarok-origin"]:
        api_server_id_param_value = server_id_frontend_key

    url = config["url_template"].format(user_id=user_id)
    params = {"serverId": api_server_id_param_value} if api_server_id_param_value else {}

    logging.info(f"Sending Razer {config['name']}: URL='{url}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(url, params=params, headers=config["headers"], timeout=10)
        raw_text = response.text
        logging.info(f"Razer {config['name']} Raw Response (UID:{user_id}, FrontendSrvKey:{server_id_frontend_key}, APISrvVal:{api_server_id_param_value}): {raw_text}")
        data = response.json()
        logging.info(f"Razer {config['name']} Parsed JSON: {data}")

        if response.status_code == 200:
            username = None
            if game_slug == "ragnarok-origin":
                if "roles" in data and isinstance(data["roles"], list) and data["roles"]:
                    username = data["roles"][0].get("Name")
            elif game_slug == "snowbreak":
                username = data.get("username")
            else:
                username = data.get("username") or data.get("name")

            if username and isinstance(username, str) and username.strip():
                return {"status": "success", "username": username.strip()}
            
            api_code = data.get("code")
            api_msg = data.get("message")
            if api_code == 77003 and api_msg == "Invalid game user credentials":
                 return {"status": "error", "message": f"Invalid User ID or Server ({config['name']})"}
            elif api_code == 0:
                alt_name = data.get("name") or data.get("data", {}).get("name")
                if alt_name and alt_name.strip(): return {"status": "success", "username": alt_name.strip()}
                return {"status": "success", "message": f"Account Verified (Razer {config['name']} - Nickname not directly available)"}
            return {"status": "error", "message": api_msg or f"Unknown success response format (Razer {config['name']})"}
        
        error_msg_from_api = data.get("message", f"Razer API HTTP Error ({config['name']}): {response.status_code}")
        return {"status": "error", "message": error_msg_from_api}
    except ValueError:
        logging.error(f"JSON Parse Error (Razer {config['name']}). Status: {response.status_code if 'response' in locals() else 'N/A'}. Raw: {raw_text}")
        if "<html" in raw_text.lower(): return {"status": "error", "message": f"Razer API check returned HTML, possibly blocked ({config['name']})"}
        return {"status": "error", "message": f"Invalid API response format (Razer {config['name']}, Status: {response.status_code if 'response' in locals() else 'N/A'})"}
    except requests.Timeout:
        logging.warning(f"API Timeout (Razer {config['name']})")
        return {"status": "error", "message": f"API Request Timed Out (Razer {config['name']})"}
    except requests.RequestException as e:
        logging.error(f"API Connection Error (Razer {config['name']}): {e}")
        return {"status": "error", "message": f"Razer API Connection Error ({config['name']}, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp:
        logging.exception(f"Unexpected error during Razer API call for {config['name']}: {e_unexp}")
        return {"status": "error", "message": f"Unexpected server error (Razer {config['name']})"}

def check_nuverse_rox_api(role_id):
    params = {
        "tab": "purchase",
        "aid": NUVERSE_ROX_AID,
        "role_id": role_id
    }
    current_headers = NUVERSE_ROX_HEADERS.copy()
    tea_payload_data = {
        "role_id": role_id, "user_unique_id": None, "environment": "online",
        "payment_channel": "out_pay_shop", "pay_way": "out_app_pay", "aid": NUVERSE_ROX_AID,
        "session_id": str(uuid.uuid4()), "page_instance":"game", "geo":"SG",
        "url": f"https://pay.nvsgames.com/topup/{NUVERSE_ROX_AID}/sg-en", "language":"en",
        "x-scene":0, "req_id": str(uuid.uuid4()), "timestamp": int(time.time() * 1000),
    }
    current_headers["x-tea-payload"] = json.dumps(tea_payload_data)
    logging.info(f"Sending Nuverse ROX: URL='{NUVERSE_ROX_VALIDATE_URL}', Params={params}")
    raw_text = ""
    try:
        response = requests.get(NUVERSE_ROX_VALIDATE_URL, params=params, headers=current_headers, timeout=10)
        raw_text = response.text
        logging.info(f"Nuverse ROX Raw Response (RoleID:{role_id}): {raw_text}")
        data = response.json()
        logging.info(f"Nuverse ROX Parsed JSON: {data}")

        if data.get("code") == 0 and data.get("message", "").lower() == "success":
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                role_info = data["data"][0]
                username = role_info.get("role_name")
                server_name = role_info.get("server_name")
                if username and username.strip():
                    return {"status": "success", "username": username.strip(), "server_name": server_name}
                return {"status": "success", "message": "Role ID Verified (Username not available)", "server_name": server_name}
            return {"status": "error", "message": "Role ID not found or invalid (No data)"}
        else:
            error_message = data.get("message", "Unknown error from Nuverse API")
            if data.get("code") == 20012: error_message = "Invalid Role ID (Nuverse)"
            return {"status": "error", "message": error_message}
    except ValueError:
        logging.error(f"JSON Parse Error (Nuverse ROX). Raw: {raw_text}")
        return {"status": "error", "message": "Invalid API response format (Nuverse ROX)"}
    except requests.Timeout:
        logging.warning(f"API Timeout (Nuverse ROX)")
        return {"status": "error", "message": "API Request Timed Out (Nuverse ROX)"}
    except requests.RequestException as e:
        logging.error(f"API Connection Error (Nuverse ROX): {e}")
        return {"status": "error", "message": f"API Connection Error (Nuverse ROX, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception as e_unexp:
        logging.exception(f"Unexpected error during Nuverse ROX API call: {e_unexp}")
        return {"status": "error", "message": "Unexpected server error (Nuverse ROX)"}

# --- Gamepoint MSA API Check Function (Simplified for existence check) ---
def check_gamepoint_msa_api(role_id_from_frontend, server_id_from_frontend=None): # server_id_from_frontend is now optional
    """
    Attempts to validate Metal Slug: Awakening Role ID via Gamepoint.club API.
    Sends PInput02 as empty if server_id_from_frontend is None or empty.
    """
    api_server_id_for_payload = "" # Default to empty for PInput02
    if server_id_from_frontend:
        # If you still want to map or use it, do it here.
        # For just existence check with PInput02 potentially empty, this can be simple.
        api_server_id_for_payload = str(server_id_from_frontend)


    payload = {
        "PProductIDN": GAMEPOINT_MSA_PRODUCT_ID,
        "PInput01": str(role_id_from_frontend),
        "PInput02": api_server_id_for_payload, # Send selected server or empty
        "PInput03": ""
    }
    logging.info(f"Sending Gamepoint MSA: URL='{GAMEPOINT_MSA_VALIDATE_URL}', Payload='{json.dumps(payload)}'") # Log full payload
    raw_text = ""
    try:
        response = requests.post(GAMEPOINT_MSA_VALIDATE_URL, json=payload, headers=GAMEPOINT_MSA_HEADERS, timeout=10)
        raw_text = response.text
        logging.info(f"Gamepoint MSA Raw Response (RoleID:{role_id_from_frontend}, ServerSent:{api_server_id_for_payload}): {raw_text}")
        data = response.json()
        logging.info(f"Gamepoint MSA Parsed JSON: {data}")

        if response.status_code == 200 and data and "d" in data:
            d_response = data["d"]
            # Check for successful validation based on API's success indicators
            if d_response.get("Status") == 5 and d_response.get("IsCompleted") is True and d_response.get("Exception") is None:
                validated_role_id = d_response.get("Result")
                if str(validated_role_id) == str(role_id_from_frontend):
                    # Since username/server name isn't directly in *this* response, return generic success.
                    return {"status": "success", "message": "Role ID Verified.", "username": None} # Username is not returned by this API
                else:
                    logging.warning(f"Gamepoint MSA: Role ID mismatch. Input: {role_id_from_frontend}, API Result: {validated_role_id}")
                    return {"status": "error", "message": "Unverified, please check your ID."} # Role ID mismatch
            else:
                # Handle cases where 'Status' is not 5 or there's an exception or IsCompleted is false
                error_msg = d_response.get("Result") if isinstance(d_response.get("Result"), str) else "Unverified, please check your ID."
                if d_response.get("Exception"):
                    error_msg = f"API Error: {d_response.get('Exception')}"
                logging.warning(f"Gamepoint MSA: Validation failed. API Response 'd': {d_response}")
                return {"status": "error", "message": error_msg}
        else:
            logging.warning(f"Gamepoint MSA: API request failed. HTTP Status: {response.status_code}, Raw: {raw_text[:500]}")
            return {"status": "error", "message": "Verification service unavailable."}

    except ValueError:
        logging.error(f"JSON Parse Error (Gamepoint MSA). Raw: {raw_text}")
        return {"status": "error", "message": "Invalid response from verification service."}
    except requests.Timeout:
        logging.warning(f"API Timeout (Gamepoint MSA)")
        return {"status": "error", "message": "Verification timed out."}
    except requests.RequestException as e:
        logging.error(f"API Connection Error (Gamepoint MSA): {e}")
        return {"status": "error", "message": "Could not connect to verification service."}
    except Exception as e_unexp:
        logging.exception(f"Unexpected error during Gamepoint MSA API call: {e_unexp}")
        return {"status": "error", "message": "Unexpected error during verification."}


# --- Flask Routes ---
@app.route('/')
def home():
    return "NinjaTopUp Validation Backend is Live!"

@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id): # server_id can be None
    game_lower = game_slug_from_frontend.lower()
    result = {}
    intended_region_display = None

    if not uid:
        return jsonify({"status": "error", "message": "User ID/Role ID is required."}), 400

    if game_lower == "metal-slug-awakening":
        if not uid.isdigit():
            return jsonify({"status": "error", "message": "Numeric Role ID required for Metal Slug: Awakening."}), 400
        # Server_id is now optional for the API call to Gamepoint. Pass it if provided by frontend.
        # The API itself might not use PInput02 if it can derive server from RoleID + ProductIDN.
        result = check_gamepoint_msa_api(uid, server_id) # Pass server_id (which can be None)
        # Since Gamepoint API doesn't return server name in *this* validation,
        # we'll use a generic or the frontend-provided server_id for context.
        intended_region_display = f"Server {server_id}" if server_id else "Metal Slug Server"
        if result.get("status") == "success" and result.get("message"): # Gamepoint returns message on success
             result["username"] = None # Ensure username is explicitly null as API doesn't provide it
                                       # but message like "Role ID Verified." is set.

    elif game_lower == "ragnarok-x-next-generation":
        if not uid.isdigit() or len(uid) < 10:
             return jsonify({"status": "error", "message": "Invalid Role ID format for Ragnarok X."}), 400
        result = check_nuverse_rox_api(uid) # server_id is not used for Nuverse ROX validation query
        intended_region_display = result.get("server_name", "ROX Server") # Use API's server_name if available
        if result.get("status") == "success" and result.get("server_name"): # Update for display
            intended_region_display = result.get("server_name")


    elif game_lower == "mobile-legends-sg":
        intended_region_display = "SG"
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_SG_CHECKROLE", "YOUR_MLBB_SG_PID_HERE")
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB SG."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "mobile-legends":
        intended_region_display = "ID"
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_ID_CHECKROLE", "25")
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "genshin-impact":
        if not server_id: return jsonify({"status": "error", "message": "Server ID required for Genshin Impact."}), 400
        server_display_map = {"os_asia": "Asia", "os_usa": "America", "os_euro": "Europe", "os_cht": "TW/HK/MO"}
        intended_region_display = server_display_map.get(server_id, "Unknown Genshin Server")
        result = check_razer_api(game_lower, uid, server_id)
    elif game_lower == "zenless-zone-zero":
        if not server_id: return jsonify({"status": "error", "message": "Server selection required for ZZZ."}), 400
        if RAZER_ZZZ_SERVER_ID_MAP.get(server_id):
            server_display_map = {"prod_official_asia": "Asia", "prod_official_usa": "America", "prod_official_eur": "Europe", "prod_official_cht": "TW/HK/MO"}
            intended_region_display = server_display_map.get(server_id, "Mapped ZZZ Server")
            result = check_razer_api(game_lower, uid, server_id)
        else: return jsonify({"status": "error", "message": "Invalid server key provided for ZZZ."}), 400
    elif game_lower == "ragnarok-origin":
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for Ragnarok Origin."}), 400
        intended_region_display = "MY"
        result = check_razer_api(game_lower, uid, server_id)
    elif game_lower == "snowbreak-containment-zone":
        if not server_id: return jsonify({"status": "error", "message": "Server ID required for Snowbreak: Containment Zone."}), 400
        server_display_map = {"sea": "Southeast Asia (Snowbreak)", "asia": "Asia (Snowbreak)", "americas": "Americas (Snowbreak)", "europe": "Europe (Snowbreak)"}
        intended_region_display = server_display_map.get(server_id.lower(), "Unknown Snowbreak Server")
        result = check_razer_api("snowbreak", uid, server_id.lower())
    elif game_lower == "identity-v":
        if not uid.isdigit(): return jsonify({"status": "error", "message": "Numeric Role ID required for Identity V."}), 400
        if not server_id or server_id.lower() not in IDV_SERVER_CODES: return jsonify({"status": "error", "message": "Valid server (Asia or NA-EU) required for IDV."}), 400
        intended_region_display = "Asia (IDV)" if server_id.lower() == "asia" else "NA-EU (IDV)"
        result = check_identityv_api(server_id, uid)
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        smileone_game_code_map = {"honkai-star-rail": "honkaistarrail", "bloodstrike": "bloodstrike", "ragnarok-m-classic": "ragnarokmclassic", "love-and-deepspace": "loveanddeepspace", "bigo-live": "bigolive"}
        smileone_game_code = smileone_game_code_map.get(game_lower)
        if not smileone_game_code: return jsonify({"status": "error", "message": f"Internal: Game '{game_lower}' not configured for SmileOne routing."}), 500
        if game_lower == "honkai-star-rail" and not server_id: return jsonify({"status": "error", "message": "Server ID required for Honkai: Star Rail."}), 400
        if game_lower == "love-and-deepspace" and (not server_id or not server_id.isdigit()): return jsonify({"status": "error", "message": "Numeric Server ID required for Love and Deepspace."}), 400
        if game_lower == "bloodstrike" and (not server_id or server_id != "-1"): return jsonify({"status": "error", "message": "Invalid server parameter for Bloodstrike."}), 400
        if game_lower == "ragnarok-m-classic" and (not server_id or server_id != "50001"): return jsonify({"status": "error", "message": "Invalid server parameter for Ragnarok M Classic."}), 400
        result = check_smile_one_api(smileone_game_code, uid, server_id)
    else:
        return jsonify({"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}), 400

    status_code_http = 200
    if result.get("status") == "error":
        msg_lower = (result.get("message", "") or result.get("error", "")).lower()
        if "timeout" in msg_lower: status_code_http = 504
        elif "invalid response format" in msg_lower or "invalid api response" in msg_lower or "not json" in msg_lower or "returned html" in msg_lower: status_code_http = 502
        elif "connection error" in msg_lower or "cannot connect" in msg_lower: status_code_http = 503
        elif "unauthorized" in msg_lower or "forbidden" in msg_lower or "rate limited" in msg_lower or "blocked" in msg_lower: status_code_http = 403
        elif "unexpected" in msg_lower or "pid not configured" in msg_lower or "pid could not be resolved" in msg_lower or "invalid server config" in msg_lower or "internal server error" in msg_lower or "remote" in msg_lower: status_code_http = 500
        elif "invalid uid" in msg_lower or "not found" in msg_lower or "invalid user id" in msg_lower or "invalid game user credentials" in msg_lower or "invalid role id" in msg_lower or "role not exist" in msg_lower or "player found, username unavailable" in msg_lower or "user id não existe" in msg_lower or "invalid server" in msg_lower or "character not found" in msg_lower or "role id mismatch" in msg_lower or "unverified" in msg_lower : status_code_http = 404
        else: status_code_http = 400

    final_response_data = {
        "status": result.get("status"), "username": result.get("username"), # username will be None for gamepoint msa
        "message": result.get("message"), "error": result.get("error"),
        "region_product_context": intended_region_display
    }
    # This was for Nuverse ROX, Gamepoint MSA validation doesn't return server_name directly
    if result.get("server_name_from_api") and game_lower == "ragnarok-x-next-generation":
        final_response_data["server_name_from_api"] = result.get("server_name_from_api")
    elif result.get("server_name_from_api") and game_lower == "metal-slug-awakening": # If Gamepoint ever returns it
        final_response_data["server_name_from_api"] = result.get("server_name_from_api")


    final_response_data_cleaned = {k: v for k, v in final_response_data.items() if v is not None}

    logging.info(f"Flask final response for {game_lower} (UID: {uid}, Server: {server_id}): {final_response_data_cleaned}, HTTP Status: {status_code_http}")
    return jsonify(final_response_data_cleaned), status_code_http

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
