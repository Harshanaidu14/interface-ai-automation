# AI Business Automation — Discovery and Deterministic Replay

An AI-assisted browser automation prototype developed for the interface.ai Applied AI Engineer (Business Automation) take-home assignment.

## Overview

This project demonstrates how an AI agent can discover a business workflow through a browser, generate a reusable capability artifact, and replay that capability deterministically without requiring an LLM during execution.

The demonstration uses a locally hosted fictional banking application for customer lookup.

## Key Features

- **LLM-powered discovery:** Uses OpenAI GPT-4.1 mini and Playwright to explore and execute a customer lookup workflow.
- **Automatically generated capability:** Compiles observed browser actions into a versioned, parameterized JSON artifact.
- **Deterministic replay:** Executes the generated workflow using Playwright without additional LLM calls.
- **Business outcome classification:** Distinguishes successful lookups from customers who do not exist.
- **Failure handling:** Records invalid inputs and unavailable websites as failures.
- **Human-in-the-loop recovery:** Supports manual correction in the same browser session after a simulated interaction failure.
- **Evidence:** Produces JSON event logs and browser screenshots.

## Technology Stack

Python, FastAPI, Playwright, OpenAI API, JSON, and Uvicorn.

## Project Structure

```text
interface-ai-automation/
├── app.py
├── discovery_agent.py
├── replay_agent.py
├── human_handoff.py
├── test_automation.py
├── capabilities/
│   └── customer_lookup_v1.json
├── evidence/
├── .gitignore
└── README.md
```

## Setup

Requires Python 3.12 or a compatible version.

Create a virtual environment:

```powershell
python -m venv .venv
```

Install the required packages:

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn playwright openai python-dotenv
```

Install the Playwright browser:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Create a `.env` file containing:

```text
OPENAI_API_KEY=your_api_key_here
```

Never commit the `.env` file or expose your API key.

## Running the Application

In Terminal 1:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:8000.

Keep the server running.

## AI Discovery

In Terminal 2:

```powershell
.\.venv\Scripts\python.exe discovery_agent.py
```

The discovery agent uses an LLM to select browser actions, verifies the observed result, and generates:

```text
capabilities/customer_lookup_v1.json
```

Discovery evidence is saved in the `evidence` directory.

## Deterministic Replay

Replay the generated capability for another customer:

```powershell
.\.venv\Scripts\python.exe replay_agent.py 67890
```

The replay engine executes the capability without using the LLM.

## Business Outcome Test

```powershell
.\.venv\Scripts\python.exe replay_agent.py 99999
```

Expected outcome:

```json
{
  "outcome": "customer_not_found",
  "customer_id": "99999",
  "customer_name": null,
  "balance": null
}
```

## Human-in-the-Loop Recovery

```powershell
.\.venv\Scripts\python.exe replay_agent.py 67890 --simulate-failure
```

When prompted, complete the pending search action in the open browser, then return to the terminal and press Enter.

The engine validates the resulting browser state before resuming.

## Failure Scenarios

Invalid input:

```powershell
.\.venv\Scripts\python.exe replay_agent.py ABC
```

Expected: validation failure.

Unavailable website: stop `app.py` and run a replay.

Expected: connection failure recorded as `replay_failed`.

Restart `app.py` after the test.

## Automated Tests

```powershell
.\.venv\Scripts\python.exe test_automation.py
```

The initial suite contains six artifact and evidence-directory checks. Browser workflow scenarios have also been tested manually.

## Evidence

The `evidence/` directory contains discovery and replay logs, screenshots, and human-handoff evidence generated during execution.

## Scope and Limitations

This is a demonstration against a local fictional banking website, not a production banking integration.

The capability compiler and replay engine are tailored to the demonstrated customer lookup workflow. Production deployment would require stronger authorization, secret management, sensitive-data redaction, tenant isolation, audit retention policies, and approval controls for consequential actions.

The project demonstrates a browser-based human handoff; it does not implement a complete production approval or access-management system.
