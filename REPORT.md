# 1. Architecture

The prototype separates AI-assisted workflow discovery from deterministic execution.

During discovery, an OpenAI GPT-4.1 mini model selects browser actions based on the current interface. Playwright executes those actions against a local FastAPI banking application. The discovery process observes the resulting browser state, verifies the customer lookup, and generates a reusable capability artifact.

During replay, the execution engine loads the generated JSON capability and performs the workflow through Playwright without invoking an LLM.

The architecture consists of:

- **Demo application:** FastAPI-based fictional banking customer lookup.
- **Discovery agent:** LLM-driven browser interaction and observation.
- **Capability compiler:** Converts observed actions into a reusable JSON workflow.
- **Replay engine:** Deterministic browser execution with validation checkpoints.
- **Human handoff:** Allows manual recovery in the same browser session.
- **Evidence layer:** Records structured execution events and screenshots.

This separation limits model variability to discovery while keeping repeated execution predictable and auditable.

# 2. Artifact schema

The discovery agent generates `capabilities/customer_lookup_v1.json`.

The artifact includes a capability identifier, version, input and output definitions, and an ordered sequence of executable steps.

Its input is a five-digit customer ID. The output contains a business outcome, customer ID, customer name, and account balance.

The workflow contains three principal steps:

1. Enter the customer ID.
2. Submit the customer search.
3. Extract the customer details or not-found outcome.

The customer ID is parameterized using `{{customer_id}}`, allowing the same discovered capability to be reused for different customers.

The replay engine validates the artifact version and supported execution configuration before running it.

The schema is intentionally limited to the demonstrated workflow. A broader implementation would require a formal schema definition, compatibility rules, migration support, and additional action types.

# 3. Determinism & error handling

Replay executes recorded actions without calling an LLM. It uses constrained Playwright interactions and checks the browser state after key steps.

The system distinguishes three categories of results.

**Business outcomes:** A valid customer lookup may return customer information or `customer_not_found`. The latter is a legitimate result, not an automation failure.

**Recoverable interaction failures:** When a supported interaction fails, the automation can request human assistance. The operator completes the pending action in the existing browser session, after which the system validates the resulting state before resuming.

**Hard failures:** Invalid customer IDs and an unavailable application cause the replay to stop and record `replay_failed`.

The prototype was manually tested for successful replay, customer-not-found handling, invalid input, website unavailability, and simulated human-assisted recovery.

A six-test automated suite also verifies basic artifact properties and evidence-directory availability. These tests are not a comprehensive browser regression suite.

# 4. Heterogeneity & multi-tenant

The current implementation uses Playwright to automate a local web application. The general architecture could be extended to other web applications through additional action adapters and target-specific capability schemas.

Legacy applications and desktop software would require separate integration approaches, such as supported accessibility APIs, desktop automation frameworks, or approved application-specific interfaces.

These integrations are not implemented in the prototype.

For multi-tenant operation, a production system should separate capability ownership, execution credentials, browser sessions, logs, and stored evidence by tenant.

Capabilities should be authorized for specific applications and tenant contexts. Tenant-specific secrets and sensitive data must not be embedded directly in reusable artifacts.

The current prototype demonstrates a single local application and does not implement production multi-tenant isolation.

# 5. Escalation & handoff

The replay engine includes a human-in-the-loop recovery mechanism for supported interaction failures.

The demonstrated flow is:

1. The automation encounters a simulated browser interaction failure.
2. Execution pauses and requests operator assistance.
3. The existing browser session remains available.
4. The operator completes the pending search action manually.
5. The operator returns to the terminal and confirms completion.
6. The automation verifies the browser state.
7. Execution resumes and records the final business outcome.

This approach preserves the active browser context rather than restarting the workflow from the beginning.

The evidence log includes handoff and resumption events.

The current handoff mechanism is terminal-driven. It does not include production operator authentication, escalation queues, time-limited approvals, or independent approval verification.

# 6. Safety

The prototype applies several safety restrictions.

- **Restricted target:** Browser automation is limited to the local demonstration application.
- **Action allowlisting:** Replay uses supported browser actions and constrained semantic targets.
- **Input validation:** Customer IDs must match the expected five-digit format.
- **Artifact validation:** The replay engine checks the capability version and supported execution parameters.
- **Execution checkpoints:** The engine validates important browser states rather than assuming an action succeeded.
- **Credential separation:** The OpenAI API key is stored in `.env`, which is excluded from version control.
- **Auditable evidence:** Structured logs and screenshots support inspection of execution results.

The demo does not perform financial transfers, account changes, or other irreversible banking operations.

For production use, irreversible or high-impact actions should require explicit authorization and, where appropriate, a verified human approval step before execution.

Customer records in this demonstration are fictional. Production use would additionally require personally identifiable information redaction, encrypted evidence storage, retention policies, access controls, and secure credential management.

# 7. Cuts

The implementation deliberately prioritizes an end-to-end demonstration of discovery, artifact generation, deterministic replay, outcome classification, and human recovery.

The following features are outside the current prototype:

- General-purpose discovery across arbitrary applications.
- Production-grade schema migrations and capability registries.
- Desktop and legacy-system execution adapters.
- Multi-tenant authorization and infrastructure isolation.
- Enterprise secret management and sensitive-data redaction.
- Persistent human approval queues and operator authentication.
- Automated browser regression tests covering every execution path.
- Distributed scheduling, concurrency control, and large-scale monitoring.

These omissions keep the prototype focused on demonstrating the core architectural pattern while identifying the additional controls required for production deployment.