import time
from playwright.sync_api import Playwright, sync_playwright

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Login process
    page.goto("https://mobile-tracker-free.com/")
    page.get_by_role("link", name=" Login").click()
    page.get_by_role("textbox", name="Email").fill("enormouspan@gmail.com")
    page.get_by_role("textbox", name="Password").fill("pankaj437")
    time.sleep(2)
    page.get_by_role("button", name="Sign in ").click()
    page.wait_for_timeout(3000)

    # Optional: Close ad iframe if exists
    try:
        iframe = page.frame(name="aswift_5")
        if iframe:
            close_btn = iframe.get_by_role("button", name="Close ad")
            if close_btn:
                close_btn.click()
    except Exception as e:
        print("Ad close failed or not present:", e)

    # List of URLs and filenames for screenshot
    sections = {
        "whatsappmessages": "whatsapp_data.png",
        "snapchatmessages": "snapchat_data.png",
        "calls": "calls.png",
        # Add more like:
        "sms": "sms.png",
        # "contacts": "contacts.png",
        "instagrammessages": "instagram.png",
    }

    for section, filename in sections.items():
        try:
            url = f"https://mobile-tracker-free.com/dashboard/{section}.php"
            print(f"Navigating to: {url}")
            page.goto(url)
            page.wait_for_timeout(3000)

            # Try capturing the full page if no table
            if page.locator("table").is_visible():
                page.locator("table").screenshot(path=filename)
            else:
                page.screenshot(path=filename, full_page=True)

            print(f"Saved screenshot: {filename}")
        except Exception as e:
            print(f"Failed to capture {section}: {e}")

    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
