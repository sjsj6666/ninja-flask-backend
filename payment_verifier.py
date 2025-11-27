# payment_verifier.py

import os
import email
import imaplib
import time
import re
import smtplib
from email.message import EmailMessage
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta, timezone
from itertools import permutations

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
IMAP_SERVER = os.environ.get("IMAP_SERVER")
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
BANK_EMAIL_SENDER = os.environ.get("BANK_EMAIL_SENDER")
CHECK_INTERVAL_SECONDS = 15
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = os.environ.get("SMTP_PORT")
ADMIN_EMAIL_RECEIVER = os.environ.get("ADMIN_EMAIL_RECEIVER")
ALERT_EMAIL_SENDER = os.environ.get("ALERT_EMAIL_SENDER")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logging.info("Successfully connected to Supabase.")
except Exception as e:
    logging.critical(f"FATAL: Could not connect to Supabase. {e}")
    exit()

def send_admin_alert(amount, from_name, potential_matches):
    if not all([SMTP_SERVER, SMTP_PORT, ADMIN_EMAIL_RECEIVER, ALERT_EMAIL_SENDER, ALERT_EMAIL_PASSWORD]):
        logging.error("SMTP alert credentials are not fully configured. Cannot send admin alert.")
        return
    
    order_details = [f"  - Order ID: {order['id']}, User Name: {order['remitter_name']}" for order in potential_matches]

    msg = EmailMessage()
    msg.set_content(
        f"An ambiguous payment of S${amount:.2f} from '{from_name}' was detected.\n\n"
        f"Multiple orders matched these details, and their statuses have been set to 'manual_review'.\n"
        f"Please log in to your admin panel to resolve this.\n\n"
        f"Ambiguous Orders:\n" + "\n".join(order_details)
    )
    msg['Subject'] = f"[URGENT] GameVault Manual Payment Review Required"
    msg['From'] = ALERT_EMAIL_SENDER
    msg['To'] = ADMIN_EMAIL_RECEIVER
    try:
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(ALERT_EMAIL_SENDER, ALERT_EMAIL_PASSWORD)
            server.send_message(msg)
            logging.info(f"Successfully sent manual review alert to {ADMIN_EMAIL_RECEIVER}")
    except Exception as e:
        logging.error(f"Failed to send admin alert email: {e}")

def strip_html_tags(text):
    """Removes HTML tags to ensure clean regex matching."""
    clean = re.sub('<[^<]+?>', ' ', text)
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
    clean = " ".join(clean.split())
    return clean

def parse_payment_email(email_body):
    try:
        clean_body = strip_html_tags(email_body)
        # Log start of body for debugging
        logging.info(f"DEBUG CLEAN BODY (First 100 chars): {clean_body[:100]}...")

        # 1. Extract Amount
        amount_match = re.search(r"(?:S\$|SGD)\s?([\d,]+\.\d{2})", clean_body, re.IGNORECASE)
        if not amount_match: return None
        amount = float(amount_match.group(1).replace(',', ''))
        
        # 2. Extract Reference
        reference_match = re.search(r"reference (\d+)|Notes(?:\s*\(Optional\))?[:\s]\s*(\w+)", clean_body, re.IGNORECASE)
        reference_id = None
        if reference_match:
            reference_id = (reference_match.group(1) or reference_match.group(2)).strip()
        
        # 3. Extract Name
        from_name = "N/A"
        match = re.search(r"(?:From|Payer|Sent by)[\s:]+([A-Za-z\s]+?)(?=\s+(?:If this|Transaction|Amount|Ref|To:))", clean_body, re.IGNORECASE)
        
        if match:
            from_name = match.group(1).strip()

        logging.info(f"Parsed email: Amount=${amount}, Reference={reference_id or 'N/A'}, From={from_name}")
        return {"amount": amount, "reference_id": reference_id, "from_name": from_name}
    except Exception as e:
        logging.error(f"Error parsing email body: {e}")
    return None

def names_are_equivalent(bank_name, user_name):
    if not bank_name or not user_name:
        return False
    
    norm_bank = bank_name.lower().strip()
    norm_user = user_name.lower().strip()
    
    if norm_bank == norm_user:
        return True
        
    bank_words = norm_bank.split()
    user_words = norm_user.split()
    
    if sorted(bank_words) == sorted(user_words):
        return True
        
    user_no_space = norm_user.replace(" ", "")
    # Check permutations: "shengjunton" == "sheng" + "jun" + "ton"
    if len(bank_words) < 6:
        for p in permutations(bank_words):
            if "".join(p) == user_no_space:
                return True
                
    return False

