import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv 
import logging
import hashlib 

load_dotenv()

app = Flask(__name__)
CORS(app) 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SMILE_ONE_API_URL = "https://globalapi.smile.one/smilecoin/api/product/checkrole"
# Ensure these are correctly set in your Render environment variables
SMILE_ONE_USER_ID = os.getenv("SMILE_ONE_USER_ID") 
SMILE_ONE_SECRET_KEY = os.getenv("SMILE_ONE_SECRET_KEY") 
SMILE_ONE_MERCHANT_ID = os.getenv("SMILE_ONE_MERCHANT_ID") 

SMILE_ONE_PRODUCT_IDS = {
    "mobile-legends": "1001",
    "honkai-star-rail": "2056",
    "bloodstrike": "2103",
    "ragnarok-m-classic": "3010",
    "love-and-deepspace": "2088",
    "bigo-live": "4001",
}

NETEASE_IDV_API_URL = os.getenv("NETEASE_IDV_API_URL", "https://pay.neteasegames.com/g37/api/check_user")

@app.route('/')
def home():
    return "Ninja Flask Backend is running!"

def generate_smile_one_signature(params, secret_key):
    # Ensure secret_key is a string before concatenation, if it might be None
    if not secret_key:
        logger.error("Smile.One secret key is not set. Signature generation will fail.")
        return "dummy_key_error_secret_not_set" # Or raise an error

    sorted_params = sorted(params.items())
    query_string_parts = [f"{k}={v}" for k, v in sorted_params if v is not None and k != "key"]
    raw_string = "&".join(query_string_parts) + secret_key
    signature = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
    return signature

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
@app.route('/check-smile/<game>/<uid>', methods=['GET'])
def check_game_user_proxy(game, uid, server_id=None):
    logger.info(f"Received check request for game: {game}, UID: {uid}, Server ID: {server_id}")

    razer_base_url = "https://gold.razer.com/api/ext"
    
    razer_headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': f'https://gold.razer.com/gold/catalog/{game}', 
        'Origin': 'https://gold.razer.com', 
    }

    # Determine if the game is a Razer game and construct URL
    razer_url = None
    service_name = None

    if game == 'genshin-impact':
        if not server_id:
            logger.warning("Genshin Impact check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        razer_url = f"{razer_base_url}/genshinimpact/users/{uid}?serverId={server_id}"
        service_name = "Razer (Genshin Impact)"
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/genshin-impact'
    elif game == 'zenless-zone-zero':
        if not server_id:
            logger.warning("Zenless Zone Zero check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Zenless Zone Zero."}), 400
        razer_url = f"{razer_base_url}/zenlesszonezero/users/{uid}?serverId={server_id}"
        service_name = "Razer (Zenless Zone Zero)"
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/zenless-zone-zero'
    elif game == 'marvel-rivals': 
        if not server_id: # Adjust if Marvel Rivals on Razer doesn't need server_id
            logger.warning("Marvel Rivals (Razer) check: Server ID missing (assuming required).")
            return jsonify({"status": "error", "message": "Server ID is required for Marvel Rivals (Razer)."}), 400
        razer_url = f"{razer_base_url}/marvelrivals/users/{uid}?serverId={server_id}" # Guessed path
        service_name = "Razer (Marvel Rivals)"
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/marvel-rivals' 

    # --- Razer API Call Logic ---
    if razer_url and service_name:
        logger.info(f"Calling {service_name} API: {razer_url} with headers: {razer_headers}")
        try:
            response = requests.get(razer_url, headers=razer_headers, timeout=10)
            
            logger.info(f"{service_name} raw response status: {response.status_code}")
            # logger.debug(f"{service_name} raw response headers: {response.headers}") # Use debug for verbose
            # logger.debug(f"{service_name} raw response text: {response.text[:500]}")

            response.raise_for_status() 
            data = response.json()
            logger.info(f"{service_name} API JSON response: {data}")

            if data.get("status") == "success" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif data.get("status") == "fail" and data.get("message"):
                return jsonify({"status": "error", "message": data["message"]})
            else:
                logger.warning(f"Unexpected JSON response structure from {service_name}: {data}")
                return jsonify({"status": "error", "message": f"Unexpected response from {service_name}."})

        except requests.exceptions.HTTPError as errh:
            error_content = errh.response.text[:500] 
            logger.error(f"HTTPError calling {service_name}: Status {errh.response.status_code}, Response: {error_content}")
            # Try to parse JSON from error response, otherwise use raw text
            try: error_message = errh.response.json().get("message", error_content)
            except ValueError: error_message = error_content
            return jsonify({"status": "error", "message": error_message}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling {service_name} API.")
            return jsonify({"status": "error", "message": f"Request to {service_name} API timed out."}), 504
        except requests.exceptions.RequestException as e: # Catches other issues like NameResolutionError if it happened for Razer
            logger.error(f"RequestException calling {service_name}: {str(e)}")
            return jsonify({"status": "error", "message": f"{service_name} API Request Error: {str(e)}"}), 500
        except ValueError: 
            raw_text_on_error = locals().get('response', {}).text[:500] if 'response' in locals() else "N/A"
            logger.error(f"ValueError (JSONDecodeError) parsing {service_name} response. Raw text: {raw_text_on_error}")
            return jsonify({"status": "error", "message": f"Invalid JSON response from {service_name}."}), 500

    # --- Smile.One API Call Logic ---
    elif game in SMILE_ONE_PRODUCT_IDS:
        if not SMILE_ONE_MERCHANT_ID or not SMILE_ONE_USER_ID or not SMILE_ONE_SECRET_KEY:
            logger.error("Smile.One credentials (MERCHANT_ID, USER_ID, or SECRET_KEY) are not configured in environment variables.")
            return jsonify({"status": "error", "message": "Smile.One integration not configured correctly."}), 500
            
        product_id = SMILE_ONE_PRODUCT_IDS[game]
        params = {
            "merchant_id": SMILE_ONE_MERCHANT_ID,
            "product_id": product_id,
            "game_user_id": uid,
            "user_id": SMILE_ONE_USER_ID, 
        }
        if server_id and server_id != "null" and server_id != "" and server_id != "-1":
            params["game_zone_id"] = server_id
        
        params["key"] = generate_smile_one_signature(params, SMILE_ONE_SECRET_KEY)

        logger.info(f"Calling Smile.One API with params: {params} (URL: {SMILE_ONE_API_URL})")
        try:
            response = requests.post(SMILE_ONE_API_URL, data=params, timeout=7)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Smile.One API response for {game}: {data}")

            if str(data.get("status")) == "200" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif str(data.get("status")) == "200" and data.get("message") == "OK":
                 return jsonify({"status": "success", "message": "Account Verified"})
            else:
                error_msg = data.get("message", f"Unknown error from Smile.One (Status: {data.get('status')}).")
                return jsonify({"status": "error", "message": error_msg})
        except requests.exceptions.HTTPError as errh:
            logger.error(f"HTTPError calling Smile.One for {game}: {str(errh.response.text[:200])}")
            return jsonify({"status": "error", "message": f"Smile.One API HTTP Error: {str(errh.response.text[:100])}"}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling Smile.One for {game}.")
            return jsonify({"status": "error", "message": "Request to Smile.One API timed out."}), 504
        except requests.exceptions.RequestException as e: # This will catch NameResolutionError for Smile.One
            logger.error(f"RequestException calling Smile.One for {game}: {str(e)}")
            return jsonify({"status": "error", "message": f"Smile.One API Request Error: {str(e)}"}), 500
        except ValueError:
            logger.error(f"ValueError parsing Smile.One response for {game}.")
            return jsonify({"status": "error", "message": "Invalid JSON response from Smile.One."}), 500
            
    # --- Fallback for unsupported games ---
    else:
        logger.warning(f"Unsupported game for check: {game}")
        return jsonify({"status": "error", "message": "Unsupported game for UID check."}), 404


# --- Netease Identity V Proxy (Placeholder - likely needs significant auth work) ---
@app.route('/check-netease/identityv/<server_id>/<role_id>', methods=['GET'])
def check_netease_identityv_proxy(server_id, role_id):
    logger.info(f"Received Netease IDV check request for Server: {server_id}, Role ID: {role_id}")
    payload = {
        "game": "g37", "roleid": role_id, "serverid": server_id, "check_type": "user_info" 
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://pay.neteasegames.com/' 
    }
    logger.warning("Netease Identity V check is a placeholder and likely requires more complex authentication (signatures, tokens) than implemented.")
    try:
        response = requests.post(NETEASE_IDV_API_URL, data=payload, headers=headers, timeout=7)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Netease IDV API response: {data}")

        if str(data.get("code")) == "0" and data.get("userInfo", {}).get("rolename"):
            return jsonify({"status": "success", "username": data["userInfo"]["rolename"]})
        else:
            error_msg = data.get("msg", "Invalid Role ID or Server for Identity V.")
            return jsonify({"status": "error", "message": error_msg})
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException calling Netease IDV: {str(e)}")
        return jsonify({"status": "error", "message": f"Netease IDV API Request Error: {str(e)}"}), 500
    # ... other specific exception handling ...
    except Exception as e: # Catch-all for unexpected issues
        logger.error(f"Unexpected error in Netease IDV check: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred during Netease IDV check."}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001)) 
    # Set FLASK_ENV to 'development' in your .env file for local debug mode
    is_development = os.environ.get("FLASK_ENV") == "development"
    app.run(host='0.0.0.0', port=port, debug=is_development)
