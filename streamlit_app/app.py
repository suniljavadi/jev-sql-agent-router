import os

import httpx
import streamlit as st


st.set_page_config(page_title="Jev | SQL Agent", page_icon="◆", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f6f8f7; color: #152b2a; }
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: 0; }
.block-container { max-width: 1200px; padding-top: 2.25rem; }
.eyebrow { color: #bc5938; text-transform: uppercase; font-size: .75rem; font-weight: 700; letter-spacing: .15em; }
.brand { font: 700 2.5rem 'Space Grotesk', sans-serif; margin: .1rem 0 .3rem; }
.stage { border-top: 3px solid #157a70; background: #e9f1ee; padding: .8rem .65rem; font-weight: 700; text-align: center; min-height: 3.8rem; }
.stButton button[kind="primary"] { background: #155e57; border: 0; color: white; }
div[data-testid="stMetric"] { border-top: 2px solid #bc5938; padding-top: .5rem; }
code { font-family: 'Space Mono', monospace; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Connection")
    api_url = st.text_input("API URL", value=os.getenv("API_URL", "http://localhost:8000"))
    api_key = st.text_input("Query API key", type="password")
    reviewer_key = st.text_input("Reviewer API key", type="password")
    if st.button("Check health", icon="🔄"):
        try:
            response = httpx.get(f"{api_url.rstrip('/')}/health", timeout=5)
            response.raise_for_status()
            st.success("API online")
        except httpx.HTTPError:
            st.error("API unavailable")

st.markdown('<div class="eyebrow">Decision operations / SQL</div>', unsafe_allow_html=True)
st.markdown('<div class="brand">Jev SQL Agent Router</div>', unsafe_allow_html=True)
st.caption("Enterprise query workspace")

with st.form("query_form"):
    user_request = st.text_area("Natural language request", value="List customers",
                                height=110, placeholder="Ask a question about customers or revenue")
    submitted = st.form_submit_button("Run request", type="primary", icon="▶")

if submitted:
    if not user_request.strip():
        st.warning("Enter a request")
    else:
        try:
            with st.spinner("Processing request"):
                response = httpx.post(f"{api_url.rstrip('/')}/api/query",
                                      json={"user_request": user_request},
                                      headers={"X-API-Key": api_key or reviewer_key} if api_key or reviewer_key else {},
                                      timeout=30)
                response.raise_for_status()
                st.session_state["result"] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            st.error(f"API request failed: {type(exc).__name__}")

result = st.session_state.get("result")
if result:
    st.divider()
    st.subheader("Decision flow")
    final_stage = "Tool" if result.get("selected_action") == "select_tool" else (
        "SQL" if result.get("execution_status") == "success" else "Hold")
    for column, stage in zip(st.columns(5), ["01  Request", "02  LLM", "03  Jev", "04  Router", f"05  {final_stage}"]):
        with column:
            st.markdown(f'<div class="stage">{stage}</div>', unsafe_allow_html=True)

    decision = result.get("jev_decision") or {}
    first, second, third, fourth = st.columns(4)
    first.metric("Status", result["execution_status"].replace("_", " ").title())
    second.metric("Confidence", f"{decision.get('confidence', 0):.0%}" if decision else "N/A")
    third.metric("Selected action", (result.get("selected_action") or "none").replace("_", " ").title())
    fourth.metric("Execution time", f"{result['execution_time_ms']:.2f} ms")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Generated SQL")
        st.code(result.get("generated_sql") or "No SQL generated", language="sql")
        st.subheader("Tool result" if result.get("selected_action") == "select_tool" else "SQL execution result")
        if result.get("rows"):
            st.dataframe(result["rows"], use_container_width=True, hide_index=True)
        else:
            st.info(result["execution_status"].replace("_", " ").title())
    with right:
        st.subheader("Decision")
        st.write("Jev proposal:", (decision.get("selected_action") or "Unavailable").replace("_", " ").title())
        st.write("Security validation:", result["security_validation"].replace("_", " ").title())
        st.subheader("Why this action")
        st.write(result["explanation"])
        if decision.get("reason") and decision["reason"] != result["explanation"]:
            st.caption(f"Jev reason: {decision['reason']}")
        if result.get("error_message"):
            st.error(result["error_message"])
        st.subheader("Audit")
        st.write("Record:", result["audit_id"])
        st.write("Timestamp:", result["timestamp"])

if reviewer_key:
    st.divider()
    st.subheader("Review queue")
    if st.session_state.get("review_outcome"):
        st.success(st.session_state.pop("review_outcome"))
    try:
        pending_response = httpx.get(f"{api_url.rstrip('/')}/api/reviews",
                                     headers={"X-API-Key": reviewer_key}, timeout=10)
        pending_response.raise_for_status()
        pending = pending_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Review queue unavailable: {type(exc).__name__}")
        pending = []

    if pending:
        selected_id = st.selectbox("Pending audit record", [item["audit_id"] for item in pending])
        selected = next(item for item in pending if item["audit_id"] == selected_id)
        st.write(selected["user_request"])
        st.code(selected.get("generated_sql") or "No SQL generated", language="sql")
        st.write("Jev confidence:", f"{selected['confidence']:.0%}" if selected["confidence"] is not None else "N/A")
        with st.form("review_resolution"):
            reviewer = st.text_input("Reviewer name", max_chars=100)
            outcome = st.radio("Resolution", ["Approve", "Reject"], horizontal=True)
            confirmed = st.checkbox("I reviewed the generated SQL")
            resolve_clicked = st.form_submit_button("Resolve review", type="primary",
                disabled=not reviewer.strip() or (outcome == "Approve" and not confirmed))
        if resolve_clicked:
            try:
                action = "approve" if outcome == "Approve" else "reject"
                resolution = httpx.post(f"{api_url.rstrip('/')}/api/reviews/{selected_id}/{action}",
                                        headers={"X-API-Key": reviewer_key},
                                        json={"reviewer": reviewer}, timeout=30)
                resolution.raise_for_status()
                st.session_state["review_outcome"] = f"Review {selected_id}: {resolution.json()['status']}"
                st.rerun()
            except (httpx.HTTPError, ValueError) as exc:
                st.error(f"Review resolution failed: {type(exc).__name__}")
    else:
        st.info("No pending reviews")