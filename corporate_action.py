import asyncio
import json
import smtplib
import os
import logging
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def save_text_summary(data, from_date, to_date, filename):
    """Save corporate actions as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"NSE Corporate Actions ({from_date} to {to_date})\n")
            f.write("=" * 60 + "\n\n")
            if not data:
                f.write("No corporate actions found for the specified date range.\n")
            else:
                for item in data:
                    f.write(f"Symbol: {item['symbol']}\n")
                    f.write(f"Company: {item['comp']}\n")
                    f.write(f"ISIN: {item['isin']}\n")
                    f.write(f"Subject: {item['subject']}\n")
                    f.write(f"Ex-Date: {item['exDate']}\n")
                    f.write(f"Record Date: {item['recDate']}\n")
                    f.write(f"Face Value: {item['faceVal']}\n")
                    f.write(f"Series: {item['series']}\n")
                    f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_nse_corporate_actions():
    # Set date range (past week to current day)
    today = datetime.today()
    to_date = today.strftime("%d-%m-%Y")
    from_date = today.strftime("%d-%m-%Y")  # Matches 11-04-2025 to 18-04-2025
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"nse_corporate_actions_{to_date}.json"
    summary_filename = f"nse_corporate_actions_{to_date}_summary.txt"

    logger.info(f"Fetching NSE corporate actions for {from_date} to {to_date}")

    async with async_playwright() as p:
        try:
            browser = await p.firefox.launch(headless=True)
            logger.info("Browser launched successfully")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return None, None

        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-corporate-action",
                    "Accept-Language": "en-US,en;q=0.9"
                },
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            logger.info("Browser context and page created")
        except Exception as e:
            logger.error(f"Failed to create browser context: {e}")
            await browser.close()
            return None, None

        # API URL
        api_url = f"https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date={from_date}&to_date={to_date}"
        logger.info(f"Fetching corporate actions from: {api_url}")

        corporate_actions_data = []
        for attempt in range(3):
            try:
                # Navigate to NSE corporate actions page to set cookies
                await page.goto("https://www.nseindia.com/companies-listing/corporate-filings-corporate-action", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("NSE corporate actions page loaded")

                # Make API request
                response = await page.evaluate("""
                    async (url) => {
                        const res = await fetch(url, {
                            method: 'GET',
                            headers: {
                                'Accept': 'application/json',
                                'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-corporate-action'
                            }
                        });
                        return await res.json();
                    }
                """, api_url)
                corporate_actions_data = response
                logger.info(f"Attempt {attempt + 1}: Fetched {len(corporate_actions_data)} corporate actions")
                break
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: Page load or API request timed out")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching corporate actions: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if corporate_actions_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(corporate_actions_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Corporate actions JSON saved as {output_filename}")
                save_text_summary(corporate_actions_data, from_date, to_date, summary_filename)
            except Exception as e:
                logger.error(f"Failed to save JSON or summary: {e}")
        else:
            logger.warning("No corporate actions data fetched")
            save_text_summary([], from_date, to_date, summary_filename)
            try:
                with open(f"nse_corporate_actions_raw_{to_date}.html", 'w', encoding='utf-8') as f:
                    f.write(await page.content())
                logger.info(f"Saved raw HTML as nse_corporate_actions_raw_{to_date}.html for debugging")
            except Exception as e:
                logger.error(f"Failed to save raw HTML: {e}")

        try:
            await browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return corporate_actions_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the NSE corporate actions text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"NSE Corporate Actions Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the NSE corporate actions summary for {date_str} (text format).
Please review the attachment for details.

Best regards,
Automated Data Service
"""
    msg.attach(MIMEText(body, 'plain'))
    logger.info(f"Email body prepared")

    if os.path.exists(summary_filename):
        try:
            with open(summary_filename, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(summary_filename)}"')
            msg.attach(part)
            logger.info(f"Attached {summary_filename}")
        except Exception as e:
            logger.error(f"Failed to attach {summary_filename}: {e}")
    else:
        logger.warning(f"Summary file {summary_filename} not found")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Email sending failed: {e}")

async def main():
    corporate_actions_data, summary_filename = await fetch_nse_corporate_actions()
    if summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
