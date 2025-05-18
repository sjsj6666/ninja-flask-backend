from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid # For Netease traceid

app = Flask(__name__)

# Define allowed origins
allowed_origins = [
    "http://127.0.0.1:5500", # Your local VS Code Live Server or similar
    "http://localhost:5500",  # Alternative local address
    "https://coxx.netlify.app"  # Your deployed Netlify site
]

# Apply CORS with specific origins
# More specific for /check-id/, but you can broaden if needed
CORS(app, resources={r"/check-id/*": {"origins": allowed_origins}}, supports_credentials=True)
# Example of a broader CORS setup if you add more routes later:
# CORS(app, origins=allowed_origins, supports_credentials=True)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
port = int(os.environ.get("PORT", 5000))

# --- Smile One Config ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    # It's better to manage cookies dynamically if they expire or are session-specific.
    # For now, using environment variable or a placeholder.
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "YOUR_SMILE_ONE_COOKIE_PLACEHOLDER_IF_ANY")
}

# --- Netease Identity V Config ---
NETEASE_IDV_BASE_URL_TEMPLATE = "https://pay.neteasegames.com/gameclub/identityv/{server_code}/login-role"
NETEASE_IDV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pay.neteasegames.com/identityv/topup", # Important Referer
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
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero"
RAZER_ZZZ_SERVER_ID_MAP = { # Maps frontend server key to Razer's API server key
    "prod_official_asia": "prod_gf_jp", # Assuming Asia maps to JP for Razer ZZZ
    "prod_official_usa": "prod_gf_us",
    "prod_official_eur": "prod_gf_eu",
    "prod_official_cht": "prod_gf_sg"  # Assuming TW/HK/MO maps to SG for Razer ZZZ
}

RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact"
# No server map needed for Genshin if Razer API takes frontend values directly for serverId param

RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin" # Referer for RO MY as per your logs
# No server map needed for RO if Razer API takes numeric server ID directly

# --- API Check Functions ---

