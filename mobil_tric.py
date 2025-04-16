import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def take_screenshot_of_ipo_data():
    async with async_playwright() as p:
        # Launch the browser (headless=False to see the browser in action)
        browser = await p.firefox.launch(headless=False)
        
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

        # Navigate to the IPO page using the same context (cookies are retained)
        await page.goto("https://www.nseindia.com/market-data/all-upcoming-issues-ipo", timeout=60000)

        # Wait for the table to load (adjust selector based on actual table structure)
        await page.wait_for_selector("table")  # Replace with specific table selector if needed

        # Wait 2 seconds before taking the screenshot
        await asyncio.sleep(2)

        # Take a screenshot of the table
        table = page.locator("table")  # Adjust selector to match the IPO data table
        await table.screenshot(path="ipo_data_screenshot.png")
        print("✅ Screenshot saved as ipo_data_screenshot.png")

        # Close the browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshot_of_ipo_data())
