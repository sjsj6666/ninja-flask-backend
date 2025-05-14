import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants for Smile.One (Example, you might have more) ---
SMILE_ONE_API_URL = "https://globalapi.smile.one/smilecoin/api/product/checkrole"
SMILE_ONE_USER_ID = os.getenv("SMILE_ONE_USER_ID")
SMILE_ONE_KEY = os.getenv("SMILE_ONE_KEY")
SMILE_ONE_MERCHANT_ID = "198765" # Replace with your actual merchant ID if different

# Game-specific configurations or mappings for Smile.One (if needed)
SMILE_ONE_PRODUCT_IDS = {
    "mobile-legends": "1001",
    "honkai-star-rail": "2056", # Example, replace with actual if using Smile.One for HSR
    # "genshin-impact": "2002", # Old Smile.One ID, now Genshin will use Razer
    "zenless-zone-zero": "RAZER_ZZZ", # Special marker, handled differently
    "bloodstrike": "2103", # Example ID for Smile.One
    "ragnarok-m-classic": "3010", # Example ID for Smile.One
    "love-and-deepspace": "2088", # Example ID for Smile.One
    "bigo-live": "4001", # Example ID for Smile.One
    "marvel-rivals": "RAZER_MARVEL_RIVALS" # Placeholder if it also uses Razer via a similar pattern
    # Add other games that use Smile.One with their product IDs
}

# --- Netease Identity V Specific ---
NETEASE_IDV_API_URL = "https://pay.neteasegames.com/g37/api/check_user" # Replace with actual if different

@app.route('/')
def home():
    return "Ninja Flask Backend is running!"

