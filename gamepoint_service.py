import os
import time
import json
import jwt
import requests
import logging
import certifi
from supabase import create_client
from error_handler import ExternalAPIError, AppError

logger = logging.getLogger(__name__)

_token_cache = {}

class GamePointService:
    def __init__(self, supabase_client=None):
        # Optimization: Reuse existing client if provided
        if supabase_client:
            self.supabase = supabase_client
        else:
            self.supabase = create_client(
                os.environ.get('SUPABASE_URL'), 
                os.environ.get('SUPABASE_SERVICE_KEY')
            )
            
        self.config = self._load_config()

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
                timeout=20,
                verify=certifi.where()
            )
            
            try:
                resp_json = response.json()
            except json.JSONDecodeError:
                logger.error(f"GamePoint Non-JSON Response (Status {response.status_code}): {response.text[:200]}")
                if response.status_code == 407:
                    raise ExternalAPIError("Proxy Authentication Failed (407). Check DB credentials.", service_name="AlibabaProxy")
                raise ExternalAPIError(f"Invalid response from Supplier (Status {response.status_code})", service_name="GamePoint")
            
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
        mode = self.config['mode']
        current_time = time.time()
        
        if mode in _token_cache:
            cached_data = _token_cache[mode]
            if cached_data['expires'] > current_time:
                return cached_data['token']

        response = self._request("merchant/token", {})
        token = response.get('token')
        
        if token:
            _token_cache[mode] = {
                'token': token,
                'expires': current_time + 3600
            }
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
        
        full_catalog = []
        
        for p in products:
            try:
                time.sleep(0.2)
                detail_resp = self._request("product/detail", {"token": token, "productid": p['id']})
                
                if detail_resp.get('code') == 200:
                    p_data = {
                        "id": p['id'],
                        "name": p['name'],
                        "fields": detail_resp.get('fields', []),
                        "packages": detail_resp.get('package', [])
                    }
                    full_catalog.append(p_data)
            except Exception as e:
                logger.warning(f"Failed to fetch detail for {p.get('name', 'Unknown')}: {e}")
                continue
                
        return full_catalog

    def validate_id(self, product_id, inputs):
        token = self.get_token()
        payload = {
            "token": token,
            "productid": int(product_id),
            "fields": inputs
        }
        return self._request("order/validate", payload)

    def create_order(self, package_id, validation_token, merchant_code):
        token = self.get_token()
        payload = {
            "token": token,
            "packageid": int(package_id),
            "validate_token": validation_token,
            "merchantcode": merchant_code
        }
        return self._request("order/create", payload)
