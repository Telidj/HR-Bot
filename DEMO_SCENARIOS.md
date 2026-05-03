# Demo Scenarios

## Employee Flow
1. Ask: `What can you help with?`
2. Select: `1` or `PTO`
3. Ask: `How far in advance should I request vacation?`
4. Ask: `Can I request partial-day PTO?`
5. Create a request: `I need vacation from 04/10 to 04/12`
6. Confirm that the assistant creates a workflow request and returns the request ID.

## Workflow Request Flow
1. Create an access request: `I need access to the payroll system`
2. Create an equipment request: `Please replace my broken laptop`
3. Create an onboarding blocker: `I am blocked during onboarding because my account setup is not complete`
4. Open `View My Requests` in the employee UI or `Workflow Requests` in the admin UI.
5. Confirm that the new requests show their type, status, assignee, and original comment.

## Manager Flow
1. Ask: `How do schedule changes work?`
2. Ask: `Do overtime hours require approval?`
3. Ask: `How should sick leave be reported?`
4. Use the response to explain manager review expectations and policy-backed answers.

## Admin Flow
1. Open the Streamlit admin console.
2. Load the current system prompt.
3. Refresh the document list.
4. Rebuild the vector index after a document change.
5. Load logs and show that user text can be masked.
6. Load workflow requests and update one request status from `pending` to `approved`.

## Teams Flow
1. In Teams chat, type: `help`
2. Ask: `How often are salaries paid?`
3. Ask: `How do I request VPN access?`
4. Type: `requests` to show workflow history.
5. Type: `request <request_id_fragment>` to inspect one of your workflow requests.
6. In Teams admin, authenticate with `login <ADMIN_TOKEN>`.
7. Run: `docs list`, `docs preview Payroll_FAQ.md`, `logs 10`, and `requests 10 status pending`.
8. Run: `request get <request_id_fragment>` to inspect the user, owner, status, date, and comment for one request.

## Suggested Narrative
- Start with employee self-service.
- Show policy-grounded answers rather than generic LLM output.
- Transition into workflow creation, including access, equipment, and onboarding requests.
- End with administration and auditability.
- If useful, close with the Teams channel to show multi-interface support.
