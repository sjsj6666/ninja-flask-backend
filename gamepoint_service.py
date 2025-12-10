import os
import time
import json
import jwt
import requests
import logging
import certifi
from supabase import create_client
from redis_cache import cache
from error_handler import ExternalAPIError, AppError

logger = logging.getLogger(__name__)

class GamePointService:
    def __init__(self):
        self.supabase = create_client(
            os.environ.get('SUPABASE_URL'), 
            os.environ.get('SUPABASE_SERVICE_KEY')
        )
        self.config = self._load_config()

        # Switch URL based on Admin Panel setting
        if self.config['mode'] == 'live':
            self.base_url = "https://api.gamepointclub.net"
            self.partner_id = self.config['partner_id_live']
            self.secret_key = self.config['secret_key_live']
        else:
            self.base_url = "https://sandbox.gamepointclub.net"
            self.partner_id = self.config['partner_id_sandbox']
            self.secret_key = self.config['secret_key_sandbox']

        self.proxies = None
        if self.config['proxy_url']:
            proxy_url = self.config['proxy_url'].strip()
            self.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }

    def _load_config(self):
        keys = [
            'gamepoint_mode', 
            'gamepoint_partner_id_sandbox', 'gamepoint_secret_key_sandbox',
            'gamepoint_partner_id_live', 'gamepoint_secret_key_live',
            'gamepoint_proxy_url'
        ]
        try:
            response = self.supabase.table('settings').select('key,value').in_('key', keys).execute()
            settings = {item['key']: item['value'] for item in response.data}
            
            def get_val(key):
                val = settings.get(key)
                return val.strip() if val else None

            mode = get_val('gamepoint_mode')
            if mode not in ['live', 'sandbox']:
                mode = 'sandbox'

            return {
                'mode': mode,
                'partner_id_sandbox': get_val('gamepoint_partner_id_sandbox'),
                'secret_key_sandbox': get_val('gamepoint_secret_key_sandbox'),
                'partner_id_live': get_val('gamepoint_partner_id_live'),
                'secret_key_live': get_val('gamepoint_secret_key_live'),
                'proxy_url': get_val('gamepoint_proxy_url')
            }
        except Exception as e:
            logger.error(f"Failed to load GamePoint config from DB: {e}")
            raise AppError("Configuration Error")

    def _generate_payload(self, data):
        payload = data.copy()
        payload['timestamp'] = int(time.time())
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return json.dumps({"payload": token})

    def _request(self, endpoint, data):
        url = f"{self.base_url}/{endpoint}"
        body = self._generate_payload(data)
        
        headers = {
            'Content-Type': 'application/json',
            'partnerid': self.partner_id,
            'User-Agent': 'GameVault/1.0'
        }

        try:
            logger.info(f"GamePoint Request [{self.config['mode']}]: {endpoint}")
            
            response = requests.post(
                url, 
                data=body, 
                headers=headers, 
                proxies=self.proxies, 
                timeout=30,
                verify=certifi.where()
            )
            
            try:
                resp_json = response.json()
            except json.JSONDecodeError:
                logger.error(f"GamePoint Non-JSON Response (Status {response.status_code}): {response.text[:200]}")
                if response.status_code == 407:
                    raise ExternalAPIError("Proxy Authentication Failed (407). Check DB credentials.", service_name="AlibabaProxy")
                raise ExternalAPIError(f"Invalid response from Supplier (Status {response.status_code})", service_name="GamePoint")
            
            # API Error Handling
            # 200 = Success (General)
            # 100 = Purchase Successful (Order/Create)
            # 101 = Purchase Pending (Order/Create)
            if resp_json.get('code') not in [100, 101, 200]:
                logger.error(f"GamePoint API Error: {resp_json}")
                raise ExternalAPIError(
                    f"GamePoint Error {resp_json.get('code')}: {resp_json.get('message')}",
                    service_name="GamePoint"
                )
                
            return resp_json

        except requests.exceptions.ProxyError as e:
            logger.error(f"Proxy Connection Failed: {str(e)}")
            raise ExternalAPIError("Proxy Connection Failed (407). Password might contain special chars.", service_name="AlibabaProxy")
        except requests.RequestException as e:
            logger.error(f"Network Error connecting to GamePoint: {str(e)}")
            raise ExternalAPIError("Failed to connect to GamePoint Supplier", service_name="GamePoint")

    def get_token(self):
        cache_key = f"gamepoint_token_{self.config['mode']}"
        cached_token = cache.get(cache_key)
        
        if cached_token:
            return cached_token

        response = self._request("merchant/token", {})
        token = response.get('token')
        
        if token:
            cache.set(cache_key, token, expire_seconds=3600)
            return token
        else:
            raise ExternalAPIError("Failed to retrieve GamePoint Token", service_name="GamePoint")

    def check_balance(self):
        token = self.get_token()
        response = self._request("merchant/balance", {"token": token})
        return response.get('balance')

    def get_full_catalog(self):
        token = self.get_token()
        try:
            list_resp = self._request("product/list", {"token": token})
            products = list_resp.get('detail', [])
        except Exception as e:
            logger.error(f"Failed to fetch product list: {e}")
            return []
        return products

    # --- IMPLEMENTING ORDER/VALIDATE ---
    def validate_id(self, product_id, inputs):
        """
        Validates User ID / Zone ID.
        Output: Returns full response containing 'validation_token'.
        NOTE: validation_token expires in 30 seconds.
        """
        token = self.get_token()
        
        # Ensure productid is integer
        payload = {
            "token": token,
            "productid": int(product_id),
            "fields": inputs # inputs = {"input1": "12345", "input2": "1234"}
        }
        
        return self._request("order/validate", payload)

    # --- IMPLEMENTING ORDER/CREATE ---
    def create_order(self, package_id, validation_token, merchant_code):
        """
        Executes the purchase using the token from validate_id.
        """
        token = self.get_token()
        
        payload = {
            "token": token,
            "packageid": int(package_id),
            "validate_token": validation_token,
            "merchantcode": merchant_code
        }
        
        # Returns: { code: 100/101, message: "...", referenceno: "..." }
        return self._request("order/create", payload)
