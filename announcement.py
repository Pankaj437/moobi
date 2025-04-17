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
    """Save announcements as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"NSE Corporate Announcements ({from_date} to {to_date})\n")
            f.write("=" * 60 + "\n\n")
            if not data:
                f.write("No announcements found for the specified date range.\n")
            else:
                for item in data:
                    f.write(f"Symbol: {item['symbol']}\n")
                    f.write(f"Company: {item['sm_name']}\n")
                    f.write(f"ISIN: {item['sm_isin']}\n")
                    f.write(f"Description: {item['desc']}\n")
                    f.write(f"Announcement Date: {item['an_dt']}\n")
                    f.write(f"Industry: {item['smIndustry']}\n")
                    f.write(f"Details: {item['attchmntText']}\n")
                    f.write(f"Attachment: {item['attchmntFile']}\n")
                    f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_nse_announcements():
    # Set date range (previous day to current day)
    today = datetime.today()
    to_date = today.strftime("%d-%m-%Y")
    from_date = today.strftime("%d-%m-%Y")
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"nse_announcements_{to_date}.json"
    summary_filename = f"nse_announcements_{to_date}_summary.txt"

    logger.info(f"Fetching NSE announcements for {from_date} to {to_date}")

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
                    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
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
        api_url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_date}&to_date={to_date}"
        logger.info(f"Fetching announcements from: {api_url}")

        announcements_data = []
        for attempt in range(3):
            try:
                # Navigate to NSE announcements page to set cookies
                await page.goto("https://www.nseindia.com", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("NSE announcements page loaded")

                # Make API request
                response = await page.evaluate("""
                    async (url) => {
                        const res = await fetch(url, {
                            method: 'GET',
                            headers: {
                                'Accept': 'application/json',
                                'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-announcements'
                            }
                        });
                        return await res.json();
                    }
                """, api_url)
                announcements_data = response
                logger.info(f"Attempt {attempt + 1}: Fetched {len(announcements_data)} announcements")
                break
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: Page load or API request timed out")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching announcements: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if announcements_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(announcements_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Announcements JSON saved as {output_filename}")
                save_text_summary(announcements_data, from_date, to_date, summary_filename)
            except Exception as e:
                logger.error(f"Failed to save JSON or summary: {e}")
        else:
            logger.warning("No announcements data fetched")
            save_text_summary([], from_date, to_date, summary_filename)
            try:
                with open(f"nse_announcements_raw_{to_date}.html", 'w', encoding='utf-8') as f:
                    f.write(await page.content())
                logger.info(f"Saved raw HTML as nse_announcements_raw_{to_date}.html for debugging")
            except Exception as e:
                logger.error(f"Failed to save raw HTML: {e}")

        try:
            await browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return announcements_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the NSE announcements text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"NSE Announcements Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the NSE corporate announcements summary for {date_str} (text format).
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
    announcements_data, summary_filename = await fetch_nse_announcements()
    if summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
