# API examples

Start the API as shown in the README. Then:

```powershell
curl.exe -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"user_request":"Count customers"}'
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/api/decisions/1
```

Successful decisions contain `audit_id`, `generated_sql`, `jev_decision` (including `confidence`, flags and `reason`), `selected_action`, `security_validation`, `execution_status`, `rows` and `execution_time_ms`. The audit lookup returns the same envelope. A blocked write request returns `security_validation: blocked` and never reaches the SQL executor. Unknown audit IDs return 404; invalid input returns 422.

To resolve a review, set `REVIEWER_API_KEY` in `.env` and restart the API. Also set `$env:REVIEWER_API_KEY` to that same value in the shell running these commands; `.env` is loaded by the Python process, not PowerShell. Provide it as `X-API-Key`:

```powershell
curl.exe -H "X-API-Key: $env:REVIEWER_API_KEY" http://localhost:8000/api/reviews
curl.exe -X POST http://localhost:8000/api/reviews/1/approve -H "Content-Type: application/json" -H "X-API-Key: $env:REVIEWER_API_KEY" -d '{"reviewer":"Analyst"}'
curl.exe -X POST http://localhost:8000/api/reviews/1/reject -H "Content-Type: application/json" -H "X-API-Key: $env:REVIEWER_API_KEY" -d '{"reviewer":"Analyst"}'
curl.exe -H "X-API-Key: $env:REVIEWER_API_KEY" http://localhost:8000/api/reviews/1
```

Use the `audit_id` returned by a `review_required` query, not necessarily `1`. Approval and rejection are mutually exclusive and produce a `resolution_audit_id`. Look it up via `/api/decisions/{id}`. Missing reviewer keys return 401; already claimed reviews and unsafe approvals return 409; unknown reviews return 404. With `API_KEY` set, also pass its value as `X-API-Key` to `/api/query` and `/api/decisions/{id}`. The reviewer key works for those endpoints as well. Health remains public.