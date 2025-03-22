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
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": os.environ.get("SMILE_ONE_COOKIE", "PHPSESSID=ejhpiht0fal17bd25smd2e91nu; cf_clearance=G9wXc39MaI28uqvi8GIZe52wsmH4LdiVDGZxLCx.BG0-1742661501-1.2.1.1-SP5DtI_TyUfB6xDxd9j6f8EOSHmjStqhqIHFqrzEwdqc9.8SCv4mURAwf.nxvVWR9O9GM9P51uGX9WwT36GJX_M6v._d0Zwd5n9g4KzqRfPtgo9Yahl4jB9w6Yh79HAcouEr4IzSt8sQYyOJq18cyuHA33.NYTf6TEu8qkZTA9s7QioyAK72A4rmEpwe22BiKIhK9mM..IEJjoeXbtQt7uTUC3RnZSSZWfewVWxBvD9OyEi1t577KhnRAGeoJ24ifleIcp2eRD8vSd7g1Xm3KaUt1DMMuls8mwIMr4byiNIQZ7n0YZfZu3rN_ldkQwfH1Yimpekzlail7397.zwhKYf5sSJUw7KrUjfE_WC1VUU; ...")
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
    # Update Referer based on game
    SMILE_ONE_HEADERS["Referer"] = "https://www.smile.one/merchant/mobilelegends" if game == "mobile-legends" else "https://www.smile.one/ru/merchant/genshinimpact" if game == "genshin-impact" else "https://www.smile.one/merchant/honkai"
    
    params = {
        "pid": "25" if game == "mobile-legends" else "19731" if game == "genshin-impact" else "18356",
        "checkrole": "1",
    }
    
    # MLBB uses user_id and zone_id, others use uid and sid
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
            if game == "mobile-legends" and "username" in data and data["username"]:
                return {"status": "success", "nickname": data["username"], "data": data}
            elif game == "genshin-impact":
                return {"status": "success", "message": "Account Verified"}  # For Genshin, no username
            else:  # HSR
                return {"status": "success", "message": "UID and Server verified", "data": data}
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
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
