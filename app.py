def check_smile_one_api(game, uid, server_id):
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole"
    }

    if game not in endpoints:
        return {"status": "error", "message": "Invalid game"}

    url = endpoints[game]
    SMILE_ONE_HEADERS["Referer"] = (
        "https://www.smile.one/merchant/mobilelegends" if game == "mobile-legends" 
        else "https://www.smile.one/ru/merchant/genshinimpact" if game == "genshin-impact" 
        else "https://www.smile.one/merchant/honkai"
    )
    
    params = {
        "pid": "25" if game == "mobile-legends" else "19731" if game == "genshin-impact" else "18356",
        "checkrole": "1",
    }
    
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
                return {"status": "success", "username": data["username"]}
            elif game == "honkai-star-rail":
                # Check if username exists in response; Smile One might return it as 'role_name' or similar
                username = data.get("username") or data.get("role_name") or data.get("nickname")
                if username:
                    return {"status": "success", "username": username}
                return {"status": "success", "message": "UID and Server verified"}  # Fallback if no username
            elif game == "genshin-impact":
                return {"status": "success", "message": "Account Verified"}
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
