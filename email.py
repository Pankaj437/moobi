import smtplib
import os
from datetime import datetime
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

# Get today's date
date_str = datetime.utcnow().strftime("%Y-%m-%d")

# Create the email
msg = MIMEMultipart()
msg['From'] = EMAIL_USER
msg['To'] = EMAIL_TO
msg['Subject'] = f"Mobile Tracker Screenshots - {date_str}"

# Attach all PNG files from current directory
png_files = [f for f in os.listdir('.') if f.endswith('.png')]
if not png_files:
    print("❌ No PNG files found to attach.")
    exit(1)

for file_path in png_files:
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
    print("✅ Email sent successfully with attachments:", png_files)
except Exception as e:
    print(f"❌ Email sending failed: {e}")
