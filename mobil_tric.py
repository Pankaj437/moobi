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
            date = entry.get("date", "Unknown Date")
            try:
                date = datetime.strptime(date, "%d-%b-%Y %H:%M:%S").strftime("%d-%m-%Y")
            except (ValueError, TypeError):
                try:
                    date = datetime.strptime(date, "%d-%b-%Y").strftime("%d-%m-%Y")
                except (ValueError, TypeError):
                    pass

            if date not in structured_data:
                structured_data[date] = []
            
            press_release = {
                "title": entry.get("title", "N/A"),
                "description": entry.get("description", "N/A"),
                "category": entry.get("category", "N/A"),
                "link": entry.get("link", "N/A"),
                "time": entry.get("time", "N/A")
            }
            structured_data[date].append(press_release)

        structured_data = dict(sorted(structured_data.items()))
        for date in structured_data:
            structured_data[date] = sorted(structured_data[date], key=lambda x: x["title"])

        file_name = f"press_release_{to_date}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=4)
        print(f"✅ Structured press release data saved to {file_name}")
        return file_name
    except Exception as e:
        print(f"❌ Error fetching press release data: {str(e)}")
        return None

async def take_screenshot_and_fetch_data():
    # Calculate dates dynamically: today and one day ago
    today = datetime.today()
    one_day_ago = today - timedelta(days=1)
    from_date = one_day_ago.strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.nseindia.com", timeout=30000)
            await page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            print("⚠️ Homepage load timeout—continuing anyway...")

        # Task 1: Take screenshot of IPO data
        await page.goto("https://www.nseindia.com/market-data/upcoming-issues-ipo", timeout=60000)
        await page.wait_for_load_state("networkidle")  # Ensure dynamic content loads

        # Try to find the table with a more specific selector
        try:
            # Adjust selector based on actual table structure; this is a placeholder
            table_selector = "table:has(th:text('COMPANY NAME'))"  # Example selector
            await page.wait_for_selector(table_selector, timeout=60000)
        except PlaywrightTimeoutError:
            print("❌ Table not found. Logging page content for debugging...")
            content = await page.content()
            with open("page_content.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Page content saved to page_content.html. Please inspect to find the correct table selector.")
            raise

        await asyncio.sleep(2)
        table = page.locator(table_selector)
        await table.screenshot(path="ipo_data_screenshot.png")
        print("✅ Screenshot saved as ipo_data_screenshot.png")

        # Task 2: Fetch and structure press release data
        json_file = await fetch_press_release_data(page, from_date, to_date)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshot_and_fetch_data())
