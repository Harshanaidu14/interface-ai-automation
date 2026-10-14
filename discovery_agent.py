
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import sync_playwright

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()
client = OpenAI()

BASE_URL = "http://127.0.0.1:8000"
GOAL = "Find customer 12345 and report their account balance."
DISCOVERY_CUSTOMER_ID = "12345"

MODEL = "gpt-4.1-mini"
MAX_STEPS = 8

EVIDENCE_DIR = Path("evidence")
CAPABILITIES_DIR = Path("capabilities")

EVIDENCE_DIR.mkdir(exist_ok=True)
CAPABILITIES_DIR.mkdir(exist_ok=True)

ARTIFACT_PATH = (
    CAPABILITIES_DIR / "customer_lookup_v1.json"
)

history = []
observed_actions = []


# --------------------------------------------------
# ASK AI FOR NEXT ACTION
# --------------------------------------------------

def ask_ai(page_text, current_input, previous_actions):
    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are a browser automation agent operating a "
            "local demo banking website. "
            "Choose exactly ONE next action. "
            "Respond with one valid JSON object only. "
            "Allowed actions: fill, click, finish. "
            'Fill example: {"action":"fill",'
            '"label":"Customer ID","value":"12345"} '
            'Click example: {"action":"click",'
            '"text":"Search Customer"} '
            'Finish example: {"action":"finish",'
            '"result":"Customer balance is $8,450.00"} '
            "If the customer ID is already filled correctly, "
            "click Search Customer instead of filling it again. "
            "Once the customer details are visible, finish. "
            "Never invent customer information. "
            "Never modify accounts or transfer money."
        ),
        input=(
            "Respond with one valid JSON object only.\n\n"
            f"Goal: {GOAL}\n\n"
            f"Visible page:\n{page_text}\n\n"
            f"Current customer ID input value: {current_input}\n"
            f"Previous actions: {json.dumps(previous_actions)}"
        ),
        text={
            "format": {
                "type": "json_object"
            }
        },
    )

    raw_output = response.output_text

    if not raw_output or not raw_output.strip():
        raise ValueError("OpenAI returned an empty response")

    decision = json.loads(raw_output)

    if not isinstance(decision, dict):
        raise ValueError("AI response must be a JSON object")

    return decision


# --------------------------------------------------
# BROWSER TARGETS
# --------------------------------------------------

def customer_input(page):
    # The demo HTML label is not linked to the input.
    return page.get_by_placeholder(
        "Enter customer ID",
        exact=True,
    )


def search_button(page):
    return page.get_by_role(
        "button",
        name="Search Customer",
        exact=True,
    )


def get_current_input(page):
    field = customer_input(page)

    if field.count() == 1:
        return field.input_value()

    return "No customer ID input on this page"


# --------------------------------------------------
# SAFETY AND VERIFICATION
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
            f"Navigation outside allowlist: {page.url}"
        )


def verify_discovery_result(page):
    check_url(page)

    parsed = urlparse(page.url)
    query = parse_qs(parsed.query)

    if parsed.path != "/customer":
        raise RuntimeError(
            "Discovery did not reach the customer page"
        )

    if query.get("customer_id") != [DISCOVERY_CUSTOMER_ID]:
        raise RuntimeError(
            "Discovery reached the wrong customer"
        )

    text = page.locator("body").inner_text()

    id_match = re.search(
        r"Customer ID:\s*(\d{5})",
        text,
    )

    name_match = re.search(
        r"Name:\s*(.+)",
        text,
    )

    balance_match = re.search(
        r"Balance:\s*(\$[\d,]+\.\d{2})",
        text,
    )

    if (
        not id_match
        or id_match.group(1) != DISCOVERY_CUSTOMER_ID
        or not name_match
        or not balance_match
    ):
        raise RuntimeError(
            "Discovered customer details could not be verified"
        )

    return {
        "customer_id": DISCOVERY_CUSTOMER_ID,
        "customer_name": name_match.group(1).strip(),
        "balance": balance_match.group(1),
    }


# --------------------------------------------------
# EXECUTE AI DECISION
# --------------------------------------------------

def execute_action(page, decision):
    action = decision.get("action")

    check_url(page)

    if action == "fill":
        if (
            decision.get("label") != "Customer ID"
            or decision.get("value") != DISCOVERY_CUSTOMER_ID
        ):
            raise ValueError("AI requested an unapproved input")

        field = customer_input(page)

        if field.count() != 1:
            raise RuntimeError(
                "Customer ID input is missing or ambiguous"
            )

        field.fill(DISCOVERY_CUSTOMER_ID)

        if field.input_value() != DISCOVERY_CUSTOMER_ID:
            raise RuntimeError("Input checkpoint failed")

        observed_actions.append({
            "action": "fill",
            "target": {
                "strategy": "role",
                "role": "textbox",
                "name": "Customer ID",
            },
            "value": DISCOVERY_CUSTOMER_ID,
        })

    elif action == "click":
        if decision.get("text") != "Search Customer":
            raise ValueError("AI requested an unapproved click")

        button = search_button(page)

        if button.count() != 1:
            raise RuntimeError(
                "Search button is missing or ambiguous"
            )

        button.click()

        page.wait_for_load_state("domcontentloaded")
        check_url(page)

        parsed = urlparse(page.url)

        if parsed.path != "/customer":
            raise RuntimeError(
                "Search did not navigate to customer details"
            )

        observed_actions.append({
            "action": "click",
            "target": {
                "strategy": "role",
                "role": "button",
                "name": "Search Customer",
            },
        })

    elif action == "finish":
        result = verify_discovery_result(page)

        print("\nVERIFIED DISCOVERY RESULT:")
        print(json.dumps(result, indent=2))

        return result

    else:
        raise ValueError(
            f"Unsupported AI action: {action}"
        )

    return None


