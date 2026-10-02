# Jev decision flow

The mock is deterministic development behavior, not a substitute for TypeSafe's model. The `typesafe` adapter follows the official [System One API](https://docs.typesafe.ai/api): it POSTs to `https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer TYPESAFE_API_KEY` and JSON containing `state`, `model`, and `questions`. The `selected_action` question is a Choice over the app's allowed actions. TypeSafe returns `answers.selected_action.choice`, `confidence`, and `probabilities`; the adapter validates that shape and maps the selected action into the application's typed decision model.

The outbound request includes generated SQL, user request, security validation and available actions inside the structured `state`. A concise question instruction explains when each action applies; Choice criteria define the actions. The `JEV_BASE_URL` and `JEV_MODEL` settings allow configuring the documented endpoint and model alias without changing code.

```json
{
	"state": {
		"application_state": {"generated_sql": "SELECT COUNT(*) FROM customers", "security": "passed"},
		"user_request": "Count customers",
		"available_actions": ["execute_sql", "retry", "ask_clarification", "reject", "human_review", "select_tool"]
	},
	"model": "jev-latest",
	"questions": {
		"selected_action": {
			"type": "choice",
			"instructions": "Choose the single best next application action from the listed options.",
			"criteria": {"execute_sql": "Run the generated SQL only when the request is clear and the precheck allows it."}
		}
	}
}
```

The Choice `criteria` map contains all six actions in a real request. A response has a `model`, an `answers` map keyed by question ID, and usage metadata; each Choice answer includes `choice`, `confidence`, and a probability distribution. The adapter does not treat a Jev choice as SQL authorization: the existing router threshold and SQL security validation still run before execution.

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