def process_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")
        status, messages = mail.search(None, f'(UNSEEN FROM "{BANK_EMAIL_SENDER}")')
        if status != "OK":
            logging.error("Failed to search for emails.")
            mail.logout()
            return

        message_ids = messages[0].split()
        if not message_ids:
            logging.info("No new payment emails found.")
            mail.logout()
            return

        message_id_headers = []
        for msg_id in message_ids:
            _, msg_data = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (MESSAGE-ID)])")
            if msg_data[0] and isinstance(msg_data[0], tuple):
                header_text = msg_data[0][1].decode()
                match = re.search(r"Message-ID:\s*<([^>]+)>", header_text, re.IGNORECASE)
                if match:
                    message_id_headers.append(match.group(1))

        if not message_id_headers:
            logging.warning("Found unseen emails but could not extract Message-IDs.")
            mail.logout()
            return
            
        response = supabase.table('processed_emails').select('message_id').in_('message_id', message_id_headers).execute()
        db_processed_ids = {row['message_id'] for row in response.data}
        
        for msg_id in message_ids:
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    message_id_header_full = msg.get('Message-ID', '').strip()
                    match = re.search(r"<([^>]+)>", message_id_header_full)
                    message_id = match.group(1) if match else None

                    if not message_id or message_id in db_processed_ids:
                        continue
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                body = part.get_payload(decode=True).decode(errors='ignore')
                                break
                        if not body:
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode(errors='ignore')
                                    break
                    else:
                        body = msg.get_payload(decode=True).decode(errors='ignore')
                    
                    payment_details = parse_payment_email(body)
                    if payment_details:
                        update_order_status(payment_details)
                    
                    supabase.table('processed_emails').insert({'message_id': message_id}).execute()
                    logging.info(f"Recorded email {message_id} as processed.")
        
        mail.logout()
    except Exception as e:
        logging.error(f"An error occurred while processing emails: {e}", exc_info=True)

def update_order_status(details):
    amount = details["amount"]
    reference_id = details["reference_id"]
    from_name = details["from_name"]
    
    try:
        # Window: 12 minutes (10 mins for QR + 2 mins for email delay)
        time_window_start = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
        
        # 1. Fetch ALL 'verifying' orders in this window
        # We DO NOT filter by amount in the DB query to avoid float precision errors
        response = supabase.table('orders').select('id, total_amount, remitter_name')\
            .eq('status', 'verifying')\
            .gte('created_at', time_window_start)\
            .execute()
        
        if not response.data:
            logging.warning("No 'verifying' orders found in the last 12 minutes.")
            return

        # 2. Filter matches in Python (Handling Float Precision & Name)
        potential_matches = []
        
        for order in response.data:
            db_amount = float(order['total_amount'])
            
            # Check Amount Match (tolerance 0.01)
            if abs(db_amount - amount) < 0.01:
                
                # Check Name Match (Strict)
                if from_name != "N/A":
                    user_remitter_name = order.get('remitter_name')
                    if names_are_equivalent(from_name, user_remitter_name):
                        potential_matches.append(order)
                        logging.info(f"Match found: Order {order['id']} (Name match: {user_remitter_name})")
                else:
                    # Fallback if name parser failed completely (unlikely with new regex)
                    logging.warning(f"Name N/A. Matching Order {order['id']} based on amount only.")
                    potential_matches.append(order)

        # 3. Decision Logic
        if len(potential_matches) == 1:
            order_id = potential_matches[0]['id']
            logging.info(f"SUCCESS: Matching Order Found {order_id} -> Processing")
            supabase.table('orders').update({'status': 'processing'}).eq('id', order_id).execute()
            
        elif len(potential_matches) > 1:
            logging.critical(f"AMBIGUOUS: Found {len(potential_matches)} matches for S${amount:.2f}.")
            order_ids_to_flag = [order['id'] for order in potential_matches]
            supabase.table('orders').update({'status': 'manual_review'}).in_('id', order_ids_to_flag).execute()
            send_admin_alert(amount, from_name, potential_matches)
            
        else:
            logging.warning(f"No match found for S${amount:.2f} from '{from_name}' in the last 12 minutes.")

    except Exception as e:
        logging.error(f"Error updating order status: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("Starting Payment Verification Bot...")
    if not all([IMAP_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD, SUPABASE_URL, SUPABASE_SERVICE_KEY, BANK_EMAIL_SENDER]):
        logging.critical("FATAL: Core environment variables are missing.")
        exit()
    while True:
        process_emails()
        time.sleep(CHECK_INTERVAL_SECONDS)
