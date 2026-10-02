# Jev decision flow

The mock is deterministic development behavior, not a substitute for TypeSafe's model. The `typesafe` adapter POSTs to `JEV_BASE_URL` with a bearer key and JSON fields `model`, `application_state`, `user_request`, `available_actions`, `decision_questions`. It validates the JSON response as `JevDecision`. **This is an application-owned adapter contract, not a claim about the official Jev API.** Confirm the vendor's URL, authentication, payload and response schema before connecting a live account; change only the adapter when necessary.

| Proposed action | Router outcome |
| --- | --- |
| execute_sql, confidence >= 0.90 | Execute after security validation |
| execute_sql, 0.70 <= confidence < 0.90 | Execute after strict read-only validation |
| execute_sql, confidence < 0.70 | Human review, no execution |
| retry | Execute with bounded retries for transient DB errors only |
| ask_clarification | Ask for a more specific request, no execution |
| reject | Reject, no execution |
| human_review | Review required, no execution |
| select_tool | Inspect the allowlisted business schema, no generated SQL execution |

If the Jev API times out, returns an HTTP error or malformed JSON, the request fails closed and is audited. The sample mock triggers `low confidence`, `medium confidence`, `retry`, `clarify`, `review`, `reject`, `tool` by keyword; other supported customer queries default to a high confidence read-only decision.