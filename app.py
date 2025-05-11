            if data.get("code") == 200:
                username_to_return = None
                
                # Try to get username using game-specific or common keys
                # For Love and Deepspace, 'nickname' is the key in the successful JSON.
                # For others, 'username' or 'nickname' might be primary.
                primary_username_key = "nickname" if game == "love-and-deepspace" else "username" # Smile.one uses 'nickname' for L&D
                
                username_from_api = data.get(primary_username_key)
                if username_from_api and isinstance(username_from_api, str) and username_from_api.strip():
                    username_to_return = username_from_api.strip()
                    logging.info(f"Found username for {game} using primary key '{primary_username_key}': {username_to_return}")
                else:
                    # Fallback to other common keys if primary key didn't yield a username
                    # This handles cases where Smile.One might use 'username' even for L&D, or 'nickname' for others
                    possible_username_keys = ["username", "nickname", "role_name", "name", "char_name"]
                    for key in possible_username_keys:
                        if key == primary_username_key: continue # Already checked
                        value_from_api = data.get(key)
                        if value_from_api and isinstance(value_from_api, str) and value_from_api.strip():
                            username_to_return = value_from_api.strip()
                            logging.info(f"Found username for {game} under fallback key '{key}': {username_to_return}")
                            break
                
                if username_to_return: # If any method above successfully found a username
                    return {"status": "success", "username": username_to_return}
                # If no username, proceed with game-specific "Account Verified" or error messages
                elif game in ["genshin-impact", "honkai-star-rail", "zenless-zone-zero"]:
                    # These games might just verify UID and not always return a username from this specific check
                    logging.info(f"Smile One check successful (Code: 200) for {game}, UID exists but no username returned by API. Returning 'Account Verified'. Data: {data}")
                    return {"status": "success", "message": "Account Verified"}
                elif game in ["bloodstrike", "ragnarok-m-classic"]: # Games that might just verify UID/SID
                    logging.info(f"Smile One check successful (Code: 200) for {game} but NO username found in expected keys. Returning 'Account Verified (Username not retrieved)'. UID: {uid}. Data: {data}")
                    return {"status": "success", "message": "Account Verified (Username not retrieved)"}
                else: # Includes MLBB and Love and Deepspace IF username_to_return is still None (e.g., API returned code 200 but empty 'nickname' field for L&D)
                    logging.warning(f"Smile One check successful (Code: 200) for {game} but NO username found in any expected keys (or API returned empty username). UID: {uid}. Data: {data}")
                    return {"status": "error", "message": "Username not found in API response"} # This is what the frontend receives as error
