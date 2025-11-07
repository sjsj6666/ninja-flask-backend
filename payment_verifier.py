#payment_verifier.py

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

def parse_payment_email(email_body):
    try:
        amount_match = re.search(r"S\$([\d,]+\.\d{2})", email_body)
        reference_match = re.search(r"reference (\d+)|Notes(?:\s*\(Optional\))?[:\s]\s*(\w+)", email_body, re.IGNORECASE)
        from_name_match = re.search(r"From:\s*([A-Za-z\s]+)", email_body, re.IGNORECASE)

        if not amount_match: return None
        amount = float(amount_match.group(1).replace(',', ''))
        reference_id = None
        if reference_match:
            reference_id = (reference_match.group(1) or reference_match.group(2)).strip()
        
        from_name = from_name_match.group(1).strip() if from_name_match else "N/A"
        
        logging.info(f"Parsed email: Amount=${amount}, Reference={reference_id or 'N/A'}, From={from_name}")
        return {"amount": amount, "reference_id": reference_id, "from_name": from_name}
    except Exception as e:
        logging.error(f"Error parsing email body: {e}")
    return None

def names_are_equivalent(bank_name, user_name):
    if not bank_name or not user_name:
        return False
    norm_bank_name = bank_name.lower()
    norm_user_name = user_name.lower()
    bank_words = norm_bank_name.split()
    user_name_no_spaces = norm_user_name.replace(" ", "")
    possible_combinations = {"".join(p) for p in permutations(bank_words)}
    return user_name_no_spaces in possible_combinations

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

        # Fetch all unique message IDs from the unseen emails
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
            
        # Check which of these message IDs are already in our database
        response = supabase.table('processed_emails').select('message_id').in_('message_id', message_id_headers).execute()
        db_processed_ids = {row['message_id'] for row in response.data}
        
        for msg_id in message_ids:
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    message_id_header_full = msg.get('Message-ID', '').strip()
                    
                    # Extract the core message ID (without <>)
                    match = re.search(r"<([^>]+)>", message_id_header_full)
                    message_id = match.group(1) if match else None

                    if not message_id:
                        logging.warning(f"Could not parse Message-ID from email with UID {msg_id}.")
                        continue
                    
                    # If this ID is already in our database, skip it
                    if message_id in db_processed_ids:
                        logging.info(f"Skipping already processed email: {message_id}")
                        continue
                    
                    # Process the email body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors='ignore')
                    
                    payment_details = parse_payment_email(body)
                    if payment_details:
                        update_order_status(payment_details)
                    
                    # IMPORTANT: Record this email as processed in Supabase
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
        thirty_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        
        # Priority 1: Match by Reference ID
        if reference_id:
            response = supabase.table('orders').select('id, total_amount').eq('status', 'verifying').gte('created_at', thirty_minutes_ago).execute()
            exact_match = []
            for order in response.data:
                order_numeric_ref = str(int(order['id'].replace('-', '')[:15], 16))[-8:]
                if order_numeric_ref == reference_id and abs(order['total_amount'] - amount) < 0.01:
                    exact_match.append(order)
            
            if len(exact_match) == 1:
                order_id = exact_match[0]['id']
                logging.info(f"UNIQUE MATCH FOUND via Reference ID! Updating order {order_id} to 'processing'.")
                supabase.table('orders').update({'status': 'processing'}).eq('id', order_id).execute()
                return

        # Priority 2: Match by Amount and Remitter Name
        response = supabase.table('orders').select('id, total_amount, remitter_name').eq('status', 'verifying').eq('total_amount', amount).gte('created_at', thirty_minutes_ago).execute()
        
        potential_matches = []
        if from_name and from_name != "N/A":
            logging.info(f"Attempting to match by name. Bank Name: '{from_name}'")
            for order in response.data:
                user_remitter_name = order.get('remitter_name')
                if user_remitter_name and names_are_equivalent(from_name, user_remitter_name):
                    potential_matches.append(order)
        
        if not potential_matches and response.data:
             potential_matches = response.data

        if len(potential_matches) == 1:
            order_id = potential_matches[0]['id']
            logging.info(f"UNIQUE MATCH FOUND via Amount/Name! Updating order {order_id} to 'processing'.")
            supabase.table('orders').update({'status': 'processing'}).eq('id', order_id).execute()
        elif len(potential_matches) > 1:
            logging.critical(f"AMBIGUOUS PAYMENT! Found {len(potential_matches)} orders for S${amount:.2f}.")
            order_ids_to_flag = [order['id'] for order in potential_matches]
            supabase.table('orders').update({'status': 'manual_review'}).in_('id', order_ids_to_flag).execute()
            send_admin_alert(amount, from_name, potential_matches)
        else:
            logging.warning(f"No matching 'verifying' order found for payment details.")

    except Exception as e:
        logging.error(f"Error updating order status in Supabase: {e}", exc_info=True)


if __name__ == "__main__":
    logging.info("Starting Payment Verification Bot...")
    if not all([IMAP_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD, SUPABASE_URL, SUPABASE_SERVICE_KEY, BANK_EMAIL_SENDER]):
        logging.critical("FATAL: Core environment variables are missing. Bot cannot start.")
        exit()
    while True:
        process_emails()
        time.sleep(CHECK_INTERVAL_SECONDS)
