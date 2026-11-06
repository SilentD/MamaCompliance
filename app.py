import os
import sys
from datetime import datetime
import json
import streamlit as st

# Ensure local import paths work cleanly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.schema import SMMEProfile, TenderOpportunity
from core.crypto import POPIADataMasker
from agents.orchestrator import ModularADKOrchestrator
from data.db_adapter import MongoDBAdapter
from core.auth import AuthManager

# 1. Page Configuration
st.set_page_config(
    page_title="SMME Compliance-to-Capital Engine",
    page_icon="🇿🇦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom South African Executive Dark Palette
st.markdown("""
<style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .header-container {
        background: linear-gradient(135deg, #007A4D 0%, #0B192C 60%, #FFB800 100%);
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .header-title {
        color: #FFFFFF;
        font-size: 28px;
        font-weight: 800;
        margin: 0;
    }
    .header-subtitle {
        color: #E2E8F0;
        font-size: 15px;
        margin-top: 6px;
    }
    .metric-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 700;
        color: #38BDF8;
    }
    .metric-label {
        font-size: 12px;
        color: #94A3B8;
        text-transform: uppercase;
    }
    .badge-success {
        background-color: #065F46;
        color: #34D399;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #78350F;
        color: #FBBF24;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-danger {
        background-color: #7F1D1D;
        color: #FCA5A5;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .chat-bubble-user {
        background-color: #075E54;
        color: #FFFFFF;
        padding: 12px 16px;
        border-radius: 12px 12px 2px 12px;
        margin-bottom: 10px;
        max-width: 80%;
        margin-left: auto;
    }
    .chat-bubble-agent {
        background-color: #1E293B;
        border-left: 4px solid #FFB800;
        color: #F8FAFC;
        padding: 12px 16px;
        border-radius: 12px 12px 12px 2px;
        margin-bottom: 10px;
        max-width: 88%;
    }
</style>
""", unsafe_allow_html=True)

# 2. Database & State Initialization
if "db" not in st.session_state:
    st.session_state.db = MongoDBAdapter()

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = ModularADKOrchestrator()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user_info" not in st.session_state:
    st.session_state.user_info = None

if "session_id" not in st.session_state:
    st.session_state.session_id = "sess_default"

# 3. Sidebar Layout & Database Telemetry
with st.sidebar:
    st.title("Compliance Vault")

    # DB Connection Telemetry Badge
    db_status = st.session_state.db.get_status_info()
    if db_status["connected"]:
        st.success(f"🟢 **Connected to MongoDB Atlas** ({db_status['database']})")
    else:
        st.warning(f"🟠 **Local JSON Persistence Active**\n\n*{db_status['message']}*")
        with st.expander("🔌 Connect MongoDB Atlas URI"):
            custom_uri = st.text_input("MongoDB Connection String", type="password", help="mongodb+srv://user:pass@cluster.mongodb.net/...")
            if st.button("Connect Cluster", use_container_width=True):
                if custom_uri:
                    if st.session_state.db.reconnect(custom_uri):
                        st.toast("Successfully connected to MongoDB Atlas!", icon="🚀")
                        st.rerun()
                    else:
                        st.error(f"Connection failed: {st.session_state.db.connection_error}")

    st.divider()

    # User Authentication Controls in Sidebar
    if not st.session_state.authenticated:
        st.subheader("🔑 Account Sign In")
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])

        with auth_tab1:
            login_email = st.text_input("Email Address", value="nandi@bathobeauty.co.za", key="login_email")
            login_pass = st.text_input("Password", type="password", value="Batho123!", key="login_pass")
            if st.button("Sign In", use_container_width=True, type="primary"):
                user_doc = st.session_state.db.authenticate_user(login_email, login_pass)
                if user_doc:
                    st.session_state.authenticated = True
                    st.session_state.user_info = user_doc
                    st.toast(f"Welcome back, {user_doc['business_name']}!", icon="👋")
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

            if st.button("⚡ Quick Demo Sign-In", use_container_width=True):
                user_doc = st.session_state.db.register_user("nandi@bathobeauty.co.za", "Batho123!", "Batho Beauty & Logistics")
                st.session_state.authenticated = True
                st.session_state.user_info = user_doc
                st.rerun()

        with auth_tab2:
            reg_biz = st.text_input("Business Name", value="Batho Beauty & Logistics", key="reg_biz")
            reg_email = st.text_input("Email Address", value="", key="reg_email")
            reg_pass = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Create SMME Account", use_container_width=True):
                if reg_email and reg_pass:
                    user_doc = st.session_state.db.register_user(reg_email, reg_pass, reg_biz)
                    st.session_state.authenticated = True
                    st.session_state.user_info = user_doc
                    st.toast(f"Account created for {reg_biz}!", icon="🎉")
                    st.rerun()
                else:
                    st.warning("Please fill in email and password.")

    else:
        # Authenticated User View
        user_doc = st.session_state.user_info
        user_id = user_doc["user_id"]
        
        # Load & sync profile from MongoDB
        st.session_state.smme = st.session_state.db.get_smme_profile(user_id)
        
        st.subheader(st.session_state.smme.business_name)
        st.caption(f"Reg: {st.session_state.smme.registration_number} | {st.session_state.smme.location}")
        
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_info = None
            st.session_state.messages = []
            st.rerun()

        st.divider()

        comp = st.session_state.smme.compliance
        fin = st.session_state.smme.financials

        checks = [
            comp.csd_registered,
            comp.tax_compliant,
            comp.tcs_pin_expiry_days > 0,
            comp.bbbee_affidavit_valid,
            comp.coida_valid,
        ]
        score = int((sum(checks) / len(checks)) * 100)

        st.markdown("### Tender Readiness")
        st.progress(score / 100)
        st.markdown(f"**{score}% Ready**")
        st.divider()

        st.markdown("#### Live State Feed")
        csd_class = "badge-success" if comp.csd_registered else "badge-danger"
        st.markdown(f"**CSD Supplier:** <span class='{csd_class}'>{comp.csd_number}</span>", unsafe_allow_html=True)

        tcs_class = "badge-warning" if comp.tcs_pin_expiry_days <= 3 else "badge-success"
        masked_pin = POPIADataMasker.mask_tcs_pin(comp.tcs_pin)
        st.markdown(f"**SARS TCS PIN:** <span class='{tcs_class}'>{masked_pin}</span>", unsafe_allow_html=True)
        st.caption(f"Expires in {comp.tcs_pin_expiry_days} days")

        st.markdown(f"**B-BBEE Status:** <span class='badge-success'>Level {comp.bbbee_level} EME</span>", unsafe_allow_html=True)

        coida_class = "badge-danger" if not comp.coida_valid else "badge-success"
        coida_txt = "Action Required" if not comp.coida_valid else "Valid"
        st.markdown(f"**COIDA Letter:** <span class='{coida_class}'>{coida_txt}</span>", unsafe_allow_html=True)

        st.divider()
        if st.button("⚡ Live SARS TCS Auto-Refresh", use_container_width=True):
            res = st.session_state.orchestrator.process_user_query("Refresh tax PIN", st.session_state.smme)
            
            # Persist updated profile & chat to MongoDB
            st.session_state.smme = res["updated_profile"]
            st.session_state.db.save_smme_profile(user_id, st.session_state.smme)
            st.session_state.db.save_chat_message(user_id, st.session_state.session_id, "user", "User", "Refresh tax PIN")
            st.session_state.db.save_chat_message(user_id, st.session_state.session_id, "assistant", res["delegated_agent"], res["response_text"])
            st.session_state.db.save_audit_logs(user_id, res.get("audit_logs"))

            st.toast("SARS TCS PIN auto-refreshed and synced to MongoDB!", icon="✅")
            st.rerun()

