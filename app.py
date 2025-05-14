import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv # This line requires python-dotenv to be installed
import logging
import hashlib # For Smile.One key generation if you implement it fully

load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants for Smile.One ---
SMILE_ONE_API_URL = "https://globalapi.smile.one/smilecoin/api/product/checkrole"
# These would ideally come from environment variables for security
SMILE_ONE_USER_ID = os.getenv("SMILE_ONE_USER_ID", "YOUR_SMILE_ONE_USER_ID") # Example default
SMILE_ONE_SECRET_KEY = os.getenv("SMILE_ONE_SECRET_KEY", "YOUR_SMILE_ONE_SECRET_KEY") # Example default
SMILE_ONE_MERCHANT_ID = os.getenv("SMILE_ONE_MERCHANT_ID", "198765") # Example default

# Game-specific product IDs for Smile.One
SMILE_ONE_PRODUCT_IDS = {
    "mobile-legends": "1001",
    "honkai-star-rail": "2056",
    "bloodstrike": "2103",
    "ragnarok-m-classic": "3010",
    "love-and-deepspace": "2088",
    "bigo-live": "4001",
    # "genshin-impact": "2002", # Genshin now uses Razer
    # "zenless-zone-zero": "RAZER_ZZZ", # ZZZ now uses Razer
    # "marvel-rivals": "RAZER_MARVEL_RIVALS" # Marvel Rivals if it uses Razer
}

# --- Netease Identity V Specific ---
NETEASE_IDV_API_URL = os.getenv("NETEASE_IDV_API_URL", "https://pay.neteasegames.com/g37/api/check_user")

@app.route('/')
def home():
    return "Ninja Flask Backend is running!"

