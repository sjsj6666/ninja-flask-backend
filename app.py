# ----------- app.py -----------
from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os
import logging # Added for better debugging

app = Flask(__name__)
CORS(app)

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

# --- Midasbuy Config (Hypothetical - Needs Verification) ---
MIDASBUY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15", # From your log
    "Accept": "application/json, text/plain, */*", # Common accept header for APIs
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.midasbuy.com", # Essential Header
    "Referer": "https://www.midasbuy.com/midasbuy/sg/buy/pubgm", # Referer often important (adjust country if needed)
    "X-Requested-With": "XMLHttpRequest", # Often needed for AJAX endpoints
    # NOTE: Midasbuy might require cookies or other dynamic tokens.
    # This implementation DOES NOT handle complex tokens like 'forterToken'.
}

# PUBG Mobile App ID on Midasbuy (from your log's record0 parameter 24=...)
# !!! Needs verification if this is the correct ID for the API call. !!!
MIDASBUY_PUBGM_APPID = "1450015065"
# Default Midasbuy country - may need to be adjusted or passed as parameter
MIDASBUY_DEFAULT_COUNTRY = "sg" # Example from your log

# --- API Check Functions ---

def check_smile_one_api(game, uid, server_id):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole"
        # Add ZZZ endpoint if SmileOne supports it
        # "zenless-zone-zero": "..."
    }

    if game not in endpoints:
        return {"status": "error", "message": f"Invalid game '{game}' for Smile One"}

    url = endpoints[game]
    # Dynamically set referer based on game
    current_headers = SMILE_ONE_HEADERS.copy() # Use a copy to avoid modifying global headers
    current_headers["Referer"] = (
        "https://www.smile.one/merchant/mobilelegends" if game == "mobile-legends"
        else "https://www.smile.one/ru/merchant/genshinimpact" if game == "genshin-impact"
        else "https://www.smile.one/br/merchant/honkai" # Honkai Star Rail referer might need BR path
    )

    params = {
        # Use correct PIDs for each game - VERIFY THESE
        "pid": "25" if game == "mobile-legends" else "19731" if game == "genshin-impact" else "18356" if game == "honkai-star-rail" else None,
        "checkrole": "1",
    }
    if params["pid"] is None:
         return {"status": "error", "message": f"PID not configured for game '{game}'"}


    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game == "honkai-star-rail": # Assuming HSR uses uid/sid like Genshin for SmileOne
         params["uid"] = uid
         params["sid"] = server_id # Assuming sid maps to server_id input
    elif game == "genshin-impact":
         params["uid"] = uid
         params["sid"] = server_id # Assuming sid maps to server_id input
    # Add ZZZ params if needed

    logging.info(f"Sending Smile One request for {game}: URL={url}, Params={params}")
    try:
        response = requests.post(url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game}: {data}")

            if data.get("code") == 200:
                # Try common keys for username
                username = data.get("username") or data.get("role_name") or data.get("nickname")
                if username:
                    return {"status": "success", "username": username}
                # Handle cases where code is 200 but no username (Genshin, sometimes HSR)
                elif game in ["genshin-impact", "honkai-star-rail"] and data.get("message", "").lower() == 'ok':
                     return {"status": "success", "message": "Account Verified"} # Changed message slightly
                else: # Code 200, but no username and not a known 'OK' message
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but username not found. Data: {data}")
                    return {"status": "error", "message": "Username not found in successful response"}
            else: # API returned a non-200 internal code
                 logging.warning(f"Smile One check failed for {game} with API code {data.get('code')}: {data.get('message')}")
                 return {"status": "error", "message": data.get("message", f"Invalid UID/Server or API error code: {data.get('code')}")}
        except ValueError: # Includes JSONDecodeError
            logging.error(f"Error parsing JSON for Smile One {game}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}

    except requests.Timeout:
        logging.error(f"Error: Smile One timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else "No response body"
        logging.error(f"Error checking Smile One {game} UID {uid}: Status={status_code}, Error={str(e)}, Response: {error_text}")
        user_msg = f"API Connection Error ({status_code})"
        if status_code == 403: user_msg = "API Forbidden (403)"
        elif status_code == 401: user_msg = "API Unauthorized (401)"
        elif status_code == 404: user_msg = "API Endpoint Not Found (404)"
        elif status_code >= 500: user_msg = f"API Server Error ({status_code})"
        return {"status": "error", "message": user_msg}
    except Exception as e: # Catch any other unexpected errors
        logging.error(f"Unexpected error in check_smile_one_api for {game}, UID {uid}: {str(e)}")
        return {"status": "error", "message": "An unexpected error occurred"}


# --- NEW: Midasbuy API Check Function ---
def check_midasbuy_pubgm_api(uid, country=MIDASBUY_DEFAULT_COUNTRY):
    """
    Checks PUBG Mobile Player ID using a *hypothetical* Midasbuy endpoint.
    **Endpoint URL, payload, and response structure MUST BE VERIFIED.**
    Aims to return the full username.
    """
    # !! IMPORTANT: Verify this endpoint URL by checking Midasbuy website network traffic !!
    # This is a GUESS based on common patterns. Find the REAL one.
    url = "https://www.midasbuy.com/midasbuy/api/get_player_info" # <--- !!! GUESS - VERIFY !!!

    # !! IMPORTANT: Verify the required payload keys !!
    payload = {
        "appid": MIDASBUY_PUBGM_APPID, # <--- !!! VERIFY this App ID !!!
        "userid": uid,
        "country": country,
        # Add other parameters if the real API requires them (e.g., zoneid=1?)
    }

    # Update Referer based on country if necessary
    headers = MIDASBUY_HEADERS.copy()
    headers["Referer"] = f"https://www.midasbuy.com/midasbuy/{country}/buy/pubgm"
    headers["Origin"] = "https://www.midasbuy.com" # Ensure Origin matches the domain

    logging.info(f"Sending Midasbuy request for PUBGM: URL={url}, Payload={payload}, Headers={headers}")
    try:
        # Using Session object might help with potential cookie handling persistence if needed later
        with requests.Session() as session:
            # If you find required cookies, set them on the session:
            # session.cookies.set('cookie_name', 'cookie_value', domain='.midasbuy.com')
            response = session.post(url, data=payload, headers=headers, timeout=10)

        response.raise_for_status() # Check for HTTP errors first (4xx, 5xx)
        raw_text = response.text
        logging.info(f"Midasbuy Raw Response for PUBGM (UID: {uid}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Midasbuy JSON Response for PUBGM: {data}")

            # --- Response structure analysis needed ---
            # **ASSUMPTION:** Midasbuy returns something like:
            # {"code": 0, "message": "Success", "data": {"user_name": "PlayerNinja"}}
            # OR {"ret": 0, "msg": "OK", "nickname": "PlayerNinja"}
            # ** !!! YOU MUST ADJUST THIS based on the actual response! !!! **

            api_code = data.get("code", data.get("ret", -1)) # Check common code fields, default to -1 if none found
            api_message = data.get("message", data.get("msg", "Unknown Error"))

            if api_code == 0: # Often 0 means success
                # Try to extract username from common fields - PRIORITIZE full name
                username = None
                # Check nested 'data' dictionary first
                if isinstance(data.get("data"), dict):
                     username = data["data"].get("user_name") or data["data"].get("nickname") or data["data"].get("nick") or data["data"].get("role_name")
                # Check top-level fields if not found in 'data'
                if not username:
                     username = data.get("user_name") or data.get("nickname") or data.get("nick") or data.get("role_name")

                if username:
                    logging.info(f"Midasbuy PUBGM check SUCCESS for UID {uid}. Username: {username}")
                    return {"status": "success", "username": username} # Return the username!
                else:
                    # Successful response code but couldn't find username field
                    logging.warning(f"Midasbuy PUBGM check successful (Code: {api_code}) but username field not found. UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Player found, but username unavailable"} # Adjusted message
            else:
                # API returned an error code
                logging.warning(f"Midasbuy PUBGM check FAILED with API code {api_code}: {api_message}. UID: {uid}")
                # Make error message more user-friendly
                error_msg_user = f"Invalid Player ID ({api_message})" if api_code != -1 else "Invalid Player ID or API Error"
                return {"status": "error", "message": error_msg_user}

        except ValueError: # Includes JSONDecodeError if response is not valid JSON
            logging.error(f"Error parsing JSON for Midasbuy PUBGM: UID={uid}. Raw Text: {raw_text}")
            # Check if it's an HTML response indicating login/block/error
            if "<html" in raw_text.lower() or "login" in raw_text.lower() or "forbidden" in raw_text.lower() or "cloudflare" in raw_text.lower():
                 logging.error("Midasbuy returned HTML/Error page, likely requires login/cookies/token or is blocked.")
                 return {"status": "error", "message": "Midasbuy API check blocked"} # Simplified user message
            return {"status": "error", "message": "Invalid API response format"}

    except requests.Timeout:
        logging.error(f"Error: Midasbuy timed out for PUBGM UID {uid}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        error_text = e.response.text if e.response else "No response body"
        logging.error(f"Error checking Midasbuy PUBGM UID {uid}: Status={status_code}, Error={str(e)}, Response: {error_text}")
        # Provide clearer user messages based on status code
        user_msg = f"API Connection Error ({status_code})"
        if status_code == 403:
             user_msg = "Midasbuy API Blocked (403)"
        elif status_code == 401:
             user_msg = "Midasbuy API Auth Error (401)"
        elif status_code == 404:
             user_msg = "Midasbuy API Not Found (404)"
        elif status_code >= 500:
             user_msg = f"Midasbuy Server Error ({status_code})"
        # Add check for potential rate limiting (often 429)
        elif status_code == 429:
             user_msg = "Midasbuy API Rate Limited (429)"

        return {"status": "error", "message": user_msg}
    except Exception as e: # Catch any other unexpected errors during the process
        logging.error(f"Unexpected error in check_midasbuy_pubgm_api for UID {uid}: {str(e)}")
        return {"status": "error", "message": "An unexpected error occurred"}


# --- Flask Routes ---

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    # Basic validation for UID/Server ID format can be added here if needed
    if not uid or not uid.isdigit():
        return jsonify({"status": "error", "message": "Invalid UID format"}), 400
    if game == 'mobile-legends' and (not server_id or not server_id.isdigit()):
         return jsonify({"status": "error", "message": "Invalid Server ID format for MLBB"}), 400
    # Add similar checks for Genshin/HSR server IDs if they have specific formats

    result = check_smile_one_api(game, uid, server_id)
    status_code = 200
    if result.get("status") == "error" and "Invalid UID/Server" in result.get("message", ""):
        status_code = 400 # Bad Request for invalid ID/Server from API
    elif result.get("status") == "error":
         status_code = 500 # Internal Server Error for other API issues

    return jsonify(result), status_code


# --- NEW: Route for Midasbuy PUBG Mobile Check ---
@app.route('/check-midasbuy/pubgm/<uid>', methods=['GET'])
# Optional country route if needed later:
# @app.route('/check-midasbuy/pubgm/<uid>/<country>', methods=['GET'])
def check_midasbuy_pubgm(uid, country=None):
    # Use provided country or default if route allows it, otherwise use constant
    target_country = country if country else MIDASBUY_DEFAULT_COUNTRY
    logging.info(f"Received Midasbuy check request for PUBGM UID: {uid}, Country: {target_country}")

    # Basic UID validation before calling API
    if not uid or not uid.isdigit() or len(uid) < 5: # Basic length check for PUBGM IDs
        logging.warning(f"Invalid PUBGM UID format received: {uid}")
        return jsonify({"status": "error", "message": "Invalid Player ID format"}), 400 # Return 400 Bad Request

    result = check_midasbuy_pubgm_api(uid, target_country)

    # Determine appropriate HTTP status code for the response
    status_code = 200 # Default OK
    if result.get("status") == "error":
        if "Invalid Player ID" in result.get("message", ""):
            status_code = 400 # Bad Request for invalid ID
        elif "Midasbuy API check blocked" in result.get("message", "") or "Blocked" in result.get("message", ""):
             status_code = 403 # Forbidden if blocked
        elif "Timeout" in result.get("message", ""):
             status_code = 504 # Gateway Timeout
        elif "Error" in result.get("message", ""): # Catch other errors
            status_code = 500 # Internal Server Error / Bad Gateway

    return jsonify(result), status_code

# --- Server Start ---
if __name__ == "__main__":
    # Use Gunicorn in production instead of app.run(debug=True)
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    # For development:
    app.run(host='0.0.0.0', port=port, debug=True) # Enable debug for development
