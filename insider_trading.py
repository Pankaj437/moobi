import asyncio
import json
import smtplib
import os
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def filter_insider_trading(data):
    """Filter relevant fields from insider trading data."""
    try:
        filtered = []
        for item in data.get('data', []):
            filtered.append({
                'symbol': item.get('symbol', ''),
                'company': item.get('company', ''),
                'acquirerName': item.get('acqName', ''),
                'personCategory': item.get('personCategory', ''),
                'transactionType': item.get('tdpTransactionType', ''),
                'securityType': item.get('secType', ''),
                'securityAcquired': item.get('secAcq', ''),
                'securityValue': item.get('secVal', ''),
                'preSharesNo': item.get('befAcqSharesNo', ''),
                'preSharesPer': item.get('befAcqSharesPer', ''),
                'postSharesNo': item.get('afterAcqSharesNo', ''),
                'postSharesPer': item.get('afterAcqSharesPer', ''),
                'acquisitionMode': item.get('acqMode', ''),
                'exchange': item.get('exchange', ''),
                'date': item.get('date', '')
            })
        logger.info(f"Filtered {len(filtered)} insider trading entries.")
        return filtered
    except Exception as e:
        logger.error(f"Failed to filter insider trading data: {e}")
        return []

def save_text_summary(data, from_date, to_date, filename):
    """Save filtered insider trading data as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Insider Trading Summary ({from_date} to {to_date})\n")
            f.write("=" * 60 + "\n\n")
            for item in data:
                f.write(f"Symbol: {item['symbol']}\n")
                f.write(f"Company: {item['company']}\n")
                f.write(f"Acquirer Name: {item['acquirerName']}\n")
                f.write(f"Person Category: {item['personCategory']}\n")
                f.write(f"Transaction Type: {item['transactionType']}\n")
                f.write(f"Security Type: {item['securityType']}\n")
                f.write(f"Securities Acquired: {item['securityAcquired']}\n")
                f.write(f"Security Value: Rs. {item['securityValue']}\n")
                f.write(f"Pre-Transaction Shares: {item['preSharesNo']} ({item['preSharesPer']}%)\n")
                f.write(f"Post-Transaction Shares: {item['postSharesNo']} ({item['postSharesPer']}%)\n")
                f.write(f"Acquisition Mode: {item['acquisitionMode']}\n")
                f.write(f"Exchange: {item['exchange']}\n")
                f.write(f"Date: {item['date']}\n")
                f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_insider_trading():
    today = datetime.today()
    from_date = today.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"insider_trading_{to_date}.json"
    summary_filename = f"insider_trading_{to_date}_summary.txt"

    logger.info(f"Starting insider trading download for {from_date} to {to_date}")

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
                extra_http_headers={
                    "Accept": "application/json",
                    "Referer": "https://www.nseindia.com/"
                },
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
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("NSE homepage loaded, cookies set.")
        except PlaywrightTimeoutError:
            logger.warning("Homepage load timeout—continuing anyway...")

        api_url = f"https://www.nseindia.com/api/corporates-pit?index=equities&from_date={from_date}&to_date={to_date}"
        logger.info(f"Fetching insider trading data from: {api_url}")

        json_data = None
        for attempt in range(3):
            try:
                response = await page.goto(api_url, timeout=90000)
                if response and response.ok:
                    try:
                        json_data = await response.json()
                        logger.info(f"Attempt {attempt + 1}: Successfully fetched JSON data with {len(json_data.get('data', []))} entries.")
                        break
                    except ValueError:
                        logger.error(f"Attempt {attempt + 1}: Failed to parse JSON response.")
                        with open(f"insider_trading_raw_response_attempt_{attempt + 1}.txt", "w", encoding='utf-8') as f:
                            f.write(await response.text())
                        logger.info(f"Saved raw response as insider_trading_raw_response_attempt_{attempt + 1}.txt")
                else:
                    logger.error(f"Attempt {attempt + 1}: API request failed with status: {response.status if response else 'No response'}")
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: API request timed out.")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching insider trading data: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if json_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Original insider trading JSON saved as {output_filename}")
            except Exception as e:
                logger.error(f"Failed to save original JSON: {e}")

            filtered_data = filter_insider_trading(json_data)
            if filtered_data:
                save_text_summary(filtered_data, from_date, to_date, summary_filename)

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return filtered_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the insider trading text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Insider Trading Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the insider trading summary for {date_str} (text format).
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
    filtered_data, summary_filename = await fetch_insider_trading()
    if filtered_data and summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
