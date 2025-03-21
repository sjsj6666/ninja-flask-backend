from flask import Flask, jsonify
import requests
import time
import hashlib
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Smile One SANDBOX credentials
SMILE_EMAIL = "agent@smileone.com"
SMILE_UID = "1041302"
SMILE_KEY = "7f663422060edd50b326b8a570639dac"

def make_sign(params):
    sorted_params = sorted(params.items())
    sign_str = "".join(f"{k}={v}&" for k, v in sorted_params) + SMILE_KEY
    return hashlib.md5(hashlib.md5(sign_str.encode()).hexdigest().encode()).hexdigest()

def check_mlbb_api(user_id, server_id):
    url = "https://frontsmie.smile.one/smilecoin/api/getrole"  # Sandbox URL
    params = {
        "email": SMILE_EMAIL,
        "uid": SMILE_UID,
        "userid": user_id,
        "zoneid": server_id,
        "product": "mobilelegends",
        "productid": "13",        # Default product ID
        "time": int(time.time()),
    }
    params["sign"] = make_sign(params)

    try:
        response = requests.post(url, data=params)
        data = response.json()
        print(f"Smile One Response: {data}")  # Log the full response
        if data.get("status") == 200:
            return {"status": True, "nickname": data["username"]}
        return {"status": False, "nickname": "Invalid ID or Server"}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"status": False, "nickname": "Error"}

@app.route('/')
def home():
    return "Hello! This is the Ninja Flask Backend."

@app.route('/check-mlbb/<user_id>/<server_id>')
def check_mlbb(user_id, server_id):
    result = check_mlbb_api(user_id, server_id)
    return jsonify({'username': result['nickname']})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
