from flask import Flask, jsonify
import requests
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

def check_mlbb_api(user_id, server_id):
    url = "https://api.jollymax.com/jolly-gateway/topup/order/check-uid"
    payload = {
        "gameId": "mlbb",
        "userId": user_id,
        "serverId": server_id,
        "country": "SG",
        "goodsId": "25",
        "appId": "mlbb"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.jollymax.com",
        "Referer": "https://www.jollymax.com/"
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        response.raise_for_status()
        raw_text = response.text
        print(f"JollyMax Raw Response: {raw_text}")
        data = response.json()
        print(f"JollyMax JSON Response: {data}")
        if "nickName" in data:
            return {"status": True, "nickname": data["nickName"]}
        elif "username" in data:
            return {"status": True, "nickname": data["username"]}
        elif "message" in data and "〆Gemini、子" in data["message"]:
            return {"status": True, "nickname": data["message"]}
        return {"status": False, "nickname": f"Invalid: {data.get('msg', 'Unknown')}"}
    except requests.Timeout:
        print("Error: JollyMax timed out")
        return {"status": False, "nickname": "API Timeout"}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"status": False, "nickname": f"Error: {str(e)}"}

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-mlbb/<user_id>/<server_id>')
def check_mlbb(user_id, server_id):
    result = check_mlbb_api(user_id, server_id)
    return jsonify({'username': result['nickname']})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    
