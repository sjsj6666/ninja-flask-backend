from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging
import time
import uuid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) # Allow all origins for now

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
    "Referer": "https://pay.neteasegames.com/identityv/topup", # Important for Netease
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
NETEASE_IDV_STATIC_PARAMS = {
    "gc_client_version": "1.9.111", # This might need updating if API changes
    "client_type": "gameclub"
}
IDV_SERVER_CODES = { # Mapping from your frontend server value to Netease's code
    "asia": "2001",
    "na-eu": "2011"
}

# --- Razer Gold API Config ---
RAZER_GOLD_COMMON_HEADERS = { # Common headers for Razer Gold /ext/custom APIs
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin", # As these are called from your server to Razer, this might not be strictly needed, but good to mimic
}

# Razer Gold ZZZ Specifics
RAZER_GOLD_ZZZ_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{user_id}"
RAZER_GOLD_ZZZ_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_ZZZ_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/zenless-zone-zero" # Example referer

RAZER_ZZZ_SERVER_ID_MAP = { # Mapping from your frontend server value to Razer's serverId for ZZZ
    "prod_official_asia": "prod_gf_jp",
    "prod_official_usa": "prod_gf_us",
    "prod_official_eur": "prod_gf_eu",
    "prod_official_cht": "prod_gf_sg" # (TW/HK/MO often map to SG or JP on Razer)
}

# Razer Gold Genshin Impact Specifics
RAZER_GOLD_GENSHIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/genshinimpact/users/{user_id}"
RAZER_GOLD_GENSHIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_GENSHIN_HEADERS["Referer"] = "https://gold.razer.com/sg/en/gold/catalog/genshin-impact" # Example referer

# --- ADDED: Razer Gold Ragnarok Origin Specifics ---
RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE = "https://gold.razer.com/api/ext/custom/gravity-ragnarok-origin/users/{user_id}"
RAZER_GOLD_RO_ORIGIN_HEADERS = RAZER_GOLD_COMMON_HEADERS.copy()
RAZER_GOLD_RO_ORIGIN_HEADERS["Referer"] = "https://gold.razer.com/my/en/gold/catalog/ragnarok-origin" # Based on your log

# --- API Check Functions ---

