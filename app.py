from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

port = int(os.environ.get("PORT", 5000))

# Shared headers for Smile One requests
SMILE_ONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.smile.one",
    "Referer": "https://www.smile.one/ru/merchant/genshinimpact",
    "Cookie": "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=54PNbJJykj74253lEBL3lhST2ojhlCG6fFZhjlZJs7g-1742613814-1.2.1.1-xDV1MmpU.dkJ.0HeTur4HT0I8BIfwZnhGXXo.N.dgPvUvo5BcfulDDNOhqkIe2AJ1nuUQUI9ILxj_dex9DDmSGQ.u3IFSbq18U9OTAFSkbAGZfdCMZ09S2uYgqCQzCKJ5jIsTyLqXDL9kHq6kzq3jYL0UPQWQ91fduYy4eyB9XRqC5hIU5B.p7T.noupoV7fQjsBwhucVKi9eKDkHbXJJKY08mLzeX9KLDDM_ZGoIGfQxj6zZgS1z7t9f9jfQ.pEXezSbN7I_IOQISOwiAmvqjgmyUbKM5GCqAu9Q.Bk2pPnBdYjQW5bAImGVHZzo6V1nxLuoA00nIy05OqeFGqr8MLckxbPMRhWdgjE1uuQVWg"
    # Update Cookie here if expired
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
        
        # Check for success (assuming code 200 and username)
        if data.get("code") == 200 and "username" in data:
            return {"status": "success", "nickname": data["username"]}
        # Alternative success format (if nickname is used instead)
        elif data.get("status") == "success" and "nickname" in data:
            return {"status": "success", "nickname": data["nickname"]}
        # Handle error response
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

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-smile/<game>/<uid>/<server_id>', methods=['GET'])
def check_smile_one(game, uid, server_id):
    result = check_smile_one_api(game, uid, server_id)
    return jsonify({"username": result["nickname"]} if game == "mobile-legends" else result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
