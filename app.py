import streamlit as st
from curata_core import init_auth_state, main_app   # removed login_screen import

# ---------------------- Login System ---------------------- #
def login_screen():
    # --- Branded Curata Header ---
    st.markdown(
        """
        <div style="
            text-align: center;
            padding: 1.5rem 0 1rem 0;
            border-bottom: 1px solid #333;
        ">
            <div style="
                font-size: 2rem;
                font-weight: 900;
                color: #ffffff;
                letter-spacing: -0.5px;
            ">
                Curata Dashboard Login
            </div>
            <div style="
                font-size: 1rem;
                font-weight: 500;
                color: #cccccc;
                margin-top: 0.4rem;
            ">
                Secure access to your daily performance insights
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Show/Hide Password Toggle ---
    show_password = st.checkbox("Show password", value=False)

    # --- Autofocus on Username (JS-based, Streamlit-safe) ---
    st.markdown(
        """
        <script>
        setTimeout(function() {
            const input = window.parent.document.querySelector('input[placeholder="Username"]');
            if (input) { input.focus(); }
        }, 150);
        </script>
        """,
        unsafe_allow_html=True,
    )

    # --- Login Form (Enter-to-submit works here) ---
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Username")
        password = st.text_input(
            "Password",
            type="default" if show_password else "password",
            placeholder="Password"
        )
        submit = st.form_submit_button("Login")

    # --- Login Logic ---
    if submit:
        normalized = username.strip().lower()

        # User 1
        if (
            normalized == st.secrets["auth"]["user1"].lower()
            and password == st.secrets["auth"]["pass1"]
        ):
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = normalized
            st.rerun()

        # User 2
        elif (
            normalized == st.secrets["auth"]["user2"].lower()
            and password == st.secrets["auth"]["pass2"]
        ):
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = normalized
            st.rerun()

        else:
            st.error("Invalid username or password")


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user_id"] = None
    st.rerun()


# ---------------------- Page config ---------------------- #
st.set_page_config(
    page_title="Curata Daily Performance Dashboard",
    layout="wide",
)

# ---------------------- Styling (dark mode + mobile) ---------------------- #
st.markdown(
    """
<style>
 /* ------------------------------
   GLOBAL DARK THEME
------------------------------ */
.main, .block-container {
    background-color: #0d0d0d !important;
    color: #ffffff !important;
}
.main * {
    color: #ffffff !important;
}

/* ------------------------------
   HEADER
------------------------------ */
.curata-header {
    text-align: center;
    padding: 12px 0 20px 0;
    border-bottom: 1px solid #333333;
}
.curata-title {
    font-size: 28px;
    font-weight: 800;
}
.curata-tagline {
    font-size: 15px;
    opacity: 0.85;
}

/* ------------------------------
   HEADINGS
------------------------------ */
h1, h2, h3, h4, h5 {
    font-weight: 700 !important;
}

/* ------------------------------
   METRICS
------------------------------ */
[data-testid="stMetric"], .stMetric {
    background-color: #1a1a1a !important;
    border-radius: 10px !important;
    padding: 10px !important;
}
[data-testid="stMetric"] * {
    color: #ffffff !important;
    font-weight: 600;
}

/* ------------------------------
   DIVIDERS
------------------------------ */
.curata-divider {
    margin: 18px 0;
    border-top: 1px solid #2e2e2e;
}

/* ------------------------------
   TABS
------------------------------ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.4rem;
}
.stTabs [data-baseweb="tab"] {
    background-color: #1a1a1a !important;
    padding: 8px 14px !important;
    border-radius: 20px !important;
    color: #cccccc !important;
    font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}

/* ------------------------------
   INPUTS
------------------------------ */
input, textarea, select {
    background-color: #1a1a1a !important;
    color: #ffffff !important;
    border: 1px solid #333333 !important;
    font-weight: 500 !important;
}
.stTextInput label,
.stNumberInput label,
.stDateInput label,
.stSelectbox label,
.stSlider label,
.stMultiSelect label,
.stRadio label,
.stCheckbox label,
.stTextArea label {
    color: #ffffff !important;
    font-weight: 700 !important;
}

/* ------------------------------
   TABLES
------------------------------ */
.stDataFrame, .stTable {
    color: #ffffff !important;
}

/* ------------------------------
   BUTTONS (GLOBAL + EXPORT + LOGIN)
------------------------------ */
div.stDownloadButton[data-testid="stDownloadButton"] > button[data-testid="stBaseButton-secondary"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    border: none !important;
    box-shadow: none !important;
}
div.stDownloadButton[data-testid="stDownloadButton"] > button[data-testid="stBaseButton-secondary"]:hover {
    background-color: #1d4ed8 !important;
}

.stButton > button,
button[data-testid="formSubmitButton"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    border: none !important;
    box-shadow: none !important;
    opacity: 1 !important;
    visibility: visible !important;
}
.stButton > button:hover,
button[data-testid="formSubmitButton"]:hover {
    background-color: #1d4ed8 !important;
}

/* Remove white wrapper div around form submit buttons */
button[data-testid="formSubmitButton"] + div {
    background-color: transparent !important;
}
div.stButton {
    background-color: transparent !important;
}

/* ------------------------------
   EXPANDERS (MATCHING YOUR DOM)
------------------------------ */
div.stExpander[data-testid="stExpander"] {
    background-color: #111111 !important;
    border-radius: 6px !important;
}
div.stExpander[data-testid="stExpander"] > details > summary {
    background-color: #1a1a1a !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    padding: 8px !important;
    list-style: none !important;
}
div.stExpander[data-testid="stExpander"] > details[open] > summary {
    background-color: #16a34a !important;
    color: #ffffff !important;
    font-weight: 800 !important;
}
div.stExpander[data-testid="stExpander"] > details[open] > summary:hover {
    background-color: #15803d !important;
}
div.stExpander[data-testid="stExpander"] > details > div[data-testid="stExpanderDetails"] {
    background-color: #111111 !important;
}

/* ------------------------------
   MOBILE
------------------------------ */
@media (max-width: 768px) {
    .curata-title {
        font-size: 22px;
    }
    .curata-tagline {
        font-size: 13px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------- Run the app ---------------------- #
init_auth_state()

if not st.session_state["authenticated"]:
    login_screen()
else:
    main_app()