def generate_smile_one_signature(params, secret_key):
    """
    Generates a signature for Smile.One API calls.
    This is a simplified example. Refer to Smile.One documentation for exact requirements.
    Typically involves sorting parameters, concatenating them with the secret key, and hashing.
    """
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        # 'Referer': 'https://gold.razer.com/' # Sometimes helpful
    }

    # --- Razer Gold API Games ---
    if game == 'genshin-impact':
        if not server_id:
            logger.warning("Genshin Impact check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        razer_url = f"{razer_base_url}/genshinimpact/users/{uid}?serverId={server_id}"
        service_name = "Razer (Genshin Impact)"
    elif game == 'zenless-zone-zero':
        if not server_id:
            logger.warning("Zenless Zone Zero check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Zenless Zone Zero."}), 400
        # Assuming ZZZ Razer API path is similar to Genshin. Adjust if different.
        razer_url = f"{razer_base_url}/zenlesszonezero/users/{uid}?serverId={server_id}"
        service_name = "Razer (Zenless Zone Zero)"
    elif game == 'marvel-rivals': # Example if Marvel Rivals uses a similar Razer API
        if not server_id: # Marvel Rivals might not need a server_id for Razer check. Adjust as needed.
             logger.warning("Marvel Rivals (Razer) check: Server ID missing, but might not be required by this specific Razer endpoint.")
             # If server_id is truly optional for this game on Razer:
             # razer_url = f"{razer_base_url}/marvelrivals/users/{uid}" # Example without serverId
             # If it IS required:
             # return jsonify({"status": "error", "message": "Server ID is required for Marvel Rivals (Razer)."}), 400
        # For now, assuming it requires serverId for consistency, adjust if API differs:
        razer_url = f"{razer_base_url}/marvelrivals/users/{uid}?serverId={server_id}"
        service_name = "Razer (Marvel Rivals)"
    else:
        razer_url = None # Not a Razer game handled here

    if razer_url:
        logger.info(f"Calling {service_name} API: {razer_url}")
        try:
            response = requests.get(razer_url, headers=razer_headers, timeout=8)
            response.raise_for_status()
            data = response.json()
            logger.info(f"{service_name} API response: {data}")

            if data.get("status") == "success" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif data.get("status") == "fail" and data.get("message"):
                return jsonify({"status": "error", "message": data["message"]})
            else:
                logger.warning(f"Unexpected JSON response structure from {service_name}: {data}")
                return jsonify({"status": "error", "message": f"Unexpected response from {service_name}."})

        except requests.exceptions.HTTPError as errh:
            error_message = f"{service_name} API HTTP Error"
            try:
                error_data = errh.response.json()
                error_message = error_data.get("message", str(errh.response.text[:200]))
            except ValueError:
                error_message = str(errh.response.text[:200]) if errh.response.text else str(errh)
            logger.error(f"HTTPError calling {service_name}: {error_message} (Status: {errh.response.status_code})")
            return jsonify({"status": "error", "message": error_message}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling {service_name} API.")
            return jsonify({"status": "error", "message": f"Request to {service_name} API timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling {service_name}: {str(e)}")
            return jsonify({"status": "error", "message": f"{service_name} API Request Error: {str(e)}"}), 500
        except ValueError:
            logger.error(f"ValueError (JSONDecodeError) parsing {service_name} response.")
            return jsonify({"status": "error", "message": f"Invalid JSON response from {service_name}."}), 500

    # --- Smile.One API (for other games) ---
    elif game in SMILE_ONE_PRODUCT_IDS:
        product_id = SMILE_ONE_PRODUCT_IDS[game]
        params = {
            "merchant_id": SMILE_ONE_MERCHANT_ID,
            "product_id": product_id,
            "game_user_id": uid,
            "user_id": SMILE_ONE_USER_ID, # Smile.One's own User ID for your account
            # "key": SMILE_ONE_SECRET_KEY # The 'key' is usually a signature, not the secret directly
        }
        # Add game_zone_id if server_id is present and meaningful for Smile.One
        if server_id and server_id != "null" and server_id != "" and server_id != "-1":
            params["game_zone_id"] = server_id
        
        # Generate Smile.One signature (important for live environment)
        params["key"] = generate_smile_one_signature(params, SMILE_ONE_SECRET_KEY)

        logger.info(f"Calling Smile.One API with params: {params} (URL: {SMILE_ONE_API_URL})")
        try:
            response = requests.post(SMILE_ONE_API_URL, data=params, timeout=7)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Smile.One API response for {game}: {data}")

            if str(data.get("status")) == "200" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif str(data.get("status")) == "200" and data.get("message") == "OK": # Old verification style
                 return jsonify({"status": "success", "message": "Account Verified"})
            else:
                error_msg = data.get("message", f"Unknown error from Smile.One (Status: {data.get('status')}).")
                return jsonify({"status": "error", "message": error_msg})
        except requests.exceptions.HTTPError as errh:
            logger.error(f"HTTPError calling Smile.One for {game}: {str(errh)}")
            return jsonify({"status": "error", "message": f"Smile.One API HTTP Error: {str(errh.response.text[:100])}"}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling Smile.One for {game}.")
            return jsonify({"status": "error", "message": "Request to Smile.One API timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling Smile.One for {game}: {str(e)}")
            return jsonify({"status": "error", "message": f"Smile.One API Request Error: {str(e)}"}), 500
        except ValueError:
            logger.error(f"ValueError parsing Smile.One response for {game}.")
            return jsonify({"status": "error", "message": "Invalid JSON response from Smile.One."}), 500
            
    else:
        logger.warning(f"Unsupported game for check: {game}")
        return jsonify({"status": "error", "message": "Unsupported game for UID check."}), 404


@app.route('/check-netease/identityv/<server_id>/<role_id>', methods=['GET'])
def check_netease_identityv_proxy(server_id, role_id):
    logger.info(f"Received Netease IDV check request for Server: {server_id}, Role ID: {role_id}")
    payload = {
        "game": "g37",
        "roleid": role_id,
        "serverid": server_id,
        "check_type": "user_info" 
        # Netease APIs often require a complex signature (sign, token, timestamp).
        # This is a placeholder and will likely fail without proper auth.
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0',
    }

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

    except requests.exceptions.HTTPError as errh:
        logger.error(f"HTTPError calling Netease IDV: {str(errh)}")
        return jsonify({"status": "error", "message": f"Netease IDV API HTTP Error: {str(errh.response.text[:100])}"}), errh.response.status_code
    except requests.exceptions.Timeout:
        logger.error("Timeout calling Netease IDV API.")
        return jsonify({"status": "error", "message": "Request to Netease IDV API timed out."}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException calling Netease IDV: {str(e)}")
        return jsonify({"status": "error", "message": f"Netease IDV API Request Error: {str(e)}"}), 500
    except ValueError:
        logger.error("ValueError parsing Netease IDV response.")
        return jsonify({"status": "error", "message": "Invalid JSON response from Netease IDV."}), 500

if __name__ == '__main__':
    # For local development, Gunicorn isn't typically used this way.
    # This is more for how Gunicorn might be invoked by Render.
    # When running locally: python app.py
    # Render will use your Procfile (e.g., web: gunicorn app:app)
    port = int(os.environ.get("PORT", 5001)) 
    app.run(host='0.0.0.0', port=port, debug=True) # Added debug=True for local dev
