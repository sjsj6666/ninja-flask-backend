from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid # For Netease traceid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) # Allow all origins for development

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 5000))

# --- Smile One Config ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    # Cookie might be necessary if Smile.One requires a session or has anti-bot measures.
    # Best to get a fresh one if issues arise or manage it dynamically.
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "YOUR_DEFAULT_SMILE_ONE_COOKIE_IF_NEEDED_FOR_TESTING")
}

# --- Netease Identity V Config ---
NETEASE_IDV_BASE_URL_TEMPLATE = "https://pay.neteasegames.com/gameclub/identityv/{server_code}/login-role"
NETEASE_IDV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pay.neteasegames.com/identityv/topup",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
NETEASE_IDV_STATIC_PARAMS = {
    "gc_client_version": "1.9.111", # This may change over time
    "client_type": "gameclub"
}
IDV_SERVER_CODES = { # Mapping from your frontend server value to Netease's API server_code
    "asia": "2001",
    "na-eu": "2011"
}

# --- Razer Gold API Config ---
RAZER_GOLD_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin", # As called from your server, less critical but good to mimic
}

# Razer Gold ZZZ Specifics
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero" # Example

RAZER_ZZZ_SERVER_ID_MAP = { # Mapping from your frontend server value to Razer's serverId param for ZZZ API
    "prod_official_asia": "prod_gf_jp",
    "prod_official_usa": "prod_gf_us",
    "prod_official_eur": "prod_gf_eu",
    "prod_official_cht": "prod_gf_sg"
}

# Razer Gold Genshin Impact Specifics
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact" # Example

# Razer Gold Ragnarok Origin Specifics
RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin" # Based on observed logs

# --- API Check Functions ---

