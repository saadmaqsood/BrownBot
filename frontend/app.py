"""
Module: frontend/app.py
Purpose: Streamlit frontend for Brown University Forager course search.
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Brown University Forager", page_icon="🐻", layout="centered")

# Gruvbox dark + synthwave accents
st.markdown(
    """<style>
    .block-container {max-width: 760px; padding-top: 2.5rem;}

    /* Title glow */
    [data-testid="stMarkdownContainer"] h1 {
        text-align: center;
        color: #ff6ec7;
        text-shadow: 0 0 20px rgba(255, 110, 199, 0.3);
    }
    /* Center the subtitle caption */
    .block-container > [data-testid="stMarkdownContainer"] + [data-testid="stCaptionContainer"] {
        text-align: center;
    }

    /* Search input neon focus */
    [data-testid="stTextInput"] input:focus {
        border-color: #ff6ec7 !important;
        box-shadow: 0 0 10px rgba(255, 110, 199, 0.25);
    }

    /* Example chip buttons */
    .stButton > button {
        border-radius: 20px;
        font-size: 0.82rem;
        border-color: #504945;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        border-color: #45e6e6;
        color: #45e6e6;
    }

    /* Expander cards */
    [data-testid="stExpander"] {
        border: 1px solid #3c3836;
        border-radius: 8px;
    }
    [data-testid="stExpander"]:hover {
        border-color: #504945;
    }

    /* Metric values in cyan */
    [data-testid="stMetricValue"] {
        color: #45e6e6;
    }

    /* Dividers */
    hr {border-color: #3c3836 !important;}
    </style>""",
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🐻 Brown University Forager")
st.caption("Finding the right honey for every Brown bear")


# ── Cached API call ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def _search(q: str, top_k: int = 10) -> dict:
    payload: dict = {"q": q, "top_k": top_k}
    r = requests.post(f"{API_URL}/query", json=payload, timeout=500)
    r.raise_for_status()
    return r.json()


# ── Search bar ────────────────────────────────────────────────────────────────
# Apply prefill from example chips (must happen before widget creation)
if "prefill" in st.session_state:
    st.session_state.query_input = st.session_state.pop("prefill")

if "query_input" not in st.session_state:
    st.session_state.query_input = ""

query = st.text_input(
    "q",
    key="query_input",
    placeholder="Ask about any Brown course — schedules, instructors, recommendations …",
    label_visibility="collapsed",
)

# ── Example queries ───────────────────────────────────────────────────────────
EXAMPLES = [
    "Any comic related courses?",
    "Can I play the banjo in any class?",
    "Who teaches quantum mechanics?",
    "Courses about climate change",
]

cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    with col:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state.prefill = ex
            st.rerun()

if not query:
    st.stop()

# ── Execute search ────────────────────────────────────────────────────────────
with st.spinner("Foraging …"):
    try:
        data = _search(query)
    except requests.RequestException as exc:
        st.error(f"Search failed — is the API running? ({exc})")
        st.stop()

# ── Answer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(data["answer"])

# ── Department filter (client-side, no re-fetch) ─────────────────────────────
courses = data["courses"]
scores = data.get("scores", [])

depts = sorted({c["department"] for c in courses if c.get("department")})

dept_filter = None
if depts:
    selected = st.radio(
        "Filter by department",
        ["All"] + depts,
        horizontal=True,
        label_visibility="collapsed",
        key=f"dept_{query}",
    )
    if selected != "All":
        dept_filter = selected

# Apply filter client-side
if dept_filter:
    filtered = [
        (c, scores[i] if i < len(scores) else None)
        for i, c in enumerate(courses)
        if c.get("department") == dept_filter
    ]
else:
    filtered = [(c, scores[i] if i < len(scores) else None) for i, c in enumerate(courses)]

# ── Course cards ──────────────────────────────────────────────────────────────
st.caption(f"{len(filtered)} courses found")

for c, score in filtered:
    score_label = f" · {score:.0%} match" if score is not None else ""
    header = f"**{c['course_code']}** — {c['title']}{score_label}"

    with st.expander(header):
        meta = " · ".join(
            filter(None, [c.get("instructor"), c.get("meeting_times"), c.get("source")])
        )
        if meta:
            st.caption(meta)
        if c.get("prerequisites"):
            st.markdown(f"**Prerequisites:** {c['prerequisites']}")
        if c.get("description"):
            st.markdown(c["description"])

# ── Suggestions ───────────────────────────────────────────────────────────────
suggestions = data.get("suggestions", [])
if suggestions:
    st.divider()
    st.markdown("**Students exploring this also found**")
    for c in suggestions:
        meta = " · ".join(
            filter(None, [c.get("department"), c.get("instructor")])
        )
        with st.expander(f"**{c['course_code']}** — {c['title']}"):
            if meta:
                st.caption(meta)
            if c.get("description"):
                st.markdown(c["description"])

# ── Pipeline metrics ──────────────────────────────────────────────────────────
st.markdown("")
st.markdown("")
st.markdown("")
timings = data.get("timings", {})
if timings:
    with st.expander("Wanna see my insides?"):
        row1 = st.columns(3)
        with row1[0]:
            st.metric("Direct Lookup", f"{timings.get('direct_lookup_ms', 0)}ms")
        with row1[1]:
            st.metric("Semantic Search", f"{timings.get('semantic_ms', 0)}ms")
        with row1[2]:
            st.metric("Keyword Rerank", f"{timings.get('rerank_ms', 0)}ms")
        row2 = st.columns(3)
        with row2[0]:
            st.metric("Suggestions", f"{timings.get('suggest_ms', 0)}ms")
        with row2[1]:
            st.metric("LLM Generation", f"{timings.get('llm_ms', 0)}ms")
        with row2[2]:
            st.metric("Total", f"{data['latency_ms']}ms")
