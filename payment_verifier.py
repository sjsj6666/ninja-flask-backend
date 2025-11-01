# payment_verifier.py

import os
import email
import imaplib
import time
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Email Credentials from .env file
IMAP_SERVER = os.environ.get("IMAP_SERVER") # e.g., "imap.gmail.com"
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") # Your 16-digit App Password

# Supabase Credentials from .env file
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

# Bank Email Details
BANK_EMAIL_SENDER = "notifications@maribank.com" # IMPORTANT: Change this to the exact sender email from your bank
CHECK_INTERVAL_SECONDS = 15 # Check for new emails every 15 seconds

# --- Initialization ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logging.info("Successfully connected to Supabase.")
except Exception as e:
    logging.critical(f"FATAL: Could not connect to Supabase. {e}")
    exit()

def parse_payment_email(email_body):
    try:
        # --- IMPORTANT: This part MUST be customized for your bank's email format ---
        # Example for a DBS email that looks like: "You have received S$5.45 from someone with reference 65319336."
        
        amount_match = re.search(r"S\$([\d,]+\.\d{2})", email_body)
        reference_match = re.search(r"reference (\d+)", email_body)

        if amount_match and reference_match:
            amount = float(amount_match.group(1).replace(',', ''))
            reference_id = reference_match.group(1)
            logging.info(f"Parsed email: Amount=${amount}, Reference={reference_id}")
            return {"amount": amount, "reference_id": reference_id}
            
    except Exception as e:
        logging.error(f"Error parsing email body: {e}")

    return None

def process_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")
        
        # Search for unread emails from the specific bank sender
        status, messages = mail.search(None, f'(UNSEEN FROM "{BANK_EMAIL_SENDER}")')

        if status == "OK":
            message_ids = messages[0].split()
            if not message_ids:
                logging.info("No new payment emails found.")
                return

            for msg_id in message_ids:
                logging.info(f"Processing new email with ID: {msg_id.decode()}")
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()

                        payment_details = parse_payment_email(body)
                        if payment_details:
                            update_order_status(payment_details)

        mail.logout()
    except Exception as e:
        logging.error(f"An error occurred while processing emails: {e}")

def update_order_status(details):
    amount = details["amount"]
    reference_id = details["reference_id"]

    try:
        # Find the matching order in Supabase
        # We match on amount AND the last 8 digits of the UUID converted to a number
        response = supabase.table('orders').select('id, total_amount').eq('status', 'verifying').execute()
        
        matching_order = None
        for order in response.data:
            # Recreate the numeric reference ID from the order's UUID
            order_numeric_ref = str(int(order['id'].replace('-', '')[:15], 16))[-8:]
            
            # Check if amount and reference match
            if order_numeric_ref == reference_id and abs(order['total_amount'] - amount) < 0.01:
                matching_order = order
                break

        if matching_order:
            order_id = matching_order['id']
            logging.info(f"MATCH FOUND! Updating order {order_id} to 'completed'.")
            supabase.table('orders').update({'status': 'completed'}).eq('id', order_id).execute()
        else:
            logging.warning(f"No matching 'verifying' order found for Amount: {amount}, Reference: {reference_id}")

    except Exception as e:
        logging.error(f"Error updating order status in Supabase: {e}")

if __name__ == "__main__":
    logging.info("Starting Payment Verification Bot...")
    while True:
        process_emails()
        time.sleep(CHECK_INTERVAL_SECONDS)
