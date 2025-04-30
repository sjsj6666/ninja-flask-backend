# ----------- app.py -----------
from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging # Added for better debugging
import time # For timestamp
import uuid # For traceid

app = Flask(__name__)
# Allow all origins for development, refine for production if needed
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
    # Load cookie from environment variable, provide a default only if necessary for testing
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "YOUR_DEFAULT_SMILE_ONE_COOKIE_IF_NEEDED") # Replace with your actual fallback if needed
}

# --- Netease Identity V Config ---
NETEASE_IDV_BASE_URL_TEMPLATE = "https://pay.neteasegames.com/gameclub/identityv/{server_code}/login-role" # Use a template
NETEASE_IDV_HEADERS = { # Headers remain the same
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pay.neteasegames.com/identityv/topup",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    # Omitting cookies initially based on log analysis
}
NETEASE_IDV_STATIC_PARAMS = {
    "gc_client_version": "1.9.111",
    "client_type": "gameclub"
}
# Mapping from user-friendly server name to API code
IDV_SERVER_CODES = {
    "asia": "2001",
    "na-eu": "2011" # Combined NA/EU code based on log
    # Add other servers if they exist and you find their codes
}

# --- API Check Functions ---

def check_smile_one_api(game, uid, server_id):
    # (This function remains unchanged)
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole"
    }

    if game not in endpoints:
        return {"status": "error", "message": f"Invalid game '{game}' for Smile One"}

    url = endpoints[game]
    current_headers = SMILE_ONE_HEADERS.copy()
    current_headers["Referer"] = (
        "https://www.smile.one/merchant/mobilelegends" if game == "mobile-legends"
        else "https://www.smile.one/ru/merchant/genshinimpact" if game == "genshin-impact"
        else "https://www.smile.one/br/merchant/honkai"
    )

    params = {
        "pid": "25" if game == "mobile-legends" else "19731" if game == "genshin-impact" else "18356" if game == "honkai-star-rail" else None,
        "checkrole": "1",
    }
    if params["pid"] is None:
         return {"status": "error", "message": f"PID not configured for game '{game}'"}

    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game == "honkai-star-rail" or game == "genshin-impact":
         params["uid"] = uid
         params["sid"] = server_id

    logging.info(f"Sending Smile One request for {game}: URL={url}, Params={params}")
    try:
        response = requests.post(url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game}: {data}")
            if data.get("code") == 200:
                username = data.get("username") or data.get("role_name") or data.get("nickname")
                if username:
                    return {"status": "success", "username": username}
                elif game in ["genshin-impact", "honkai-star-rail"] and data.get("message", "").lower() == 'ok':
                     return {"status": "success", "message": "Account Verified"}
                else:
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but username not found. Data: {data}")
                    return {"status": "error", "message": "Username not found in successful response"}
            else:
                 logging.warning(f"Smile One check failed for {game} with API code {data.get('code')}: {data.get('message')}")
                 # Use the actual message from the API if available
                 error_msg = data.get("message", f"Invalid UID/Server or API error code: {data.get('code')}")
                 return {"status": "error", "message": error_msg}
        except ValueError:
            logging.error(f"Error parsing JSON for Smile One {game}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}

    except requests.Timeout:
        logging.error(f"Error: Smile One timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        error_text = e.response.text if e.response else "No response body"
        logging.error(f"Error checking Smile One {game} UID {uid}: Status={status_code}, Error={str(e)}, Response: {error_text}")
        user_msg = f"API Connection Error ({status_code})"
        if status_code == 403: user_msg = "API Forbidden (403)"
        elif status_code == 401: user_msg = "API Unauthorized (401)"
        elif status_code == 404: user_msg = "API Endpoint Not Found (404)"
        elif status_code >= 500: user_msg = f"API Server Error ({status_code})"
        return {"status": "error", "message": user_msg}
    except Exception as e:
        logging.error(f"Unexpected error in check_smile_one_api for {game}, UID {uid}: {str(e)}")
        return {"status": "error", "message": "An unexpected error occurred"}


# --- Corrected: Netease Identity V API Check Function ---
def check_identityv_api(server, roleid):
    """Checks Identity V Player ID for a specific server."""

    server_code = IDV_SERVER_CODES.get(server.lower())
    if not server_code:
        logging.error(f"Invalid server provided for Identity V check: {server}")
        return {"status": "error", "message": "Invalid server specified"}

    url = NETEASE_IDV_BASE_URL_TEMPLATE.format(server_code=server_code)
    current_timestamp = int(time.time() * 1000)
    trace_id = str(uuid.uuid4())
    # deviceid value from the log - **This might still need dynamic generation or might be validated!**
    device_id = "156032181698579111" # Using value from log, test omitting if issues persist

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
        # We will check the status code after attempting to parse JSON

        raw_text = response.text
        logging.info(f"Netease IDV Raw Response (Server: {server}, RoleID: {roleid}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Netease IDV JSON Response: {data}")

            api_code = data.get("code") # Netease uses "code" as string
            # Get message, default to empty string if None/null
            api_message = data.get("message", data.get("msg", "")) or ""

            # --- Corrected Success Check ---
            if api_code == "0000":
                username = None
                if isinstance(data.get("data"), dict):
                    # --- Corrected Username Key ---
                    username = data["data"].get("rolename") # Use 'rolename' based on log

                if username:
                    logging.info(f"Netease IDV check SUCCESS (Server: {server}, RoleID: {roleid}). Username: {username}")
                    return {"status": "success", "username": username}
                else:
                    logging.warning(f"Netease IDV check successful (Code: {api_code}) but username field ('rolename') not found. RoleID: {roleid}. Data: {data}")
                    # Check success message safely
                    if "ok" in api_message.lower() or "success" in api_message.lower():
                         return {"status": "success", "message": "Role ID Verified (Name missing)"}
                    else:
                         return {"status": "error", "message": "Player found, but username unavailable"}

            # --- Corrected Error Handling ---
            # Check for role not existing (assuming 'role not exist' in message or a specific code like 40004 if confirmed)
            elif "role not exist" in api_message.lower() or "role_not_exist" in api_message.lower() or api_code == "40004": # Check common phrases/codes
                logging.warning(f"Netease IDV check FAILED: Role not found. (Server: {server}, RoleID: {roleid}), Code: {api_code}, Msg: {api_message}")
                return {"status": "error", "message": "Invalid Role ID for this server"}
            else:
                # Generic API error based on code/message
                logging.warning(f"Netease IDV check FAILED with API code {api_code}: {api_message}. (Server: {server}, RoleID: {roleid})")
                error_detail = f" ({api_message})" if api_message else ""
                return {"status": "error", "message": f"Invalid Role ID or API Error{error_detail}"}

        except ValueError: # JSONDecodeError
            logging.error(f"Error parsing JSON for Netease IDV: (Server: {server}, RoleID: {roleid}). Status: {response.status_code}. Raw Text: {raw_text}")
            # Check HTTP status code here if JSON parsing failed
            if response.status_code >= 500:
                 return {"status": "error", "message": "Netease Server Error"}
            elif response.status_code == 403:
                 return {"status": "error", "message": "Netease API Forbidden (403)"}
            elif response.status_code == 429:
                 return {"status": "error", "message": "Netease API Rate Limited (429)"}
            # Check for HTML only if other checks fail
            elif "<html" in raw_text.lower():
                 return {"status": "error", "message": "Netease API check blocked or unavailable"}
            else:
                 # Fallback for non-JSON, non-HTML responses
                 return {"status": "error", "message": f"Invalid API response (Status: {response.status_code})"}

    except requests.Timeout:
        logging.error(f"Error: Netease IDV timed out for (Server: {server}, RoleID {roleid})")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        error_text = e.response.text if e.response else "No response body"
        logging.error(f"Error checking Netease IDV (Server: {server}, RoleID {roleid}): Status={status_code}, Error={str(e)}, Response: {error_text}")
        user_msg = f"API Connection Error ({status_code})"
        # Add more specific messages based on status code
        if status_code == 403: user_msg = "Netease API Forbidden (403)"
        elif status_code == 401: user_msg = "Netease API Auth Error (401)"
        elif status_code == 404: user_msg = "Netease API Endpoint Not Found (404)" # Less likely with correct URL
        elif status_code == 429: user_msg = "Netease API Rate Limited (429)"
        elif status_code >= 500: user_msg = f"Netease Server Error ({status_code})"
        return {"status": "error", "message": user_msg}
    except Exception as e:
        # Log the full traceback for unexpected errors
        logging.exception(f"Unexpected error in check_identityv_api for (Server: {server}, RoleID {roleid})")
        return {"status": "error", "message": "An unexpected server error occurred"}


# --- Flask Routes ---

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

# --- Smile One Route (Unchanged) ---
@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    if not uid or not uid.isdigit():
        return jsonify({"status": "error", "message": "Invalid UID format"}), 400
    if game == 'mobile-legends' and (not server_id or not server_id.isdigit()):
         return jsonify({"status": "error", "message": "Invalid Server ID format for MLBB"}), 400

    result = check_smile_one_api(game, uid, server_id)
    status_code = 200
    if result.get("status") == "error":
        if "Invalid UID/Server" in result.get("message", "") or \
           "Invalid UID format" in result.get("message", "") or \
           "Invalid Server ID format" in result.get("message", ""):
            status_code = 400
        else:
            status_code = 500

    return jsonify(result), status_code

# --- Corrected: Route for Netease Identity V Check ---
@app.route('/check-netease/identityv/<server>/<roleid>', methods=['GET'])
def check_netease_identityv(server, roleid):
    logging.info(f"Received Netease IDV check request for Server: {server}, RoleID: {roleid}")

    # Validate server input against our known codes
    if server.lower() not in IDV_SERVER_CODES:
         logging.warning(f"Invalid Identity V server received: {server}")
         return jsonify({"status": "error", "message": "Invalid server specified"}), 400

    # Basic Role ID validation
    if not roleid or not roleid.isdigit():
        logging.warning(f"Invalid Identity V RoleID format received: {roleid}")
        return jsonify({"status": "error", "message": "Invalid Role ID format"}), 400

    result = check_identityv_api(server, roleid) # Pass server to the check function

    status_code = 200 # Default OK
    if result.get("status") == "error":
        # Check for specific messages that indicate a user error (400)
        if "Invalid Role ID" in result.get("message", "") or \
           "Invalid server" in result.get("message", ""):
            status_code = 400 # Bad Request
        # Check for blocking/forbidden errors (403)
        elif "Forbidden" in result.get("message", "") or "blocked" in result.get("message", ""):
             status_code = 403
        # Check for timeouts (504)
        elif "Timeout" in result.get("message", ""):
             status_code = 504
        # Check for rate limiting (429)
        elif "Rate Limited" in result.get("message", ""):
             status_code = 429
        # Treat other errors as server-side issues (500)
        else:
            status_code = 500

    return jsonify(result), status_code


# --- Server Start ---
if __name__ == "__main__":
    # Use Gunicorn in production instead of app.run(debug=True)
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    # For development:
    app.run(host='0.0.0.0', port=port, debug=True) # Enable debug for development
