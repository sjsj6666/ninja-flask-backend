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
SMILE_ONE_USER_ID = os.getenv("SMILE_ONE_USER_ID", "YOUR_SMILE_ONE_USER_ID") 
SMILE_ONE_SECRET_KEY = os.getenv("SMILE_ONE_SECRET_KEY", "YOUR_SMILE_ONE_SECRET_KEY") 
SMILE_ONE_MERCHANT_ID = os.getenv("SMILE_ONE_MERCHANT_ID", "198765") 

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
    
    # --- MODIFIED RAZER HEADERS ---
    razer_headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', # A common, modern User-Agent
        'Referer': f'https://gold.razer.com/gold/catalog/{game}', # Dynamic referer based on game
        'Origin': 'https://gold.razer.com', # Often sent with CORS requests
        # Avoid sending complex cookies like 'forterToken' or '_ga' from backend unless you have a specific strategy for them
    }
    # --- END MODIFIED RAZER HEADERS ---

    if game == 'genshin-impact':
        if not server_id:
            logger.warning("Genshin Impact check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        razer_url = f"{razer_base_url}/genshinimpact/users/{uid}?serverId={server_id}"
        service_name = "Razer (Genshin Impact)"
        # Update referer specifically if needed for genshin
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/genshin-impact'
    elif game == 'zenless-zone-zero':
        if not server_id:
            logger.warning("Zenless Zone Zero check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Zenless Zone Zero."}), 400
        razer_url = f"{razer_base_url}/zenlesszonezero/users/{uid}?serverId={server_id}"
        service_name = "Razer (Zenless Zone Zero)"
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/zenless-zone-zero' # Example
    elif game == 'marvel-rivals': 
        # Assuming Marvel Rivals uses Razer and requires serverId. Adjust as necessary.
        if not server_id:
            logger.warning("Marvel Rivals (Razer) check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Marvel Rivals (Razer)."}), 400
        razer_url = f"{razer_base_url}/marvelrivals/users/{uid}?serverId={server_id}" # Guessed path
        service_name = "Razer (Marvel Rivals)"
        razer_headers['Referer'] = 'https://gold.razer.com/gold/catalog/marvel-rivals' # Example
    else:
        razer_url = None

    if razer_url:
        logger.info(f"Calling {service_name} API: {razer_url} with headers: {razer_headers}")
        try:
            # Consider using a session object for multiple requests to the same host if needed
            # s = requests.Session()
            # response = s.get(razer_url, headers=razer_headers, timeout=10) 
            response = requests.get(razer_url, headers=razer_headers, timeout=10) # Increased timeout slightly
            
            logger.info(f"{service_name} raw response status: {response.status_code}")
            logger.info(f"{service_name} raw response headers: {response.headers}")
            # logger.info(f"{service_name} raw response text: {response.text[:500]}") # Log start of text

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
            error_content = errh.response.text[:500] # Get first 500 chars of error response
            logger.error(f"HTTPError calling {service_name}: Status {errh.response.status_code}, Response: {error_content}")
            try:
                error_data = errh.response.json()
                error_message = error_data.get("message", error_content)
            except ValueError: # If error response is not JSON
                error_message = error_content
            return jsonify({"status": "error", "message": error_message}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling {service_name} API.")
            return jsonify({"status": "error", "message": f"Request to {service_name} API timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling {service_name}: {str(e)}")
            return jsonify({"status": "error", "message": f"{service_name} API Request Error: {str(e)}"}), 500
        except ValueError: # JSONDecodeError
            logger.error(f"ValueError (JSONDecodeError) parsing {service_name} response. Raw text: {response.text[:500] if 'response' in locals() else 'N/A'}")
            return jsonify({"status": "error", "message": f"Invalid JSON response from {service_name}."}), 500

    elif game in SMILE_ONE_PRODUCT_IDS:
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
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://pay.neteasegames.com/' # Example, might need specific referer
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
        logger.error(f"HTTPError calling Netease IDV: {str(errh.response.text[:200])}")
        return jsonify({"status": "error", "message": f"Netease IDV API HTTP Error: {str(errh.response.text[:100])}"}), errh.response.status_code
    except requests.exceptions.Timeout:
        logger.error("Timeout calling Netease IDV API.")
        return jsonify({"status": "error", "message": "Request to Netease IDV API timed out."}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException calling Netease IDV: {str(e)}")
        return jsonify({"status": "error", "message": f"Netease IDV API Request Error: {str(e)}"}), 500
    except ValueError:
        logger.error(f"ValueError parsing Netease IDV response.")
        return jsonify({"status": "error", "message": "Invalid JSON response from Netease IDV."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001)) 
    app.run(host='0.0.0.0', port=port, debug=True if os.environ.get("FLASK_ENV") == "development" else False)
