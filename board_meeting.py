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

def filter_board_meetings(data):
    """Filter relevant fields from board meetings data."""
    try:
        filtered = []
        for item in data:
            # Extract fields based on provided JSON format
            entry = {
                'symbol': item.get('bm_symbol', ''),
                'companyName': item.get('sm_name', ''),
                'purpose': item.get('bm_purpose', ''),
                'boardMeetingDate': item.get('bm_date', ''),
                'description': item.get('bm_desc', ''),
                'industry': item.get('sm_indusrty', ''),  # Optional field for summary
                'isin': item.get('sm_isin', ''),         # Optional field for summary
                'attachment': item.get('attachment', '')  # Optional field for summary
            }
            # Skip entries with no symbol or company name
            if not entry['symbol'] or not entry['companyName']:
                logger.warning(f"Skipping invalid entry (missing symbol or company): {item}")
                continue
            filtered.append(entry)
        logger.info(f"Filtered {len(filtered)} valid board meeting entries (out of {len(data)} total).")
        return filtered
    except Exception as e:
        logger.error(f"Failed to filter board meetings data: {e}")
        return []

def save_text_summary(data, from_date, to_date, filename):
    """Save filtered board meetings data as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"NSE Board Meetings Summary ({from_date} to {to_date})\n")
            f.write("=" * 60 + "\n\n")
            if not data:
                f.write("No valid board meetings found for the specified date range.\n")
            else:
                for item in data:
                    f.write(f"Symbol: {item['symbol']}\n")
                    f.write(f"Company: {item['companyName']}\n")
                    f.write(f"ISIN: {item['isin']}\n")
                    f.write(f"Industry: {item['industry']}\n")
                    f.write(f"Purpose: {item['purpose']}\n")
                    f.write(f"Date: {item['boardMeetingDate']}\n")
                    f.write(f"Description: {item['description']}\n")
                    f.write(f"Attachment: {item['attachment']}\n")
                    f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_board_meetings():
    today = datetime.today()
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"board_meetings_{to_date}.json"
    summary_filename = f"board_meetings_{to_date}_summary.txt"
    raw_filename = f"board_meetings_raw_{to_date}.json"

    logger.info(f"Fetching NSE board meetings for {from_date} to {to_date}")

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
                    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-board-meetings",
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

        # Navigate to board meetings page to set cookies
        try:
            await page.goto("https://www.nseindia.com/companies-listing/corporate-filings-board-meetings", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("NSE board meetings page loaded, cookies set")
        except PlaywrightTimeoutError:
            logger.warning("Board meetings page load timeout—continuing anyway")

        api_url = f"https://www.nseindia.com/api/corporate-board-meetings?index=equities&from_date={from_date}&to_date={to_date}"
        logger.info(f"Fetching board meetings from: {api_url}")

        json_data = None
        for attempt in range(3):
            try:
                response = await page.evaluate("""
                    async (url) => {
                        const res = await fetch(url, {
                            method: 'GET',
                            headers: {
                                'Accept': 'application/json',
                                'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-board-meetings'
                            }
                        });
                        return await res.json();
                    }
                """, api_url)
                json_data = response
                logger.info(f"Attempt {attempt + 1}: Successfully fetched JSON data with {len(json_data)} entries")
                break
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: API request timed out")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching board meetings: {e}")
                try:
                    with open(f"board_meetings_raw_response_attempt_{attempt + 1}_{to_date}.html", 'w', encoding='utf-8') as f:
                        f.write(await page.content())
                    logger.info(f"Saved raw page HTML as board_meetings_raw_response_attempt_{attempt + 1}_{to_date}.html")
                except:
                    pass
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        filtered_data = []
        if json_data:
            try:
                # Save raw JSON for debugging
                with open(raw_filename, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Raw board meetings JSON saved as {raw_filename}")

                # Filter and save data
                filtered_data = filter_board_meetings(json_data)
                if filtered_data:
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(filtered_data, f, indent=4, ensure_ascii=False)
                    logger.info(f"Filtered board meetings JSON saved as {output_filename}")
                    save_text_summary(filtered_data, from_date, to_date, summary_filename)
                else:
                    logger.warning("No valid board meetings after filtering")
                    save_text_summary([], from_date, to_date, summary_filename)
            except Exception as e:
                logger.error(f"Failed to save JSON or summary: {e}")
        else:
            logger.warning("No board meetings data fetched")
            save_text_summary([], from_date, to_date, summary_filename)

        try:
            await browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return filtered_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the board meetings text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"NSE Board Meetings Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the NSE board meetings summary for {date_str} (text format).
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
    filtered_data, summary_filename = await fetch_board_meetings()
    if summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
