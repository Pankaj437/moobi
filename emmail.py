import smtplib
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Get environment variables
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

# Validate environment variables
if not EMAIL_USER or not EMAIL_PASS:
    print("❌ EMAIL_USER or EMAIL_PASS is not set in environment variables.")
    exit(1)

# Calculate today's date and one day ago for the JSON file name
today = datetime.today()
one_day_ago = today - timedelta(days=1)
to_date = today.strftime("%d-%m-%Y")
date_str = today.strftime("%Y-%m-%d")

# Create the email
msg = MIMEMultipart()
msg['From'] = EMAIL_USER
msg['To'] = EMAIL_TO
msg['Subject'] = f"IPO Issue and Press Release Data - {date_str}"

# Files to attach
png_file = "ipo_data_screenshot.png"
json_file = f"press_release_{to_date}.json"
files_to_attach = []

# Check and add PNG file
if os.path.exists(png_file):
    files_to_attach.append(png_file)
else:
    print(f"❌ PNG file {png_file} not found.")

# Check and add JSON file
if os.path.exists(json_file):
    files_to_attach.append(json_file)
else:
    print(f"❌ JSON file {json_file} not found.")

# If no files to attach, exit
if not files_to_attach:
    print("❌ No files found to attach.")
    exit(1)

# Attach files (PNG and JSON)
for file_path in files_to_attach:
    try:
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
        msg.attach(part)
    except Exception as e:
        print(f"⚠️ Failed to attach {file_path}: {e}")

# Send the email
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
    print("✅ Email sent successfully with attachments:", files_to_attach)
except Exception as e:
    print(f"❌ Email sending failed: {e}")
