# gamepoint_service.py

import os
import time
import json
import jwt
import requests
import logging
import certifi
from supabase import create_client
from redis_cache import cache  # Using your existing Redis cache
from error_handler import ExternalAPIError, AppError

logger = logging.getLogger(__name__)

class GamePointService:
    def __init__(self):
        # 1. Connect to Supabase to get dynamic settings
        self.supabase = create_client(
            os.environ.get('SUPABASE_URL'), 
            os.environ.get('SUPABASE_SERVICE_KEY')
        )
        self.config = self._load_config()

        # 2. Set Base URL based on mode
        if self.config['mode'] == 'live':
            self.base_url = "https://api.gamepointclub.net"
            self.partner_id = self.config['partner_id_live']
            self.secret_key = self.config['secret_key_live']
        else:
            self.base_url = "https://sandbox.gamepointclub.net"
            self.partner_id = self.config['partner_id_sandbox']
            self.secret_key = self.config['secret_key_sandbox']

        # 3. Configure Proxy (Alibaba Cloud)
        self.proxies = None
        if self.config['proxy_url']:
            self.proxies = {
                "http": self.config['proxy_url'],
                "https": self.config['proxy_url']
            }

    def _load_config(self):
        """Fetches active configuration from Supabase Settings."""
        keys = [
            'gamepoint_mode', 
            'gamepoint_partner_id_sandbox', 'gamepoint_secret_key_sandbox',
            'gamepoint_partner_id_live', 'gamepoint_secret_key_live',
            'gamepoint_proxy_url'
        ]
        try:
            response = self.supabase.table('settings').select('key,value').in_('key', keys).execute()
            settings = {item['key']: item['value'] for item in response.data}
            
            return {
                'mode': settings.get('gamepoint_mode', 'sandbox'),
                'partner_id_sandbox': settings.get('gamepoint_partner_id_sandbox'),
                'secret_key_sandbox': settings.get('gamepoint_secret_key_sandbox'),
                'partner_id_live': settings.get('gamepoint_partner_id_live'),
                'secret_key_live': settings.get('gamepoint_secret_key_live'),
                'proxy_url': settings.get('gamepoint_proxy_url')
            }
        except Exception as e:
            logger.error(f"Failed to load GamePoint config from DB: {e}")
            raise AppError("Configuration Error")

    def _generate_payload(self, data):
        """Encrypts data using HMAC SHA-256 JWT."""
        payload = data.copy()
        payload['timestamp'] = int(time.time())
        
        # JWT Encode
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        # GamePoint expects: {"payload": "jwt_token_string"}
        return json.dumps({"payload": token})

    def _request(self, endpoint, data):
        """Sends request to GamePoint with Proxy and Partner ID Header."""
        url = f"{self.base_url}/{endpoint}"
        body = self._generate_payload(data)
        
        headers = {
            'Content-Type': 'application/json',
            'partnerid': self.partner_id
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
                logger.error(f"GamePoint Non-JSON Response: {response.text}")
                raise ExternalAPIError("Invalid response from Supplier", service_name="GamePoint")
            
            # Check for API-level errors (Code 200, 100, 101 are usually success/pending)
            if resp_json.get('code') not in [100, 101, 200]:
                logger.error(f"GamePoint API Error: {resp_json}")
                raise ExternalAPIError(
                    f"GamePoint Error {resp_json.get('code')}: {resp_json.get('message')}",
                    service_name="GamePoint"
                )
                
            return resp_json

        except requests.RequestException as e:
            logger.error(f"Network Error connecting to GamePoint: {str(e)}")
            raise ExternalAPIError("Failed to connect to GamePoint Supplier", service_name="GamePoint")

    def get_token(self):
        """
        Gets the Daily Token. 
        Cached in Redis because it expires daily at 00:00 UTC+8.
        """
        cache_key = f"gamepoint_token_{self.config['mode']}"
        cached_token = cache.get(cache_key)
        
        if cached_token:
            return cached_token

        response = self._request("merchant/token", {})
        token = response.get('token')
        
        if token:
            # Cache for 1 hour
            cache.set(cache_key, token, expire_seconds=3600)
            return token
        else:
            raise ExternalAPIError("Failed to retrieve GamePoint Token", service_name="GamePoint")

    def check_balance(self):
        """Returns the merchant balance."""
        token = self.get_token()
        response = self._request("merchant/balance", {"token": token})
        return response.get('balance')

    def get_full_catalog(self):
        """Fetches product list for Admin Panel."""
        token = self.get_token()
        list_resp = self._request("product/list", {"token": token})
        products = list_resp.get('detail', [])
        
        full_catalog = []
        # Limiting to first 10 for safety/speed if running purely as test, remove slice for full sync
        for p in products:
            try:
                detail_resp = self._request("product/detail", {"token": token, "productid": p['id']})
                if detail_resp.get('code') == 200:
                    p_data = {
                        "id": p['id'],
                        "name": p['name'],
                        "fields": detail_resp.get('fields', []),
                        "packages": detail_resp.get('package', [])
                    }
                    full_catalog.append(p_data)
                time.sleep(0.1) # Rate limit protection
            except Exception as e:
                logger.warning(f"Failed to fetch detail for {p['name']}: {e}")
                continue
                
        return full_catalog

    def validate_id(self, product_id, inputs):
        """
        Validates User ID / Zone ID.
        inputs: {'input1': 'userid', 'input2': 'zoneid'}
        """
        token = self.get_token()
        payload = {
            "token": token,
            "productid": int(product_id),
            "fields": inputs
        }
        # GamePoint returns a 'validation_token' valid for 30s
        return self._request("order/validate", payload)

    def create_order(self, package_id, validation_token, merchant_code):
        """Executes the purchase."""
        token = self.get_token()
        payload = {
            "token": token,
            "packageid": int(package_id),
            "validate_token": validation_token,
            "merchantcode": merchant_code
        }
        # 100 = Success, 101 = Pending
        return self._request("order/create", payload)
