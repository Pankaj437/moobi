import asyncio
import json
import smtplib
import os
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_notices(html_content):
    """Parse BSE notices from HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'ContentPlaceHolder1_GridView2'})
        if not table:
            logger.error("Notices table not found in HTML.")
            return []

        notices = []
        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            if 'pgr' in row.get('class', []):  # Skip pagination row
                continue
            cols = row.find_all('td')
            if len(cols) >= 6:
                notice_no = cols[0].text.strip()
                subject_link = cols[1].find('a')
                subject = subject_link.text.strip() if subject_link else ''
                subject_url = subject_link['href'] if subject_link else ''
                if subject_url and not subject_url.startswith('http'):
                    subject_url = f"https://www.bseindia.com{subject_url}"
                segment = cols[2].text.strip()
                category = cols[3].text.strip()
                department = cols[4].text.strip()
                pdf_input = cols[5].find('input', {'type': 'image'})
                pdf_id = pdf_input['id'] if pdf_input else ''
                
                notices.append({
                    'noticeNo': notice_no,
                    'subject': subject,
                    'subjectUrl': subject_url,
                    'segment': segment,
                    'category': category,
                    'department': department,
                    'pdfId': pdf_id
                })
        logger.info(f"Parsed {len(notices)} notices.")
        return notices
    except Exception as e:
        logger.error(f"Failed to parse notices: {e}")
        return []

def save_text_summary(data, from_date, to_date, filename):
    """Save filtered notices as a human-readable text file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"BSE Notices Summary ({from_date} to {to_date})\n")
            f.write("=" * 60 + "\n\n")
            for item in data:
                f.write(f"Notice No: {item['noticeNo']}\n")
                f.write(f"Subject: {item['subject']}\n")
                f.write(f"Subject URL: {item['subjectUrl']}\n")
                f.write(f"Segment: {item['segment']}\n")
                f.write(f"Category: {item['category']}\n")
                f.write(f"Department: {item['department']}\n")
                f.write(f"PDF ID: {item['pdfId']}\n")
                f.write("=" * 60 + "\n\n")
        logger.info(f"Text summary saved as {filename}")
    except Exception as e:
        logger.error(f"Failed to save text summary: {e}")

async def fetch_bse_notices():
    today = datetime.today()
    from_date = today.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")
    date_str = today.strftime("%Y-%m-%d")
    output_filename = f"bse_notices_{to_date}.json"
    summary_filename = f"bse_notices_{to_date}_summary.txt"

    logger.info(f"Starting BSE notices download for {from_date} to {to_date}")

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
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Referer": "https://www.bseindia.com/"
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

        url = "https://www.bseindia.com/markets/MarketInfo/NoticesCirculars.aspx?id=2"
        logger.info(f"Fetching BSE notices from: {url}")

        # Set form data for single-day query
        form_data = {
            "ctl00$ContentPlaceHolder1$txtDate": from_date,
            "ctl00$ContentPlaceHolder1$txtTodate": to_date,
            "ctl00$ContentPlaceHolder1$txtNoticeNo": "",
            "ctl00$ContentPlaceHolder1$ddlSegment": "All",
            "ctl00$ContentPlaceHolder1$ddlCategory": "All",
            "ctl00$ContentPlaceHolder1$ddlDep": "All",
            "ctl00$ContentPlaceHolder1$SmartSearch$smartSearch": "",
            "ctl00$ContentPlaceHolder1$txtSub": "",
            "ctl00$ContentPlaceHolder1$txtfreeText": "",
            "ctl00$ContentPlaceHolder1$btnSubmit": "Submit"
        }

        notices_data = []
        html_content = None
        for attempt in range(3):
            try:
                # Navigate to page and wait for load
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("BSE notices page loaded.")

                # Fill and submit the form
                await page.fill("#ContentPlaceHolder1_txtDate", from_date)
                await page.fill("#ContentPlaceHolder1_txtTodate", to_date)
                await page.select_option("#ContentPlaceHolder1_ddlSegment", "All")
                await page.select_option("#ContentPlaceHolder1_ddlCategory", "All")
                await page.select_option("#ContentPlaceHolder1_ddlDep", "All")
                await page.click("#ContentPlaceHolder1_btnSubmit")
                await page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("Form submitted and results loaded.")

                # Get page content
                html_content = await page.content()
                notices_data = parse_notices(html_content)
                if notices_data:
                    logger.info(f"Attempt {attempt + 1}: Successfully parsed {len(notices_data)} notices.")
                    break
                else:
                    logger.warning(f"Attempt {attempt + 1}: No notices parsed.")
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: Page load or form submission timed out.")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching notices: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if notices_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(notices_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Notices JSON saved as {output_filename}")
            except Exception as e:
                logger.error(f"Failed to save JSON: {e}")

            save_text_summary(notices_data, from_date, to_date, summary_filename)

        if html_content and not notices_data:
            try:
                with open(f"bse_notices_raw_{to_date}.html", 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Saved raw HTML as bse_notices_raw_{to_date}.html for debugging.")
            except Exception as e:
                logger.error(f"Failed to save raw HTML: {e}")

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

        return notices_data, summary_filename

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
    notices_data, summary_filename = await fetch_bse_notices()
    if notices_data and summary_filename:
        date_str = datetime.today().strftime("%Y-%m-%d")
        send_email(summary_filename, date_str)

if __name__ == "__main__":
    asyncio.run(main())