def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole", # Brazil endpoint
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", # Brazil endpoint, product in URL
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole", # SG endpoint
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/", # US endpoint
        "bigolive": "https://www.smile.one/sg/merchant/bigo/checkrole" # SG endpoint
    }
    if game_code_for_smileone not in endpoints:
        return {"status": "error", "message": f"Game '{game_code_for_smileone}' not configured for SmileOne."}

    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = { # Referers matching the endpoint regions
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends", # Generic for MLBB
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai",
        "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike",
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace",
        "bigolive": "https://www.smile.one/sg/merchant/bigo"
    }
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, f"https://www.smile.one/merchant/{game_code_for_smileone}") # Fallback

    pid_to_use = specific_smileone_pid # If provided, use it directly

    if not pid_to_use: # If no specific PID, use defaults
        # PIDs from your previous working versions or environment variables
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" } # Frontend server ID to SmileOne PID
        default_pids_map = {
            "mobilelegends": os.environ.get("SMILE_ONE_PID_MLBB_DEFAULT", "25"), # MLBB ID default
            "honkaistarrail": os.environ.get("SMILE_ONE_PID_HSR_DEFAULT", "18356"),
            "bloodstrike": os.environ.get("SMILE_ONE_PID_BLOODSTRIKE", "20294"), # Ensure this is correct
            "ragnarokmclassic": os.environ.get("SMILE_ONE_PID_ROM_DEFAULT", "23026"),
            "bigolive": os.environ.get("SMILE_ONE_PID_BIGO", "20580")
        }
        pid_to_use = love_deepspace_pids_map.get(str(server_id)) if game_code_for_smileone == "loveanddeepspace" else default_pids_map.get(game_code_for_smileone)

    if pid_to_use is None: return {"status": "error", "message": f"Product ID (PID) could not be resolved for '{game_code_for_smileone}'."}

    params = {"pid": pid_to_use, "checkrole": "1"}
    if game_code_for_smileone == "mobilelegends": params.update({"user_id": uid, "zone_id": server_id})
    elif game_code_for_smileone in ["honkaistarrail", "ragnarokmclassic", "loveanddeepspace"]: params.update({"uid": uid, "sid": server_id})
    elif game_code_for_smileone == "bloodstrike": params.update({"uid": uid, "sid": server_id}) # SmileOne uses sid for Bloodstrike
    elif game_code_for_smileone == "bigolive": params.update({"uid": uid, "product": "bigosg"}) # Product param for Bigo SG

    logging.info(f"Sending SmileOne: Game='{game_code_for_smileone}', URL='{url}', PID='{pid_to_use}', Params={params}")
    try:
        # Bloodstrike uses product in URL query string for checkrole, others don't seem to.
        req_url = f"{url}?product=bloodstrike" if game_code_for_smileone == "bloodstrike" else url
        response = requests.post(req_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        logging.info(f"SmileOne Raw Response (Game: {game_code_for_smileone}, UID:{uid}): {raw_text}")
        data = response.json()
        logging.info(f"SmileOne Parsed JSON (Game: {game_code_for_smileone}): {data}")

        if data.get("code") == 200:
            # Try to get username from common keys, prioritizing specific ones
            name_key = "username" if game_code_for_smileone == "mobilelegends" else \
                       "message" if game_code_for_smileone == "bigolive" else "nickname" # Default 'nickname' for others
            username = data.get(name_key)

            if not username or not isinstance(username, str) or not username.strip():
                # Fallback to other potential keys if primary one is empty/missing
                for alt_key in ["username", "nickname", "role_name", "name", "char_name", "message"]:
                    if alt_key == name_key: continue # Skip if already tried
                    username = data.get(alt_key)
                    if username and isinstance(username, str) and username.strip(): break

            if username and username.strip(): return {"status": "success", "username": username.strip()}
            # For games that verify but might not return a username text from SmileOne
            if game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]:
                 return {"status": "success", "message": "Account Verified (Username N/A from API)"}
            return {"status": "error", "message": "Username not found in API response (Code 200)"}
        return {"status": "error", "message": data.get("message", data.get("info", f"API error (Code: {data.get('code')})"))}
    except ValueError: # JSONDecodeError
        # Specific HTML parsing for Love & Deepspace if JSON fails but HTML has the name
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
    server_code = IDV_SERVER_CODES.get(server_frontend_key.lower()) # Ensure lowercase for key matching
    if not server_code: return {"status": "error", "message": "Invalid server specified for Identity V."}

    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    # Generate dynamic params
    params = {
        "roleid": roleid,
        "timestamp": int(time.time() * 1000),
        "traceid": str(uuid.uuid4()),
        "deviceid": os.environ.get("NETEASE_DEVICE_ID", "YOUR_FALLBACK_NETEASE_DEVICE_ID_HERE"), # Use env var
        **NETEASE_IDV_STATIC_PARAMS # Merge static params
    }
    current_headers = NETEASE_IDV_HEADERS.copy()
    current_headers["X-TASK-ID"] = f"transid={params['traceid']},uni_transaction_id=default" # Dynamic X-TASK-ID

    logging.info(f"Sending Netease IDV: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=current_headers, timeout=10)
        raw_text = response.text
        logging.info(f"Netease IDV Raw Response (Server: {server_frontend_key}, Role: {roleid}): {raw_text}")
        data = response.json()
        logging.info(f"Netease IDV Parsed JSON: {data}")
        api_code = data.get("code")
        api_msg = (data.get("message", "") or data.get("msg", "")).strip() # Get message, prefer 'message' over 'msg'

        if api_code == "0000": # Success code from Netease
            username = data.get("data", {}).get("rolename")
            if username and username.strip(): return {"status": "success", "username": username.strip()}
            # If API says OK but rolename is missing/empty
            return {"status": "success", "message": "Role Verified (Username not provided by API)"} if "ok" in api_msg.lower() or "success" in api_msg.lower() else {"status": "error", "message": f"Player found, but username unavailable ({api_msg or 'No details from API'})"}
        # Specific error handling based on observed messages/codes
        if "role not exist" in api_msg.lower() or api_code == "40004":
            return {"status": "error", "message": "Invalid Role ID for this server"}
        return {"status": "error", "message": f"Invalid Role ID or API Error ({api_msg or 'No details from API'}, Code: {api_code})"}
    except ValueError: # JSONDecodeError
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
        "ragnarok-origin": {"url_template": RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE, "headers": RAZER_GOLD_RO_ORIGIN_HEADERS, "server_map": None, "name": "Ragnarok Origin"}
    }
    if game_slug not in api_details: return {"status": "error", "message": f"Razer API configuration not found for game: {game_slug}"}

    config = api_details[game_slug]
    # Determine the serverId parameter value for Razer's API
    api_server_id_param_value = server_id_frontend_key # Default: use frontend key directly
    if config["server_map"]: # If a specific mapping is defined (e.g., for ZZZ)
        api_server_id_param_value = config["server_map"].get(server_id_frontend_key)
        if not api_server_id_param_value:
            return {"status": "error", "message": f"Invalid server configuration for {config['name']} using frontend key '{server_id_frontend_key}'"}

    url = config["url_template"].format(user_id=user_id)
    params = {"serverId": api_server_id_param_value} if api_server_id_param_value else {} # Only add serverId if it's relevant/resolved

    logging.info(f"Sending Razer {config['name']}: URL='{url}', Params={params}")
    try:
        response = requests.get(url, params=params, headers=config["headers"], timeout=10)
        raw_text = response.text
        logging.info(f"Razer {config['name']} Raw Response (UID:{user_id}, FrontendSrvKey:{server_id_frontend_key}, APISrvVal:{api_server_id_param_value}): {raw_text}")
        data = response.json()
        logging.info(f"Razer {config['name']} Parsed JSON: {data}")

        if response.status_code == 200: # HTTP OK
            username = None
            if game_slug == "ragnarok-origin": # Specific parsing for RO Origin's structure
                if "roles" in data and isinstance(data["roles"], list) and data["roles"]:
                    username = data["roles"][0].get("Name") # Get name of the first role
            else: # General parsing for other Razer games (Genshin, ZZZ)
                username = data.get("username") or data.get("name") # Try 'username' then 'name'

            if username and isinstance(username, str) and username.strip():
                return {"status": "success", "username": username.strip()}

            # Handle Razer's own error codes if username not found but HTTP 200
            api_code = data.get("code")
            api_msg = data.get("message")
            if api_code == 77003 and api_msg == "Invalid game user credentials":
                 return {"status": "error", "message": f"Invalid User ID or Server ({config['name']})"}
            elif api_code == 0: # Razer's generic success code
                alt_name = data.get("name") or data.get("data", {}).get("name") # Try another common key
                if alt_name and alt_name.strip(): return {"status": "success", "username": alt_name.strip()}
                return {"status": "success", "message": f"Account Verified (Razer {config['name']} - Nickname not directly available)"}
            return {"status": "error", "message": api_msg or f"Unknown success response format (Razer {config['name']})"}

        # Handle non-200 HTTP status codes from Razer API
        error_msg_from_api = data.get("message", f"Razer API HTTP Error ({config['name']}): {response.status_code}")
        return {"status": "error", "message": error_msg_from_api}
    except ValueError: # JSONDecodeError
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


