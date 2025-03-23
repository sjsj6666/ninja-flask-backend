from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

port = int(os.environ.get("PORT", 5000))

# Smile One API Headers
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=...")
}

# Tokogame API Headers
TOKOGAME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.tokogame.com",
    "Referer": "https://www.tokogame.com/",
    "X-Currency": "IDR",
    "X-Language": "ID",
    "X-Region": "ID",
    "X-Secret-Id": os.environ.get("TOKOGAME_SECRET_ID", "03be7be4923c99108a0e8fee1079189684dab8fff7837de8f327cc4af15d19c6")
}

def check_smile_one_api(game, uid, server_id):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole"
    }

    if game not in endpoints:
        return {"status": "error", "message": "Invalid game"}

    url = endpoints[game]
    SMILE_ONE_HEADERS["Referer"] = (
        "https://www.smile.one/merchant/mobilelegends" if game == "mobile-legends"
        else "https://www.smile.one/ru/merchant/genshinimpact" if game == "genshin-impact"
        else "https://www.smile.one/merchant/honkai"
    )
    
    params = {
        "pid": "25" if game == "mobile-legends" else "19731" if game == "genshin-impact" else "18356",
        "checkrole": "1",
    }
    
    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    else:
        params["uid"] = uid
        params["sid"] = server_id

    try:
        response = requests.post(url, data=params, headers=SMILE_ONE_HEADERS, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")
        data = response.json()
        print(f"Smile One JSON Response for {game}: {data}")
        
        if data.get("code") == 200:
            if game == "mobile-legends":
                username = data.get("username")
                if username:
                    return {"status": "success", "username": username}
                return {"status": "error", "message": "Username not found"}
            elif game == "honkai-star-rail":
                username = data.get("username") or data.get("role_name") or data.get("nickname")
                if username:
                    return {"status": "success", "username": username}
                return {"status": "success", "message": "UID and Server verified"}
            elif game == "genshin-impact":
                return {"status": "success", "message": "Account Verified"}
        return {"status": "error", "message": data.get("message", "Invalid UID or Server")}
    except requests.Timeout:
        print(f"Error: Smile One timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        print(f"Error checking {game} UID: {str(e)} - Response: {response.text if 'response' in locals() else 'No response'}")
        return {"status": "error", "message": f"Error: {str(e)}"}
    except ValueError as e:
        print(f"Error parsing JSON for {game}: {str(e)} - Raw: {raw_text}")
        return {"status": "error", "message": "Invalid response format"}

def check_honor_of_kings_name(uid):
    url = "https://api.tokogame.com/core/v1/orders/validate-order"
    payload = {
        "game": "honor-of-kings",
        "uid": uid,
        "productId": "hok_generic",  # Placeholder; replace with actual product ID if known
        "questionnaireAnswers": "default"  # Placeholder; adjust based on API requirements
    }

    try:
        response = requests.post(url, json=payload, headers=TOKOGAME_HEADERS, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"Tokogame Raw Response for Honor of Kings (UID: {uid}): {raw_text}")
        data = response.json()
        print(f"Tokogame JSON Response: {data}")

        if response.status_code == 200:
            validated_username = data.get("username") or data.get("nickname") or data.get("player_name")
            if validated_username:
                return {"status": "success", "username": validated_username, "message": "Username retrieved"}
            return {"status": "success", "message": "UID verified (no username returned)"}
        return {"status": "error", "message": data.get("message", "Invalid UID")}
    except requests.Timeout:
        print(f"Error: Tokogame API timed out for Honor of Kings")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        print(f"Error checking Honor of Kings UID: {str(e)} - Response: {response.text if 'response' in locals() else 'No response'}")
        return {"status": "error", "message": f"Error: {str(e)}"}
    except ValueError as e:
        print(f"Error parsing JSON from Tokogame: {str(e)} - Raw: {raw_text}")
        return {"status": "error", "message": "Invalid response format"}

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    result = check_smile_one_api(game, uid, server_id)
    return jsonify(result)

@app.route('/check-hok-name/<uid>', methods=['GET'])
def check_hok_name(uid):
    result = check_honor_of_kings_name(uid)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
