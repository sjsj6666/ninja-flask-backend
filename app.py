# ----------- app.py -----------
from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid

app = Flask(__name__) # <<< THIS SHOULD BE NEAR THE TOP, AFTER IMPORTS
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

port = int(os.environ.get("PORT", 5000))

# --- Smile One Config ---
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
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
    "gc_client_version": "1.9.111",
    "client_type": "gameclub"
}
IDV_SERVER_CODES = {
    "asia": "2001",
    "na-eu": "2011"
}

# --- API Check Functions ---

def check_smile_one_api(game, uid, server_id): # <<< FUNCTION DEFINITION STARTS HERE
    # The line "if data.get("code") == 200:" should be indented INSIDE this function
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole",
        "zenless-zone-zero": "https://www.smile.one/br/merchant/zzz/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole",
        "ragnarok-m-classic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "love-and-deepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/"
    }

    if game not in endpoints:
        return {"status": "error", "message": f"Invalid game '{game}' for Smile One"}

    url = endpoints[game]
    current_headers = SMILE_ONE_HEADERS.copy()

    referer_map = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai",
        "zenless-zone-zero": "https://www.smile.one/br/merchant/zzz",
        "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike",
        "ragnarok-m-classic": "https://www.smile.one/sg/merchant/ragnarokmclassic",
        "love-and-deepspace": "https://www.smile.one/us/merchant/loveanddeepspace"
    }
    current_headers["Referer"] = referer_map.get(game, "https://www.smile.one")

    bloodstrike_pid = os.environ.get("BLOODSTRIKE_SMILE_ONE_PID", "20294")
    zzz_pid = os.environ.get("ZZZ_SMILE_ONE_PID", "YOUR_ZZZ_PID_NEEDS_TO_BE_SET")
    
    love_deepspace_pids = {
        "81": "19226", 
        "82": "19227", 
        "83": "19227"
    }

    current_pid = None
    if game == "love-and-deepspace":
        current_pid = love_deepspace_pids.get(server_id)
    else:
        params_pid_map = {
            "mobile-legends": "25",
            "genshin-impact": "19731",
            "honkai-star-rail": "18356",
            "zenless-zone-zero": zzz_pid,
            "bloodstrike": bloodstrike_pid,
            "ragnarok-m-classic": "23026"
        }
        current_pid = params_pid_map.get(game)

    if current_pid is None or current_pid == "YOUR_ZZZ_PID_NEEDS_TO_BE_SET":
         return {"status": "error", "message": f"PID not configured or invalid server for game '{game}'"}

    params = { "pid": current_pid, "checkrole": "1" }

    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game in ["honkai-star-rail", "genshin-impact", "zenless-zone-zero", "ragnarok-m-classic", "love-and-deepspace"]:
         params["uid"] = uid
         params["sid"] = server_id
    elif game == "bloodstrike":
        params["uid"] = uid
        params["sid"] = server_id

    logging.info(f"Sending Smile One request for {game}: URL={url}, Params={params}, Cookie(part)={current_headers.get('Cookie')[:50]}...")
    try:
        request_url = url
        if game == "bloodstrike":
            request_url = f"{url}?product=bloodstrike"

        response = requests.post(request_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game}: {data}")

            if data.get("code") == 200: # <<< THIS IF IS CORRECTLY INDENTED WITHIN THE TRY-EXCEPT BLOCK, WHICH IS WITHIN THE FUNCTION
                username_to_return = None
                
                primary_username_key = "nickname" if game == "love-and-deepspace" else "username"
                
                username_from_api = data.get(primary_username_key)
                if username_from_api and isinstance(username_from_api, str) and username_from_api.strip():
                    username_to_return = username_from_api.strip()
                    logging.info(f"Found username for {game} using primary key '{primary_username_key}': {username_to_return}")
                else:
                    possible_username_keys = ["username", "nickname", "role_name", "name", "char_name"]
                    for key in possible_username_keys:
                        if key == primary_username_key: continue
                        value_from_api = data.get(key)
                        if value_from_api and isinstance(value_from_api, str) and value_from_api.strip():
                            username_to_return = value_from_api.strip()
                            logging.info(f"Found username for {game} under fallback key '{key}': {username_to_return}")
                            break
                
                if username_to_return:
                    return {"status": "success", "username": username_to_return}
                elif game in ["genshin-impact", "honkai-star-rail", "zenless-zone-zero"]:
                    return {"status": "success", "message": "Account Verified"}
                elif game in ["bloodstrike", "ragnarok-m-classic"]:
                    return {"status": "success", "message": "Account Verified (Username not retrieved)"}
                else: 
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but NO username found in any expected keys. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response"}
            else:
                 error_msg = data.get("message", f"Invalid UID/Server or API error code: {data.get('code')}")
                 logging.warning(f"Smile One check FAILED for {game} with API code {data.get('code')}: {error_msg}")
                 return {"status": "error", "message": error_msg}
        
        except ValueError: 
            if game == "love-and-deepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
                try:
                    start_tag = "<span class=\"name\">"
                    end_tag = "</span>"
                    start_index = raw_text.find(start_tag)
                    if start_index != -1:
                        end_index = raw_text.find(end_tag, start_index + len(start_tag))
                        if end_index != -1:
                            username = raw_text[start_index + len(start_tag):end_index].strip()
                            logging.info(f"Successfully parsed username '{username}' from HTML for Love and Deepspace.")
                            return {"status": "success", "username": username}
                except Exception as parse_ex:
                    logging.error(f"Error parsing username from HTML for Love and Deepspace: {parse_ex} - Raw Text: {raw_text}")
            
            logging.error(f"Error parsing JSON for Smile One {game}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}

    except requests.Timeout:
        logging.error(f"Error: Smile One API timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        error_text = e.response.text if e.response is not None else "No response body"
        logging.error(f"Error checking Smile One {game} (UID {uid}): HTTP Status={status_code_str}, Error={str(e)}, Response: {error_text}")
        
        user_msg = f"API Connection Error ({status_code_str})"
        if e.response is not None:
            status_code_val = e.response.status_code
            if status_code_val == 400: user_msg = "Invalid request to Smile One (400)"
            elif status_code_val == 401: user_msg = "Smile One API Unauthorized (401). Check SMILE_ONE_COOKIE."
            elif status_code_val == 403: user_msg = "Smile One API Forbidden (403). Check SMILE_ONE_COOKIE or IP restrictions."
            elif status_code_val == 404: user_msg = "Smile One API Endpoint Not Found (404)"
            elif status_code_val == 429: user_msg = "Smile One API Rate Limited (429)"
            elif status_code_val >= 500: user_msg = f"Smile One API Server Error ({status_code_val})"
        return {"status": "error", "message": user_msg}
    except Exception as e:
        logging.exception(f"Unexpected error in check_smile_one_api for {game}, UID {uid}")
        return {"status": "error", "message": "An unexpected error occurred"}


def check_identityv_api(server, roleid):
    # ... (keep this function as is) ...
    server_code = IDV_SERVER_CODES.get(server.lower())
    if not server_code:
        logging.error(f"Invalid server provided for Identity V check: {server}")
        return {"status": "error", "message": "Invalid server specified"}

    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    current_timestamp = int(time.time() * 1000)
    trace_id = str(uuid.uuid4())
    device_id = os.environ.get("NETEASE_DEVICE_ID", "156032181698579111") 

    query_params = {
        "roleid": roleid,
        "timestamp": current_timestamp,
        "traceid": trace_id,
        "deviceid": device_id,
        **NETEASE_IDV_STATIC_PARAMS
    }
    headers = NETEASE_IDV_HEADERS.copy()
    headers["X-TASK-ID"] = f"transid={trace_id},uni_transaction_id=default"

    logging.info(f"Sending Netease IDV request: URL={url}, Params={query_params}")
    try:
        response = requests.get(url, params=query_params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Netease IDV Raw Response (Server: {server}, RoleID: {roleid}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Netease IDV JSON Response: {data}")
            api_code = data.get("code")
            api_message = data.get("message", data.get("msg", "")) or ""

            if api_code == "0000":
                username = None
                if isinstance(data.get("data"), dict):
                    username = data["data"].get("rolename")
                if username:
                    logging.info(f"Netease IDV check SUCCESS (Server: {server}, RoleID: {roleid}). Username: {username}")
                    return {"status": "success", "username": username}
                else:
                    logging.warning(f"Netease IDV check successful (Code: {api_code}) but username 'rolename' not found. RoleID: {roleid}. Data: {data}")
                    if "ok" in api_message.lower() or "success" in api_message.lower():
                         return {"status": "success", "message": "Role ID Verified (Name missing)"}
                    else:
                         return {"status": "error", "message": "Player found, but username unavailable"}
            elif "role not exist" in api_message.lower() or "role_not_exist" in api_message.lower() or api_code == "40004":
                logging.warning(f"Netease IDV check FAILED: Role not found. (Server: {server}, RoleID: {roleid}), Code: {api_code}, Msg: {api_message}")
                return {"status": "error", "message": "Invalid Role ID for this server"}
            else:
                logging.warning(f"Netease IDV check FAILED with API code {api_code}: {api_message}. (Server: {server}, RoleID: {roleid})")
                error_detail = f" ({api_message})" if api_message else ""
                return {"status": "error", "message": f"Invalid Role ID or API Error{error_detail}"}
        except ValueError: 
            logging.error(f"Error parsing JSON for Netease IDV: (Server: {server}, RoleID: {roleid}). Status: {response.status_code}. Raw Text: {raw_text}")
            if response.status_code >= 500: return {"status": "error", "message": "Netease Server Error"}
            elif response.status_code == 403: return {"status": "error", "message": "Netease API Forbidden (403)"}
            elif response.status_code == 429: return {"status": "error", "message": "Netease API Rate Limited (429)"}
            elif "<html" in raw_text.lower(): return {"status": "error", "message": "Netease API check blocked or unavailable"}
            else: return {"status": "error", "message": f"Invalid API response (Status: {response.status_code})"}
    except requests.Timeout:
        logging.error(f"Error: Netease IDV timed out for (Server: {server}, RoleID {roleid})")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        error_text = e.response.text if e.response is not None else "No response body"
        logging.error(f"Error checking Netease IDV (Server: {server}, RoleID {roleid}): Status={status_code_str}, Error={str(e)}, Response: {error_text}")
        user_msg = f"API Connection Error ({status_code_str})"
        if e.response is not None:
            status_code_val = e.response.status_code
            if status_code_val == 403: user_msg = "Netease API Forbidden (403)"
            elif status_code_val == 401: user_msg = "Netease API Auth Error (401)"
            elif status_code_val == 404: user_msg = "Netease API Endpoint Not Found (404)"
            elif status_code_val == 429: user_msg = "Netease API Rate Limited (429)"
            elif status_code_val >= 500: user_msg = f"Netease Server Error ({status_code_val})"
        return {"status": "error", "message": user_msg}
    except Exception as e:
        logging.exception(f"Unexpected error in check_identityv_api for (Server: {server}, RoleID {roleid})")
        return {"status": "error", "message": "An unexpected server error occurred"}


# --- Flask Routes ---
@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    if not uid or not uid.isdigit():
        return jsonify({"status": "error", "message": "Invalid UID format"}), 400
    
    games_requiring_numeric_server_id = ['mobile-legends', 'ragnarok-m-classic', 'love-and-deepspace']
    if game.lower() in games_requiring_numeric_server_id and (not server_id or not server_id.isdigit()):
         return jsonify({"status": "error", "message": f"Invalid Server ID format for {game}. Expected numeric."}), 400
    
    result = check_smile_one_api(game, uid, server_id)
    status_code = 200 

    if result.get("status") == "error":
        msg = result.get("message", "")
        if "API Timeout" in msg: status_code = 504
        elif "Invalid response format" in msg: status_code = 502
        elif "API Connection Error" in msg: status_code = 502
        elif "Smile One API Unauthorized" in msg or \
             "Smile One API Forbidden" in msg or \
             "Smile One API Rate Limited" in msg:
            status_code = 403
        elif "An unexpected error occurred" in msg: status_code = 500
        elif msg.startswith("Invalid game") and "for Smile One" in msg: status_code = 500 
        elif msg.startswith("PID not configured") or "invalid server for game" in msg : status_code = 500
        elif "Invalid UID/Server" in msg or "not found in API response" in msg or "Invalid UID" in msg:
            status_code = 404
    return jsonify(result), status_code

@app.route('/check-netease/identityv/<server>/<roleid>', methods=['GET'])
def check_netease_identityv(server, roleid):
    logging.info(f"Received Netease IDV check request for Server: {server}, RoleID: {roleid}")
    if server.lower() not in IDV_SERVER_CODES:
         logging.warning(f"Invalid Identity V server received: {server}")
         return jsonify({"status": "error", "message": "Invalid server specified"}), 400
    if not roleid or not roleid.isdigit():
        logging.warning(f"Invalid Identity V RoleID format received: {roleid}")
        return jsonify({"status": "error", "message": "Invalid Role ID format"}), 400

    result = check_identityv_api(server, roleid)
    status_code = 200
    if result.get("status") == "error":
        msg = result.get("message", "")
        if "Invalid Role ID format" in msg or "Invalid server specified" in msg: status_code = 400
        elif "Netease API Forbidden" in msg or "blocked" in msg: status_code = 403
        elif "API Timeout" in msg: status_code = 504
        elif "Netease API Rate Limited" in msg: status_code = 429
        elif "Netease Server Error" in msg : status_code = 502
        elif "Invalid Role ID" in msg: status_code = 404 
        elif "An unexpected server error occurred" in msg: status_code = 500
    return jsonify(result), status_code

# --- Server Start ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True)