def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", # Needs ?product=bloodstrike
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/",
        "bigolive": "https://www.smile.one/sg/merchant/bigo/checkrole"
    }
    if game_code_for_smileone not in endpoints:
        return {"status": "error", "message": f"Invalid game_code_for_smileone '{game_code_for_smileone}' for Smile One"}

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
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, "https://www.smile.one")

    pid_to_use = specific_smileone_pid
    if not pid_to_use: # Fallback to default PIDs
        bloodstrike_default_pid = os.environ.get("SMILE_ONE_PID_BLOODSTRIKE", "20294")
        bigo_default_pid = os.environ.get("SMILE_ONE_PID_BIGO", "20580")
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" }

        if game_code_for_smileone == "loveanddeepspace":
            pid_to_use = love_deepspace_pids_map.get(str(server_id))
        else:
            default_pids_map = {
                "mobilelegends": os.environ.get("SMILE_ONE_PID_MLBB_DEFAULT", "25"),
                "honkaistarrail": os.environ.get("SMILE_ONE_PID_HSR_DEFAULT", "18356"),
                "bloodstrike": bloodstrike_default_pid,
                "ragnarokmclassic": os.environ.get("SMILE_ONE_PID_ROM_DEFAULT", "23026"),
                "bigolive": bigo_default_pid
            }
            pid_to_use = default_pids_map.get(game_code_for_smileone)
    
    if pid_to_use is None:
         return {"status": "error", "message": f"PID not configured or resolved for game '{game_code_for_smileone}'"}

    params = { "pid": pid_to_use, "checkrole": "1" }
    if game_code_for_smileone == "mobilelegends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace"]:
         params["uid"] = uid
         params["sid"] = server_id
    elif game_code_for_smileone == "bloodstrike":
        params["uid"] = uid
        params["sid"] = server_id # Smile.One uses 'sid' even if fixed for Bloodstrike checkrole
    elif game_code_for_smileone == "bigolive":
        params["uid"] = uid
        params["product"] = "bigosg" # Example, verify actual if needed

    logging.info(f"Sending Smile One request for {game_code_for_smileone}: URL={url}, PID={pid_to_use}, Params={params}")
    try:
        request_url_final = url
        if game_code_for_smileone == "bloodstrike": 
            request_url_final = f"{url}?product=bloodstrike" 

        response = requests.post(request_url_final, data=params, headers=current_headers, timeout=10)
        response.raise_for_status() 
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game_code_for_smileone} (UID: {uid}, Server: {server_id}): {raw_text}")
        
        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game_code_for_smileone}: {data}")

            if data.get("code") == 200:
                username_to_return = None
                primary_username_key = "nickname" 
                if game_code_for_smileone == "mobilelegends": primary_username_key = "username"
                elif game_code_for_smileone == "bigolive": primary_username_key = "message"
                
                username_from_api = data.get(primary_username_key)
                if username_from_api and isinstance(username_from_api, str) and username_from_api.strip():
                    username_to_return = username_from_api.strip()
                else: 
                    possible_username_keys = ["username", "nickname", "role_name", "name", "char_name", "message"]
                    for key in possible_username_keys:
                        if key == primary_username_key: continue
                        value_from_api = data.get(key)
                        if value_from_api and isinstance(value_from_api, str) and value_from_api.strip():
                            username_to_return = value_from_api.strip(); break
                
                if username_to_return:
                    return {"status": "success", "username": username_to_return}
                elif game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]:
                    return {"status": "success", "message": "Account Verified (Username not directly provided by this API call)"}
                else: 
                    logging.warning(f"Smile One check successful (Code: 200) for {game_code_for_smileone} but NO username. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response (Code 200)"}
            else: 
                 error_msg = data.get("message", data.get("info", f"Invalid UID/Server or API error (Code: {data.get('code')})"))
                 return {"status": "error", "message": error_msg}
        
        except ValueError: 
            if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
                try: # Attempt to parse L&D HTML
                    start_tag = "<span class=\"name\">"; end_tag = "</span>"
                    start_index = raw_text.find(start_tag) + len(start_tag)
                    end_index = raw_text.find(end_tag, start_index)
                    if start_index > len(start_tag) -1 and end_index != -1:
                        username = raw_text[start_index:end_index].strip()
                        if username: return {"status": "success", "username": username}
                except Exception as parse_ex: logging.error(f"Error parsing HTML for L&D: {parse_ex}")
            
            logging.error(f"Error parsing JSON for Smile One {game_code_for_smileone}: Raw: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}

    except requests.Timeout:
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e: 
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        return {"status": "error", "message": f"Smile One API Connection Error ({status_code_str})"}
    except Exception as e: 
        logging.exception(f"Unexpected error in check_smile_one_api for {game_code_for_smileone}, UID {uid}")
        return {"status": "error", "message": "Unexpected server error (Smile One)"}

def check_identityv_api(server_frontend_key, roleid):
    server_code_for_api = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code_for_api: return {"status": "error", "message": "Invalid server (IDV)"}
    
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code_for_api)
    params = {"roleid": roleid, "timestamp": int(time.time() * 1000), "traceid": str(uuid.uuid4()), 
              "deviceid": os.environ.get("NETEASE_DEVICE_ID", "YOUR_FALLBACK_DEVICE_ID"), **NETEASE_IDV_STATIC_PARAMS}
    headers = NETEASE_IDV_HEADERS.copy(); headers["X-TASK-ID"] = f"transid={params['traceid']},uni_transaction_id=default"
    
    logging.info(f"Sending Netease IDV: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text; logging.info(f"Netease IDV Raw (Server: {server_frontend_key}, Role: {roleid}): {raw_text}")
        data = response.json(); logging.info(f"Netease IDV JSON: {data}")
        api_code = data.get("code"); api_msg = (data.get("message", "") or data.get("msg", "")).strip()

        if api_code == "0000":
            username = data.get("data", {}).get("rolename")
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            elif "ok" in api_msg.lower() or "success" in api_msg.lower(): return {"status": "success", "message": "Role Verified (Name missing)"}
            return {"status": "error", "message": f"Player found, username unavailable ({api_msg or 'No details'})"}
        elif "role not exist" in api_msg.lower() or api_code == "40004": return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details'}, Code: {api_code})"}
    except ValueError: # JSONDecodeError
        logging.error(f"Error parsing JSON (IDV). Status: {response.status_code}. Raw: {raw_text}")
        if response.status_code >= 500: return {"status": "error", "message": "Netease Server Error"}
        elif "<html" in raw_text.lower(): return {"status": "error", "message": "Netease API check blocked"}
        return {"status": "error", "message": f"Invalid API response (Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout (IDV)"}
    except requests.RequestException as e:
        return {"status": "error", "message": f"Netease API Connection Error ({getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (IDV)"); return {"status": "error", "message": "Unexpected server error (IDV)"}

def check_razer_zzz_api(user_id, server_id_frontend_key):
    razer_server_id = RAZER_ZZZ_SERVER_ID_MAP.get(server_id_frontend_key)
    if not razer_server_id: return {"status": "error", "message": "Invalid server config (ZZZ)"}

    url = RAZER_GOLD_ZZZ_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": razer_server_id}; headers = RAZER_GOLD_ZZZ_HEADERS
    logging.info(f"Sending Razer ZZZ: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text; logging.info(f"Razer ZZZ Raw (UID: {user_id}, ServerKey: {server_id_frontend_key}, API SID: {razer_server_id}): {raw_text}")
        data = response.json(); logging.info(f"Razer ZZZ JSON: {data}")

        if response.status_code == 200:
            nickname = data.get("username")
            if nickname and isinstance(nickname, str) and nickname.strip(): return {"status": "success", "username": nickname.strip()}
            api_code = data.get("code"); api_msg = data.get("message")
            if api_code == 77003 and api_msg == "Invalid game user credentials": return {"status": "error", "message": "Invalid User ID or Server (ZZZ)"}
            elif api_code == 0:
                alt_name = data.get("name") or data.get("data", {}).get("name")
                if alt_name and alt_name.strip(): return {"status": "success", "username": alt_name.strip()}
                return {"status": "success", "message": "Account Verified (Razer ZZZ Nickname N/A)"}
            return {"status": "error", "message": api_msg or "Unknown success response (Razer ZZZ)"}
        error_msg = data.get("message", f"Razer API HTTP Error (ZZZ): {response.status_code}")
        return {"status": "error", "message": error_msg}
    except ValueError: # JSONDecodeError
        logging.error(f"Error parsing JSON (Razer ZZZ). Status: {response.status_code}. Raw: {raw_text}")
        if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer API check blocked (ZZZ)"}
        return {"status": "error", "message": f"Invalid API response (Razer ZZZ, Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout (Razer ZZZ)"}
    except requests.RequestException as e:
        return {"status": "error", "message": f"Razer API Connection Error (ZZZ, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (Razer ZZZ)"); return {"status": "error", "message": "Unexpected server error (Razer ZZZ)"}

def check_razer_genshin_api(user_id, server_id_frontend_key):
    url = RAZER_GOLD_GENSHIN_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": server_id_frontend_key}; headers = RAZER_GOLD_GENSHIN_HEADERS
    logging.info(f"Sending Razer Genshin: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text; logging.info(f"Razer Genshin Raw (UID: {user_id}, ServerKey: {server_id_frontend_key}): {raw_text}")
        data = response.json(); logging.info(f"Razer Genshin JSON: {data}")

        if response.status_code == 200:
            nickname = data.get("username") or data.get("name")
            if nickname and isinstance(nickname, str) and nickname.strip(): return {"status": "success", "username": nickname.strip()}
            api_code = data.get("code"); api_msg = data.get("message")
            if api_code == 0 and (api_msg == "Success" or not api_msg):
                alt_name = data.get("name")
                if alt_name and alt_name.strip(): return {"status": "success", "username": alt_name.strip()}
                return {"status": "success", "message": "Account Verified (Razer Genshin Nickname N/A)"}
            elif api_code == 77003 and api_msg == "Invalid game user credentials": return {"status": "error", "message": "Invalid User ID or Server (Genshin)"}
            return {"status": "error", "message": api_msg or "Unknown success response (Razer Genshin)"}
        error_msg = data.get("message", f"Razer API HTTP Error (Genshin): {response.status_code}")
        return {"status": "error", "message": error_msg}
    except ValueError: # JSONDecodeError
        logging.error(f"Error parsing JSON (Razer Genshin). Status: {response.status_code}. Raw: {raw_text}")
        if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer API check blocked (Genshin)"}
        return {"status": "error", "message": f"Invalid API response (Razer Genshin, Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout (Razer Genshin)"}
    except requests.RequestException as e:
        return {"status": "error", "message": f"Razer API Connection Error (Genshin, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (Razer Genshin)"); return {"status": "error", "message": "Unexpected server error (Razer Genshin)"}

def check_razer_ragnarok_origin_api(user_id, server_id_numeric): # Expects numeric server_id
    url = RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": server_id_numeric}; headers = RAZER_GOLD_RO_ORIGIN_HEADERS
    logging.info(f"Sending Razer RO Origin: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text; logging.info(f"Razer RO Origin Raw (UID: {user_id}, Server: {server_id_numeric}): {raw_text}")
        data = response.json(); logging.info(f"Razer RO Origin JSON: {data}")

        if response.status_code == 200 and data.get("code") == 0: # Common Razer success pattern
            username = data.get("username") or data.get("name") or data.get("characterName") or data.get("roleName")
            if username and isinstance(username, str) and username.strip(): return {"status": "success", "username": username.strip()}
            logging.warning(f"Razer RO Origin success (Code 0) but no username. Data: {data}")
            return {"status": "success", "message": "Account Verified (Razer RO Nickname N/A)"}
        error_msg = data.get("message", f"Razer API Error (RO Origin, Code: {data.get('code', 'N/A')}, HTTP: {response.status_code})")
        return {"status": "error", "message": error_msg}
    except ValueError: # JSONDecodeError
        logging.error(f"Error parsing JSON (Razer RO). Status: {response.status_code}. Raw: {raw_text}")
        if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer API check blocked (RO Origin)"}
        return {"status": "error", "message": f"Invalid API response (Razer RO, Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout (Razer RO)"}
    except requests.RequestException as e:
        return {"status": "error", "message": f"Razer API Connection Error (Razer RO, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (Razer RO)"); return {"status": "error", "message": "Unexpected server error (Razer RO)"}

# --- Flask Routes ---
@app.route('/')
def home(): 
    return "NinjaTopUp Validation Backend is Live!"

# Generic dispatcher route for ID checks
@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    game_lower = game_slug_from_frontend.lower()
    result = {}
    intended_region_display = None # This will be part of the response to frontend

    # --- Mobile Legends Variants (using Smile.One) ---
    if game_lower == "mobile-legends-sg":
        intended_region_display = "SG"
        # IMPORTANT: Find the actual PID Smile.One uses for SG checkrole
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_SG_CHECKROLE", "YOUR_MLBB_SG_CHECKROLE_PID_HERE") 
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB SG."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "mobile-legends": # Assuming this is your default/ID version
        intended_region_display = "ID" 
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_ID_CHECKROLE", "25") # '25' is common for ID
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    
    # --- Razer Gold Integrated Games ---
    elif game_lower == "genshin-impact":
        if not server_id: return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        # Infer display region from server_id (frontend key) if needed for display consistency
        if server_id == "os_asia": intended_region_display = "Asia"
        elif server_id == "os_usa": intended_region_display = "America"
        elif server_id == "os_euro": intended_region_display = "Europe"
        elif server_id == "os_cht": intended_region_display = "TW/HK/MO"
        result = check_razer_genshin_api(uid, server_id) # server_id is the frontend key like 'os_asia'
    elif game_lower == "zenless-zone-zero":
        if not server_id: return jsonify({"status": "error", "message": "Server selection is required for ZZZ."}), 400
        if "asia" in server_id: intended_region_display = "Asia" # Based on your frontend key
        elif "usa" in server_id: intended_region_display = "America"
        elif "eur" in server_id: intended_region_display = "Europe"
        elif "cht" in server_id: intended_region_display = "TW/HK/MO"
        result = check_razer_zzz_api(uid, server_id) # server_id is the frontend key like 'prod_official_asia'
    
    # --- Ragnarok Origin (using Razer Gold) ---
    elif game_lower == "ragnarok-origin":
        if not server_id or not server_id.isdigit(): # Razer RO API expects numeric serverId
            return jsonify({"status": "error", "message": "Numeric Server ID is required for Ragnarok Origin."}), 400
        # Set region based on your product targeting. If Razer's referer was /my/, you might set "MY"
        # For example, if your 'ragnarok-origin' slug on frontend is for Malaysia:
        intended_region_display = "MY" 
        result = check_razer_ragnarok_origin_api(uid, server_id) # uid can be alphanumeric for RO
        
    # --- Netease Identity V ---
    elif game_lower == "identity-v":
        if not server_id or server_id.lower() not in IDV_SERVER_CODES: # server_id is 'asia' or 'na-eu'
            return jsonify({"status": "error", "message": "Valid server (Asia or NA-EU) is required for IDV."}), 400
        if server_id.lower() == "asia": intended_region_display = "Asia"
        elif server_id.lower() == "na-eu": intended_region_display = "NA-EU"
        result = check_identityv_api(server_id, uid) 
        
    # --- Other Smile.One Games (General Handling) ---
    # Map your frontend game_slug to Smile.One's internal game code if they differ.
    # Also map to any specific PIDs if known for these games.
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        smileone_game_code_map = {
            "honkai-star-rail": "honkaistarrail",
            "bloodstrike": "bloodstrike",
            "ragnarok-m-classic": "ragnarokmclassic",
            "love-and-deepspace": "loveanddeepspace",
            "bigo-live": "bigolive"
        }
        smileone_game_code = smileone_game_code_map.get(game_lower)
        if not smileone_game_code:
            return jsonify({"status": "error", "message": f"Game slug '{game_lower}' not configured for Smile One."}), 400
        
        # Basic server_id validation for games that require it for Smile.One
        if game_lower == "honkai-star-rail" and not server_id: # Expects keys like 'prod_official_asia'
             return jsonify({"status": "error", "message": "Server ID required for Honkai: Star Rail."}), 400
        if game_lower == "love-and-deepspace" and (not server_id or not server_id.isdigit()): # Expects numeric server ID e.g. "81"
             return jsonify({"status": "error", "message": "Numeric Server ID required for Love and Deepspace."}), 400
        # For ragnarok-m-classic, Smile.One logic uses a fixed server_id '50001' internally if not passed or if `pid_override` not used
        # For bloodstrike, server_id needed.
        # For bigo-live, server_id is typically not applicable.

        result = check_smile_one_api(smileone_game_code, uid, server_id) # Uses default PIDs if specific_smileone_pid not passed
    else:
        return jsonify({"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}), 400

    # --- Determine HTTP status code for the response ---
    status_code_http = 200
    if result.get("status") == "error":
        msg_lower = (result.get("message", "") or result.get("error", "")).lower() # Check both message and error
        if "timeout" in msg_lower: status_code_http = 504 
        elif "invalid response format" in msg_lower or \
             "invalid api response" in msg_lower : status_code_http = 502 
        elif "connection error" in msg_lower or \
             "cannot connect" in msg_lower : status_code_http = 503 
        elif "unauthorized" in msg_lower or "forbidden" in msg_lower or \
             "rate limited" in msg_lower or "blocked" in msg_lower: status_code_http = 403 
        elif "unexpected" in msg_lower or "pid not configured" in msg_lower or \
             "invalid server configuration" in msg_lower or "internal server error" in msg_lower: status_code_http = 500 
        elif "invalid uid" in msg_lower or "not found" in msg_lower or \
              "invalid user id" in msg_lower or "invalid game user credentials" in msg_lower or \
              "invalid role id" in msg_lower or "role not exist" in msg_lower or \
              "player found, but username unavailable" in msg_lower or \
              "user id não existe" in msg_lower: status_code_http = 404 
        else: status_code_http = 400 

    final_response_data = {
        "status": result.get("status"),
        "username": result.get("username"),
        "message": result.get("message"),
        "error": result.get("error"), 
        "region_product_context": intended_region_display 
    }
    final_response_data_cleaned = {k: v for k, v in final_response_data.items() if v is not None}
    
    logging.info(f"Flask final response for {game_lower} (UID: {uid}): {final_response_data_cleaned}, HTTP Status: {status_code_http}")
    return jsonify(final_response_data_cleaned), status_code_http


if __name__ == "__main__":
    # For Render, Gunicorn will set the host and port. This is for local dev.
    app.run(host='0.0.0.0', port=port, debug=True) # Set debug=False for production on Render
