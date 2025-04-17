import asyncio
import json
import logging
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_html(text):
    """Remove HTML tags using BeautifulSoup."""
    try:
        soup = BeautifulSoup(text, 'html.parser')
        cleaned_text = soup.get_text(separator=' ').strip()
        cleaned_text = ' '.join(cleaned_text.split())
        logger.info("Successfully cleaned HTML from text.")
        return cleaned_text
    except Exception as e:
        logger.error(f"Failed to clean HTML: {e}")
        return text

def simplify_press_release(data):
    """Extract key fields, clean body, and sort by date."""
    try:
        simplified = []
        for item in data:
            content = item.get('content', {})
            category = content.get('field_category_press', [])
            category_name = (
                category[0]['content']['name']
                if isinstance(category, list) and category and isinstance(category[0], dict)
                else content.get('field_type', 'Unknown')
            )
            attachment_url = content.get('field_file_attachement', {}).get('url', '')
            simplified.append({
                'title': content.get('title', ''),
                'date': content.get('field_date', ''),
                'body': clean_html(content.get('body', '')),
                'attachment_url': attachment_url,
                'category': category_name
            })
            logger.debug(f"Parsed item: title={content.get('title', '')}, attachment_url={attachment_url}")
        simplified = sorted(simplified, key=lambda x: datetime.strptime(x['date'], '%d-%b-%Y'), reverse=True)
        logger.info(f"Simplified and sorted {len(simplified)} press release entries.")
        return simplified
    except Exception as e:
        logger.error(f"Failed to simplify press release data: {e}")
        return []

async def download_press_release():
    today = datetime.today()
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")
    output_filename = f"press_release_{to_date}.json"
    simplified_filename = f"press_release_{to_date}_simplified.json"
    summary_filename = f"press_release_{to_date}_summary.txt"

    logger.info(f"Starting press release download for {from_date} to {to_date}")

    async with async_playwright() as p:
        try:
            browser = await p.firefox.launch(headless=True)
            logger.info("Browser launched successfully.")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return

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
            return

        try:
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("NSE homepage loaded, cookies set.")
        except PlaywrightTimeoutError:
            logger.warning("Homepage load timeout—continuing anyway...")

        api_url = f"https://www.nseindia.com/api/press-release?fromDate={from_date}&toDate={to_date}"
        logger.info(f"Fetching press release data from: {api_url}")

        json_data = None
        for attempt in range(3):
            try:
                response = await page.goto(api_url, timeout=90000)
                if response and response.ok:
                    try:
                        json_data = await response.json()
                        logger.info(f"Attempt {attempt + 1}: Successfully fetched JSON data with {len(json_data)} entries.")
                        break
                    except ValueError:
                        logger.error(f"Attempt {attempt + 1}: Failed to parse JSON response.")
                        with open(f"raw_response_attempt_{attempt + 1}.txt", "w", encoding='utf-8') as f:
                            f.write(await response.text())
                        logger.info(f"Saved raw response as raw_response_attempt_{attempt + 1}.txt")
                else:
                    logger.error(f"Attempt {attempt + 1}: API request failed with status: {response.status if response else 'No response'}")
            except PlaywrightTimeoutError:
                logger.error(f"Attempt {attempt + 1}: API request timed out.")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching press release data: {e}")
            if attempt < 2:
                logger.info("Retrying after 2 seconds...")
                await asyncio.sleep(2)

        if json_data:
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Original press release JSON saved as {output_filename}")
            except Exception as e:
                logger.error(f"Failed to save original JSON: {e}")

            try:
                simplified_data = simplify_press_release(json_data)
                if simplified_data:
                    with open(simplified_filename, 'w', encoding='utf-8') as f:
                        json.dump(simplified_data, f, indent=4, ensure_ascii=False)
                    logger.info(f"Simplified press release JSON saved as {simplified_filename}")
                else:
                    logger.warning("No simplified data generated.")
            except Exception as e:
                logger.error(f"Failed to save simplified JSON: {e}")

            try:
                with open(summary_filename, 'w', encoding='utf-8') as f:
                    f.write(f"Press Release Summary ({from_date} to {to_date})\n")
                    f.write("=" * 60 + "\n\n")
                    for item in simplified_data:
                        f.write(f"Title: {item['title']}\n")
                        f.write(f"Date: {item['date']}\n")
                        f.write(f"Category: {item['category']}\n")
                        f.write(f"Body: {item['body']}\n")
                        f.write(f"Attachment: {item['attachment_url']}\n")
                        f.write("=" * 60 + "\n\n")
                logger.info(f"Text summary saved as {summary_filename}")
            except Exception as e:
                logger.error(f"Failed to save text summary: {e}")
        else:
            logger.error("Failed to fetch valid JSON after all retries.")

        try:
            await browser.close()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")

if __name__ == "__main__":
    asyncio.run(download_press_release())
