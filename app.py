from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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

# --- Razer Gold API Config ---
RAZER_GOLD_HEADERS = { # Common headers for Razer Gold
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Razer Gold ZZZ Specifics
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_HEADERS.copy()
RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero"

RAZER_ZZZ_SERVER_ID_MAP = {
    "prod_official_asia": "prod_gf_jp",
    "prod_official_usa": "prod_gf_us",
    "prod_official_eur": "prod_gf_eu",
    "prod_official_cht": "prod_gf_sg"
}

# Razer Gold Genshin Impact Specifics
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_HEADERS.copy()
RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact"


# --- API Check Functions ---

def check_smile_one_api(game, uid, server_id=None):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole",
        "ragnarok-m-classic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "love-and-deepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/",
        "bigo-live": "https://www.smile.one/sg/merchant/bigo/checkrole"
    }
    if game not in endpoints:
        return {"status": "error", "message": f"Invalid game '{game}' for Smile One"}

    url = endpoints[game]
    current_headers = SMILE_ONE_HEADERS.copy()
    referer_map = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai",
        "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike",
        "ragnarok-m-classic": "https://www.smile.one/sg/merchant/ragnarokmclassic",
        "love-and-deepspace": "https://www.smile.one/us/merchant/loveanddeepspace",
        "bigo-live": "https://www.smile.one/sg/merchant/bigo"
    }
    current_headers["Referer"] = referer_map.get(game, "https://www.smile.one")

    bloodstrike_pid = os.environ.get("BLOODSTRIKE_SMILE_ONE_PID", "20294")
    bigo_pid = os.environ.get("BIGO_SMILE_ONE_PID", "20580")
    love_deepspace_pids = { "81": "19226", "82": "19227", "83": "19227" }

    current_pid = None
    if game == "love-and-deepspace":
        current_pid = love_deepspace_pids.get(str(server_id))
    else:
        params_pid_map = {
            "mobile-legends": "25",
            "honkai-star-rail": "18356",
            "bloodstrike": bloodstrike_pid,
            "ragnarok-m-classic": "23026",
            "bigo-live": bigo_pid
        }
        current_pid = params_pid_map.get(game)

    if current_pid is None:
         return {"status": "error", "message": f"PID not configured for game '{game}'"}

    params = { "pid": current_pid, "checkrole": "1" }
    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game in ["honkai-star-rail", "ragnarok-m-classic", "love-and-deepspace"]:
         params["uid"] = uid
         params["sid"] = server_id
    elif game == "bloodstrike":
        params["uid"] = uid
        params["sid"] = server_id
    elif game == "bigo-live":
        params["uid"] = uid
        params["product"] = "bigosg"

    logging.info(f"Sending Smile One request for {game}: URL={url}, Params={params}")
    try:
        request_url = url
        if game == "bloodstrike": request_url = f"{url}?product=bloodstrike"
        response = requests.post(request_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")
        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game}: {data}")
            if data.get("code") == 200:
                username_to_return = None
                primary_username_key = "nickname"
                if game == "mobile-legends": primary_username_key = "username"
                elif game == "bigo-live": primary_username_key = "message"
                elif game == "love-and-deepspace": primary_username_key = "nickname"

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
                elif game in ["honkai-star-rail"]:
                    return {"status": "success", "message": "Account Verified"}
                elif game in ["bloodstrike", "ragnarok-m-classic"]:
                    return {"status": "success", "message": "Account Verified (Username not retrieved)"}
                else:
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but NO username found. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response"}
            else:
                 error_msg = data.get("message", data.get("info", f"Invalid UID/Server or API error code: {data.get('code')}"))
                 return {"status": "error", "message": error_msg}
        except ValueError:
            if game == "love-and-deepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
                try:
                    start_tag = "<span class=\"name\">"; end_tag = "</span>"
                    start_index = raw_text.find(start_tag)
                    if start_index != -1:
                        end_index = raw_text.find(end_tag, start_index + len(start_tag))
                        if end_index != -1:
                            username = raw_text[start_index + len(start_tag):end_index].strip()
                            if username:
                                return {"status": "success", "username": username}
                except Exception as parse_ex: logging.error(f"Error parsing HTML for L&D: {parse_ex}")
            
            logging.error(f"Error parsing JSON for Smile One {game}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}
    except requests.Timeout:
        logging.error(f"Error: Smile One API timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Smile One RequestException for {game}: Status {status_code_str}, Error: {e}")
        return {"status": "error", "message": f"Smile One API Connection Error ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_smile_one_api for {game}, UID {uid}")
        return {"status": "error", "message": "An unexpected error occurred"}

def check_identityv_api(server, roleid):
    server_code = IDV_SERVER_CODES.get(server.lower())
    if not server_code: return {"status": "error", "message": "Invalid server specified"}
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    current_timestamp = int(time.time() * 1000)
    trace_id = str(uuid.uuid4()); device_id = os.environ.get("NETEASE_DEVICE_ID", "156032181698579111")
    query_params = {"roleid": roleid, "timestamp": current_timestamp, "traceid": trace_id, "deviceid": device_id, **NETEASE_IDV_STATIC_PARAMS}
    headers = NETEASE_IDV_HEADERS.copy(); headers["X-TASK-ID"] = f"transid={trace_id},uni_transaction_id=default"
    logging.info(f"Sending Netease IDV request: URL={url}, Params={query_params}")
    try:
        response = requests.get(url, params=query_params, headers=headers, timeout=10)
        raw_text = response.text; logging.info(f"Netease IDV Raw Response (Server: {server}, RoleID: {roleid}): {raw_text}")
        try:
            data = response.json(); logging.info(f"Netease IDV JSON Response: {data}")
            api_code = data.get("code"); api_message = data.get("message", data.get("msg", "")) or ""
            if api_code == "0000":
                username = data.get("data", {}).get("rolename")
                if username: return {"status": "success", "username": username}
                else:
                    if "ok" in api_message.lower() or "success" in api_message.lower():
                        return {"status": "success", "message": "Role ID Verified (Name missing)"}
                    else:
                        return {"status": "error", "message": "Player found, but username unavailable"}
            elif "role not exist" in api_message.lower() or "role_not_exist" in api_message.lower() or api_code == "40004":
                return {"status": "error", "message": "Invalid Role ID for this server"}
            else:
                error_detail = f" ({api_message})" if api_message else ""
                return {"status": "error", "message": f"Invalid Role ID or API Error{error_detail}"}
        except ValueError:
            logging.error(f"Error parsing JSON for Netease IDV. Status: {response.status_code}. Raw: {raw_text}")
            if response.status_code >= 500: return {"status": "error", "message": "Netease Server Error"}
            elif "<html" in raw_text.lower(): return {"status": "error", "message": "Netease API check blocked"}
            else: return {"status": "error", "message": f"Invalid API response (Status: {response.status_code})"}
    except requests.Timeout: return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Netease IDV RequestException: Status {status_code_str}, Error: {e}")
        return {"status": "error", "message": f"Netease API Connection Error ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_identityv_api")
        return {"status": "error", "message": "An unexpected server error occurred"}

def check_razer_zzz_api(user_id, server_id_internal):
    razer_server_id = RAZER_ZZZ_SERVER_ID_MAP.get(server_id_internal)
    if not razer_server_id:
        logging.error(f"ZZZ Razer Check: Invalid internal server ID mapping for '{server_id_internal}'")
        return {"status": "error", "message": "Invalid server configuration for ZZZ."}

    url = RAZER_GOLD_ZZZ_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": razer_server_id}
    headers = RAZER_GOLD_ZZZ_HEADERS
    logging.info(f"Sending Razer Gold ZZZ request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold ZZZ Raw Response (UID: {user_id}, Server: {razer_server_id}): {raw_text}")
        try:
            data = response.json()
            logging.info(f"Razer Gold ZZZ JSON Response: {data}")

            if response.status_code == 200:
                nickname = data.get("username") # ZZZ seems to consistently use "username"
                if nickname and isinstance(nickname, str):
                    logging.info(f"Razer Gold ZZZ check SUCCESS. Nickname: {nickname}")
                    return {"status": "success", "username": nickname}
                
                razer_api_code = data.get("code")
                razer_api_message = data.get("message")
                if razer_api_code == 77003 and razer_api_message == "Invalid game user credentials":
                    logging.warning(f"Razer Gold ZZZ check FAILED (Invalid Credentials). API Code: {razer_api_code}, Msg: {razer_api_message}")
                    return {"status": "error", "message": "Invalid User ID or Server for ZZZ."}
                elif razer_api_code == 0: # Generic success if code is 0 but username wasn't picked up above
                    # This might happen if the 'username' key changes or is nested differently
                    name_in_data = data.get("data", {}).get("name") # Fallback for a different structure
                    if name_in_data and isinstance(name_in_data, str):
                        return {"status": "success", "username": name_in_data}
                    logging.info(f"Razer Gold ZZZ check SUCCESS (Code 0), but no clear nickname. Data: {data}")
                    return {"status": "success", "message": "Account Verified (Nickname may be unavailable from Razer for ZZZ)"}
                
                logging.warning(f"Razer Gold ZZZ HTTP 200, but unclear API response (no username/known codes). UID: {user_id}. Data: {data}")
                return {"status": "error", "message": razer_api_message or "Unknown success response from Razer Gold (ZZZ)."}
            else:
                error_message_from_api = data.get("message", f"Razer Gold API HTTP Error (ZZZ): {response.status_code}")
                logging.warning(f"Razer Gold ZZZ check FAILED. HTTP: {response.status_code}, API Msg: {error_message_from_api}")
                return {"status": "error", "message": error_message_from_api}

        except ValueError:
            logging.error(f"Error parsing JSON for Razer Gold ZZZ. Status: {response.status_code}. Raw: {raw_text}")
            if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer Gold API check blocked (ZZZ)"}
            return {"status": "error", "message": f"Invalid API response from Razer Gold (ZZZ) (Status: {response.status_code})."}

    except requests.Timeout:
        logging.error("Error: Razer Gold ZZZ API timed out.")
        return {"status": "error", "message": "Razer Gold API Timeout (ZZZ)"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Razer Gold ZZZ RequestException: Status {status_code_str}, Error: {str(e)}")
        return {"status": "error", "message": f"Razer Gold API Connection Error (ZZZ) ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_razer_zzz_api for UID {user_id}")
        return {"status": "error", "message": "An unexpected error occurred with ZZZ validation."}

def check_razer_genshin_api(user_id, server_id):
    url = RAZER_GOLD_GENSHIN_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": server_id}
    headers = RAZER_GOLD_GENSHIN_HEADERS

    logging.info(f"Sending Razer Gold Genshin request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold Genshin Raw Response (UID: {user_id}, Server: {server_id}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Razer Gold Genshin JSON Response: {data}")

            if response.status_code == 200:
                # Case 1: Direct username (observed in logs: {"username":"A*****y","serverId":"os_asia"})
                # Razer API can be inconsistent; "username" or "name" might be used.
                nickname = data.get("username") or data.get("name")
                if nickname and isinstance(nickname, str):
                    logging.info(f"Razer Gold Genshin check SUCCESS (direct name/username). Nickname: {nickname}")
                    return {"status": "success", "username": nickname}

                # Case 2: API code and message based (previously observed: {"name":"PlayerName", "code":0, "message":"Success"})
                razer_api_code = data.get("code")
                razer_api_message = data.get("message")

                if razer_api_code == 0 and razer_api_message == "Success":
                    name_field_in_code_success = data.get("name") # Check "name" if code 0 and msg success
                    if name_field_in_code_success and isinstance(name_field_in_code_success, str):
                        logging.info(f"Razer Gold Genshin check SUCCESS (code 0, msg Success, with name). Nickname: {name_field_in_code_success}")
                        return {"status": "success", "username": name_field_in_code_success}
                    else:
                        # This means code 0, msg Success, but "name" field was missing or invalid.
                        logging.warning(f"Razer Gold Genshin check success (Code 0, Msg Success), but 'name' field missing/invalid. Data: {data}")
                        return {"status": "success", "message": "Account Verified (Nickname not retrieved from Razer - C0S)"}
                
                # Known error case from Razer
                elif razer_api_code == 77003 and razer_api_message == "Invalid game user credentials":
                    logging.warning(f"Razer Gold Genshin check FAILED (Invalid Credentials). API Code: {razer_api_code}, Msg: {razer_api_message}")
                    return {"status": "error", "message": "Invalid User ID or Server for Genshin Impact."}
                
                # If code is 0 but message is not "Success", or other codes (and no direct nickname was found earlier)
                elif razer_api_code == 0 : 
                    logging.info(f"Razer Gold Genshin check SUCCESS (Code 0), but no direct nickname and message not 'Success'. Data: {data}")
                    return {"status": "success", "message": f"Account Verified (Razer: {razer_api_message or 'Details N/A'})"}

                # Unclear HTTP 200 response if none of the above specific conditions matched
                logging.warning(f"Razer Gold Genshin HTTP 200, but unclear API response. UID: {user_id}. Data: {data}")
                return {"status": "error", "message": razer_api_message or "Unknown success response from Razer Gold (Genshin)."}

            else: # HTTP error from Razer
                error_message_from_api = "Unknown Razer API Error"
                try:
                    error_data_on_http_fail = response.json() # Attempt to parse error message from JSON
                    error_message_from_api = error_data_on_http_fail.get("message", f"Razer Gold API HTTP Error (Genshin): {response.status_code}")
                except ValueError: # If response on HTTP error is not JSON
                    error_message_from_api = f"Razer Gold API HTTP Error (Genshin): {response.status_code}. Non-JSON response: {raw_text[:100]}"
                
                logging.warning(f"Razer Gold Genshin check FAILED. HTTP: {response.status_code}, API Msg: {error_message_from_api}")
                return {"status": "error", "message": error_message_from_api}

        except ValueError: # JSONDecodeError for the main try block's response.json()
            logging.error(f"Error parsing JSON for Razer Gold Genshin. Status: {response.status_code}. Raw: {raw_text}")
            if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer Gold API check blocked (Genshin)"} # WAF/Captcha
            return {"status": "error", "message": f"Invalid API response from Razer Gold (Genshin) (Status: {response.status_code})."}

    except requests.Timeout:
        logging.error("Error: Razer Gold Genshin API timed out.")
        return {"status": "error", "message": "Razer Gold API Timeout (Genshin)"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Razer Gold Genshin RequestException: Status {status_code_str}, Error: {str(e)}")
        return {"status": "error", "message": f"Razer Gold API Connection Error (Genshin) ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_razer_genshin_api for UID {user_id}")
        return {"status": "error", "message": "An unexpected error occurred with Genshin Impact validation."}


# --- Flask Routes ---
@app.route('/')
def home(): return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    if not uid or not uid.isdigit():
        return jsonify({"status": "error", "message": "Invalid UID format. UID must be numeric."}), 400
    
    game_lower = game.lower()

    games_req_num_server_id_smileone = ['mobile-legends', 'ragnarok-m-classic', 'love-and-deepspace']
    if game_lower in games_req_num_server_id_smileone:
        if not server_id or not server_id.isdigit():
            return jsonify({"status": "error", "message": f"Invalid Server ID for {game}. Expected numeric."}), 400

    if game_lower == "zenless-zone-zero":
        logging.info(f"Routing ZZZ check to Razer Gold API for UID: {uid}, Server (internal key): {server_id}")
        if not server_id:
            return jsonify({"status": "error", "message": "Server ID (internal key) is required for Zenless Zone Zero."}), 400
        result = check_razer_zzz_api(uid, server_id)
    elif game_lower == "genshin-impact":
        logging.info(f"Routing Genshin Impact check to Razer Gold API for UID: {uid}, Server: {server_id}")
        if not server_id: 
            return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact (Razer check)."}), 400
        result = check_razer_genshin_api(uid, server_id)
    else:
        result = check_smile_one_api(game_lower, uid, server_id)

    status_code = 200
    if result.get("status") == "error":
        msg = result.get("message", "").lower()
        if "timeout" in msg: status_code = 504
        elif "invalid response format" in msg or "invalid api response" in msg or "invalid api response from razer gold" in msg : status_code = 502
        elif "connection error" in msg or "cannot connect" in msg: status_code = 503
        elif "unauthorized" in msg or "forbidden" in msg or "rate limited" in msg or "blocked" in msg: status_code = 403
        elif "unexpected error" in msg or "pid not configured" in msg or "invalid server configuration" in msg: status_code = 500
        elif ("invalid uid" in msg or "not found" in msg or "invalid user id" in msg or 
              "invalid game user credentials" in msg or "invalid role id" in msg or 
              "role not exist" in msg or "player found, but username unavailable" in msg or
              "user id não existe" in msg # From SmileOne for MLBB
              ):
            status_code = 404
    
    return jsonify(result), status_code

@app.route('/check-netease/identityv/<server>/<roleid>', methods=['GET'])
def check_netease_identityv(server, roleid):
    if server.lower() not in IDV_SERVER_CODES:
         return jsonify({"status": "error", "message": "Invalid server specified for Identity V"}), 400
    if not roleid or not roleid.isdigit():
        return jsonify({"status": "error", "message": "Invalid Role ID format for Identity V. Must be numeric."}), 400
    
    result = check_identityv_api(server, roleid)

    status_code = 200
    if result.get("status") == "error":
        msg = result.get("message", "").lower()
        if "timeout" in msg: status_code = 504
        elif "invalid role id" in msg or "role not exist" in msg : status_code = 404
        elif "netease server error" in msg: status_code = 502
        elif "connection error" in msg: status_code = 503
        elif "blocked" in msg : status_code = 403
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port)
