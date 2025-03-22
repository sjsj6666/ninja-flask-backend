from flask import Flask, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration for deployment (e.g., Render sets PORT env variable)
port = int(os.environ.get("PORT", 5000))

def check_mlbb_api(user_id, server_id):
    url = "https://www.smile.one/merchant/mobilelegends/checkrole"
    params = {
        "user_id": user_id,
        "zone_id": server_id,
        "pid": "25",
        "checkrole": "1",
        "pay_method": "",
        "channel_method": ""
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.smile.one",
        "Referer": "https://www.smile.one/merchant/mobilelegends?source=googleads",
        "Cookie": "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=R_U2mryS8KHrGPyGzqBVdl.zv8YI39tks9aMiZgyke8-1742530734-1.2.1.1-rzbGMal_wVoz9A_I6GmtzqxFVNL3c4Y95.yPBUtbT3O5ZVW65qsU8pa.Q_d41oNcbFKayCIimvI8MQQ7gSQVY2bHZONEJScxEzeoZ5tplQ4Tstf74a4CDK7mgjM52Yi0.4oSezZ6WBAoO4pYItGy6vfKRsgGOeXcj6ijkDL2ybCXIiiAsj0Kqb02pKU6RwlT.L93Q4EmQz9430JP4VtUjCGQCTGt1UoNyrtbRN0_CAci8iXsoqe2p0pJsfJCdjdVO8EfGwVui9STlGm9bqiDb.d653GzAvt5CWk123otvDFOU0mHPSpofPq4wEx932B7Fg_xOtqmtKUViVMs2HcMPJB6PVXpc7oWLI7O5axzkeA"
    }

    try:
        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"Smile One Raw Response: {raw_text}")
        data = response.json()
        print(f"Smile One JSON Response: {data}")
        if data.get("code") == 200 and "username" in data:
            return {"status": True, "nickname": data["username"]}
        return {"status": False, "nickname": f"Invalid: {data.get('message', 'Unknown')}"}
    except requests.Timeout:
        print("Error: Smile One timed out")
        return {"status": False, "nickname": "API Timeout"}
    except Exception as e:
        print(f"Error checking MLBB: {str(e)}")
        return {"status": False, "nickname": f"Error: {str(e)}"}

def check_razer_gold_api(game, uid, server_id):
    base_url = "https://gold.razer.com/api/ext"
    endpoints = {
        "honkai-star-rail": f"{base_url}/custom/mihoyo-honkai-star-rail/users/{uid}",
        "zenless-zone-zero": f"{base_url}/custom/cognosphere-zenless-zone-zero/users/{uid}",
        "genshin-impact": f"{base_url}/genshinimpact/users/{uid}"
    }

    if game not in endpoints:
        return {"status": "error", "message": "Invalid game"}

    url = f"{endpoints[game]}?serverId={server_id}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
        # Add Cookie or API key here if required by Razer Gold
        # "Cookie": "your_cookie_here"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"Razer Gold Response for {game}: {data}")
        if data.get("status") == "success" and "nickname" in data:
            return {"status": "success", "nickname": data["nickname"]}
        return {"status": "error", "message": data.get("message", "Invalid UID or Server")}
    except requests.Timeout:
        print(f"Error: Razer Gold timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except Exception as e:
        print(f"Error checking {game} UID: {str(e)}")
        return {"status": "error", "message": f"Error: {str(e)}"}

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-mlbb/<user_id>/<server_id>')
def check_mlbb(user_id, server_id):
    result = check_mlbb_api(user_id, server_id)
    return jsonify({'username': result['nickname']})

@app.route('/check-razer/<game>/<uid>/<server_id>', methods=['GET'])
def check_razer_gold(game, uid, server_id):
    result = check_razer_gold_api(game, uid, server_id)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
