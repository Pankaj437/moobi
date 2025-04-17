import asyncio
import json
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Optional: Install html2text for better HTML cleaning
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False

def clean_html(text):
    """Remove HTML tags and clean text."""
    if HTML2TEXT_AVAILABLE:
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        return h.handle(text).strip()
    else:
        # Fallback: Use regex to remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

def simplify_press_release(data):
    """Extract key fields and clean body for simplified JSON."""
    simplified = []
    for item in data:
        content = item.get('content', {})
        category = content.get('field_category_press', [])
        category_name = (
            category[0]['content']['name']
            if isinstance(category, list) and category and isinstance(category[0], dict)
            else content.get('field_type', 'Unknown')
        )
        simplified.append({
            'title': content.get('title', ''),
            'date': content.get('field_date', ''),
            'body': clean_html(content.get('body', '')),
            'attachment_url': content.get('field_file_attachement', {}).get('url', ''),
            'category': category_name
        })
    return simplified

async def download_press_release():
    # Calculate date range (today and one day ago)
    today = datetime.today()
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")  # e.g., 16-04-2025
    to_date = today.strftime("%d-%m-%Y")          # e.g., 17-04-2025
    output_filename = f"press_release_{to_date}.json"
    simplified_filename = f"press_release_{to_date}_simplified.json"
    summary_filename = f"press_release_{to_date}_summary.txt"

    async with async_playwright() as p:
        # Launch the browser
        browser = await p.firefox.launch(headless=True)
        
        # Create a new context with a user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Navigate to the NSE homepage to set cookies
        try:
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("✅ NSE homepage loaded, cookies set.")
        except PlaywrightTimeoutError:
            print("⚠️ Homepage load timeout—continuing anyway...")

        # Construct the press release API URL
        api_url = f"https://www.nseindia.com/api/press-release?fromDate={from_date}&toDate={to_date}"
        print(f"Fetching press release data from: {api_url}")

        # Make the API request
        try:
            response = await page.goto(api_url, timeout=60000)
            if response and response.ok:
                # Get the JSON content
                try:
                    json_data = await response.json()
                    # Save original JSON
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=4, ensure_ascii=False)
                    print(f"✅ Original press release JSON saved as {output_filename}")

                    # Save simplified JSON
                    simplified_data = simplify_press_release(json_data)
                    with open(simplified_filename, 'w', encoding='utf-8') as f:
                        json.dump(simplified_data, f, indent=4, ensure_ascii=False)
                    print(f"✅ Simplified press release JSON saved as {simplified_filename}")

                    # Generate text summary
                    with open(summary_filename, 'w', encoding='utf-8') as f:
                        f.write(f"Press Release Summary ({from_date} to {to_date})\n")
                        f.write("=" * 50 + "\n\n")
                        for item in simplified_data:
                            f.write(f"Title: {item['title']}\n")
                            f.write(f"Date: {item['date']}\n")
                            f.write(f"Category: {item['category']}\n")
                            f.write(f"Body: {item['body']}\n")
                            f.write(f"Attachment: {item['attachment_url']}\n")
                            f.write("-" * 50 + "\n\n")
                    print(f"✅ Text summary saved as {summary_filename}")

                except ValueError:
                    print("❌ Failed to parse JSON response. Response may not be valid JSON.")
                    # Save raw response for debugging
                    with open("raw_response.txt", "w", encoding='utf-8') as f:
                        f.write(await response.text())
                    print("Saved raw response as raw_response.txt for debugging.")
            else:
                print(f"❌ API request failed with status: {response.status if response else 'No response'}")
        except PlaywrightTimeoutError:
            print("❌ API request timed out.")
        except Exception as e:
            print(f"❌ Error fetching press release data: {e}")

        # Close the browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(download_press_release())
