#i18n.py

import os
import json
from flask import request, g
import pytz
from babel import Locale, numbers, dates

class I18n:
    def __init__(self):
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        locales_dir = 'locales'
        for filename in os.listdir(locales_dir):
            if filename.endswith('.json'):
                lang = filename.replace('.json', '')
                with open(os.path.join(locales_dir, filename), 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
    
    def get_text(self, key, lang='en', **kwargs):
        """Get translated text for a key"""
        try:
            translation = self.translations.get(lang, {}).get(key, self.translations['en'].get(key, key))
            
            # Replace placeholders
            if kwargs:
                translation = translation.format(**kwargs)
            
            return translation
        except Exception:
            return key
    
    def get_supported_languages(self):
        return list(self.translations.keys())
    
    def get_user_language(self):
        """Determine user language from request"""
        # From URL parameter
        lang = request.args.get('lang')
        if lang and lang in self.translations:
            return lang
        
        # From Accept-Language header
        accept_language = request.headers.get('Accept-Language', 'en')
        preferred_lang = accept_language.split(',')[0].split('-')[0]
        if preferred_lang in self.translations:
            return preferred_lang
        
        # Default to English
        return 'en'

i18n = I18n()

def gettext(key, **kwargs):
    """Translation function for templates"""
    lang = getattr(g, 'language', 'en')
    return i18n.get_text(key, lang, **kwargs)

_ = gettext

def format_currency(amount, currency='SGD', lang='en'):
    """Format currency based on language"""
    try:
        locale = Locale.parse(lang)
        return numbers.format_currency(amount, currency, locale=locale)
    except Exception:
        return f"${amount:.2f}"

def format_datetime(dt, format='medium', lang='en'):
    """Format datetime based on language"""
    try:
        locale = Locale.parse(lang)
        return dates.format_datetime(dt, format=format, locale=locale)
    except Exception:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
