# In app.py

def check_smile_one_api(game, uid, server_id):
    # ... (endpoints, headers, pid logic - KEEP AS IS from your previous correct version) ...
    endpoints = {
        "mobile-legends": "https://www.smile.one/merchant/mobilelegends/checkrole",
        "genshin-impact": "https://www.smile.one/ru/merchant/genshinimpact/checkrole",
        "honkai-star-rail": "https://www.smile.one/br/merchant/honkai/checkrole",
        "zenless-zone-zero": "https://www.smile.one/br/merchant/zzz/checkrole",
        "bloodstrike": "https://www.smile.one/br/merchant/game/checkrole",
        "ragnarok-m-classic": "https://www.smile.one/sg/merchant/ragnarokmclassic/checkrole",
        "love-and-deepspace": "https://www.smile.one/us/merchant/loveanddeepspace/checkrole/"
    }

    if game not in endpoints:
        return {"status": "error", "message": f"Invalid game '{game}' for Smile One"}

    url = endpoints[game]
    current_headers = SMILE_ONE_HEADERS.copy()

    # Set Referer based on game
    if game == "mobile-legends":
        current_headers["Referer"] = "https://www.smile.one/merchant/mobilelegends"
    elif game == "genshin-impact":
        current_headers["Referer"] = "https://www.smile.one/ru/merchant/genshinimpact"
    elif game == "honkai-star-rail":
        current_headers["Referer"] = "https://www.smile.one/br/merchant/honkai"
    elif game == "zenless-zone-zero":
        current_headers["Referer"] = "https://www.smile.one/br/merchant/zzz"
    elif game == "bloodstrike":
        current_headers["Referer"] = "https://www.smile.one/br/merchant/game/bloodstrike"
    elif game == "ragnarok-m-classic":
        current_headers["Referer"] = "https://www.smile.one/sg/merchant/ragnarokmclassic"
    elif game == "love-and-deepspace":
        current_headers["Referer"] = "https://www.smile.one/us/merchant/loveanddeepspace"


    bloodstrike_pid = os.environ.get("BLOODSTRIKE_SMILE_ONE_PID", "20294")
    zzz_pid = os.environ.get("ZZZ_SMILE_ONE_PID", "YOUR_ZZZ_PID_NEEDS_TO_BE_SET")
    
    love_deepspace_pids = {
        "81": "19226", 
        "82": "19227", 
        "83": "19227"
    }

    current_pid = None
    if game == "love-and-deepspace":
        current_pid = love_deepspace_pids.get(server_id)
    else:
        params_pid_map = {
            "mobile-legends": "25",
            "genshin-impact": "19731",
            "honkai-star-rail": "18356",
            "zenless-zone-zero": zzz_pid,
            "bloodstrike": bloodstrike_pid,
            "ragnarok-m-classic": "23026"
        }
        current_pid = params_pid_map.get(game)

    if current_pid is None or current_pid == "YOUR_ZZZ_PID_NEEDS_TO_BE_SET":
         return {"status": "error", "message": f"PID not configured or invalid server for game '{game}'"}

    params = { "pid": current_pid, "checkrole": "1" }

    if game == "mobile-legends":
        params["user_id"] = uid
        params["zone_id"] = server_id
    elif game in ["honkai-star-rail", "genshin-impact", "zenless-zone-zero", "ragnarok-m-classic", "love-and-deepspace"]:
         params["uid"] = uid
         params["sid"] = server_id
    elif game == "bloodstrike":
        params["uid"] = uid
        params["sid"] = server_id

    logging.info(f"Sending Smile One request for {game}: URL={url}, Params={params}, Headers={current_headers.get('Cookie')[:50]}...")
    try:
        request_url = url
        if game == "bloodstrike":
            request_url = f"{url}?product=bloodstrike"

        response = requests.post(request_url, data=params, headers=current_headers, timeout=10)
        response.raise_for_status() # Will raise HTTPError for bad responses (4xx or 5xx)
        raw_text = response.text
        logging.info(f"Smile One Raw Response for {game} (UID: {uid}, Server: {server_id}): {raw_text}")

        try:
            data = response.json()
            logging.info(f"Smile One JSON Response for {game}: {data}")

            if data.get("code") == 200:
                username_to_return = None
                
                # Try to get username using game-specific or common keys
                # For Love and Deepspace, 'nickname' is the key in the successful JSON.
                # For others, 'username' or 'nickname' might be primary.
                primary_username_key = "nickname" if game == "love-and-deepspace" else "username"
                
                username_from_api = data.get(primary_username_key)
                if username_from_api and isinstance(username_from_api, str) and username_from_api.strip():
                    username_to_return = username_from_api.strip()
                    logging.info(f"Found username for {game} using primary key '{primary_username_key}': {username_to_return}")
                else:
                    # Fallback to other common keys if primary key didn't yield a username
                    possible_username_keys = ["username", "nickname", "role_name", "name", "char_name"]
                    for key in possible_username_keys:
                        if key == primary_username_key: continue # Already checked
                        value_from_api = data.get(key)
                        if value_from_api and isinstance(value_from_api, str) and value_from_api.strip():
                            username_to_return = value_from_api.strip()
                            logging.info(f"Found username for {game} under fallback key '{key}': {username_to_return}")
                            break
                
                if username_to_return:
                    return {"status": "success", "username": username_to_return}
                elif game in ["genshin-impact", "honkai-star-rail", "zenless-zone-zero"]:
                    logging.info(f"Smile One check successful (Code: 200) for {game}, UID exists but no username returned by API. Returning 'Account Verified'. Data: {data}")
                    return {"status": "success", "message": "Account Verified"}
                elif game in ["bloodstrike", "ragnarok-m-classic"]: # Games that might just verify UID/SID
                    logging.info(f"Smile One check successful (Code: 200) for {game} but NO username found in expected keys. Returning 'Account Verified (Username not retrieved)'. UID: {uid}. Data: {data}")
                    return {"status": "success", "message": "Account Verified (Username not retrieved)"}
                else: # Includes MLBB and Love and Deepspace if username_to_return is still None
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but NO username found in any expected keys (or API returned empty username). UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response"} # This is what the frontend receives as error
            else:
                 logging.warning(f"Smile One check FAILED for {game} with API code {data.get('code')}: {data.get('message')}")
                 error_msg = data.get("message", f"Invalid UID/Server or API error code: {data.get('code')}")
                 return {"status": "error", "message": error_msg}
        
        except ValueError: # JSONDecodeError
            # HTML parsing fallback for Love and Deepspace if JSON fails
            if game == "love-and-deepspace" and "<span class=\"name\">" in raw_text and "uid_error_tips" not in raw_text:
                try:
                    start_tag = "<span class=\"name\">"
                    end_tag = "</span>"
                    start_index = raw_text.find(start_tag)
                    if start_index != -1:
                        end_index = raw_text.find(end_tag, start_index + len(start_tag))
                        if end_index != -1:
                            username = raw_text[start_index + len(start_tag):end_index].strip()
                            logging.info(f"Successfully parsed username '{username}' from HTML for Love and Deepspace.")
                            return {"status": "success", "username": username}
                except Exception as parse_ex:
                    logging.error(f"Error parsing username from HTML for Love and Deepspace: {parse_ex} - Raw Text: {raw_text}")
            
            logging.error(f"Error parsing JSON for Smile One {game}: - Raw Text: {raw_text}")
            return {"status": "error", "message": "Invalid response format from Smile One API"}

    # ... (rest of the exception handling: Timeout, RequestException, generic Exception - KEEP AS IS) ...
    except requests.Timeout:
        logging.error(f"Error: Smile One API timed out for {game}")
        return {"status": "error", "message": "API Timeout"}
    except requests.RequestException as e:
        status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
        error_text = e.response.text if e.response is not None else "No response body"
        logging.error(f"Error checking Smile One {game} (UID {uid}): HTTP Status={status_code_str}, Error={str(e)}, Response: {error_text}")
        
        user_msg = f"API Connection Error ({status_code_str})"
        if e.response is not None:
            status_code_val = e.response.status_code
            if status_code_val == 400: user_msg = "Invalid request to Smile One (400)"
            elif status_code_val == 401: user_msg = "Smile One API Unauthorized (401). Check SMILE_ONE_COOKIE."
            elif status_code_val == 403: user_msg = "Smile One API Forbidden (403). Check SMILE_ONE_COOKIE or IP restrictions."
            elif status_code_val == 404: user_msg = "Smile One API Endpoint Not Found (404)"
            elif status_code_val == 429: user_msg = "Smile One API Rate Limited (429)"
            elif status_code_val >= 500: user_msg = f"Smile One API Server Error ({status_code_val})"
        return {"status": "error", "message": user_msg}
    except Exception as e:
        logging.exception(f"Unexpected error in check_smile_one_api for {game}, UID {uid}")
        return {"status": "error", "message": "An unexpected error occurred"}
