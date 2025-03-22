from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

port = int(os.environ.get("PORT", 5000))

SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "Referer": "https://www.smile.one/ru/merchant/genshinimpact",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=54PNbJJykj74253lEBL3lhST2ojhlCG6fFZhjlZJs7g-1742613814-1.2.1.1-xDV1MmpU...")
}

RAZER_GOLD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-SG,en-GB;q=0.9,en;q=0.8",
    "Cookie": os.environ.get("RAZER_GOLD_COOKIE", "_ga=GA1.2.1238030224.1736596983; _gid=GA1.2.2042942313.1742611402; RazerIDLanguage=en; ...")  # Full cookie from your request
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
                return {"status": "success", "nickname": data["username"]}
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

def check_razer_gold_api(game, uid, server_id):
    if game != "zenless-zone-zero":
        return {"status": "error", "message": "Only Zenless Zone Zero is supported"}

    url = f"https://gold.razer.com/api/ext/custom/cognosphere-zenless-zone-zero/users/{uid}"
    params = {"serverId": server_id}

    try:
        response = requests.get(url, params=params, headers=RAZER_GOLD_HEADERS, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"Razer Gold Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")
        data = response.json()
        print(f"Razer Gold JSON Response for {game}: {data}")
        
        if response.status_code == 200:
            return {"status": "success", "message": "UID and Server verified", "data": data}
        return {"status": "error", "message": "Invalid UID or Server"}
    except requests.Timeout:
        print(f"Error: Razer Gold timed out for {game}")
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

@app.route('/check-razer/<game>/<uid>/<server_id>', methods=['GET'])
def check_razer_gold(game, uid, server_id):
    result = check_razer_gold_api(game, uid, server_id)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