# Generic proxy for Smile.One or other services
@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
@app.route('/check-smile/<game>/<uid>', methods=['GET'])  # For games without server_id
def check_smile_one_proxy(game, uid, server_id=None):
    logger.info(f"Received check request for game: {game}, UID: {uid}, Server ID: {server_id}")

    # --- Razer Gold API for Genshin Impact ---
    if game == 'genshin-impact':
        if not server_id:
            logger.warning("Genshin Impact check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Genshin Impact."}), 400
        
        razer_url = f"https://gold.razer.com/api/ext/genshinimpact/users/{uid}?serverId={server_id}"
        logger.info(f"Calling Razer API for Genshin Impact: {razer_url}")
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            # Add other headers if Razer requires them, like 'Referer' or specific cookies, though often not needed for direct API calls if public.
            # The cookie string from your log is very long and likely session-specific for browser use.
            # For a backend-to-backend call, often fewer headers are needed. Start simple.
        }
        try:
            response = requests.get(razer_url, headers=headers, timeout=8) # 8 second timeout
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            
            data = response.json()
            logger.info(f"Razer API response for Genshin Impact: {data}")

            # Razer's success response example: {"status":"success","username":"x********z"}
            # Razer's "user not found" example: {"message":"User not found.","status":"fail"}
            if data.get("status") == "success" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif data.get("status") == "fail" and data.get("message"):
                 return jsonify({"status": "error", "message": data["message"]})
            else:
                logger.warning(f"Unexpected JSON response structure from Razer (Genshin): {data}")
                return jsonify({"status": "error", "message": "Unexpected response from Razer."})

        except requests.exceptions.HTTPError as errh:
            error_message = f"Razer API HTTP Error: {str(errh)}"
            try: # Try to get more specific message from Razer's error response
                error_data = errh.response.json()
                error_message = error_data.get("message", str(errh.response.text[:200]))
            except ValueError: # If Razer's error response is not JSON
                error_message = str(errh.response.text[:200]) if errh.response.text else str(errh)
            logger.error(f"HTTPError calling Razer for Genshin: {error_message} (Status: {errh.response.status_code})")
            return jsonify({"status": "error", "message": error_message}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error("Timeout calling Razer API for Genshin.")
            return jsonify({"status": "error", "message": "Request to Razer API timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling Razer for Genshin: {str(e)}")
            return jsonify({"status": "error", "message": f"Razer API Request Error: {str(e)}"}), 500
        except ValueError: # JSONDecodeError
            logger.error("ValueError (JSONDecodeError) parsing Razer response for Genshin.")
            return jsonify({"status": "error", "message": "Invalid JSON response from Razer."}), 500

    # --- Razer Gold API for Zenless Zone Zero (Example from previous work) ---
    elif game == 'zenless-zone-zero':
        if not server_id:
            logger.warning("Zenless Zone Zero check: Server ID missing.")
            return jsonify({"status": "error", "message": "Server ID is required for Zenless Zone Zero."}), 400

        # Note: ZZZ Razer API endpoint might be different from Genshin's. Adjust if necessary.
        # Assuming it's similar for now:
        razer_zzz_url = f"https://gold.razer.com/api/ext/zenlesszonezero/users/{uid}?serverId={server_id}" 
        # ^^^ Ensure 'zenlesszonezero' is the correct path segment if it's different from 'genshinimpact'
        logger.info(f"Calling Razer API for Zenless Zone Zero: {razer_zzz_url}")
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(razer_zzz_url, headers=headers, timeout=8)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Razer API response for ZZZ: {data}")
            if data.get("status") == "success" and data.get("username"):
                return jsonify({"status": "success", "username": data["username"]})
            elif data.get("status") == "fail" and data.get("message"):
                 return jsonify({"status": "error", "message": data["message"]})
            else:
                logger.warning(f"Unexpected JSON response structure from Razer (ZZZ): {data}")
                return jsonify({"status": "error", "message": "Unexpected response from Razer for ZZZ."})
        except requests.exceptions.HTTPError as errh:
            # Similar error handling as Genshin
            error_message = f"Razer API HTTP Error (ZZZ): {str(errh)}"
            try:
                error_data = errh.response.json()
                error_message = error_data.get("message", str(errh.response.text[:200]))
            except ValueError:
                error_message = str(errh.response.text[:200]) if errh.response.text else str(errh)
            logger.error(f"HTTPError calling Razer for ZZZ: {error_message} (Status: {errh.response.status_code})")
            return jsonify({"status": "error", "message": error_message}), errh.response.status_code
        # ... (add other exception handling for ZZZ like Timeout, RequestException, ValueError) ...
        except requests.exceptions.Timeout:
            logger.error("Timeout calling Razer API for ZZZ.")
            return jsonify({"status": "error", "message": "Request to Razer API (ZZZ) timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling Razer for ZZZ: {str(e)}")
            return jsonify({"status": "error", "message": f"Razer API Request Error (ZZZ): {str(e)}"}), 500
        except ValueError:
            logger.error("ValueError (JSONDecodeError) parsing Razer response for ZZZ.")
            return jsonify({"status": "error", "message": "Invalid JSON response from Razer (ZZZ)."}), 500


    # --- Smile.One API (for other games) ---
    elif game in SMILE_ONE_PRODUCT_IDS:
        product_id = SMILE_ONE_PRODUCT_IDS[game]
        params = {
            "merchant_id": SMILE_ONE_MERCHANT_ID,
            "product_id": product_id,
            "game_user_id": uid,
            "key": SMILE_ONE_KEY, # This should be calculated based on Smile.One's signature rules
        }
        if server_id and server_id != "null" and server_id != "-1": # Smile.One might need zone_id
            params["game_zone_id"] = server_id 
        
        # Note: Smile.One key generation is complex and involves hashing.
        # This example assumes 'key' is a pre-shared secret or that you have the logic elsewhere.
        # For a real Smile.One integration, you'd need to implement their signature algorithm.
        # For now, this is a placeholder for how you *might* call it if 'key' was simple.

        logger.info(f"Calling Smile.One API with params: {params} (URL: {SMILE_ONE_API_URL})")
        try:
            response = requests.post(SMILE_ONE_API_URL, data=params, timeout=7)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Smile.One API response for {game}: {data}")

            # Smile.One responses vary. Adapt this based on actual responses.
            # Example: {"status":200,"message":"OK","username":"PlayerName"}
            # Example Error: {"status":500, "message":"Invalid User"}
            if data.get("status") == 200 and data.get("username"): # Assuming 200 is success status code in JSON
                return jsonify({"status": "success", "username": data["username"]})
            elif data.get("status") == 200 and data.get("message") == "OK": # For cases like old Genshin verify
                 return jsonify({"status": "success", "message": "Account Verified"}) # No username
            else:
                error_msg = data.get("message", "Unknown error from Smile.One.")
                return jsonify({"status": "error", "message": error_msg})
        except requests.exceptions.HTTPError as errh:
            logger.error(f"HTTPError calling Smile.One for {game}: {str(errh)}")
            return jsonify({"status": "error", "message": f"Smile.One API HTTP Error: {str(errh)}"}), errh.response.status_code
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling Smile.One for {game}.")
            return jsonify({"status": "error", "message": "Request to Smile.One API timed out."}), 504
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException calling Smile.One for {game}: {str(e)}")
            return jsonify({"status": "error", "message": f"Smile.One API Request Error: {str(e)}"}), 500
        except ValueError: # JSONDecodeError
            logger.error(f"ValueError parsing Smile.One response for {game}.")
            return jsonify({"status": "error", "message": "Invalid JSON response from Smile.One."}), 500
            
    else:
        logger.warning(f"Unsupported game for check: {game}")
        return jsonify({"status": "error", "message": "Unsupported game for UID check."}), 404


@app.route('/check-netease/identityv/<server_id>/<role_id>', methods=['GET'])
def check_netease_identityv_proxy(server_id, role_id):
    logger.info(f"Received Netease IDV check request for Server: {server_id}, Role ID: {role_id}")
    # Example params; these will vary based on Netease's actual requirements
    payload = {
        "game": "g37",  # Or whatever Identity V's game code is
        "roleid": role_id,
        "serverid": server_id,
        "check_type": "user_info" # Or similar parameter
        # May need other parameters like "token", "sign", "timestamp" etc.
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded', # Or 'application/json'
        'User-Agent': 'Mozilla/5.0',
        # Add other required headers
    }

    try:
        # Netease might use POST or GET, adjust accordingly
        response = requests.post(NETEASE_IDV_API_URL, data=payload, headers=headers, timeout=7)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Netease IDV API response: {data}")

        # Adapt this to actual Netease response structure
        # Example success: {"code": 0, "userInfo": {"rolename": "PlayerName"}}
        # Example error: {"code": 1, "msg": "User not found"}
        if data.get("code") == 0 and data.get("userInfo", {}).get("rolename"):
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
    port = int(os.environ.get("PORT", 5001)) # Render typically sets PORT env var
    app.run(host='0.0.0.0', port=port)