# --- Flask Routes ---
@app.route('/')
def home():
    return "NinjaTopUp Validation Backend is Live!"

@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    game_lower = game_slug_from_frontend.lower()
    result = {}
    intended_region_display = None # This will be passed back to frontend

    if not uid:
        return jsonify({"status": "error", "message": "User ID/Role ID is required."}), 400

    # --- Mobile Legends Variants (using Smile.One) ---
    if game_lower == "mobile-legends-sg":
        intended_region_display = "SG"
        # IMPORTANT: Ensure this PID is correctly set in your environment for MLBB SG
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_SG_CHECKROLE", "YOUR_MLBB_SG_PID_HERE")
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB SG."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "mobile-legends": # Assuming this is MLBB ID
        intended_region_display = "ID"
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_ID_CHECKROLE", "25") # Default for MLBB ID
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)

    # --- Razer Gold Integrated Games ---
    elif game_lower == "genshin-impact":
        if not server_id: return jsonify({"status": "error", "message": "Server ID required for Genshin Impact."}), 400
        # Map frontend server key to display region
        if server_id == "os_asia": intended_region_display = "Asia"
        elif server_id == "os_usa": intended_region_display = "America"
        elif server_id == "os_euro": intended_region_display = "Europe"
        elif server_id == "os_cht": intended_region_display = "TW/HK/MO"
        else: intended_region_display = "Unknown Genshin Server"
        result = check_razer_api(game_lower, uid, server_id)
    elif game_lower == "zenless-zone-zero":
        if not server_id: return jsonify({"status": "error", "message": "Server selection required for ZZZ."}), 400
        if RAZER_ZZZ_SERVER_ID_MAP.get(server_id): # Check if the frontend key is valid for mapping
            if "asia" in server_id: intended_region_display = "Asia" # Based on frontend key
            elif "usa" in server_id: intended_region_display = "America"
            elif "eur" in server_id: intended_region_display = "Europe"
            elif "cht" in server_id: intended_region_display = "TW/HK/MO"
            else: intended_region_display = "Mapped ZZZ Server"
            result = check_razer_api(game_lower, uid, server_id)
        else:
            return jsonify({"status": "error", "message": "Invalid server key provided for ZZZ."}), 400
    elif game_lower == "ragnarok-origin":
        # UID can be alphanumeric for RO, server_id should be numeric
        if not server_id or not server_id.isdigit():
            return jsonify({"status": "error", "message": "Numeric Server ID required for Ragnarok Origin."}), 400
        intended_region_display = "MY" # As per your product setup, Razer RO is likely MY
        result = check_razer_api(game_lower, uid, server_id)

    # --- Netease Identity V ---
    elif game_lower == "identity-v":
        if not uid.isdigit(): return jsonify({"status": "error", "message": "Numeric Role ID required for Identity V."}), 400
        if not server_id or server_id.lower() not in IDV_SERVER_CODES:
            return jsonify({"status": "error", "message": "Valid server (Asia or NA-EU) required for IDV."}), 400
        if server_id.lower() == "asia": intended_region_display = "Asia (IDV)"
        elif server_id.lower() == "na-eu": intended_region_display = "NA-EU (IDV)"
        result = check_identityv_api(server_id, uid)

    # --- Other Smile.One Games ---
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        smileone_game_code_map = {
            "honkai-star-rail": "honkaistarrail", "bloodstrike": "bloodstrike",
            "ragnarok-m-classic": "ragnarokmclassic", "love-and-deepspace": "loveanddeepspace",
            "bigo-live": "bigolive"
        }
        smileone_game_code = smileone_game_code_map.get(game_lower)
        if not smileone_game_code: # Should not happen due to outer if, but good safeguard
            return jsonify({"status": "error", "message": f"Internal: Game '{game_lower}' not configured for SmileOne routing."}), 500

        # Server ID validation for specific games
        if game_lower == "honkai-star-rail" and not server_id:
            return jsonify({"status": "error", "message": "Server ID required for Honkai: Star Rail."}), 400
        if game_lower == "love-and-deepspace" and (not server_id or not server_id.isdigit()):
            return jsonify({"status": "error", "message": "Numeric Server ID required for Love and Deepspace."}), 400
        if game_lower == "bloodstrike" and (not server_id or server_id != "-1"): # Bloodstrike uses -1 for its server ID
            return jsonify({"status": "error", "message": "Invalid server parameter for Bloodstrike."}), 400
        if game_lower == "ragnarok-m-classic" and (not server_id or server_id != "50001"): # Specific server ID for ROM Classic
            return jsonify({"status": "error", "message": "Invalid server parameter for Ragnarok M Classic."}), 400
        # Bigo Live does not typically use a server_id in the same way for SmileOne checks.

        result = check_smile_one_api(smileone_game_code, uid, server_id)
    else:
        return jsonify({"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}), 400

    # Determine HTTP status code for the response based on result
    status_code_http = 200
    if result.get("status") == "error":
        msg_lower = (result.get("message", "") or result.get("error", "")).lower()
        if "timeout" in msg_lower: status_code_http = 504
        elif "invalid response format" in msg_lower or "invalid api response" in msg_lower or "not json" in msg_lower or "returned html" in msg_lower: status_code_http = 502
        elif "connection error" in msg_lower or "cannot connect" in msg_lower: status_code_http = 503
        elif "unauthorized" in msg_lower or "forbidden" in msg_lower or "rate limited" in msg_lower or "blocked" in msg_lower: status_code_http = 403
        elif "unexpected" in msg_lower or "pid not configured" in msg_lower or "pid could not be resolved" in msg_lower or "invalid server config" in msg_lower or "internal server error" in msg_lower or "remote" in msg_lower: status_code_http = 500
        elif "invalid uid" in msg_lower or "not found" in msg_lower or "invalid user id" in msg_lower or "invalid game user credentials" in msg_lower or "invalid role id" in msg_lower or "role not exist" in msg_lower or "player found, username unavailable" in msg_lower or "user id não existe" in msg_lower or "invalid server" in msg_lower: status_code_http = 404 # User/server not found type errors
        else: status_code_http = 400 # Generic client error if not matched

    # Construct final response, ensuring only non-None values are included for cleaner JSON
    final_response_data = {
        "status": result.get("status"),
        "username": result.get("username"),
        "message": result.get("message"),
        "error": result.get("error"),
        "region_product_context": intended_region_display # Include the determined region
    }
    final_response_data_cleaned = {k: v for k, v in final_response_data.items() if v is not None}

    logging.info(f"Flask final response for {game_lower} (UID: {uid}): {final_response_data_cleaned}, HTTP Status: {status_code_http}")
    return jsonify(final_response_data_cleaned), status_code_http

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False) # debug=False for production or Render deployment
