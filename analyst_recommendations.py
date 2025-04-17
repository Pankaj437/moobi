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

def filter_analyst_recommendations(html_content, today):
    """Filter relevant fields from analyst recommendations HTML (placeholder)."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        recommendations = []
        # Placeholder: Adjust selectors based on source (e.g., Yahoo Finance)
        # This is an example and may need customization
        rows = soup.select('table tbody tr')
        for row in rows:
            cols = row.select('td')
            if len(cols) >= 5:
                date_str = cols[2].text.strip()
                try:
                    rec_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if rec_date.date() == today.date():
                        recommendations.append({
                            'symbol': cols[0].text.strip(),
                            'companyName': cols[1].text.strip(),
                            'analyst': cols[3].text.strip(),
                            'recommendation': cols[4].text.strip(),
                            'targetPrice': cols[5].text.strip(),
                            'date': date_str
                        })
                except ValueError:
                    continue
        logger.info(f"Filtered {len(recommendations)} analyst recommendation entries.")
        return recommendations
    except Exception as e:
        logger.error(f"Failed to filter analyst recommendations: {e}")
        return []

def save_text_summary(data, today, filename):
    """Save filtered analyst recommendations as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Analyst Recommendations Summary ({today.strftime('%d-%m-%Y')})\n")
            f.write("=" * 60 + "\n\n")
            for item in data:
                f.write(f"Symbol: {item['symbol']}\n")
                f.write(f"Company: {item['companyName']}\n")
                f.write(f"Analyst: {item['analyst']}\n")
                f.write(f"Recommendation: {item['recommendation']}\n")
                f.write(f"Target Price: {item['targetPrice']}\n")
                f.write(f"Date: {item['date']}\n")
                f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_analyst_recommendations():
    today = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    summary_filename = f"analyst_recommendations_{today.strftime('%d-%m-%Y')}_summary.txt"

    logger.info(f"Starting analyst recommendations download for {today.strftime('%d-%m-%Y')}")

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
            # Placeholder: Use a real source like Yahoo Finance or a news aggregator
            await page.goto("https://finance.yahoo.com/quote/RELIANCE.NS/analysis", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            logger.info("Analyst recommendations page loaded.")
            html_content = await page.content()
        except PlaywrightTimeoutError:
            logger.error("Analyst recommendations page load timeout.")
            await browser.close()
            return None, None
        except Exception as e:
            logger.error(f"Error fetching analyst recommendations page: {e}")
            await browser.close()
            return None, None

        filtered_data = filter_analyst_recommendations(html_content, today)
        if filtered_data:
            save_text_summary(filtered_data, today, summary_filename)

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return filtered_data, summary_filename

def send_email(summary_filename, date_str):
    """Send email with the analyst recommendations text summary attached."""
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Analyst Recommendations Data - {date_str}"

    body = f"""Dear Recipient,

Attached is the analyst recommendations summary for {date_str} (text format).
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
    filtered_data, summary_filename = await fetch_analyst_recommendations()
    if filtered_data and summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
