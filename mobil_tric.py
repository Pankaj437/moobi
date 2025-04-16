from playwright.sync_api import sync_playwright
import time
def take_screenshot_of_ipo_data():
    # Initialize Playwright
    with sync_playwright() as p:
        # Launch the browser (headless=False to see the browser in action)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the NSE IPO page
        page.goto("https://www.nseindia.com/market-data/all-upcoming-issues-ipo")

        # Wait for the table to load (adjust selector based on actual table structure)
        page.wait_for_selector("table")  # Replace with specific table selector if needed
        time.sleep(2)
        # Take a screenshot of the table
        table = page.locator("table")  # Adjust selector to match the IPO data table
        table.screenshot(path="ipo_data_screenshot.png")

        # Close the browser
        browser.close()

# Run the function
if __name__ == "__main__":
    take_screenshot_of_ipo_data()
