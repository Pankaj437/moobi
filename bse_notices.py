import asyncio
import json
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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_notices(html_content):
    logger.debug("Parsing HTML content")
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'ContentPlaceHolder1_GridView2'})
        if not table:
            logger.error("Notices table not found. Saving HTML for inspection.")
            return []
        notices = []
        rows = table.find_all('tr')[1:]
        for row in rows:
            if 'pgr' in row.get('class', []):
                continue
            cols = row.find_all('td')
            if len(cols) >= 6:
                notices.append({
                    'noticeNo': cols[0].text.strip(),
                    'subject': cols[1].find('a').text.strip() if cols[1].find('a') else '',
                    'subjectUrl': f"https://www.bseindia.com{cols[1].find('a')['href']}" if cols[1].find('a') else '',
                    'segment': cols[2].text.strip(),
                    'category': cols[3].text.strip(),
                    'department': cols[4].text.strip(),
                    'pdfId': cols[5].find('input', {'type': 'image'})['id'] if cols[5].find('input', {'type': 'image'}) else ''
                })
        logger.info(f"Parsed {len(notices)} notices")
        return notices
    except Exception as e:
        logger.error(f"Parsing failed: {e}")
        return []

def save_text_summary(data, from_date, to_date, filename):
    logger.debug(f"Saving text summary to {filename}")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            if not data:
                f.write(f"No BSE notices found for {from_date} to {to_date}\n")
            else:
                f.write(f"BSE Notices Summary ({from_date} to {to_date})\n" + "=" * 60 + "\n\n")
                for item in data:
                    f.write(f"Notice No: {item['noticeNo']}\nSubject: {item['subject']}\nSubject URL: {item['subjectUrl']}\nSegment: {item['segment']}\nCategory: {item['category']}\nDepartment: {item['department']}\nPDF ID: {item['pdfId']}\n" + "=" * 60 + "\n\n")
        logger.info(f"Text summary saved")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_bse_notices():
    today = datetime.today()
    # Check for holidays
    holidays = ["18-04-2025", "14-04-2025", "10-04-2025"]
    if today.strftime("%d-%m-%Y") in holidays:
        today -= timedelta(days=1)
    from_date = today.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"bse_notices_{to_date}.json"
    summary_filename = f"bse_notices_{to_date}_summary.txt"

    logger.info(f"Fetching notices for {from_date} to {to_date}")

    async with async_playwright() as p:
        try:
            browser = await p.firefox.launch(headless=True)
            logger.info("Browser launched")
        except Exception as e:
            logger.error(f"Browser launch failed: {e}")
            return None, None

        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            logger.info("Browser context created")
        except Exception as e:
            logger.error(f"Context creation failed: {e}")
            await browser.close()
            return None, None

        url = "https://www.bseindia.com/markets/MarketInfo/NoticesCirculars.aspx?id=2"
        for attempt in range(3):
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)
                logger.info("Page loaded")
                # Handle cookies
                try:
                    await page.click('button[id*="accept-cookies"]', timeout=5000)
                    logger.info("Cookies accepted")
                except:
                    logger.info("No cookie popup")
                # Fill form
                await page.fill("#ContentPlaceHolder1_txtDate", from_date)
                await page.fill("#ContentPlaceHolder1_txtTodate", to_date)
                await page.select_option("#ContentPlaceHolder1_ddlSegment", "All")
                await page.select_option("#ContentPlaceHolder1_ddlCategory", "All")
                await page.select_option("#ContentPlaceHolder1_ddlDep", "All")
                logger.info("Form filled")
                await page.evaluate('document.getElementById("ContentPlaceHolder1_btnSubmit").click()')
                await page.wait_for_load_state("networkidle", timeout=60000)
                logger.info("Form submitted")
                await page.screenshot(path=f"bse_notices_screenshot_{to_date}.png")
                html_content = await page.content()
                notices_data = parse_notices(html_content)
                if notices_data or not notices_data:
                    break
            except PlaywrightTimeoutError as e:
                logger.error(f"Attempt {attempt + 1}: Timeout - {e}")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error - {e}")
            await asyncio.sleep(5)

        if not notices_data:
            logger.warning("No notices parsed")
            with open(f"bse_notices_raw_{to_date}.html", 'w', encoding='utf-8') as f:
                f.write(html_content)
            save_text_summary([], from_date, to_date, summary_filename)
        else:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(notices_data, f, indent=4)
            save_text_summary(notices_data, from_date, to_date, summary_filename)

        await browser.close()
        return notices_data, summary_filename

def send_email(summary_filename, date_str):
    logger.debug("Sending email")
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

    if not os.path.exists(summary_filename):
        logger.error(f"Summary file {summary_filename} missing")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"BSE Notices Data - {date_str}"
    body = f"BSE notices summary for {date_str} attached."
    msg.attach(MIMEText(body, 'plain'))

    try:
        with open(summary_filename, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(summary_filename)}"')
        msg.attach(part)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info("Email sent")
    except Exception as e:
        logger.error(f"Email failed: {e}")

async def main():
    notices_data, summary_filename = await fetch_bse_notices()
    if summary_filename:
        send_email(summary_filename, datetime.today().strftime("%Y-%m-%d"))

if __name__ == "__main__":
    asyncio.run(main())
