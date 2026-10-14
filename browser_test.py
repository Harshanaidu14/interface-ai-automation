
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    # Open our banking application
    page.goto("http://127.0.0.1:8000")

    # Enter a fictional customer ID
    page.get_by_placeholder("Enter customer ID").fill("12345")

    # Click the search button
    page.get_by_role("button", name="Search Customer").click()

    # Read the displayed information
    page.get_by_text("Alex Morgan").wait_for()

    print("Customer search completed successfully!")
    print("Page URL:", page.url)
    print("Customer name:", page.get_by_text("Alex Morgan").inner_text())

    # Save evidence of the successful interaction
    page.screenshot(
        path="browser_test_success.png",
        full_page=True
    )

    browser.close()
