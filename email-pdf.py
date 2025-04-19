import smtplib
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging
from pathlib import Path

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
date_str = today.strftime("%Y-%m-%d")  # e.g., 2025-04-17

# Create the email
msg = MIMEMultipart()
msg['From'] = EMAIL_USER
msg['To'] = EMAIL_TO
msg['Subject'] = f"IPO Issue, Press Release, and Gemini Reports - {date_str}"

# Add email body
body = f"""Dear Recipient,

Attached are the data files for {date_str}:
- IPO screenshot (if available)
- Press release summary and data
- All Gemini-generated FSI article summaries in PDF

Please review the attachments for details.

Best regards,
Automated Data Service
"""
msg.attach(MIMEText(body, 'plain'))

# Files to attach
png_file = "ipo_data_screenshot.png"
to_date = today.strftime("%d-%m-%Y")
json_file = f"press_release_{to_date}_simplified.json"
summary_file = f"press_release_{to_date}_summary.txt"

# Collect predefined files if they exist
files_to_attach = []
for file_path in [png_file, json_file, summary_file]:
    if os.path.exists(file_path):
        files_to_attach.append(file_path)
        logger.info(f"{file_path} found and will be attached.")
    else:
        logger.warning(f"{file_path} not found.")

# Collect all PDF files in the current directory
pdf_files = list(Path('.').glob("*.pdf"))
for pdf_path in pdf_files:
    files_to_attach.append(str(pdf_path))
    logger.info(f"PDF file {pdf_path} will be attached.")

# Attach all files
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

# Send the email
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
    logger.info(f"✅ Email sent successfully with {len(files_to_attach)} attachment(s).")
except Exception as e:
    logger.error(f"❌ Email sending failed: {e}")
