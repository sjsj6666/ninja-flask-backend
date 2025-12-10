def _load_config(self):
        keys = [
            'gamepoint_mode', 
            'gamepoint_partner_id_sandbox', 'gamepoint_secret_key_sandbox',
            'gamepoint_partner_id_live', 'gamepoint_secret_key_live',
            'gamepoint_proxy_url'
        ]
        try:
            # Add .execute() to ensure the query runs
            response = self.supabase.table('settings').select('key,value').in_('key', keys).execute()
            settings = {item['key']: item['value'] for item in response.data}
            
            # Helper to safely get and trim values
            def get_val(key):
                val = settings.get(key)
                return val.strip() if val else None

            mode = get_val('gamepoint_mode')
            # Default to sandbox if mode is missing or invalid
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
