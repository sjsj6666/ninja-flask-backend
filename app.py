from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def check_mlbb_api(user_id, server_id):
    url = "https://speedyninja.co/sg/product/mobile-legends-special-promo/check-id"
    params = {
        "user_id": user_id,
        "server_id": server_id,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15"
    }

    try:
        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()  # Check for HTTP errors
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find username (adjust selector based on real HTML)
        username_element = soup.find('span', class_='username')  # Guessing class
        if username_element:
            username = username_element.text.strip()
            return {"status": True, "nickname": username}
        return {"status": False, "nickname": "Invalid ID or Server"}
    except requests.Timeout:
        print("Error: SpeedyNinja timed out")
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
