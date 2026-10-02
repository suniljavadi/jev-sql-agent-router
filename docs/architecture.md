# Architecture

```text
Streamlit -> FastAPI -> LLM provider -> Jev provider -> confidence router
                                           |                |
                                           |                +-> review queue / clarification / reject / schema tool
                                           +-> policy check -> SQL executor -> SQLite / PostgreSQL
                                                               |
                                                               +-> audit_events + human_reviews
```

The LLM proposes SQL or an intent. Jev receives the request, SQL/intent, security status, available actions and decision questions. The router can override a proposed execute with human review below the configured threshold. The validator runs before Jev and again before execution; SQL is never executed solely because a provider approves it. A non-execute action never runs generated SQL. The `select_tool` action invokes a read-only schema inspector restricted to configured business tables.

`app/services/jev_service.py` owns the Jev transport mapping. `app/services/agent_service.py` owns orchestration; `app/services/sql_service.py` owns database retries and timeouts. Alembic applies versioned schema changes before startup seeding. Each request produces an `audit_events` row even when providers or execution fail. FastAPI uses injected sessions and providers to support unit tests without network services.

A `review_required` audit event creates a linked pending `human_reviews` row in the same transaction. A reviewer-key-protected operation claims it once; rejection creates a separate audit event without executing SQL. Approval revalidates the saved SQL using strict read-only rules, executes it with the normal timeout and row limit, and writes a resolution audit event. The original audit event is never overwritten. If a process dies after claiming but before resolving, the review remains `processing` for operational recovery; production deployments need a reconciler and an identity provider.