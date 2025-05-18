from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid # For Netease traceid

app = Flask(__name__)
# Allow all origins for development. For production, restrict to your actual frontend domain.
CORS(app, resources={r"/check-id/*": {"origins": "*"}}) 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 5000))

# --- Smile One Config ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "YOUR_DEFAULT_SMILE_ONE_COOKIE_IF_NEEDED_FOR_TESTING_ONLY") 
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
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero"
RAZER_ZZZ_SERVER_ID_MAP = { "prod_official_asia": "prod_gf_jp", "prod_official_usa": "prod_gf_us", "prod_official_eur": "prod_gf_eu", "prod_official_cht": "prod_gf_sg"}
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact"
RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy(); RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin"

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
    # More specific referers if needed by Smile.One for certain games
    referer_map = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai", # Example
        # Add other specific referers if known to be required
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
    
    if pid_to_use is None: return {"status": "error", "message": f"PID unresolved for '{game_code_for_smileone}'."}

    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code_for_smileone == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace"]: params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bloodstrike": params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bigolive": params.update({"uid": uid, "product": "bigosg"}) # Example

    logging.info(f"Sending SmileOne: {game_code_for_smileone}, URL={url}, PID={pid_to_use}, Params={params}")
    try:
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status() 
        raw_text = response.text; logging.info(f"SmileOne Raw ({game_code_for_smileone}, UID:{uid}): {raw_text}")
        data = response.json(); logging.info(f"SmileOne JSON ({game_code_for_smileone}): {data}")

        if data.get("code") == 200:
            name_key = "username" if game_code_for_smileone == "mobilelegends" else \
                       "message" if game_code_for_smileone == "bigolive" else "nickname"
            username = data.get(name_key)
            if not username or not isinstance(username, str) or not username.strip(): # Fallback
                for alt_key in ["username", "nickname", "role_name", "name", "char_name", "message"]:
                    if alt_key == name_key: continue
                    username = data.get(alt_key)
                    if username and isinstance(username, str) and username.strip(): break
            
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            if game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]:
                 return {"status": "success", "message": "Account Verified (No username from API)"}
            return {"status": "error", "message": "Username not found in API response (Code 200)"}
        return {"status": "error", "message": data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))}
    except ValueError: # JSONDecodeError
        if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
            try:
                start_idx = raw_text.find("<span class=\"name\">") + len("<span class=\"name\">")
                end_idx = raw_text.find("</span>", start_idx)
                if start_idx > len("<span class=\"name\">") -1 and end_idx != -1:
                    username = raw_text[start_idx:end_idx].strip()
                    if username: return {"status": "success", "username": username}
            except Exception as ex: logging.error(f"HTML parse L&D err: {ex}")
        logging.error(f"JSON Parse Err (SmileOne {game_code_for_smileone}): Raw: {raw_text}"); return {"status": "error", "message": "Invalid API response format"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e: return {"status": "error", "message": f"API Connection Error ({getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (SmileOne)"); return {"status": "error", "message": "Unexpected server error (SmileOne)"}

def check_identityv_api(server_frontend_key, roleid):
    server_code = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code: return {"status": "error", "message": "Invalid server (IDV)"}
    
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    params = {"roleid": roleid, "timestamp": int(time.time() * 1000), "traceid": str(uuid.uuid4()), 
              "deviceid": os.environ.get("NETEASE_DEVICE_ID", "YOUR_FALLBACK_DEVICE_ID_HERE"), **NETEASE_IDV_STATIC_PARAMS}
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
            return {"status": "success", "message": "Role Verified (Name missing)"} if "ok" in api_msg.lower() or "success" in api_msg.lower() else {"status": "error", "message": f"Player found, username unavailable ({api_msg or 'No details'})"}
        if "role not exist" in api_msg.lower() or api_code == "40004": return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details'}, Code: {api_code})"}
    except ValueError: 
        logging.error(f"JSON Parse Err (IDV). Status: {response.status_code}. Raw: {raw_text}")
        if response.status_code >= 500: return {"status": "error", "message": "Netease Server Error"}
        return {"status": "error", "message": "Netease API check blocked or invalid response"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout (IDV)"}
    except requests.RequestException as e: return {"status": "error", "message": f"Netease API Connection Error ({getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception("Unexpected error (IDV)"); return {"status": "error", "message": "Unexpected server error (IDV)"}

def check_razer_api(game_slug, user_id, server_id_frontend_key):
    api_details = {
        "genshin-impact": {"url_template": RAZER_GOLD_GENSHIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_GENSHIN_HEADERS, "server_map": None, "name": "Genshin"},
        "zenless-zone-zero": {"url_template": RAZER_GOLD_ZZZ_API_URL_TEMPLATE, "headers": RAZER_GOLD_ZZZ_HEADERS, "server_map": RAZER_ZZZ_SERVER_ID_MAP, "name": "ZZZ"},
        "ragnarok-origin": {"url_template": RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_RO_ORIGIN_HEADERS, "server_map": None, "name": "RO Origin"}
    }
    if game_slug not in api_details: return {"status": "error", "message": f"Razer API config not found for {game_slug}"}

    config = api_details[game_slug]
    api_server_id = server_id_frontend_key
    if config["server_map"]: # Map frontend server key to Razer's API serverId if needed (like for ZZZ)
        api_server_id = config["server_map"].get(server_id_frontend_key)
        if not api_server_id: return {"status": "error", "message": f"Invalid server config ({config['name']})"}
    
    url = config["url_template"].format(user_id=user_id)
    params = {"serverId": api_server_id} if api_server_id else {} # Only add serverId if applicable
    
    logging.info(f"Sending Razer {config['name']}: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=config["headers"], timeout=10)
        raw_text = response.text; logging.info(f"Razer {config['name']} Raw (UID:{user_id}, ServerKey:{server_id_frontend_key}): {raw_text}")
        data = response.json(); logging.info(f"Razer {config['name']} JSON: {data}")

        if response.status_code == 200:
            # Attempt to get username from common keys or game-specific structures
            username = data.get("username") or data.get("name")
            if game_slug == "ragnarok-origin" and "roles" in data and isinstance(data["roles"], list) and data["roles"]:
                username = data["roles"][0].get("Name") or username # Prioritize 'roles[0].Name' for RO

            if username and isinstance(username, str) and username.strip():
                return {"status": "success", "username": username.strip()}
            
            api_code = data.get("code")
            api_msg = data.get("message")
            if api_code == 77003 and api_msg == "Invalid game user credentials": return {"status": "error", "message": f"Invalid User ID or Server ({config['name']})"}
            elif api_code == 0: # Generic success for Razer if username wasn't directly found
                return {"status": "success", "message": f"Account Verified (Razer {config['name']} Nickname N/A)"}
            return {"status": "error", "message": api_msg or f"Unknown success response (Razer {config['name']})"}
        
        error_msg = data.get("message", f"Razer API HTTP Error ({config['name']}): {response.status_code}")
        return {"status": "error", "message": error_msg}
    except ValueError: 
        logging.error(f"JSON Parse Err (Razer {config['name']}). Status: {response.status_code}. Raw: {raw_text}")
        if "<html" in raw_text.lower(): return {"status": "error", "message": f"Razer API check blocked ({config['name']})"}
        return {"status": "error", "message": f"Invalid API response (Razer {config['name']}, Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": f"API Timeout (Razer {config['name']})"}
    except requests.RequestException as e:
        return {"status": "error", "message": f"Razer API Connection Error ({config['name']}, Status: {getattr(e.response, 'status_code', 'N/A')})"}
    except Exception: logging.exception(f"Unexpected error (Razer {config['name']})"); return {"status": "error", "message": f"Unexpected server error (Razer {config['name']})"}


# --- Flask Routes ---
@app.route('/')
def home(): 
    return "NinjaTopUp Validation Backend is Live!"

@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    game_lower = game_slug_from_frontend.lower()
    result = {}
    intended_region_display = None 

    # Validate UID format for games that expect numeric UIDs (most Smile.One games)
    if game_lower not in ["ragnarok-origin", "identity-v"] and (not uid or not uid.isdigit()): # RO and IDV can have non-numeric
        return jsonify({"status": "error", "message": "Invalid UID format. UID must be numeric."}), 400
    elif game_lower in ["ragnarok-origin", "identity-v"] and not uid: # UID still required
         return jsonify({"status": "error", "message": "User ID/Role ID is required."}), 400


    if game_lower == "mobile-legends-sg":
        intended_region_display = "SG"
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_SG_CHECKROLE", "YOUR_SG_PID_HERE") # Replace with actual SG PID
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID for MLBB SG."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "mobile-legends": 
        intended_region_display = "ID" 
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_ID_CHECKROLE", "25") 
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID for MLBB."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    
    elif game_lower == "genshin-impact":
        if not server_id: return jsonify({"status": "error", "message": "Server ID for Genshin Impact."}), 400
        if server_id == "os_asia": intended_region_display = "Asia" # Example, refine as needed
        # ... other Genshin server to region mappings for display ...
        result = check_razer_api(game_lower, uid, server_id)
    elif game_lower == "zenless-zone-zero":
        if not server_id: return jsonify({"status": "error", "message": "Server for ZZZ."}), 400
        if "asia" in server_id: intended_region_display = "Asia" # Example
        result = check_razer_api(game_lower, uid, server_id)
    elif game_lower == "ragnarok-origin":
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID for Ragnarok Origin."}), 400
        intended_region_display = "MY" # Example: Product context for RO on your site
        result = check_razer_api(game_lower, uid, server_id)
        
    elif game_lower == "identity-v":
        if not server_id or server_id.lower() not in IDV_SERVER_CODES: return jsonify({"status": "error", "message": "Valid server (Asia or NA-EU) for IDV."}), 400
        if server_id.lower() == "asia": intended_region_display = "Asia"
        elif server_id.lower() == "na-eu": intended_region_display = "NA-EU"
        result = check_identityv_api(server_id, uid) 
        
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        smileone_game_code_map = {
            "honkai-star-rail": "honkaistarrail", "bloodstrike": "bloodstrike",
            "ragnarok-m-classic": "ragnarokmclassic", "love-and-deepspace": "loveanddeepspace",
            "bigo-live": "bigolive"
        }
        smileone_game_code = smileone_game_code_map.get(game_lower)
        if not smileone_game_code: return jsonify({"status": "error", "message": f"Game '{game_lower}' not configured for SmileOne."}), 400
        
        if game_lower == "honkai-star-rail" and not server_id: return jsonify({"status": "error", "message": "Server ID for HSR."}), 400
        if game_lower == "love-and-deepspace" and (not server_id or not server_id.isdigit()): return jsonify({"status": "error", "message": "Numeric Server ID for L&D."}), 400
        
        result = check_smile_one_api(smileone_game_code, uid, server_id)
    else:
        return jsonify({"status": "error", "message": f"Validation not configured for: {game_slug_from_frontend}"}), 400

    status_code_http = 200
    if result.get("status") == "error":
        msg_lower = (result.get("message", "") or result.get("error", "")).lower()
        if "timeout" in msg_lower: status_code_http = 504 
        elif "invalid response format" in msg_lower or "invalid api response" in msg_lower : status_code_http = 502 
        elif "connection error" in msg_lower or "cannot connect" in msg_lower : status_code_http = 503 
        elif "unauthorized" in msg_lower or "forbidden" in msg_lower or "rate limited" in msg_lower or "blocked" in msg_lower: status_code_http = 403 
        elif "unexpected" in msg_lower or "pid not configured" in msg_lower or "invalid server config" in msg_lower or "internal server error" in msg_lower: status_code_http = 500 
        elif "invalid uid" in msg_lower or "not found" in msg_lower or "invalid user id" in msg_lower or "invalid game user credentials" in msg_lower or "invalid role id" in msg_lower or "role not exist" in msg_lower or "player found, username unavailable" in msg_lower or "user id não existe" in msg_lower: status_code_http = 404 
        else: status_code_http = 400 

    final_response_data = {
        "status": result.get("status"), "username": result.get("username"),
        "message": result.get("message"), "error": result.get("error"), 
        "region_product_context": intended_region_display 
    }
    final_response_data_cleaned = {k: v for k, v in final_response_data.items() if v is not None}
    
    logging.info(f"Flask final response for {game_lower} (UID: {uid}): {final_response_data_cleaned}, HTTP Status: {status_code_http}")
    return jsonify(final_response_data_cleaned), status_code_http

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False) # Set debug=False for production
