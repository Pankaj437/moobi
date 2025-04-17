import smtplib
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get environment variables
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

# Validate environment variables
if not EMAIL_USER or not EMAIL_PASS:
    logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
    exit(1)

# Calculate today's date for file names
today = datetime.today()
to_date = today.strftime("%d-%m-%Y")  # e.g., 17-04-2025
date_str = today.strftime("%Y-%m-%d")  # e.g., 2025-04-17

# Create the email
msg = MIMEMultipart()
msg['From'] = EMAIL_USER
msg['To'] = EMAIL_TO
msg['Subject'] = f"IPO Issue and Press Release Data - {date_str}"

# Add email body
body = f"""Dear Recipient,

Attached are the IPO and press release data files for {date_str}:
- IPO screenshot (if available)
- Press release summary (text format)
- Press release data (simplified JSON format)

Please review the attachments for details.

Best regards,
Automated Data Service
"""
msg.attach(MIMEText(body, 'plain'))

# Files to attach
png_file = "ipo_data_screenshot.png"
json_file = f"press_release_{to_date}_simplified.json"
summary_file = f"press_release_{to_date}_summary.txt"
files_to_attach = []

# Check and add PNG file
if os.path.exists(png_file):
    files_to_attach.append(png_file)
    logger.info(f"PNG file {png_file} found and will be attached.")
else:
    logger.warning(f"PNG file {png_file} not found.")

# Check and add simplified JSON file
if os.path.exists(json_file):
    files_to_attach.append(json_file)
    logger.info(f"JSON file {json_file} found and will be attached.")
else:
    logger.warning(f"JSON file {json_file} not found.")

# Check and add text summary file
if os.path.exists(summary_file):
    files_to_attach.append(summary_file)
    logger.info(f"Text summary file {summary_file} found and will be attached.")
else:
    logger.warning(f"Text summary file {summary_file} not found.")

# Attach files
for file_path in files_to_attach:
    try:
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
        msg.attach(part)
        logger.info(f"Successfully attached {file_path}")
    except Exception as e:
        logger.error(f"Failed to attach {file_path}: {e}")

# Send the email (even if no files are attached)
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
    if files_to_attach:
        logger.info(f"Email sent successfully with attachments: {files_to_attach}")
    else:
        logger.warning("Email sent successfully without attachments.")
except Exception as e:
    logger.error(f"Email sending failed: {e}")