# 4. Main Executive Header & Dashboard
st.markdown(
    """
    <div class="header-container">
        <div class="header-title">🇿🇦 SMME Compliance-to-Capital Engine</div>
        <div class="header-subtitle">Master ADK Orchestrator | Persistent Session & MongoDB Data Store</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.authenticated:
    st.info("💡 **Welcome to the SMME Compliance Engine.** Please sign in or use **Quick Demo Sign-In** in the sidebar to access your persistent profile.")
    st.stop()

# Authenticated Application Body
user_doc = st.session_state.user_info
user_id = user_doc["user_id"]
session_id = st.session_state.session_id

# Load Chat History from MongoDB / Local JSON Store
db_messages = st.session_state.db.get_chat_history(user_id, session_id)
if not db_messages:
    welcome_msg = (
        f"**Molo {st.session_state.smme.owner_name}!** I am your ADK Master Compliance-to-Capital Orchestrator. "
        f"I am monitoring your CSD profile ({st.session_state.smme.compliance.csd_number}), SARS Tax PIN, and Bloemfontein municipal tenders 24/7.\n\n"
        "Try saying: 'Refresh my tax PIN', 'Apply for Mangaung catering tender', 'Log sale of R2,500', or 'Check SEFA loan eligibility'."
    )
    st.session_state.db.save_chat_message(user_id, session_id, "assistant", "MasterOrchestrator (ADK)", welcome_msg)
    db_messages = st.session_state.db.get_chat_history(user_id, session_id)

st.session_state.messages = db_messages

fin = st.session_state.smme.financials
comp = st.session_state.smme.compliance

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">12M Revenue</div><div class="metric-value">R {fin.rolling_revenue_12m:,.0f}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Provisional Tax Est.</div><div class="metric-value" style="color: #FBBF24;">R {fin.provisional_tax_estimate:,.0f}</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="metric-card"><div class="metric-label">Matched Tenders</div><div class="metric-value" style="color: #34D399;">2 Active</div></div>', unsafe_allow_html=True)
with col4:
    max_loan = min(250000.0, fin.rolling_revenue_12m * 0.5) if comp.tax_compliant else 0.0
    st.markdown(f'<div class="metric-card"><div class="metric-label">SEFA Capital Eligibility</div><div class="metric-value" style="color: #A78BFA;">Up to R {max_loan:,.0f}</div></div>', unsafe_allow_html=True)

st.write("")
left_col, right_col = st.columns([1, 1.2], gap="large")

SAMPLE_TENDERS = [
    TenderOpportunity(
        id="MMM-2026-C04",
        title="Supply & Delivery of Catering Services - Mangaung Municipal Event",
        issuer="Mangaung Metropolitan Municipality",
        value="R 185,000.00",
        closing_date="2026-11-15",
        required_docs=["CSD Report", "SARS TCS PIN", "B-BBEE Sworn Affidavit", "MBD 4", "MBD 6.1"],
    ),
    TenderOpportunity(
        id="FSP-2026-T12",
        title="Local Transport & Logistics Services for Free State Health",
        issuer="Free State Dept of Health",
        value="R 420,000.00",
        closing_date="2026-11-20",
        required_docs=["CSD Report", "SARS TCS PIN", "3-Month Bank Summary", "MBD 4"],
    ),
]

with left_col:
    st.subheader("🎯 Matched Tenders & Capital Opportunities")
    st.caption("Live tenders matched against CSD supplier profiles")

    for tender in SAMPLE_TENDERS:
        with st.expander(f"📌 {tender.title} ({tender.value})", expanded=True):
            st.markdown(f"**Issuer:** {tender.issuer}")
            st.markdown(f"**Closing Date:** {tender.closing_date}")
            st.markdown("**Required Documentation:**")

            for doc in tender.required_docs:
                if doc == "SARS TCS PIN" and comp.tcs_pin_expiry_days <= 3:
                    st.markdown(f"- ⚠️ **{doc}** *(Expiring - Auto-refresh available)*")
                else:
                    st.markdown(f"- ✅ **{doc}** *(Ready)*")

            if st.button(f"Generate Tender Pack for {tender.id}", key=tender.id, use_container_width=True):
                user_msg = f"Apply for {tender.title} ({tender.id})"

                res = st.session_state.orchestrator.process_user_query(user_msg, st.session_state.smme, target_tender_id=tender.id)

                # Persist updated profile & chat to MongoDB
                st.session_state.smme = res["updated_profile"]
                st.session_state.db.save_smme_profile(user_id, st.session_state.smme)
                st.session_state.db.save_chat_message(user_id, session_id, "user", "User", user_msg)
                st.session_state.db.save_chat_message(user_id, session_id, "assistant", res["delegated_agent"], res["response_text"])
                st.session_state.db.save_audit_logs(user_id, res.get("audit_logs"))

                st.rerun()

with right_col:
    st.subheader("💬 ADK Orchestrator Feed (Persistent WhatsApp Session)")
    st.caption("Live multi-agent routing with POPIA auditing & MongoDB persistence")

    chat_container = st.container(height=380)
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div class="chat-bubble-user">
                        <small style="color: #94A3B8;">User • {msg['timestamp']}</small><br/>
                        {msg['content']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                agent_name = msg.get("agent", "MasterOrchestrator")
                st.markdown(
                    f"""
                    <div class="chat-bubble-agent">
                        <small style="color: #FFB800;">✨ {agent_name}</small>
                        <small style="color: #94A3B8;"> • {msg['timestamp']}</small><br/>
                        {msg['content']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("**Quick Triggers:**")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    def execute_and_persist(prompt_text: str):
        res = st.session_state.orchestrator.process_user_query(prompt_text, st.session_state.smme)
        st.session_state.smme = res["updated_profile"]
        st.session_state.db.save_smme_profile(user_id, st.session_state.smme)
        st.session_state.db.save_chat_message(user_id, session_id, "user", "User", prompt_text)
        st.session_state.db.save_chat_message(user_id, session_id, "assistant", res["delegated_agent"], res["response_text"])
        st.session_state.db.save_audit_logs(user_id, res.get("audit_logs"))
        st.rerun()

    with btn_col1:
        if st.button("🔍 Gap Analysis", use_container_width=True):
            execute_and_persist("Run compliance gap analysis")

    with btn_col2:
        if st.button("💵 Log Sale R2,500", use_container_width=True):
            execute_and_persist("Logged sale of R2500 beauty product supplies")

    with btn_col3:
        if st.button("📊 Funding Match", use_container_width=True):
            execute_and_persist("Check my SEFA loan funding eligibility")

    if user_input := st.chat_input("Ask ADK Orchestrator or send simulated voice note..."):
        execute_and_persist(user_input)

with st.expander("🛡️ POPIA Audit Log Drawer (Live MongoDB Audit Trail)"):
    data_logs = st.session_state.db.local_store._read_data().get("audit_logs", {}).get(user_id, []) if not st.session_state.db.is_connected else []
    if st.session_state.db.is_connected:
        try:
            db_logs = list(st.session_state.db.db.audit_logs.find({"user_id": user_id}).limit(10))
            for l in db_logs:
                l.pop("_id", None)
            st.json(db_logs)
        except Exception:
            st.caption("Unable to fetch remote audit log drawer.")
    elif data_logs:
        st.json(data_logs[-10:])
    else:
        st.caption("No data access entries logged yet for this session.")

st.divider()
st.caption("🇿🇦 Built for Academic Prototyping & South African SMME Economic Access | Powered by Google ADK & Streamlit Cloud")