def check_smile_one_api(game_code_for_smileone, uid, server_id=None, specific_smileone_pid=None):
    endpoints = {
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends/checkrole", # Note: game_code_for_smileone
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai/checkrole", # Adjusted to match potential Smile.One game codes
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole", # Needs ?product=bloodstrike
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/",
        "bigolive": "https://www.smile.one/sg/merchant/bigo/checkrole"
    }
    if game_code_for_smileone not in endpoints:
        return {"status": "error", "message": f"Invalid game_code_for_smileone '{game_code_for_smileone}' for Smile One"}

    url = endpoints[game_code_for_smileone]
    current_headers = SMILE_ONE_HEADERS.copy()
    
    referer_map = { # Referers specific to Smile.One pages
        "mobilelegends": "https://www.smile.one/merchant/mobilelegends",
        "honkaistarrail": "https://www.smile.one/br/merchant/honkai",
        "bloodstrike": "https://www.smile.one/br/merchant/game/bloodstrike",
        "ragnarokmclassic": "https://www.smile.one/sg/merchant/ragnarokmclassic",
        "loveanddeepspace": "https://www.smile.one/us/merchant/loveanddeepspace",
        "bigolive": "https://www.smile.one/sg/merchant/bigo"
    }
    current_headers["Referer"] = referer_map.get(game_code_for_smileone, "https://www.smile.one")

    # PID determination logic
    pid_to_use = specific_smileone_pid # Prioritize passed PID

    if not pid_to_use: # Fallback to default PIDs if no specific_smileone_pid is given
        bloodstrike_default_pid = os.environ.get("SMILE_ONE_PID_BLOODSTRIKE", "20294")
        bigo_default_pid = os.environ.get("SMILE_ONE_PID_BIGO", "20580")
        love_deepspace_pids_map = { "81": "19226", "82": "19227", "83": "19227" } # Server ID to PID

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
    elif game_code_for_smileone == "bloodstrike": # Bloodstrike needs product in URL
        params["uid"] = uid
        params["sid"] = server_id # or just uid if serverId is not used for bloodstrike's checkrole
    elif game_code_for_smileone == "bigolive":
        params["uid"] = uid
        params["product"] = "bigosg" # Example, check actual if needed

    logging.info(f"Sending Smile One request for {game_code_for_smileone}: URL={url}, PID={pid_to_use}, Params={params}")
    try:
        request_url_final = url
        if game_code_for_smileone == "bloodstrike": 
            request_url_final = f"{url}?product=bloodstrike" # Append product to URL for bloodstrike

        response = requests.post(request_url_final, data=params, headers=current_headers, timeout=10)
        response.raise_for_status() # Will raise HTTPError for bad responses (4xx or 5xx)
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game_code_for_smileone} (UID: {uid}, Server: {server_id}): {raw_text}")
        
        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game_code_for_smileone}: {data}")

            if data.get("code") == 200: # Common success code for Smile.One
                username_to_return = None
                # Determine primary key for username based on game
                primary_username_key = "nickname" # Default
                if game_code_for_smileone == "mobilelegends": primary_username_key = "username"
                elif game_code_for_smileone == "bigolive": primary_username_key = "message" # Bigo often puts name in message
                # Add other game-specific primary keys if known

                username_from_api = data.get(primary_username_key)
                if username_from_api and isinstance(username_from_api, str) and username_from_api.strip():
                    username_to_return = username_from_api.strip()
                else: # Fallback to check other common username keys
                    possible_username_keys = ["username", "nickname", "role_name", "name", "char_name", "message"]
                    for key in possible_username_keys:
                        if key == primary_username_key: continue # Already checked
                        value_from_api = data.get(key)
                        if value_from_api and isinstance(value_from_api, str) and value_from_api.strip():
                            username_to_return = value_from_api.strip()
                            break # Found a username
                
                if username_to_return:
                    return {"status": "success", "username": username_to_return}
                # Specific handling for games that return success but no direct username
                elif game_code_for_smileone in ["honkaistarrail", "bloodstrike", "ragnarokmclassic"]:
                    return {"status": "success", "message": "Account Verified (Username not directly provided by this API call)"}
                else: # Success code 200, but no identifiable username found
                    logging.warning(f"Smile One check successful (Code: 200) for {game_code_for_smileone} but NO username found. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response despite success code"}
            else: # API returned a non-200 'code' within its JSON
                 error_msg = data.get("message", data.get("info", f"Invalid UID/Server or API error code: {data.get('code')}"))
                 return {"status": "error", "message": error_msg}
        
        except ValueError: # JSONDecodeError - response was not valid JSON
            # Special handling for Love and Deepspace HTML response
            if game_code_for_smileone == "loveanddeepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
                try:
                    start_tag = "<span class=\"name\">"; end_tag = "</span>"
                    start_index = raw_text.find(start_tag)
                    if start_index != -1:
                        end_index = raw_text.find(end_tag, start_index + len(start_tag))
                        if end_index != -1:
                            username = raw_text[start_index + len(start_tag):end_index].strip()
                            if username:
                                logging.info(f"Successfully parsed username for Love & Deepspace from HTML: {username}")
                                return {"status": "success", "username": username}
                except Exception as parse_ex: 
                    logging.error(f"Error parsing HTML for Love & Deepspace username: {parse_ex}")
            
            logging.error(f"Error parsing JSON for Smile One {game_code_for_smileone}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API (not JSON)"}

    except requests.Timeout:
        logging.error(f"Error: Smile One API timed out for {game_code_for_smileone}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e: # Covers ConnectionError, HTTPError, etc.
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Smile One RequestException for {game_code_for_smileone}: Status {status_code_str}, Error: {e}")
        return {"status": "error", "message": f"Smile One API Connection Error ({status_code_str})"}
    except Exception as e: # Catch-all for other unexpected errors
        logging.exception(f"Unexpected error in check_smile_one_api for {game_code_for_smileone}, UID {uid}")
        return {"status": "error", "message": "An unexpected server error occurred during Smile One check"}

def check_identityv_api(server_frontend_key, roleid): # server_frontend_key is 'asia' or 'na-eu'
    server_code_for_api = IDV_SERVER_CODES.get(server_frontend_key.lower())
    if not server_code_for_api: 
        return {"status": "error", "message": "Invalid server specified for Identity V"}
    
    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code_for_api)
    current_timestamp = int(time.time() * 1000)
    trace_id = str(uuid.uuid4())
    device_id = os.environ.get("NETEASE_DEVICE_ID", "156032181698579111") # Example, use a real one or rotate
    
    query_params = {
        "roleid": roleid, 
        "timestamp": current_timestamp, 
        "traceid": trace_id, 
        "deviceid": device_id, 
        **NETEASE_IDV_STATIC_PARAMS
    }
    headers = NETEASE_IDV_HEADERS.copy()
    headers["X-TASK-ID"] = f"transid={trace_id},uni_transaction_id=default" # Netease specific header
    
    logging.info(f"Sending Netease IDV request: URL={url}, Params={query_params}")
    try:
        response = requests.get(url, params=query_params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Netease IDV Raw Response (Server: {server_frontend_key}, RoleID: {roleid}): {raw_text}")
        
        try:
            data = response.json()
            logging.info(f"Netease IDV JSON Response: {data}")
            api_code = data.get("code")
            api_message = data.get("message", data.get("msg", "")).strip()

            if api_code == "0000": # Netease success code
                username = data.get("data", {}).get("rolename")
                if username and isinstance(username, str) and username.strip():
                    return {"status": "success", "username": username.strip()}
                elif "ok" in api_message.lower() or "success" in api_message.lower(): # Success but no rolename
                    return {"status": "success", "message": "Role ID Verified (Name missing in API response)"}
                else: # Code 0000 but unclear success from message
                    return {"status": "error", "message": f"Player found, but username unavailable ({api_message or 'No details'})"}
            # Specific error messages from Netease
            elif "role not exist" in api_message.lower() or \
                 "role_not_exist" in api_message.lower() or \
                 api_code == "40004": # Observed error code for non-existent role
                return {"status": "error", "message": "Invalid Role ID for this server"}
            else: # Other API errors
                error_detail = f" ({api_message})" if api_message else ""
                return {"status": "error", "message": f"Invalid Role ID or API Error{error_detail} (Code: {api_code})"}
        
        except ValueError: # JSONDecodeError
            logging.error(f"Error parsing JSON for Netease IDV. Status: {response.status_code}. Raw: {raw_text}")
            if response.status_code >= 500: 
                return {"status": "error", "message": "Netease Server Error"}
            elif "<html" in raw_text.lower(): # Often indicates WAF/block
                return {"status": "error", "message": "Netease API check blocked or unavailable"}
            else: 
                return {"status": "error", "message": f"Invalid API response (Status: {response.status_code})"}

    except requests.Timeout: 
        logging.error(f"Error: Netease IDV API timed out for server {server_frontend_key}, role {roleid}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Netease IDV RequestException: Status {status_code_str}, Error: {e}")
        return {"status": "error", "message": f"Netease API Connection Error ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_identityv_api")
        return {"status": "error", "message": "An unexpected server error occurred during IDV check"}

def check_razer_zzz_api(user_id, server_id_frontend_key): # server_id_frontend_key is 'prod_official_asia' etc.
    razer_server_id_for_api = RAZER_ZZZ_SERVER_ID_MAP.get(server_id_frontend_key)
    if not razer_server_id_for_api:
        logging.error(f"ZZZ Razer Check: Invalid frontend server key mapping for '{server_id_frontend_key}'")
        return {"status": "error", "message": "Invalid server configuration for Zenless Zone Zero."}

    url = RAZER_GOLD_ZZZ_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": razer_server_id_for_api} # Use the mapped Razer server ID
    headers = RAZER_GOLD_ZZZ_HEADERS
    
    logging.info(f"Sending Razer Gold ZZZ request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold ZZZ Raw Response (UID: {user_id}, Frontend ServerKey: {server_id_frontend_key}, API ServerId: {razer_server_id_for_api}): {raw_text}")
        
        try:
            data = response.json()
            logging.info(f"Razer Gold ZZZ JSON Response: {data}")

            if response.status_code == 200:
                nickname = data.get("username") # ZZZ API uses "username"
                if nickname and isinstance(nickname, str) and nickname.strip():
                    return {"status": "success", "username": nickname.strip()}
                
                razer_api_code = data.get("code")
                razer_api_message = data.get("message")
                if razer_api_code == 77003 and razer_api_message == "Invalid game user credentials":
                    return {"status": "error", "message": "Invalid User ID or Server for Zenless Zone Zero."}
                elif razer_api_code == 0: # Generic success if username wasn't directly found
                    # Try common alternative keys if "username" was missed
                    alt_name = data.get("name") or data.get("data", {}).get("name")
                    if alt_name and isinstance(alt_name, str) and alt_name.strip():
                        return {"status": "success", "username": alt_name.strip()}
                    return {"status": "success", "message": "Account Verified (Nickname may be unavailable from Razer for ZZZ)"}
                
                # Unclear HTTP 200 but not a known success pattern
                return {"status": "error", "message": razer_api_message or "Unknown success response from Razer Gold (ZZZ)."}
            else: # HTTP error
                error_message_from_api = data.get("message", f"Razer Gold API HTTP Error (ZZZ): {response.status_code}")
                return {"status": "error", "message": error_message_from_api}

        except ValueError: # JSONDecodeError
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
        return {"status": "error", "message": "An unexpected server error occurred with ZZZ validation."}

def check_razer_genshin_api(user_id, server_id_frontend_key): # server_id_frontend_key is 'os_asia' etc.
    # Genshin API uses the frontend key directly as 'serverId' parameter
    url = RAZER_GOLD_GENSHIN_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": server_id_frontend_key} # Use the frontend key directly
    headers = RAZER_GOLD_GENSHIN_HEADERS

    logging.info(f"Sending Razer Gold Genshin request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold Genshin Raw Response (UID: {user_id}, ServerKey: {server_id_frontend_key}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Razer Gold Genshin JSON Response: {data}")

            if response.status_code == 200:
                nickname = data.get("username") or data.get("name") # Check both common keys
                if nickname and isinstance(nickname, str) and nickname.strip():
                    return {"status": "success", "username": nickname.strip()}
                
                razer_api_code = data.get("code")
                razer_api_message = data.get("message")
                if razer_api_code == 0 and (razer_api_message == "Success" or not razer_api_message): # code 0, message "Success" or empty
                    alt_name = data.get("name") # Double check 'name' if 'username' was missed
                    if alt_name and isinstance(alt_name, str) and alt_name.strip():
                         return {"status": "success", "username": alt_name.strip()}
                    return {"status": "success", "message": "Account Verified (Nickname not consistently provided by Razer for Genshin)"}
                elif razer_api_code == 77003 and razer_api_message == "Invalid game user credentials":
                    return {"status": "error", "message": "Invalid User ID or Server for Genshin Impact."}
                
                return {"status": "error", "message": razer_api_message or "Unknown success response from Razer Gold (Genshin)."}
            else: # HTTP error
                error_message_from_api = data.get("message", f"Razer Gold API HTTP Error (Genshin): {response.status_code}")
                return {"status": "error", "message": error_message_from_api}

        except ValueError: # JSONDecodeError
            logging.error(f"Error parsing JSON for Razer Gold Genshin. Status: {response.status_code}. Raw: {raw_text}")
            if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer Gold API check blocked (Genshin)"}
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
        return {"status": "error", "message": "An unexpected server error occurred with Genshin Impact validation."}

# --- ADDED: Razer Gold Ragnarok Origin Check Function ---
def check_razer_ragnarok_origin_api(user_id, server_id): # server_id is the numeric ID like '19'
    url = RAZER_GOLD_RO_ORIGIN_API_URL_TEMPLATE.format(user_id=user_id)
    params = {"serverId": server_id} # Pass the numeric serverId
    headers = RAZER_GOLD_RO_ORIGIN_HEADERS

    logging.info(f"Sending Razer Gold Ragnarok Origin request: URL={url}, Params={params}")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        raw_text = response.text
        logging.info(f"Razer Gold RO Origin Raw Response (UID: {user_id}, Server: {server_id}): {raw_text}")
        
        try:
            data = response.json()
            logging.info(f"Razer Gold RO Origin JSON Response: {data}")

            # Razer's /ext/custom APIs often use "code: 0" for success.
            if response.status_code == 200 and data.get("code") == 0: 
                # The actual key for username might be "username", "name", "characterName", "roleName", etc.
                # You NEED to confirm this by looking at a successful JSON response from Razer for RO Origin.
                # For now, let's try common ones:
                username = data.get("username") or data.get("name") or data.get("characterName") or data.get("rolename")
                if username and isinstance(username, str) and username.strip():
                    return {"status": "success", "username": username.strip()}
                else:
                    # Success code, but no clear username field found.
                    logging.warning(f"Razer RO Origin success (Code 0) but no username field. Data: {data}")
                    return {"status": "success", "message": "Account Verified (Nickname not in expected field from Razer for RO Origin)"}
            else: # Error from Razer (either HTTP error or API error code in JSON)
                error_message = data.get("message", f"Razer Gold API Error (RO Origin) - Code: {data.get('code', 'N/A')}, HTTP: {response.status_code}")
                return {"status": "error", "message": error_message}
        
        except ValueError: # JSONDecodeError
            logging.error(f"Error parsing JSON for Razer Gold RO Origin. Status: {response.status_code}. Raw: {raw_text}")
            if "<html" in raw_text.lower(): return {"status": "error", "message": "Razer Gold API check blocked (RO Origin)"}
            return {"status": "error", "message": f"Invalid API response from Razer Gold (RO Origin) (Status: {response.status_code})."}

    except requests.Timeout:
        logging.error(f"Error: Razer Gold RO Origin API timed out for UID {user_id}, Server {server_id}.")
        return {"status": "error", "message": "API Timeout (Ragnarok Origin)"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        logging.error(f"Razer Gold RO Origin RequestException: Status {status_code_str}, Error: {str(e)}")
        return {"status": "error", "message": f"API Connection Error (Ragnarok Origin) ({status_code_str})"}
    except Exception as e:
        logging.exception(f"Unexpected error in check_razer_ragnarok_origin_api for UID {user_id}")
        return {"status": "error", "message": "An unexpected error occurred (Ragnarok Origin)"}

# --- Flask Routes ---
@app.route('/')
def home(): 
    return "Hello! This is the Ninja Flask Backend for Game ID Validations."

# Generic dispatcher route
@app.route('/check-id/<game_slug_from_frontend>/<uid>/', defaults={'server_id': None}, methods=['GET'])
@app.route('/check-id/<game_slug_from_frontend>/<uid>/<server_id>', methods=['GET'])
def check_game_id(game_slug_from_frontend, uid, server_id):
    # Basic UID validation
    # For RO Origin, UID might not be purely numeric (e.g., TDEEFFVN). Adjust if needed.
    # if not uid or (game_slug_from_frontend != "ragnarok-origin" and not uid.isdigit()):
    #     return jsonify({"status": "error", "message": "Invalid UID format."}), 400
    
    game_lower = game_slug_from_frontend.lower()
    result = {}
    intended_region_display = None # For display purposes on your frontend

    # --- Mobile Legends Variants (using Smile.One) ---
    if game_lower == "mobile-legends-sg":
        intended_region_display = "SG"
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_SG", "YOUR_MLBB_SG_PID_FROM_SMILEONE") # IMPORTANT: Replace
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB SG."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    elif game_lower == "mobile-legends": # Assuming this is your default/ID version
        intended_region_display = "ID" # Or "Global" if that's how you market it
        smileone_pid = os.environ.get("SMILE_ONE_PID_MLBB_ID", "25") # Common PID for ID
        if not server_id or not server_id.isdigit(): return jsonify({"status": "error", "message": "Numeric Server ID required for MLBB."}), 400
        result = check_smile_one_api("mobilelegends", uid, server_id, specific_smileone_pid=smileone_pid)
    
    # --- Razer Gold Integrated Games ---
    elif game_lower == "genshin-impact":
        if not server_id: return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        # Infer display region from server_id if desired, e.g.,
        if server_id == "os_asia": intended_region_display = "Asia"
        elif server_id == "os_usa": intended_region_display = "America"
        # ... etc.
        result = check_razer_genshin_api(uid, server_id)
    elif game_lower == "zenless-zone-zero":
        if not server_id: return jsonify({"status": "error", "message": "Server selection is required for Zenless Zone Zero."}), 400
        # Infer display region from server_id (which is your frontend key like 'prod_official_asia')
        if "asia" in server_id: intended_region_display = "Asia"
        elif "usa" in server_id: intended_region_display = "America"
        # ... etc.
        result = check_razer_zzz_api(uid, server_id) # server_id here is the frontend key e.g. "prod_official_asia"
    
    # --- ADDED: Ragnarok Origin (using Razer Gold) ---
    elif game_lower == "ragnarok-origin":
        if not server_id or not server_id.isdigit(): # Razer RO API expects numeric serverId
            return jsonify({"status": "error", "message": "Numeric Server ID is required for Ragnarok Origin."}), 400
        # You might set a default region based on your product, e.g., "MY" if the Razer referer was for MY
        intended_region_display = "MY" # Or "SEA", "Global" depending on your product target
        result = check_razer_ragnarok_origin_api(uid, server_id) # uid can be alphanumeric
        
    # --- Netease Identity V ---
    elif game_lower == "identity-v":
        if not server_id or server_id.lower() not in IDV_SERVER_CODES:
            return jsonify({"status": "error", "message": "Valid server selection (Asia or NA-EU) is required for Identity V."}), 400
        if server_id.lower() == "asia": intended_region_display = "Asia"
        elif server_id.lower() == "na-eu": intended_region_display = "NA-EU"
        result = check_identityv_api(server_id, uid) # server_id here is 'asia' or 'na-eu'
        
    # --- Other Smile.One Games (General Handling) ---
    elif game_lower in ["honkai-star-rail", "bloodstrike", "ragnarok-m-classic", "love-and-deepspace", "bigo-live"]:
        # These need specific PID logic within check_smile_one_api or passed to it
        # For HSR, server_id is like 'prod_official_asia' from frontend, map if needed or pass as is if Smile.One accepts it
        # For Bloodstrike, server_id might be fixed or not used by checkrole.
        # For Ragnarok M Classic, server_id is fixed '50001'
        # For Love & Deepspace, server_id like '81' maps to PID.
        # For Bigo, server_id is often not applicable for checkrole.
        
        smileone_game_code_map = { # Map your frontend slug to Smile.One's internal game code if different
            "honkai-star-rail": "honkaistarrail",
            "bloodstrike": "bloodstrike",
            "ragnarok-m-classic": "ragnarokmclassic",
            "love-and-deepspace": "loveanddeepspace",
            "bigo-live": "bigolive"
        }
        smileone_game_code = smileone_game_code_map.get(game_lower)
        if not smileone_game_code:
            return jsonify({"status": "error", "message": f"Game slug '{game_lower}' not configured for Smile One."}), 400

        # Some games might need server_id validation before calling Smile.One
        if game_lower == "honkai-star-rail" and not server_id:
             return jsonify({"status": "error", "message": "Server ID required for Honkai: Star Rail."}), 400
        if game_lower == "love-and-deepspace" and (not server_id or not server_id.isdigit()):
             return jsonify({"status": "error", "message": "Numeric Server ID required for Love and Deepspace."}), 400
        # For ragnarok-m-classic, server_id is fixed in check_smile_one_api if not passed or used as override
        # For bloodstrike, server_id handling within check_smile_one_api
        # For bigo-live, server_id is typically null for check_smile_one_api

        result = check_smile_one_api(smileone_game_code, uid, server_id) # specific_smileone_pid can be handled inside
    else:
        return jsonify({"status": "error", "message": f"Validation not configured for game: {game_slug_from_frontend}"}), 400

    # --- Determine HTTP status code for the response ---
    status_code_http = 200
    if result.get("status") == "error":
        msg_lower = result.get("message", "").lower()
        if "timeout" in msg_lower: status_code_http = 504 # Gateway Timeout
        elif "invalid response format" in msg_lower or \
             "invalid api response" in msg_lower : status_code_http = 502 # Bad Gateway
        elif "connection error" in msg_lower or \
             "cannot connect" in msg_lower : status_code_http = 503 # Service Unavailable
        elif "unauthorized" in msg_lower or "forbidden" in msg_lower or \
             "rate limited" in msg_lower or "blocked" in msg_lower: status_code_http = 403 # Forbidden
        elif "unexpected error" in msg_lower or "pid not configured" in msg_lower or \
             "invalid server configuration" in msg_lower : status_code_http = 500 # Internal Server Error
        elif ("invalid uid" in msg_lower or "not found" in msg_lower or \
              "invalid user id" in msg_lower or "invalid game user credentials" in msg_lower or \
              "invalid role id" in msg_lower or "role not exist" in msg_lower or \
              "player found, but username unavailable" in msg_lower or \
              "user id não existe" in msg_lower): status_code_http = 404 # Not Found
        else: status_code_http = 400 # Bad Request for other API-level errors

    final_response_data = {
        "status": result.get("status"),
        "username": result.get("username"),
        "message": result.get("message"),
        "error": result.get("error"), # Pass through any explicit error field
        "region_product_context": intended_region_display # The region of the product user selected
    }
    final_response_data_cleaned = {k: v for k, v in final_response_data.items() if v is not None}
    
    logging.info(f"Flask final response for {game_lower} (UID: {uid}): {final_response_data_cleaned}, HTTP Status: {status_code_http}")
    return jsonify(final_response_data_cleaned), status_code_http


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port)
