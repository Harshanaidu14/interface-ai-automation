
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
BASE_URL = "http://127.0.0.1:8000"
CUSTOMER_ID = "67890"

EVIDENCE_DIR = Path("evidence")
EVIDENCE_DIR.mkdir(exist_ok=True)

events = []


def log_event(event_type, **details):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        **details,
    }
    events.append(event)
    print(json.dumps(event, indent=2))


def verify_customer_page(page):
    """Verify the human reached the correct customer page."""

    parsed = urlparse(page.url)

    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 8000
        or parsed.path != "/customer"
    ):
        raise RuntimeError(
            "Human has not opened the customer details page."
        )

    # Confirm the displayed record matches the requested ID.
    body = page.locator("body").inner_text()

    id_match = re.search(
        r"Customer ID:\s*(\d{5})",
        body
    )

    if not id_match or id_match.group(1) != CUSTOMER_ID:
        raise RuntimeError(
            "The displayed customer ID does not match."
        )

    name_match = re.search(r"Name:\s*(.+)", body)
    balance_match = re.search(
        r"Balance:\s*(\$[\d,]+\.\d{2})",
        body
    )

    if not name_match or not balance_match:
        raise RuntimeError(
            "Customer details are incomplete."
        )

    return {
        "customer_id": CUSTOMER_ID,
        "customer_name": name_match.group(1).strip(),
        "balance": balance_match.group(1)
    }


def main():
    browser = None
    page = None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,
                slow_mo=800
            )

            context = browser.new_context()
            page = context.new_page()

            page.goto(BASE_URL)

            log_event(
                "automation_started",
                customer_id=CUSTOMER_ID,
                url=page.url
            )

            # Controlled simulation of a recoverable interruption.
            log_event(
                "automation_paused",
                reason="Simulated UI targeting failure",
                session_preserved=True
            )

            page.screenshot(
                path=str(EVIDENCE_DIR / "handoff_before.png"),
                full_page=True
            )

            print("\n" + "=" * 55)
            print("HUMAN ASSISTANCE REQUIRED")
            print("=" * 55)
            print(f"Please find customer ID: {CUSTOMER_ID}")
            print("\nIn the OPEN browser window:")
            print("1. Enter the customer ID.")
            print("2. Click Search Customer.")
            print("3. Leave the customer details page open.")
            print("4. Return here and press Enter.")
            print("=" * 55)

            input("\nPress Enter AFTER completing the steps...")

            log_event(
                "human_returned_control",
                url=page.url
            )

            # Verify the human's work in the SAME browser page.
            page.wait_for_timeout(2000)
            print("DEBUG - Current browser URL:", page.url)
            print("DEBUG - Open tabs:", len(context.pages))
            result = verify_customer_page(page)

            page.screenshot(
                path=str(EVIDENCE_DIR / "handoff_after.png"),
                full_page=True
            )

            log_event(
                "automation_resumed",
                customer_id=CUSTOMER_ID,
                session_preserved=True
            )

            # Automation performs its own post-handoff action.
            log_event(
                "automation_completed",
                result=result
            )

            print("\nHANDOFF SUCCESSFUL!")
            print(json.dumps(result, indent=2))

            print("\nBrowser stays open for 10 seconds...")
            page.wait_for_timeout(10000)

            browser.close()

    except Exception as error:
        log_event(
            "handoff_failed",
            error_type=type(error).__name__,
            error_message=str(error)
        )

        if page is not None:
            try:
                page.screenshot(
                    path=str(EVIDENCE_DIR / "handoff_failure.png"),
                    full_page=True
                )
            except Exception:
                pass

        raise

    finally:
        (EVIDENCE_DIR / "handoff_log.json").write_text(
            json.dumps(events, indent=2),
            encoding="utf-8"
        )


if __name__ == "__main__":
    main()
