import asyncio
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def fetch_press_release_data(page, from_date, to_date):
    """Fetch press release data from NSE API and save it in a structured JSON format."""
    url = f"https://www.nseindia.com/api/press-release?fromDate={from_date}&toDate={to_date}"
    try:
        response = await page.evaluate("""
            async (url) => {
                const res = await fetch(url, {
                    method: "GET",
                    headers: {
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "User-Agent": navigator.userAgent,
                        "Referer": "https://www.nseindia.com/press-release"
                    },
                    credentials: "include"
                });
                const text = await res.text();
                try {
                    return JSON.parse(text);
                } catch (e) {
                    console.error("❌ JSON parse error:", text);
                    throw e;
                }
            }
        """, url)

        # Structure the JSON data
        structured_data = {}
        for entry in response:
            # Assuming each entry has a 'date' field; adjust based on actual API response
            date = entry.get("date", "Unknown Date")
            # Simplify the date to DD-MM-YYYY if it includes time
            try:
                date = datetime.strptime(date, "%d-%b-%Y %H:%M:%S").strftime("%d-%m-%Y")
            except (ValueError, TypeError):
                try:
                    date = datetime.strptime(date, "%d-%b-%Y").strftime("%d-%m-%Y")
                except (ValueError, TypeError):
                    pass  # Keep the original date if parsing fails

            if date not in structured_data:
                structured_data[date] = []
            
            # Extract relevant fields (adjust based on actual API response structure)
            press_release = {
                "title": entry.get("title", "N/A"),
                "description": entry.get("description", "N/A"),
                "category": entry.get("category", "N/A"),
                "link": entry.get("link", "N/A"),
                "time": entry.get("time", "N/A")  # If time is separate in the response
            }
            structured_data[date].append(press_release)

        # Sort entries by date and within each date by title (or another field)
        structured_data = dict(sorted(structured_data.items()))
        for date in structured_data:
            structured_data[date] = sorted(structured_data[date], key=lambda x: x["title"])

        # Save the structured data to a JSON file
        file_name = f"press_release_{to_date}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=4)
        print(f"✅ Structured press release data saved to {file_name}")
    except Exception as e:
        print(f"❌ Error fetching press release data: {str(e)}")

async def take_screenshot_and_fetch_data():
    # Calculate dates: today and one day ago
    today = datetime(2025, 4, 16)  # Current date as per your context
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")

    async with async_playwright() as p:
        # Launch the browser (headless=False to see the browser in action)
        browser = await p.firefox.launch(headless=True)
        
        # Create a new context with a user agent to mimic a real browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Navigate to the NSE homepage to set cookies
        try:
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            print("⚠️ Homepage load timeout—continuing anyway...")

        # Task 1: Take screenshot of IPO data
        # Navigate to the corrected IPO page
        await page.goto("https://www.nseindia.com/market-data/upcoming-issues-ipo", timeout=60000)

        # Wait for the table to load (adjust selector based on actual table structure)
        await page.wait_for_selector("table")  # Replace with specific table selector if needed

        # Wait 2 seconds before taking the screenshot
        await asyncio.sleep(2)

        # Take a screenshot of the table
        table = page.locator("table")  # Adjust selector to match the IPO data table
        await table.screenshot(path="ipo_data_screenshot.png")
        print("✅ Screenshot saved as ipo_data_screenshot.png")

        # Task 2: Fetch and structure press release data
        await fetch_press_release_data(page, from_date, to_date)

        # Close the browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshot_and_fetch_data())
