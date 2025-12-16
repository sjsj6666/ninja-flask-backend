# email_service.py

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
from flask import render_template_string
import datetime

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587
# These come from your Environment Variables
SMTP_LOGIN = os.environ.get('BREVO_SMTP_LOGIN') 
SMTP_PASSWORD = os.environ.get('BREVO_SMTP_PASSWORD')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'GameVault <noreply@gameuniverse.co>')

# --- HTML TEMPLATES (Same as before) ---
TEMPLATE_STYLES = """
    body { font-family: sans-serif; color: #333; line-height: 1.6; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px; }
    .header { background-color: #f8fafc; padding: 15px; text-align: center; border-radius: 8px 8px 0 0; }
    .header h2 { margin: 0; color: #2563eb; }
    .details { background-color: #fff; padding: 20px; }
    .status-badge { display: inline-block; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; }
    .status-completed { background-color: #d1fae5; color: #065f46; }
    .status-processing { background-color: #dbeafe; color: #1e40af; }
    .status-failed { background-color: #fee2e2; color: #991b1b; }
    .footer { font-size: 12px; text-align: center; color: #888; margin-top: 20px; }
"""

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        {{ styles }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>GameVault Order Update</h2>
        </div>
        <div class="details">
            <p>Hi <strong>{{ customer_name }}</strong>,</p>
            <p>Your order status has been updated.</p>
            
            <div style="text-align: center; margin: 20px 0;">
                <span class="status-badge status-{{ status }}">
                    {{ status_display }}
                </span>
            </div>

            <table width="100%" style="border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Order ID:</strong></td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-family: monospace;">{{ order_id }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Game:</strong></td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right;">{{ game_name }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Product:</strong></td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right;">{{ product_name }}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Total:</strong></td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right;">S${{ amount }}</td>
                </tr>
            </table>

            {% if message %}
            <div style="margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #ccc;">
                {{ message }}
            </div>
            {% endif %}

            <p style="margin-top: 30px;">Thank you for shopping with us!</p>
        </div>
        <div class="footer">
            &copy; {{ year }} GameVault. All rights reserved.
        </div>
    </div>
</body>
</html>
"""

def _send_async(to_email, subject, html_content):
    """Internal function to run in a thread"""
    try:
        if not to_email or '@' not in to_email:
            logger.warning(f"Skipping email: Invalid address {to_email}")
            return

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        # Connect to Brevo SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SMTP_LOGIN, SMTP_PASSWORD)
        
        # Send
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Brevo email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email via Brevo to {to_email}: {e}")

def send_order_update(order, product_name, game_name, customer_email, customer_name):
    """
    Main function to trigger order update emails.
    """
    status = order.get('status')
    
    # Define Subject and Message based on status
    if status == 'completed':
        subject = f"Order Delivered! - {order.get('id')[:8]}"
        status_display = "DELIVERED"
        message = "Your top-up has been successfully delivered to your account. Happy Gaming!"
    elif status == 'processing':
        subject = f"Payment Received - {order.get('id')[:8]}"
        status_display = "PROCESSING"
        message = "We have received your payment and are delivering your items now. This usually takes 1-5 minutes."
    elif status == 'manual_review':
        subject = f"Order Under Review - {order.get('id')[:8]}"
        status_display = "UNDER REVIEW"
        message = "Your order requires manual verification. Our team has been notified and will process it shortly."
    elif status == 'failed' or status == 'cancelled':
        subject = f"Order Failed - {order.get('id')[:8]}"
        status_display = "FAILED"
        message = "We could not process your order. If you were charged, a refund will be processed automatically."
    else:
        return

    # Render HTML
    html_content = render_template_string(
        EMAIL_TEMPLATE,
        styles=TEMPLATE_STYLES,
        customer_name=customer_name or "Gamer",
        status=status,
        status_display=status_display,
        order_id=order.get('id'),
        game_name=game_name,
        product_name=product_name,
        amount=f"{order.get('total_amount'):.2f}",
        message=message,
        year=datetime.datetime.now().year
    )

    # Send in background thread
    thread = Thread(target=_send_async, args=(customer_email, subject, html_content))
    thread.start()
