
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

ARTIFACT_PATH = Path("capabilities/customer_lookup_v1.json")

EVIDENCE_DIR = Path("evidence")
EVIDENCE_DIR.mkdir(exist_ok=True)

ALLOWED_URL = "http://127.0.0.1:8000"

SLOW_MOTION = 1500
RESULT_DISPLAY_TIME = 10000

# Only one human recovery attempt per replay.
MAX_HANDOFFS = 1

# --------------------------------------------------
# STRUCTURED LOGGING
# --------------------------------------------------

def log_event(events, event_type, **details):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        **details,
    }
    events.append(event)
    print(json.dumps(event, indent=2))


# --------------------------------------------------
# LOAD SAVED CAPABILITY
# --------------------------------------------------

def load_capability():
    with ARTIFACT_PATH.open("r", encoding="utf-8") as file:
        capability = json.load(file)

    if capability.get("schema_version") != "1.0":
        raise ValueError("Unsupported capability schema version")

    if capability.get("capability_id") != "bank_customer_lookup":
        raise ValueError("Unexpected capability ID")

    if capability.get("base_url") != ALLOWED_URL:
        raise ValueError("Capability URL is not allowlisted")

    if capability.get("version") != 1:
        raise ValueError("Unsupported capability version")

    return capability


# --------------------------------------------------
# SAFETY
# --------------------------------------------------

def check_url(page):
    parsed = urlparse(page.url)

    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 8000
        or parsed.path not in ("/", "/customer")
    ):
        raise RuntimeError(
            f"Navigation outside allowed website: {page.url}"
        )


def verify_customer_url(page, customer_id):
    check_url(page)

    parsed = urlparse(page.url)

    if parsed.path != "/customer":
        raise RuntimeError(
            "Navigation checkpoint failed: not on customer page"
        )

    query = parse_qs(parsed.query)

    if query.get("customer_id") != [customer_id]:
        raise RuntimeError(
            "Navigation checkpoint failed: wrong customer ID"
        )


# --------------------------------------------------
# FIND BROWSER ELEMENTS
# --------------------------------------------------

def get_target(page, target):
    if target.get("strategy") != "role":
        raise ValueError("Unsupported targeting strategy")

    role = target.get("role")
    name = target.get("name")

    allowed_targets = {
        ("textbox", "Customer ID"),
        ("button", "Search Customer"),
    }

    if (role, name) not in allowed_targets:
        raise ValueError(f"Target not allowlisted: {target}")

    # The demo's label is not linked to its input.
    if role == "textbox":
        return page.get_by_placeholder(
            "Enter customer ID",
            exact=True,
        )

    return page.get_by_role(
        "button",
        name="Search Customer",
        exact=True,
    )


# --------------------------------------------------
# EXTRACT CUSTOMER INFORMATION
# --------------------------------------------------

def extract_customer(page, customer_id):
    verify_customer_url(page, customer_id)

    text = page.locator("body").inner_text()

    if "Customer Not Found" in text:
        return {
            "outcome": "customer_not_found",
            "customer_id": customer_id,
            "customer_name": None,
            "balance": None,
        }

    id_match = re.search(
        r"Customer ID:\s*(\d{5})",
        text,
    )

    if not id_match or id_match.group(1) != customer_id:
        raise RuntimeError(
            "Customer details do not match requested ID"
        )

    name_match = re.search(r"Name:\s*(.+)", text)

    balance_match = re.search(
        r"Balance:\s*(\$[\d,]+\.\d{2})",
        text,
    )

    if not name_match or not balance_match:
        raise RuntimeError(
            "Customer details are missing or cannot be parsed"
        )

    return {
        "outcome": "success",
        "customer_id": customer_id,
        "customer_name": name_match.group(1).strip(),
        "balance": balance_match.group(1),
    }


# --------------------------------------------------
# HUMAN-IN-THE-LOOP HANDOFF
# --------------------------------------------------

def human_handoff(page, events, customer_id, step_id, error):
    """
    Pause replay and let a person correct the browser state.

    The existing Playwright page, context, and browser are reused.
    The automation never performs the human's corrective action.
    """

    check_url(page)

    log_event(
        events,
        "handoff_requested",
        step_id=step_id,
        reason=str(error),
        url=page.url,
        session_preserved=True,
    )

    page.screenshot(
        path=str(EVIDENCE_DIR / "replay_handoff_before.png"),
        full_page=True,
    )

    print("\n" + "=" * 55)
    print("HUMAN ASSISTANCE REQUIRED")
    print("=" * 55)
    print(f"Customer ID: {customer_id}")
    print(f"Failed step: {step_id}")
    print("\nIn the SAME open browser window:")
    print("1. Return to the customer search page if needed.")
    print(f"2. Search for customer {customer_id}.")
    print("3. Wait until the correct customer page appears.")
    print("4. Return to this terminal and press Enter.")
    print("\nType CANCEL and press Enter to stop.")
    print("=" * 55)

    response = input("\nPress Enter to resume, or CANCEL: ")

    if response.strip().upper() == "CANCEL":
        log_event(events, "handoff_cancelled", step_id=step_id)
        raise RuntimeError("Human cancelled the handoff")

    # Important: process browser events after blocking terminal input.
    page.wait_for_timeout(2000)

    # Re-check safety after the human's actions.
    verify_customer_url(page, customer_id)

    # Validate the business state, not just the URL.
    result = extract_customer(page, customer_id)

    page.screenshot(
        path=str(EVIDENCE_DIR / "replay_handoff_after.png"),
        full_page=True,
    )

    log_event(
        events,
        "handoff_verified",
        step_id=step_id,
        url=page.url,
        session_preserved=True,
    )

    log_event(
        events,
        "automation_resumed",
        step_id=step_id,
    )

    return result


