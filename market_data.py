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

def filter_market_data(index_data, turnover_data):
    """Filter relevant fields from index and turnover data."""
    try:
        filtered = {
            'index': [],
            'turnover': []
        }
        # Filter index data (NIFTY 50)
        for item in index_data.get('data', []):
            filtered['index'].append({
                'indexName': item.get('index', ''),
                'date': item.get('timestamp', ''),
                'open': item.get('open', ''),
                'close': item.get('close', ''),
                'high': item.get('high', ''),
                'low': item.get('low', ''),
                'volume': item.get('volume', '')
            })
        # Filter turnover data
        for item in turnover_data.get('data', []):
            filtered['turnover'].append({
                'segment': item.get('segment', ''),
                'turnover': item.get('turnover', ''),
                'date': item.get('date', '')
            })
        logger.info(f"Filtered {len(filtered['index'])} index entries and {len(filtered['turnover'])} turnover entries.")
        return filtered
    except Exception as e:
        logger.error(f"Failed to filter market data: {e}")
        return {'index': [], 'turnover': []}

def save_text_summary(data, today, filename):
    """Save filtered market data as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Market Data Summary ({today})\n")
            f.write("=" * 60 + "\n\n")
            f.write("Index Data (NIFTY 50)\n")
            f.write("-" * 60 + "\n")
            for item in data['index']:
                f.write(f"Index: {item['indexName']}\n")
                f.write(f"Date: {item['date']}\n")
                f.write(f"Open: {item['open']}\n")
                f.write(f"Close: {item['close']}\n")
                f.write(f"High: {item['high']}\n")
                f.write(f"Low: {item['low']}\n")
                f.write(f"Volume: {item['volume']}\n")
                f.write("-" * 60 + "\n")
            f.write("\nTurnover Data\n")
            f.write("-" * 60 + "\n")
            for item in data['turnover']:
                f.write(f"Segment: {item['segment']}\n")
                f.write(f"Turnover: Rs. {item['turnover']} Cr\n")
                f.write(f"Date: {item['date']}\n")
                f.write("-" * 60 + "\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_market_data():
    today = datetime.today().strftime("%d-%m-%Y")
    date_str = datetime.today().strftime("%Y-%m-%d")
    output_filename = f"market_data_{today}.json"
    summary_filename = f"market_data_{today}_summary.txt"

    logger.info(f"Starting market data download for {today}")

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
        except Exception PipeLineError as e:
            logger.error(f"Failed to create browser context: {e}")
            await browser.close()
            return None, None

        try:
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("NSE homepage loaded, cookies set.")
        except PlaywrightTimeoutError:
            logger.warning("Homepage load timeout—continuing anyway...")

        # Fetch index data
        index_url = f"https://www.nseindia.com/api/index-history?index=NIFTY%2050&from={today}&to={today}"
        logger.info(f"Fetching index data from: {index_url}")
        index_data = None
        for attempt in range(3):
            try:
                response = await page.goto(index_url, timeout=90000)
                if response and response.ok:
                    try:
                        index_data = await response.json()
                        logger.info(f"Attempt {attempt + 1}: Successfully fetched index JSON data.")
                        break
                    except ValueError:
                        logger.error(f"Attempt {attempt + 1}: Failed to parse index JSON response.")
                        with open(f"market_index_raw_response_attempt_{attempt + 1}.txt", "w", encoding='utf-8') as f:
                            f.write(await response.text())
                        logger.info(f"Saved index raw response as market_index_raw_response_attempt_{attempt + 1}.txt")
                else:
                    logger.error(f"Attempt {attempt + 1}: Index API request failed with status: {response.status if response else 'No response'}")
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: Index API request timed out.")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching index data: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        # Fetch turnover data
        turnover_url = "https://www.nseindia.com/api/market-turnover"
        logger.info(f"Fetching turnover data from: {turnover_url}")
        turnover_data = None
        for attempt in range(3):
            try:
                response = await page.goto(turnover_url, timeout=90000)
                if response and response.ok:
                    try:
                        turnover_data = await response.json()
                        logger.info(f"Attempt {attempt + 1}: Successfully fetched turnover JSON data.")
                        break
                    except ValueError:
                        logger.error(f"Attempt {attempt + 1}: Failed to parse turnover JSON response.")
                        with open(f"market_turnover_raw_response_attempt_{attempt + 1}.txt", "w", encoding='utf-8') as f:
                            f.write(await response.text())
                        logger.info(f"Saved turnover raw response as market_turnover_raw_response_attempt_{attempt + 1}.txt")
                else:
                    logger.error(f"Attempt {attempt + 1}: Turnover API request failed with status: {response.status if response else 'No response'}")
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: Turnover API request timed out.")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching turnover data: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if index_data or turnover_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump({'index': index_data, 'turnover': turnover_data}, f, indent=4, ensure_ascii=False)
                logger.info(f"Original market data JSON saved as {output_filename}")
            except Exception as e:
                logger.error(f"Failed to save original JSON: {e}")

            filtered_data = filter_market_data(index_data or {}, turnover_data or {})
            if filtered_data['index'] or filtered_data['turnover']:
                save_text_summary(filtered_data, today, summary_filename)

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return filtered_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the market data text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Market Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the market data summary for {date_str} (text format), including NIFTY 50 index and turnover data.
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
    filtered_data, summary_filename = await fetch_market_data()
    if filtered_data and (filtered_data['index'] or filtered_data['turnover']):
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