# --------------------------------------------------
# GENERATE REUSABLE CAPABILITY
# --------------------------------------------------

def generate_capability(verified_result):
    """
    Compile observed AI actions into the supported
    deterministic replay artifact format.
    """

    if [a["action"] for a in observed_actions] != [
        "fill",
        "click",
    ]:
        raise ValueError(
            "Discovery did not observe the expected workflow"
        )

    fill_action = observed_actions[0]
    click_action = observed_actions[1]

    if fill_action["value"] != DISCOVERY_CUSTOMER_ID:
        raise ValueError(
            "Observed input differs from discovery customer"
        )

    if verified_result["customer_id"] != DISCOVERY_CUSTOMER_ID:
        raise ValueError(
            "Verified result differs from discovery customer"
        )

    capability = {
        "schema_version": "1.0",
        "capability_id": "bank_customer_lookup",
        "version": 1,
        "description": (
            "Find a banking customer by ID and "
            "retrieve account information"
        ),
        "base_url": BASE_URL,
        "inputs": {
            "customer_id": {
                "type": "string",
                "required": True,
            }
        },
        "outputs": {
            "customer_name": {
                "type": "string",
            },
            "balance": {
                "type": "string",
            },
        },
        "steps": [
            {
                "id": "enter_customer_id",
                "action": "fill",
                "target": fill_action["target"],
                "value": "{{customer_id}}",
                "checkpoint": "input_filled",
            },
            {
                "id": "search_customer",
                "action": "click",
                "target": click_action["target"],
                "checkpoint": "navigation_completed",
            },
            {
                "id": "read_customer_details",
                "action": "extract",
                "fields": [
                    "customer_name",
                    "balance",
                ],
                "checkpoint": "customer_details_visible",
            },
        ],
    }

    validate_capability(capability)
    return capability


# --------------------------------------------------
# VALIDATE GENERATED ARTIFACT
# --------------------------------------------------

def validate_capability(capability):
    if capability["schema_version"] != "1.0":
        raise ValueError("Invalid schema version")

    if capability["capability_id"] != "bank_customer_lookup":
        raise ValueError("Invalid capability ID")

    if capability["version"] != 1:
        raise ValueError("Invalid capability version")

    if capability["base_url"] != BASE_URL:
        raise ValueError("Invalid base URL")

    if capability["inputs"] != {
        "customer_id": {
            "type": "string",
            "required": True,
        }
    }:
        raise ValueError("Invalid input schema")

    expected_actions = ["fill", "click", "extract"]

    steps = capability["steps"]

    if [step["action"] for step in steps] != expected_actions:
        raise ValueError("Invalid capability steps")

    if steps[0]["value"] != "{{customer_id}}":
        raise ValueError("Customer ID was not parameterized")

    if steps[0]["target"] != {
        "strategy": "role",
        "role": "textbox",
        "name": "Customer ID",
    }:
        raise ValueError("Invalid customer input target")

    if steps[1]["target"] != {
        "strategy": "role",
        "role": "button",
        "name": "Search Customer",
    }:
        raise ValueError("Invalid search button target")

    if set(steps[2]["fields"]) != {
        "customer_name",
        "balance",
    }:
        raise ValueError("Invalid output fields")


# --------------------------------------------------
# MAIN DISCOVERY PROCESS
# --------------------------------------------------

def main():
    history.clear()
    observed_actions.clear()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            slow_mo=800,
        )

        page = browser.new_page()
        discovery_succeeded = False

        try:
            page.goto(BASE_URL)
            check_url(page)

            for step in range(1, MAX_STEPS + 1):
                page_text = page.locator("body").inner_text()
                current_input = get_current_input(page)

                previous_actions = [
                    item["decision"]
                    for item in history
                    if "decision" in item
                ]

                decision = ask_ai(
                    page_text,
                    current_input,
                    previous_actions,
                )

                print(f"\nStep {step}: {decision}")

                history.append({
                    "step": step,
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "url": page.url,
                    "observation": page_text,
                    "current_input": current_input,
                    "decision": decision,
                })

                result = execute_action(page, decision)

                if decision.get("action") == "finish":
                    # Only generate after successful verification.
                    capability = generate_capability(result)

                    # Preserve the old artifact until all
                    # validation has succeeded.
                    temp_path = ARTIFACT_PATH.with_suffix(
                        ".json.tmp"
                    )

                    temp_path.write_text(
                        json.dumps(capability, indent=2),
                        encoding="utf-8",
                    )

                    temp_path.replace(ARTIFACT_PATH)

                    history.append({
                        "type": "capability_generated",
                        "path": str(ARTIFACT_PATH),
                        "capability_id": capability["capability_id"],
                        "version": capability["version"],
                    })

                    print("\nCAPABILITY GENERATED SUCCESSFULLY!")
                    print(f"Saved to: {ARTIFACT_PATH}")

                    discovery_succeeded = True
                    break

            if not discovery_succeeded:
                raise RuntimeError(
                    "Maximum AI discovery steps reached"
                )

        except Exception as error:
            print("\nDiscovery failed:", error)

            history.append({
                "type": "error",
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "message": str(error),
            })

            raise

        finally:
            try:
                page.screenshot(
                    path=str(EVIDENCE_DIR / "discovery_final.png"),
                    full_page=True,
                )
            except Exception:
                pass

            (EVIDENCE_DIR / "discovery_log.json").write_text(
                json.dumps(history, indent=2),
                encoding="utf-8",
            )

            browser.close()


if __name__ == "__main__":
    main()