# --------------------------------------------------
# EXECUTE A SAVED STEP
# --------------------------------------------------

def execute_step(page, step, customer_id):
    action = step["action"]

    if action == "fill":
        target = get_target(page, step["target"])

        if step["value"] != "{{customer_id}}":
            raise ValueError("Unsupported input template")

        target.fill(customer_id, timeout=5000)

        if target.input_value() != customer_id:
            raise RuntimeError("Input checkpoint failed")

        return None

    if action == "click":
        target = get_target(page, step["target"])

        target.click(timeout=5000)

        page.wait_for_load_state("domcontentloaded")

        verify_customer_url(page, customer_id)
        return None

    if action == "extract":
        expected_fields = {"customer_name", "balance"}

        if set(step["fields"]) != expected_fields:
            raise ValueError("Unexpected extraction fields")

        return extract_customer(page, customer_id)

    raise ValueError(f"Unsupported action: {action}")


# --------------------------------------------------
# DETERMINISTIC REPLAY
# --------------------------------------------------

def replay(customer_id, simulate_failure=False):
    events = []
    page = None
    result = None
    handoff_count = 0

    try:
        if not re.fullmatch(r"\d{5}", customer_id):
            raise ValueError(
                "Customer ID must contain exactly five digits"
            )

        capability = load_capability()

        log_event(
            events,
            "replay_started",
            capability_id=capability["capability_id"],
            capability_version=capability["version"],
            customer_id=customer_id,
            simulate_failure=simulate_failure,
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,
                slow_mo=SLOW_MOTION,
            )

            try:
                context = browser.new_context()
                page = context.new_page()

                page.goto(
                    capability["base_url"],
                    wait_until="domcontentloaded",
                )

                check_url(page)

                for step in capability["steps"]:
                    step_id = step["id"]
                    action = step["action"]

                    log_event(
                        events,
                        "step_started",
                        step_id=step_id,
                        action=action,
                    )

                    try:
                        # Explicit test-only failure injection.
                        # Normal replay never enters this branch.
                        if (
                            simulate_failure
                            and step_id == "search_customer"
                        ):
                            raise PlaywrightTimeoutError(
                                "Simulated search button timeout"
                            )

                        step_result = execute_step(
                            page, step, customer_id
                        )

                        if step_result is not None:
                            result = step_result

                    except PlaywrightError as error:
                        # Only Playwright interaction errors are
                        # eligible for human recovery.
                        if handoff_count >= MAX_HANDOFFS:
                            raise RuntimeError(
                                "Human handoff limit exceeded"
                            ) from error

                        handoff_count += 1

                        result = human_handoff(
                            page,
                            events,
                            customer_id,
                            step_id,
                            error,
                        )

                        # Human completed the lookup.
                        # Continue the saved workflow, but skip
                        # browser actions already satisfied.
                        log_event(
                            events,
                            "step_recovered",
                            step_id=step_id,
                            recovery="human_handoff",
                        )

                        if action in ("fill", "click"):
                            continue

                    log_event(
                        events,
                        "step_completed",
                        step_id=step_id,
                        checkpoint=step.get("checkpoint"),
                        url=page.url,
                    )

                if result is None:
                    raise RuntimeError(
                        "Replay finished without a result"
                    )

                log_event(
                    events,
                    "replay_completed",
                    result=result,
                    handoff_count=handoff_count,
                )

                print("\nREPLAY RESULT:")
                print(json.dumps(result, indent=2))

                page.screenshot(
                    path=str(EVIDENCE_DIR / "replay_final.png"),
                    full_page=True,
                )

                print("\nKeeping browser open for 10 seconds...")
                page.wait_for_timeout(RESULT_DISPLAY_TIME)

            finally:
                browser.close()

    except Exception as error:
        log_event(
            events,
            "replay_failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

        if page is not None:
            try:
                page.screenshot(
                    path=str(EVIDENCE_DIR / "replay_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass

        raise

    finally:
        log_path = EVIDENCE_DIR / f"replay_{customer_id}.json"

        log_path.write_text(
            json.dumps(events, indent=2),
            encoding="utf-8",
        )


# --------------------------------------------------
# RUN PROGRAM
# --------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    simulate_failure = "--simulate-failure" in args
    customer_ids = [
        arg for arg in args if not arg.startswith("--")
    ]

    customer_id = customer_ids[0] if customer_ids else "12345"

    replay(customer_id, simulate_failure=simulate_failure)
