# price_updater.py

import os
import logging
from supabase import create_client, Client
from gamepoint_service import GamePointService
from redis_cache import cache
import concurrent.futures

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load Supabase credentials from environment
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
    raise ValueError("Supabase credentials must be set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def fetch_and_cache_prices():
    """Fetches the full GamePoint catalog and caches each package price in Redis."""
    logging.info("Starting GamePoint price update job...")
    
    try:
        gp = GamePointService(supabase_client=supabase)
        
        # This function needs to fetch the full catalog with packages
        # We can reuse the logic from your admin endpoint, but simplified.
        token = gp.get_token()
        list_resp = gp._request("product/list", {"token": token})
        products = list_resp.get('detail', [])

        if not products:
            logging.warning("No products found in GamePoint catalog.")
            return

        total_packages = 0

        def process_product(product):
            try:
                detail_resp = gp._request("product/detail", {"token": token, "productid": product['id']})
                if detail_resp.get('code') == 200:
                    packages = detail_resp.get('package', [])
                    for pkg in packages:
                        # Key: "gp_price:12345", Value: "10.50"
                        cache.set(f"gp_price:{pkg['id']}", str(pkg['price']), expire_seconds=7200) # Cache for 2 hours
                    return len(packages)
            except Exception as e:
                logging.error(f"Failed to process product {product.get('id')}: {e}")
            return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            package_counts = executor.map(process_product, products)
            total_packages = sum(package_counts)

        logging.info(f"Price update job complete. Cached prices for {total_packages} packages.")

    except Exception as e:
        logging.error(f"Critical error in price update job: {e}")

if __name__ == "__main__":
    fetch_and_cache_prices()
