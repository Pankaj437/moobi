import asyncio
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def download_press_release():
    # Calculate date range (today and one day ago)
    today = datetime.today()
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")  # e.g., 16-04-2025
    to_date = today.strftime("%d-%m-%Y")          # e.g., 17-04-2025
    output_filename = f"press_release_{to_date}.json"

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
                    # Save JSON in a pretty-printed format
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=4, ensure_ascii=False)
                    print(f"✅ Press release JSON saved as {output_filename}")
                except ValueError:
                    print("❌ Failed to parse JSON response. Response may not be valid JSON.")
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
