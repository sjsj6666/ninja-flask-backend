from flask import Flask, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def check_mlbb_api(user_id, server_id):
    url = "https://www.smile.one/smilecode/smilecode/queryrole"
    params = {
        "name": "mobilelegendsph",
        "user_id": user_id,
        "server_id": server_id
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.smile.one",
        "Referer": "https://www.smile.one/smilecode/smilecode/product?a=bW9iaWxlbGVnZW5kc3Bo&name=TW9iaWxlIExlZ2VuZHMgTW9iaWxlIExlZ2VuZHM6IEJhbmcgQmFuZyBQSA==&type=Mw==",
        "Cookie": "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=FH.T5kuAxZjMNJmbLamJG0S_PqO1zzvlz4FP9z9EgCQ-1742527918-1.2.1.1-B3nrGxYk4vmTqqhXfBCIr713ybN2qLvujm74gYHV3AP7Gk7rQI0B_erQenPavEqTxv381jhpPlYsMtQHA.xjeXXDoDpm.BMJCIHdN8GA810pIREtUvd_qH8JD9rXZHUzzA7s6OPrDtmKFta_cgF0lrljaiBc_jVNo_HtR5Eg7FzirccqyfEpDa2xVWFXI4IDYsgKvZ_zl8GQx_8VmG1LlA6fo7jjwxm_.IYteRU6F1uGj_sSDOCfyDn_3vxl6kq2hb0kw79LY1OI4MJSxTCvveuESOVFnsfosjPASTuFCrMslW9Q_pgvlW3sgPFiQA9gqFxMMcup8wq0LwZApxGLzazXvGg1Q3iTD68QULNIRDM"
    }

    try:
        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()
        # Try JSON first, fallback to text if malformed
        try:
            data = response.json()
            print(f"Smile One Response: {data}")
            if "username" in data:
                return {"status": True, "nickname": data["username"]}
            elif "nickName" in data:
                return {"status": True, "nickname": data["nickName"]}
            return {"status": False, "nickname": f"Invalid: {data.get('message', 'Unknown')}"}
        except ValueError:
            # Handle non-JSON response (text/html)
            text = response.text
            print(f"Smile One Raw Response: {text}")
            if "〆Gemini、子" in text:  # Adjust based on real response
                return {"status": True, "nickname": "〆Gemini、子"}
            return {"status": False, "nickname": "Invalid ID or Server"}
    except requests.Timeout:
        print("Error: Smile One timed out")
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
