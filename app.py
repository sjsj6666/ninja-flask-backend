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
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

RAZER_ZZZ_SERVER_ID_MAP = {
    "prod_official_asia": "prod_gf_jp",
    "prod_official_usa": "prod_gf_us",
    "prod_official_eur": "prod_gf_eu",
    "prod_official_cht": "prod_gf_sg"
}

# --- API Check Functions ---

def check_smile_one_api(game, uid, server_id=None):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
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
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact",
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
        current_pid = love_deepspace_pids.get(server_id)
    else:
        params_pid_map = {
            "mobile-legends": "25",
            "genshin-impact": "19731",
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
    elif game in ["honkai-star-rail", "genshin-impact", "ragnarok-m-classic", "love-and-deepspace"]:
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
                elif game in ["genshin-impact", "honkai-star-rail"]:
                    return {"status": "success", "message": "Account Verified"}
                elif game in ["bloodstrike", "ragnarok-m-classic"]:
                    return {"status": "success", "message": "Account Verified (Username not retrieved)"}
                else:
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but NO username found. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response"}
            else:
                 error_msg = data.get("message", f"Invalid UID/Server or API error code: {data.get('code')}")
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
                    if "ok" in api_message.lower() or "success" in api_message.lower(): return {"status": "success", "message": "Role ID Verified (Name missing)"}
                    else: return {"status": "error", "message": "Player found, but username unavailable"}
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
    headers = RAZER_GOLD_HEADERS.copy()
    logging.info(f"Sending Razer Gold ZZZ request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold ZZZ Raw Response (UID: {user_id}, Server: {razer_server_id}): {raw_text}")
        try:
            data = response.json()
            logging.info(f"Razer Gold ZZZ JSON Response: {data}")

            if response.status_code == 200:
                razer_api_code = data.get("code") # This is Razer's own API code, separate from HTTP status
                razer_api_message = data.get("message")

                if razer_api_code == 77003 and razer_api_message == "Invalid game user credentials":
                    logging.warning(f"Razer Gold ZZZ check FAILED. API Code: {razer_api_code}, Msg: {razer_api_message}")
                    return {"status": "error", "message": "Invalid User ID or Server for ZZZ."}

                # Successful response from Razer for ZZZ often has the username directly
                nickname = data.get("username") # As per your successful log: {"username":"x********z", ...}
                if nickname and isinstance(nickname, str):
                    logging.info(f"Razer Gold ZZZ check SUCCESS. Nickname: {nickname}")
                    return {"status": "success", "username": nickname}
                
                # Fallback structure if Razer's API changes to use data.name and code: 0
                elif razer_api_code == 0 and isinstance(data.get("data"), dict):
                    nickname_in_data = data["data"].get("name")
                    if nickname_in_data:
                        logging.info(f"Razer Gold ZZZ check SUCCESS (fallback structure data.name). Nickname: {nickname_in_data}")
                        return {"status": "success", "username": nickname_in_data}
                
                # If HTTP 200 but no clear success/error indicators or username
                logging.warning(f"Razer Gold ZZZ HTTP 200, but unclear API response. UID: {user_id}. Data: {data}")
                # You might want to return an error here or a generic success if code implies it
                if razer_api_code == 0 : # If Razer's code is 0, assume valid even if name isn't parsed
                    return {"status": "success", "message": "Account Verified (Nickname may be unavailable from Razer)"}
                else:
                    return {"status": "error", "message": razer_api_message or "Unknown success response from Razer Gold."}
            else: # HTTP error from Razer (e.g., 404, 500)
                error_message_from_api = data.get("message", f"Razer Gold API HTTP Error: {response.status_code}")
                logging.warning(f"Razer Gold ZZZ check FAILED. HTTP: {response.status_code}, API Msg: {error_message_from_api}")
                return {"status": "error", "message": error_message_from_api}

        except ValueError:
            logging.error(f"Error parsing JSON for Razer Gold ZZZ. Status: {response.status_code}. Raw: {raw_text}")
            if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer Gold API check blocked"}
            return {"status": "error", "message": f"Invalid API response from Razer Gold (Status: {response.status_code})."}

    except requests.Timeout:
        logging.error("Error: Razer Gold ZZZ API timed out.")
        return {"status": "error", "message": "Razer Gold API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Razer Gold ZZZ RequestException: Status {status_code_str}, Error: {str(e)}")
        return {"status": "error", "message": f"Razer Gold API Connection Error ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_razer_zzz_api for UID {user_id}")
        return {"status": "error", "message": "An unexpected error occurred with ZZZ validation."}

# --- Flask Routes ---
@app.route('/')
def home(): return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    if not uid or not uid.isdigit():
        return jsonify({"status": "error", "message": "Invalid UID format"}), 400
    game_lower = game.lower()
    games_req_num_server_id = ['mobile-legends', 'ragnarok-m-classic', 'love-and-deepspace']
    if game_lower in games_req_num_server_id and (not server_id or not server_id.isdigit()):
         return jsonify({"status": "error", "message": f"Invalid Server ID for {game}. Expected numeric."}), 400

    if game_lower == "zenless-zone-zero":
        logging.info(f"Routing ZZZ check to Razer Gold API for UID: {uid}, Server: {server_id}")
        if not server_id: # Razer check requires server_id for mapping
            return jsonify({"status": "error", "message": "Server ID is required for Zenless Zone Zero."}), 400
        result = check_razer_zzz_api(uid, server_id)
    else:
        result = check_smile_one_api(game, uid, server_id)

    status_code = 200
    if result.get("status") == "error":
        msg = result.get("message", "").lower()
        if "timeout" in msg: status_code = 504
        elif "invalid response format" in msg or "invalid api response" in msg: status_code = 502
        elif "connection error" in msg: status_code = 502
        elif "unauthorized" in msg or "forbidden" in msg or "rate limited" in msg or "blocked" in msg: status_code = 403
        elif "unexpected error" in msg or "pid not configured" in msg or "invalid server configuration" in msg: status_code = 500
        elif "invalid uid" in msg or "not found" in msg or "invalid user id" in msg or "invalid game user credentials" in msg : status_code = 404 # Razer 77003 maps here
    return jsonify(result), status_code

@app.route('/check-netease/identityv/<server>/<roleid>', methods=['GET'])
def check_netease_identityv(server, roleid):
    if server.lower() not in IDV_SERVER_CODES:
         return jsonify({"status": "error", "message": "Invalid server specified"}), 400
    if not roleid or not roleid.isdigit():
        return jsonify({"status": "error", "message": "Invalid Role ID format"}), 400
    result = check_identityv_api(server, roleid)
    status_code = 200
    if result.get("status") == "error":
        msg = result.get("message", "").lower()
        if "timeout" in msg: status_code = 504
        elif "invalid role id" in msg : status_code = 404
        # Add more specific mappings if needed
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True)
