"""Unified AI-CIO application — one journey, one user, one shell."""
from __future__ import annotations

import math
import time

import streamlit as st

import client

STEPS = [
    ("welcome", "Start"),
    ("psychometrics", "Understand me"),
    ("finances", "My finances"),
    ("goals", "My goals"),
    ("portfolio", "My portfolio"),
    ("review", "Review"),
    ("analysis", "Analysis"),
    ("decide", "Review & decide"),
]
STEP_IDS = [item[0] for item in STEPS]

st.set_page_config(page_title="AI-CIO", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-family: Inter, system-ui, sans-serif; }
    .block-container { max-width: 980px; padding-top: 1.4rem; }
    #MainMenu, footer { visibility: hidden; }
    .aic-shell {
        background: #0F172A; color: #F8FAFC; border-radius: 16px;
        padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    }
    .aic-kicker { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: #94A3B8; }
    .aic-title { font-size: 1.55rem; font-weight: 800; margin: 0.15rem 0; }
    .aic-sub { color: #CBD5E1; margin: 0; }
    .fact { border: 1px solid #E2E8F0; border-radius: 12px; padding: 0.85rem 1rem; background: white; margin-bottom: 0.5rem; }
    .tag { display: inline-block; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
           text-transform: uppercase; border-radius: 999px; padding: 0.12rem 0.55rem; margin-right: 0.35rem; }
    .known { background: #DCFCE7; color: #166534; }
    .unknown { background: #FEE2E2; color: #991B1B; }
    .user { background: #DBEAFE; color: #1E40AF; }
    .cas { background: #EDE9FE; color: #5B21B6; }
    .system { background: #FFEDD5; color: #9A3412; }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state():
    defaults = {
        "step": "welcome",
        "user_id": None,
        "user_name": "",
        "session_id": None,
        "questions": [],
        "question_index": 0,
        "selected_answers": {},
        "question_start": None,
        "profile": None,
        "observations": [],
        "error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go(step: str):
    st.session_state.step = step
    st.session_state.error = None
    if step == "finances":
        for key in (
            "income_input",
            "expenses_input",
            "liquid_input",
            "liability_name",
            "liability_balance",
            "liability_payment",
            "has_loan",
        ):
            st.session_state.pop(key, None)
    if st.session_state.user_id:
        try:
            client.set_step(st.session_state.user_id, step)
        except client.ApiError:
            pass
    st.rerun()


def shell():
    idx = STEP_IDS.index(st.session_state.step) if st.session_state.step in STEP_IDS else 0
    st.markdown(
        f"""
        <div class="aic-shell">
          <div class="aic-kicker">AI-CIO</div>
          <div class="aic-title">Your financial decision journey</div>
          <p class="aic-sub">One conversation. We learn who you are, what you own, and what you are working toward — then stop for your review. We never place trades.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.user_id:
        st.caption(f"Signed in as {st.session_state.user_name} · user {st.session_state.user_id}")
    st.progress((idx) / (len(STEPS) - 1), text=f"Step {idx + 1} of {len(STEPS)} — {STEPS[idx][1]}")
    if st.session_state.error:
        st.error(st.session_state.error)


def nav(back=None, continue_label=None, on_continue=None, disabled=False):
    left, right = st.columns(2)
    with left:
        if back and st.button("Back", use_container_width=True):
            go(back)
    with right:
        if continue_label and st.button(continue_label, type="primary", use_container_width=True, disabled=disabled):
            if on_continue:
                on_continue()
            else:
                go(continue_label)


def confidence_for(question: dict, elapsed_ms: int) -> int:
    word_count = max(1, len(question["text"].split()))
    target = max(10.0, min(45.0, 7.0 + word_count * 0.8))
    seconds = max(0.0, elapsed_ms / 1000)
    timing = 100 * math.exp(-((seconds - target) / (target * 0.65)) ** 2)
    completion = min(100.0, seconds / target * 100)
    return round(max(0.0, min(100.0, timing * 0.75 + completion * 0.25)))


def page_welcome():
    st.subheader("Let’s start with you")
    st.write("AI-CIO will walk you through a short questionnaire, your cash situation, goals, and a CAS upload. You can skip a section if you do not know the answer. We will label anything missing as unknown.")
    if st.session_state.user_id:
        st.info(f"Continuing as {st.session_state.user_name} (user {st.session_state.user_id}). One identity for the whole journey.")
        if st.button("Continue", type="primary"):
            go("psychometrics")
        return
    name = st.text_input("What should we call you?", value=st.session_state.user_name)
    if st.button("Begin", type="primary"):
        if not name.strip():
            st.session_state.error = "Please enter a name to continue."
            st.rerun()
        try:
            user = client.create_user(name.strip())
            assessment = client.start_assessment(user["id"])
            questions = client.load_questions()
        except client.ApiError as exc:
            st.session_state.error = str(exc)
            st.rerun()
            return
        st.session_state.user_id = user["id"]
        st.session_state.user_name = user["name"]
        st.session_state.session_id = assessment["id"]
        st.session_state.questions = questions.get("questions") or []
        st.session_state.question_index = 0
        st.session_state.selected_answers = {}
        st.session_state.question_start = time.time()
        if not st.session_state.questions:
            st.session_state.error = "The API did not return questions. Start the API and seed the instrument."
            st.rerun()
            return
        go("psychometrics")


def page_psychometrics():
    questions = st.session_state.questions
    index = st.session_state.question_index
    if st.session_state.profile:
        st.subheader("How you tend to decide")
        st.write("This is a behavioural sketch from your answers, not a diagnosis and not an investment recommendation.")
        for observation in st.session_state.observations:
            st.markdown(f"- {observation}")
        if st.button("Continue to finances", type="primary"):
            go("finances")
        return
    if index >= len(questions):
        go("finances")
        return
    question = questions[index]
    st.progress((index + 1) / len(questions), text=f"Question {index + 1} of {len(questions)}")
    st.subheader("A few questions about how you decide")
    st.write(question["text"])
    selected = st.session_state.selected_answers.get(question["id"])
    for option in question["options"]:
        label = option["text"]
        if st.button(("✓ " if selected == option["id"] else "") + label, key=f"{question['id']}_{option['id']}", use_container_width=True):
            st.session_state.selected_answers[question["id"]] = option["id"]
            st.rerun()
    selected = st.session_state.selected_answers.get(question["id"])
    if st.button("Submit answer", type="primary", disabled=selected is None):
        elapsed = int((time.time() - (st.session_state.question_start or time.time())) * 1000)
        try:
            client.submit_response(
                st.session_state.session_id,
                question["id"],
                selected,
                confidence_for(question, elapsed),
                elapsed,
            )
        except client.ApiError as exc:
            st.session_state.error = str(exc)
            st.rerun()
            return
        st.session_state.question_index += 1
        st.session_state.question_start = time.time()
        if st.session_state.question_index >= len(questions):
            try:
                profile = client.complete_assessment(st.session_state.session_id)
                observations = client.get_observations(st.session_state.session_id)
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
            st.session_state.profile = profile
            st.session_state.observations = observations.get("observations", [])
        st.rerun()


def page_finances():
    st.subheader("Your cash situation")
    st.write("Enter monthly figures if you know them. Leave a field blank to keep it unknown — we will not guess.")
    if "income_input" not in st.session_state:
        saved = {}
        if st.session_state.user_id:
            try:
                saved = client.get_finances(st.session_state.user_id)
            except client.ApiError:
                saved = {}
        first = (saved.get("liabilities") or [{}])[0]
        st.session_state.income_input = saved.get("income") or ""
        st.session_state.expenses_input = saved.get("expenses") or ""
        st.session_state.liquid_input = saved.get("liquid") or ""
        st.session_state.has_loan = bool(saved.get("liabilities"))
        st.session_state.liability_name = first.get("name") or ""
        st.session_state.liability_balance = first.get("balance") or ""
        st.session_state.liability_payment = first.get("monthly_payment") or ""
    income = st.text_input("Typical monthly take-home income (₹)", key="income_input", placeholder="Optional")
    expenses = st.text_input("Typical monthly expenses (₹)", key="expenses_input", placeholder="Optional")
    liquid = st.text_input("Cash or liquid savings (₹)", key="liquid_input", placeholder="Optional")
    has_loan = st.checkbox("I have a loan or other liability", key="has_loan")
    liabilities = []
    if has_loan:
        name = st.text_input("Liability name", key="liability_name", placeholder="Home loan, education loan…")
        balance = st.text_input("Outstanding balance (₹)", key="liability_balance")
        payment = st.text_input("Monthly payment (₹), optional", key="liability_payment")
        if name.strip() and balance.strip():
            liabilities.append({"name": name.strip(), "balance": balance.strip(), "monthly_payment": payment.strip() or None})
    cols = st.columns(3)
    with cols[0]:
        if st.button("Back"):
            go("psychometrics")
    with cols[1]:
        if st.button("I don’t know — skip"):
            try:
                client.skip_finances(st.session_state.user_id)
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
            go("goals")
    with cols[2]:
        if st.button("Save and continue", type="primary"):
            try:
                client.put_finances(
                    st.session_state.user_id,
                    {
                        "income": income.strip() or None,
                        "expenses": expenses.strip() or None,
                        "liquid": liquid.strip() or None,
                        "cadence": "monthly",
                        "liabilities": liabilities,
                    },
                )
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
            go("goals")


def page_goals():
    st.subheader("What you are working toward")
    st.write("Add one or more goals. Amounts you leave blank stay unknown.")
    existing = []
    try:
        existing = client.list_goals(st.session_state.user_id)
    except client.ApiError as exc:
        st.session_state.error = str(exc)
    for goal in existing:
        amount = goal.get("target_amount") or "unknown"
        st.markdown(f"**{goal['name']}** · {goal.get('goal_type')} · target ₹{amount} · {goal.get('priority')} priority")
        if st.button("Remove", key=f"del_{goal['id']}"):
            client.remove_goal(st.session_state.user_id, goal["id"])
            st.rerun()
    with st.form("goal_form", clear_on_submit=True):
        name = st.text_input("Goal name")
        goal_type = st.selectbox("Type", ["emergency", "retirement", "education", "home", "other"])
        target_amount = st.text_input("Target amount (₹)", placeholder="Optional")
        target_date = st.text_input("Target date (YYYY-MM-DD)", placeholder="Optional")
        current_funding = st.text_input("Already saved toward this (₹)", placeholder="Optional")
        priority = st.selectbox("Priority", ["high", "medium", "low"], index=1)
        flexibility = st.selectbox("Flexibility", ["fixed", "somewhat", "flexible"], index=1)
        submitted = st.form_submit_button("Add goal")
        if submitted:
            try:
                client.add_goal(
                    st.session_state.user_id,
                    {
                        "name": name,
                        "goal_type": goal_type,
                        "target_amount": target_amount or None,
                        "target_date": target_date or None,
                        "current_funding": current_funding or None,
                        "priority": priority,
                        "flexibility": flexibility,
                    },
                )
            except client.ApiError as exc:
                st.session_state.error = str(exc)
            st.rerun()
    cols = st.columns(3)
    with cols[0]:
        if st.button("Back"):
            go("finances")
    with cols[1]:
        if st.button("Skip for now"):
            try:
                client.skip_goals(st.session_state.user_id)
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
            go("portfolio")
    with cols[2]:
        if st.button("Continue", type="primary"):
            go("portfolio")


def page_portfolio():
    st.subheader("Your investment statement")
    st.write("Upload an MFCentral CAS PDF. We extract holdings we can read and flag anything we cannot. Nothing is invented.")
    uploaded = st.file_uploader("CAS PDF", type=["pdf"])
    if uploaded and st.button("Process statement", type="primary"):
        with st.spinner("Reading statement…"):
            try:
                result = client.upload_cas(st.session_state.user_id, uploaded.name, uploaded.getvalue())
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
        st.success(
            f"Stored document {result['document_id']}: {result['holdings']} holdings, {result['transactions']} transactions."
        )
        if result.get("warnings"):
            st.warning("Some pages need review: " + "; ".join(result["warnings"]))
    try:
        holdings = client.get_holdings(st.session_state.user_id)
    except client.ApiError:
        holdings = []
    if holdings:
        st.write("Extracted holdings (CAS-derived)")
        st.dataframe(
            [
                {
                    "AMC": row["amc"],
                    "Fund": row["scheme_name"],
                    "Value": row["valuation"],
                    "Page": row["source_page"],
                }
                for row in holdings
            ],
            use_container_width=True,
            hide_index=True,
        )
    cols = st.columns(3)
    with cols[0]:
        if st.button("Back"):
            go("goals")
    with cols[1]:
        if st.button("Skip for now"):
            try:
                client.skip_portfolio(st.session_state.user_id)
            except client.ApiError as exc:
                st.session_state.error = str(exc)
                st.rerun()
                return
            go("review")
    with cols[2]:
        if st.button("Continue to review", type="primary"):
            go("review")


def _tag(status: str, source: str | None) -> str:
    bits = [f'<span class="tag {status}">{status}</span>']
    if source == "user-provided":
        bits.append('<span class="tag user">user-provided</span>')
    elif source == "cas-derived":
        bits.append('<span class="tag cas">cas-derived</span>')
    elif source == "system-derived":
        bits.append('<span class="tag system">system-derived</span>')
    return "".join(bits)


def page_review():
    st.subheader("Review your financial profile")
    st.write("This is what we know so far. Unknown means we do not have the fact — not that it is zero.")
    try:
        review = client.get_review(st.session_state.user_id)
    except client.ApiError as exc:
        st.error(str(exc))
        return
    complete = review["completeness"]
    st.markdown("#### Data completeness")
    st.write(
        f"Questionnaire: {'done' if complete['psychometric'] else 'missing'} · "
        f"Income: {'known' if complete['income'] else 'unknown'} · "
        f"Goals: {'known' if complete['goals'] else 'unknown'} · "
        f"Portfolio: {'known' if complete['portfolio'] else 'unknown'}"
    )
    st.caption("Unknown means we do not have the fact. It is not treated as zero.")
    st.markdown("#### Behaviour")
    behaviour = review["behaviour"]
    st.markdown(_tag(behaviour["status"], behaviour.get("source")), unsafe_allow_html=True)
    if behaviour["status"] == "known":
        for line in behaviour.get("observations") or []:
            st.write(line)
        st.caption("A higher bias-dimension score means more adaptive / less biased behaviour, per the questionnaire.")
    st.markdown("#### Financial situation")
    for label, key in (("Income", "income"), ("Expenses", "expenses"), ("Liquid savings", "liquid")):
        fact = review["finances"][key]
        st.markdown(
            f'<div class="fact">{_tag(fact["status"], fact.get("source"))} {label}: {fact["value"] if fact["value"] is not None else "unknown"}</div>',
            unsafe_allow_html=True,
        )
    liabilities = review["finances"]["liabilities"]
    if liabilities["status"] == "known":
        for item in liabilities["value"]:
            st.write(f"- {item['name']}: ₹{item['balance']}")
    else:
        st.write("Liabilities: unknown or none recorded")
    st.markdown("#### Goals")
    if review["goals"]["status"] == "known":
        for goal in review["goals"]["items"]:
            st.write(f"- {goal['name']} ({goal['goal_type']}) target ₹{goal['target_amount'] or 'unknown'}")
    else:
        st.write("No goals recorded.")
    st.markdown("#### Portfolio")
    total = review["portfolio"]["total_value"]
    st.markdown(
        f'<div class="fact">{_tag(total["status"], total.get("source"))} Total extracted value: {total["value"] or "unknown"}</div>',
        unsafe_allow_html=True,
    )
    for row in review["portfolio"]["holdings"]:
        st.caption(f"{row['scheme_name']} · ₹{row['valuation']} · page {row['source_page']}")
    st.markdown("#### Correct something")
    edits = st.columns(4)
    with edits[0]:
        if st.button("Edit finances"):
            go("finances")
    with edits[1]:
        if st.button("Edit goals"):
            go("goals")
    with edits[2]:
        if st.button("Edit portfolio"):
            go("portfolio")
    with edits[3]:
        if st.button("Back to questionnaire summary"):
            go("psychometrics")
    cols = st.columns(2)
    with cols[0]:
        if st.button("Back"):
            go("portfolio")
    with cols[1]:
        if st.button("Continue", type="primary"):
            go("analysis")


def page_analysis():
    st.subheader("AI-CIO analysis")
    st.info(
        "This version records and reviews your profile. Specialist analysis, a Portfolio Conference, "
        "and an action plan for a sum such as ₹1,00,000 are not generated yet — so we will not invent a recommendation."
    )
    try:
        review = client.get_review(st.session_state.user_id)
        missing = [name for name, ok in review["completeness"].items() if ok is False and name in {"psychometric", "income", "goals", "portfolio"}]
        if missing:
            st.write("Still unknown: " + ", ".join(missing) + ". You can go back and add them, or continue with gaps labelled.")
    except client.ApiError:
        pass
    cols = st.columns(2)
    with cols[0]:
        if st.button("Back"):
            go("review")
    with cols[1]:
        if st.button("Continue to review & decide", type="primary"):
            go("decide")


def page_decide():
    st.subheader("Review & decide")
    st.write("No trades are executed. Record whether this profile is accepted as the basis for later AI-CIO analysis.")
    notes = st.text_area("Notes (optional)")
    cols = st.columns(4)
    mapping = [("Accept", "accept"), ("Modify later", "modify"), ("Reject", "reject")]
    with cols[0]:
        if st.button("Back"):
            go("analysis")
    for i, (label, value) in enumerate(mapping, start=1):
        with cols[i]:
            if st.button(label, type="primary" if value == "accept" else "secondary"):
                try:
                    client.record_decision(st.session_state.user_id, value, notes or None)
                except client.ApiError as exc:
                    st.session_state.error = str(exc)
                    st.rerun()
                    return
                st.success(f"Recorded your decision: {value}. Your user id remains {st.session_state.user_id}.")


def main():
    init_state()
    shell()
    page = {
        "welcome": page_welcome,
        "psychometrics": page_psychometrics,
        "finances": page_finances,
        "goals": page_goals,
        "portfolio": page_portfolio,
        "review": page_review,
        "analysis": page_analysis,
        "decide": page_decide,
    }.get(st.session_state.step, page_welcome)
    page()


main()
