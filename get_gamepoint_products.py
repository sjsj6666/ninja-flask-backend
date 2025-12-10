import requests
import time
import json
import jwt
import pandas as pd
import certifi

# --- CONFIGURATION ---
PARTNER_ID = "YOUR_PARTNER_ID_HERE"
SECRET_KEY = "YOUR_SECRET_KEY_HERE"
BASE_URL = "https://api.gamepointclub.net" 
# Use "https://sandbox.gamepointclub.net" if testing on sandbox

# --- PROXY (Optional if running locally without VPN/Proxy) ---
# If your local IP is not whitelisted, you MUST use the Alibaba proxy
# PROXY_URL = "http://gamevault:PASSWORD@47.84.96.104:3128"
PROXY_URL = None 

proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

def generate_payload(data_dict):
    data_dict['timestamp'] = int(time.time())
    token = jwt.encode(data_dict, SECRET_KEY, algorithm='HS256')
    return json.dumps({"payload": token})

def make_request(endpoint, payload_data):
    url = f"{BASE_URL}/{endpoint}"
    body = generate_payload(payload_data)
    headers = {'Content-Type': 'application/json', 'partnerid': PARTNER_ID}
    
    try:
        response = requests.post(url, data=body, headers=headers, proxies=proxies, verify=certifi.where())
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("Fetching Token...")
    token_resp = make_request("merchant/token", {})
    if not token_resp or token_resp.get('code') != 200:
        print("Failed to get token:", token_resp)
        return

    token = token_resp['token']
    print(f"Token acquired. Fetching Product List...")

    list_resp = make_request("product/list", {"token": token})
    if not list_resp or list_resp.get('code') != 200:
        print("Failed to get list:", list_resp)
        return

    products = list_resp['detail']
    print(f"Found {len(products)} products. Fetching details...")

    all_data = []

    for i, p in enumerate(products):
        print(f"[{i+1}/{len(products)}] Fetching {p['name']}...")
        detail_resp = make_request("product/detail", {"token": token, "productid": p['id']})
        
        if detail_resp and detail_resp.get('code') == 200:
            for pkg in detail_resp['package']:
                all_data.append({
                    "Product ID": p['id'],
                    "Product Name": p['name'],
                    "Package ID": pkg['id'],
                    "Package Name": pkg['name'],
                    "Cost Price": pkg['price']
                })
        time.sleep(0.2) # Be nice to the API

    print("Saving to CSV...")
    df = pd.DataFrame(all_data)
    df.to_csv("gamepoint_full_catalog.csv", index=False)
    print("Done! Saved to gamepoint_full_catalog.csv")

if __name__ == "__main__":
    main()
