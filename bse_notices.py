import asyncio
import smtplib
import os
import logging
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def filter_bse_notices(html_content, today):
    """Filter relevant fields from BSE notices HTML."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        notices = []
        # Example: Adjust selectors based on BSE website structure
        notice_rows = soup.select('table#tblBseData tr')
        for row in notice_rows[1:]:  # Skip header
            cols = row.select('td')
            if len(cols) >= 4:
                date_str = cols[1].text.strip()
                try:
                    notice_date = datetime.strptime(date_str, '%d/%m/%Y')
                    if notice_date.date() == today.date():
                        notices.append({
                            'company': cols[0].text.strip(),
                            'noticeType': cols[2].text.strip(),
                            'date': date_str,
                            'description': cols[3].text.strip(),
                            'link': cols[3].find('a')['href'] if cols[3].find('a') else ''
                        })
                except ValueError:
                    continue
        logger.info(f"Filtered {len(notices)} BSE notice entries.")
        return notices
    except Exception as e:
        logger.error(f"Failed to filter BSE notices: {e}")
        return []

def save_text_summary(data, today, filename):
    """Save filtered BSE notices as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"BSE Notices Summary ({today.strftime('%d-%m-%Y')})\n")
            f.write("=" * 60 + "\n\n")
            for item in data:
                f.write(f"Company: {item['company']}\n")
                f.write(f"Notice Type: {item['noticeType']}\n")
                f.write(f"Date: {item['date']}\n")
                f.write(f"Description: {item['description']}\n")
                f.write(f"Link: {item['link']}\n")
                f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_bse_notices():
    today = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    summary_filename = f"bse_notices_{today.strftime('%d-%m-%Y')}_summary.txt"

    logger.info(f"Starting BSE notices download for {today.strftime('%d-%m-%Y')}")

    async with async_playwright() as p:
        try:
            browser = await p.firefox.launch(headless=True)
            logger.info("Browser launched successfully.")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return None, None

        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                java_script_enabled=True
            )
            page = await context.new_page()
            logger.info("Browser context and page created.")
        except Exception as e:
            logger.error(f"Failed to create browser context: {e}")
            await browser.close()
            return None, None

        try:
            await page.goto("https://www.bseindia.com/markets/MarketInfo/NoticesCirculars.aspx", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            logger.info("BSE notices page loaded.")
            html_content = await page.content()
        except PlaywrightTimeoutError:
            logger.error("BSE notices page load timeout.")
            await browser.close()
            return None, None
        except Exception as e:
            logger.error(f"Error fetching BSE notices page: {e}")
            await browser.close()
            return None, None

        filtered_data = filter_bse_notices(html_content, today)
        if filtered_data:
            save_text_summary(filtered_data, today, summary_filename)

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return filtered_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the BSE notices text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"BSE Notices Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the BSE notices summary for {date_str} (text format).
Please review the attachment for details.

Best regards,
Automated Data Service
"""
    msg.attach(MIMEText(body, 'plain'))
    logger.info(f"Email body: {body}")

    files_to_attach = []
    if os.path.exists(summary_filename):
        files_to_attach.append(summary_filename)
        logger.info(f"Text summary file {summary_filename} found and will be attached.")
    else:
        logger.warning(f"Text summary file {summary_filename} not found.")

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

async def main():
    filtered_data, summary_filename = await fetch_bse_notices()
    if filtered_data and summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
