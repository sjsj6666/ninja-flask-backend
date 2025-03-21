from flask import Flask, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def check_mlbb_api(user_id, server_id):
    url = "https://api.elitedias.com/checkid"
    params = {
        "userid": user_id,
        "serverid": server_id,
        "game": "mlbb_special"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15"
    }

    try:
        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"EliteDias Response: {data}")
        # Check for username field (guessing "username" or "nickName")
        if "username" in data and data.get("status") == "success":
            return {"status": True, "nickname": data["username"]}
        elif "nickName" in data:
            return {"status": True, "nickname": data["nickName"]}
        return {"status": False, "nickname": f"Invalid: {data.get('message', 'Unknown')}"}
    except requests.Timeout:
        print("Error: EliteDias timed out")
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
