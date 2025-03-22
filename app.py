from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Render uses PORT environment variable by default
port = int(os.environ.get("PORT", 5000))

SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "Referer": "https://www.smile.one/ru/merchant/genshinimpact",
    # Consider moving Cookie to environment variable for Render
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=54PNbJJykj74253lEBL3lhST2ojhlCG6fFZhjlZJs7g-1742613814-1.2.1.1-xDV1MmpU...")
}

ELITE_DIAS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-SG,en-GB;q=0.9,en;q=0.8",
    "Content-Type": "application/json; charset=utf-8",
    "Origin": "https://elitedias.com",
    "Referer": "https://elitedias.com/",
    "X-Requested-With": "XMLHttpRequest"
}

def check_smile_one_api(game, uid, server_id):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole"
    }

    if game not in endpoints:
        return {"status": "error", "message": "Invalid game"}

    url = endpoints[game]
    params = {
        "uid": uid,
        "sid": server_id,
        "pid": "19731" if game == "genshin-impact" else "25",
        "checkrole": "1",
        "pay_method": "",
        "channel_method": ""
    }

    try:
        response = requests.post(url, data=params, headers=SMILE_ONE_HEADERS, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")
        data = response.json()
        print(f"Smile One JSON Response for {game}: {data}")
        
        if data.get("code") == 200:
            if game == "mobile-legends" and "username" in data and data["username"]:
                return {"status": "success", "nickname": data["nickname"]}
            return {"status": "success", "message": "UID and Server verified"}
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

def check_elite_dias_api(game, uid, server_id):
    url = "https://api.elitedias.com/checkid"
    payload = {
        "game": game,
        "uid": uid,
        "server_id": server_id
    }
    
    try:
        response = requests.post(url, json=payload, headers=ELITE_DIAS_HEADERS, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"EliteDias Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")
        data = response.json()
        print(f"EliteDias JSON Response for {game}: {data}")
        
        if response.status_code == 200:
            return {"status": "success", "message": "UID and Server verified"}
        return {"status": "error", "message": "Invalid UID or Server"}
    except requests.Timeout:
        print(f"Error: EliteDias timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        print(f"Error checking {game} UID: {str(e)} - Response: {response.text if 'response' in locals() else 'No response'}")
        return {"status": "error", "message": f"Error: {str(e)}"}
    except ValueError as e:
        print(f"Error parsing JSON for {game}: {str(e)} - Raw: {raw_text}")
        return {"status": "error", "message": "Invalid response format"}

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    result = check_smile_one_api(game, uid, server_id)
    return jsonify({"username": result["nickname"]} if game == "mobile-legends" and "nickname" in result else result)

@app.route('/check-elite/<game>/<uid>/<server_id>', methods=['GET'])
def check_elite_dias(game, uid, server_id):
    result = check_elite_dias_api(game, uid, server_id)
    return jsonify(result)

if __name__ == '__main__':
    # On Render, host must be 0.0.0.0 to accept external traffic
    app.run(host='0.0.0.0', port=port, debug=False)  # Debug=False in production
