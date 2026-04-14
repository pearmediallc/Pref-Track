import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PerfTrack — Pear Media",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = "data.json"
USERS_FILE = "users.json"

def _ord(n):
    return "st" if n == 1 else "nd" if n == 2 else "rd" if n == 3 else "th"

TIME_SLOTS = ["Full Day"] + [f"{n}{_ord(n)} Hr" for n in range(1, 14)]

# ── Users store ──────────────────────────────────────────────────────────────
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    default = {
        "admin": {
            "password": "admin123",
            "role": "admin",
            "display_name": "Admin",
            "team_lead": None,
        }
    }
    save_users(default)
    return default

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ── Data store ───────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def normalize_df(data):
    """Turn raw records into a normalized DataFrame (merges legacy + new schema)."""
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)

    # Legacy → new field mapping (keeps old entries working)
    if "FB Link Clicks" in df.columns:
        if "Clicks" not in df.columns:
            df["Clicks"] = df["FB Link Clicks"]
        else:
            df["Clicks"] = df["Clicks"].fillna(df["FB Link Clicks"])

    if "LP Clicks" in df.columns:
        if "Offer Clicks" not in df.columns:
            df["Offer Clicks"] = df["LP Clicks"]
        else:
            df["Offer Clicks"] = df["Offer Clicks"].fillna(df["LP Clicks"])

    if "Accounts" in df.columns:
        if "PML Code" not in df.columns:
            df["PML Code"] = df["Accounts"]
        else:
            df["PML Code"] = df["PML Code"].fillna(df["Accounts"])

    expected = ["Date", "Time Slot", "timestamp", "added_by", "team_lead",
                "PML Code", "Vertical", "Traffic Source", "Platform", "Brands",
                "Spend", "Revenue", "Impressions", "Clicks", "Offer Clicks", "Conversions",
                "Profit", "ROI", "CPC", "EPC", "Offer CTR", "Cost per Conv"]
    for c in expected:
        if c not in df.columns:
            df[c] = None

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    numeric_cols = ["Spend", "Revenue", "Impressions", "Clicks", "Offer Clicks",
                    "Conversions", "Profit", "ROI", "CPC", "EPC", "Offer CTR", "Cost per Conv"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def calc_metrics(spend, revenue, clicks, offer_clicks, conversions):
    profit = revenue - spend
    roi = (profit / spend * 100) if spend > 0 else 0
    cpc = (spend / clicks) if clicks > 0 else 0
    epc = (revenue / clicks) if clicks > 0 else 0
    offer_ctr = (offer_clicks / clicks * 100) if clicks > 0 else 0
    cost_per_conv = (spend / conversions) if conversions > 0 else 0
    return {
        "Profit": round(profit, 2),
        "ROI": round(roi, 2),
        "CPC": round(cpc, 4),
        "EPC": round(epc, 4),
        "Offer CTR": round(offer_ctr, 2),
        "Cost per Conv": round(cost_per_conv, 2),
    }

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif; }

.stApp { background: #0d0f14; color: #e8eaf0; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111420 0%, #0d0f14 100%);
    border-right: 1px solid #1e2235;
}

.metric-card {
    background: linear-gradient(135deg, #141824 0%, #1a1f30 100%);
    border: 1px solid #252a3d;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: #7c8dff;
}
.metric-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
    margin-bottom: 4px;
}
.profit-pos { color: #34d399; }
.profit-neg { color: #f87171; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.badge-admin  { background: #dc262622; color: #fca5a5; border: 1px solid #dc262655; }
.badge-leader { background: #7c3aed22; color: #a78bfa; border: 1px solid #7c3aed55; }
.badge-member { background: #0891b222; color: #67e8f9; border: 1px solid #0891b255; }

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: #c7cde8;
    border-bottom: 2px solid #252a3d;
    padding-bottom: 8px;
    margin-bottom: 20px;
}

div[data-testid="stForm"] {
    background: #141824;
    border: 1px solid #252a3d;
    border-radius: 16px;
    padding: 24px;
}

.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
    border-radius: 10px;
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    padding: 10px 28px;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px #6366f140;
}

[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stMultiSelect"] > div > div {
    background: #0d0f14 !important;
    border: 1px solid #252a3d !important;
    color: #e8eaf0 !important;
    border-radius: 8px !important;
}

.stDataFrame { border-radius: 12px; overflow: hidden; }

div[data-testid="metric-container"] {
    background: #141824;
    border: 1px solid #252a3d;
    border-radius: 12px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.team_lead = None
    st.session_state.display_name = ""

# ── Login ─────────────────────────────────────────────────────────────────────
def login_page():
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("""
        <div style='text-align:center; padding: 40px 0 20px;'>
            <div style='font-family:Syne,sans-serif; font-size:2.8rem; font-weight:800;
                        background:linear-gradient(135deg,#7c8dff,#a78bfa);
                        -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
                📊 PerfTrack
            </div>
            <div style='color:#6b7280; font-size:0.9rem; margin-top:8px;'>
                Pear Media · Performance Dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                users = load_users()
                u = username.strip().lower()
                if u in users and users[u]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = users[u]["role"]
                    st.session_state.team_lead = users[u].get("team_lead")
                    st.session_state.display_name = users[u].get("display_name", u.capitalize())
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

        st.markdown(
            "<div style='color:#4b5563; font-size:0.75rem; text-align:center; margin-top:20px;'>"
            "First run? Use <b>admin</b> / <b>admin123</b> and change the password right after login."
            "</div>",
            unsafe_allow_html=True,
        )

# ── Sidebar ────────────────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("""
        <div style='font-family:Syne,sans-serif; font-size:1.5rem; font-weight:800;
                    background:linear-gradient(135deg,#7c8dff,#a78bfa);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                    padding: 10px 0 4px;'>
            📊 PerfTrack
        </div>
        """, unsafe_allow_html=True)

        role = st.session_state.role
        if role == "admin":
            badge_cls, badge_label = "badge-admin", "Admin"
        elif role == "leader":
            badge_cls, badge_label = "badge-leader", "Team Leader"
        else:
            badge_cls, badge_label = "badge-member", "Media Buyer"

        sub = ""
        if role == "member" and st.session_state.team_lead:
            users = load_users()
            lead_name = users.get(st.session_state.team_lead, {}).get(
                "display_name", st.session_state.team_lead.capitalize()
            )
            sub = f"<span style='color:#6b7280; font-size:0.8rem;'> · under {lead_name}</span>"

        st.markdown(f"""
        <div style='margin-bottom:20px;'>
            <div style='color:#e8eaf0; font-weight:600; font-size:1rem;'>
                {st.session_state.display_name}
            </div>
            <span class='badge {badge_cls}'>{badge_label}</span>{sub}
        </div>
        <hr style='border:none; border-top:1px solid #1e2235; margin:10px 0 16px;'>
        """, unsafe_allow_html=True)

        if role == "admin":
            pages = ["📊 Master Dashboard", "🎯 By Team Lead", "👤 By Media Buyer",
                     "📋 All Data", "👥 User Management", "🔑 My Account"]
        elif role == "leader":
            pages = ["📊 Team Dashboard", "👤 By Media Buyer", "📋 Team Data", "🔑 My Account"]
        else:
            pages = ["📥 Add Data", "📈 My Dashboard", "🔑 My Account"]

        page = st.radio("Navigation", pages, label_visibility="collapsed")

        st.markdown("<hr style='border:none; border-top:1px solid #1e2235; margin:20px 0;'>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        return page

# ── UI helpers ────────────────────────────────────────────────────────────────
def kpi_row(items):
    cols = st.columns(len(items))
    for col, (label, val, color_val) in zip(cols, items):
        with col:
            c = ""
            if color_val is not None:
                c = "profit-pos" if color_val >= 0 else "profit-neg"
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>{label}</div>
                <div class='metric-value {c}'>{val}</div>
            </div>
            """, unsafe_allow_html=True)

def summary_kpis(df):
    ts = df["Spend"].sum()
    tr = df["Revenue"].sum()
    tp = tr - ts
    tc = df["Conversions"].sum()
    roi = (tp / ts * 100) if ts > 0 else 0
    kpi_row([
        ("Total Spend",   f"₹{ts:,.2f}", None),
        ("Total Revenue", f"₹{tr:,.2f}", None),
        ("Total Profit",  f"₹{tp:,.2f}", tp),
        ("ROI",           f"{roi:.1f}%", roi),
        ("Conversions",   f"{int(tc):,}", None),
    ])

def style_df_for_display(df):
    show = df.copy().sort_values("Date", ascending=False)
    if "Date" in show.columns:
        show["Date"] = pd.to_datetime(show["Date"]).dt.strftime("%d %b %Y")
    for c in ["Spend", "Revenue", "Profit", "Cost per Conv"]:
        if c in show.columns:
            show[c] = show[c].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "")
    if "ROI" in show.columns:
        show["ROI"] = show["ROI"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    if "Offer CTR" in show.columns:
        show["Offer CTR"] = show["Offer CTR"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    return show

def render_charts(df):
    daily = df.groupby(df["Date"].dt.date).agg(
        Spend=("Spend", "sum"), Revenue=("Revenue", "sum"), Profit=("Profit", "sum")
    ).reset_index()
    daily.columns = ["Date", "Spend", "Revenue", "Profit"]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["Date"], y=daily["Revenue"], name="Revenue",
                         marker_color="#6366f1", opacity=0.85))
    fig.add_trace(go.Bar(x=daily["Date"], y=daily["Spend"], name="Spend",
                         marker_color="#475569", opacity=0.85))
    fig.add_trace(go.Scatter(x=daily["Date"], y=daily["Profit"], name="Profit",
                             mode="lines+markers", line=dict(color="#34d399", width=2.5),
                             marker=dict(size=6)))
    fig.update_layout(
        title="Daily Revenue vs Spend vs Profit",
        barmode="group",
        paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
        font=dict(color="#e8eaf0"), height=380,
        legend=dict(bgcolor="#141824", bordercolor="#252a3d"),
        xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"),
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if df["PML Code"].notna().any() and (df["PML Code"].astype(str).str.strip() != "").any():
            acc_df = df.groupby("PML Code").agg(
                Spend=("Spend", "sum"), Revenue=("Revenue", "sum"), Profit=("Profit", "sum")
            ).reset_index().sort_values("Profit", ascending=False).head(15)
            fig2 = px.bar(acc_df, x="PML Code", y="Profit", color="Profit",
                          color_continuous_scale=["#f87171", "#fbbf24", "#34d399"],
                          title="Profit by PML Code (Top 15)")
            fig2.update_layout(paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                               font=dict(color="#e8eaf0"), height=320,
                               xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
            st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        if df["Time Slot"].notna().any():
            slot_df = df.groupby("Time Slot").agg(Profit=("Profit", "sum")).reset_index()
            slot_df["order"] = slot_df["Time Slot"].apply(lambda s: TIME_SLOTS.index(s) if s in TIME_SLOTS else 999)
            slot_df = slot_df.sort_values("order")
            fig3 = px.bar(slot_df, x="Time Slot", y="Profit", title="Profit by Time Slot",
                          color="Profit", color_continuous_scale=["#f87171", "#fbbf24", "#34d399"])
            fig3.update_layout(paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                               font=dict(color="#e8eaf0"), height=320,
                               xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
            st.plotly_chart(fig3, use_container_width=True)

def get_buyers_for_lead(lead_username):
    users = load_users()
    return [u for u, info in users.items()
            if info.get("role") == "member" and info.get("team_lead") == lead_username]

# ── Add Data (member) ─────────────────────────────────────────────────────────
def add_data_page():
    st.markdown("<div class='section-title'>📥 Add Performance Entry</div>", unsafe_allow_html=True)

    data = load_data()

    with st.form("add_data_form", clear_on_submit=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        with r1c1:
            entry_date = st.date_input("Date", value=date.today())
        with r1c2:
            time_slot = st.selectbox("Time Slot", TIME_SLOTS)
        with r1c3:
            pml_code = st.text_input("PML Code", placeholder="e.g. PML-0902-001")
        with r1c4:
            vertical = st.text_input("Vertical", placeholder="e.g. Insurance")

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            traffic_source = st.text_input("Traffic Source", placeholder="e.g. Facebook")
        with r2c2:
            platform = st.text_input("Platform", placeholder="e.g. Meta")
        with r2c3:
            brands = st.text_input("Brands", placeholder="e.g. Brand A")

        st.markdown(
            "<div style='color:#6b7280; font-size:0.75rem; letter-spacing:0.1em; "
            "text-transform:uppercase; margin:10px 0 6px;'>Performance Metrics</div>",
            unsafe_allow_html=True
        )

        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        with r3c1:
            spend = st.number_input("Spend (₹)", min_value=0.0, step=0.01, format="%.2f")
        with r3c2:
            revenue = st.number_input("Revenue (₹)", min_value=0.0, step=0.01, format="%.2f")
        with r3c3:
            impressions = st.number_input("Impressions", min_value=0, step=1)
        with r3c4:
            conversions = st.number_input("Conversions", min_value=0, step=1)

        r4c1, r4c2, r4c3 = st.columns(3)
        with r4c1:
            clicks = st.number_input("Clicks", min_value=0, step=1)
        with r4c2:
            offer_clicks = st.number_input("Offer Clicks", min_value=0, step=1)
        with r4c3:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info("Profit, ROI, CPC, EPC, Offer CTR, Cost/Conv auto-calculated", icon="⚙️")

        submitted = st.form_submit_button("➕ Add Entry", use_container_width=True)

        if submitted:
            if not pml_code.strip():
                st.error("Please enter a PML Code.")
            elif spend == 0 and revenue == 0:
                st.warning("Both Spend and Revenue are 0. Please check your data.")
            else:
                m = calc_metrics(spend, revenue, clicks, offer_clicks, conversions)
                entry = {
                    "Date": str(entry_date),
                    "Time Slot": time_slot,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "added_by": st.session_state.username,
                    "team_lead": st.session_state.team_lead,
                    "PML Code": pml_code.strip(),
                    "Vertical": vertical.strip(),
                    "Traffic Source": traffic_source.strip(),
                    "Platform": platform.strip(),
                    "Brands": brands.strip(),
                    "Spend": float(spend),
                    "Revenue": float(revenue),
                    "Impressions": int(impressions),
                    "Clicks": int(clicks),
                    "Offer Clicks": int(offer_clicks),
                    "Conversions": int(conversions),
                    **m,
                }
                data.append(entry)
                save_data(data)
                st.success(f"✅ Entry saved for {pml_code} — {time_slot} on {entry_date}")

    df = normalize_df(data)
    if not df.empty:
        mine = df[df["added_by"] == st.session_state.username]
        if not mine.empty:
            st.markdown("<div class='section-title' style='margin-top:30px;'>My Recent Entries</div>", unsafe_allow_html=True)
            cols_show = ["Date", "Time Slot", "PML Code", "Vertical", "Spend", "Revenue",
                         "Profit", "ROI", "Conversions"]
            recent = mine.sort_values("Date", ascending=False).head(15)
            st.dataframe(style_df_for_display(recent)[cols_show],
                         use_container_width=True, hide_index=True)

# ── My Dashboard (member) ─────────────────────────────────────────────────────
def my_dashboard_page():
    data = load_data()
    df = normalize_df(data)
    if not df.empty:
        df = df[df["added_by"] == st.session_state.username]

    st.markdown(f"<div class='section-title'>📈 {st.session_state.display_name} · My Dashboard</div>",
                unsafe_allow_html=True)

    if df.empty:
        st.info("No data yet. Head to 'Add Data' to get started.")
        return

    summary_kpis(df)
    st.markdown("---")
    render_charts(df)

    st.markdown("<div class='section-title' style='margin-top:10px;'>All My Entries</div>",
                unsafe_allow_html=True)
    cols_show = ["Date", "Time Slot", "PML Code", "Vertical", "Traffic Source", "Platform",
                 "Spend", "Revenue", "Profit", "ROI", "Clicks", "Offer Clicks", "Conversions",
                 "timestamp"]
    st.dataframe(style_df_for_display(df)[cols_show], use_container_width=True, hide_index=True)

# ── Leader: Team Dashboard ────────────────────────────────────────────────────
def leader_team_dashboard():
    users = load_users()
    data = load_data()
    df = normalize_df(data)

    lead = st.session_state.username
    buyers = get_buyers_for_lead(lead)
    if not df.empty:
        df = df[df["added_by"].isin(buyers)]

    st.markdown(f"<div class='section-title'>📊 Team Dashboard · {st.session_state.display_name}</div>",
                unsafe_allow_html=True)

    if not buyers:
        st.info("No media buyers are assigned to you yet. Ask the admin to assign buyers.")
        return
    if df.empty:
        st.info("Your team hasn't added any data yet.")
        return

    summary_kpis(df)
    st.markdown("---")

    buyer_df = df.groupby("added_by").agg(
        Spend=("Spend", "sum"), Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"), Conversions=("Conversions", "sum")
    ).reset_index()
    buyer_df["ROI"] = (buyer_df["Profit"] / buyer_df["Spend"].replace(0, pd.NA) * 100).round(2).fillna(0)
    buyer_df["added_by"] = buyer_df["added_by"].apply(
        lambda u: users.get(u, {}).get("display_name", u.capitalize())
    )
    buyer_df = buyer_df.rename(columns={"added_by": "Media Buyer"})

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(buyer_df, x="Media Buyer", y=["Revenue", "Spend"], barmode="group",
                     title="Revenue vs Spend by Media Buyer",
                     color_discrete_map={"Revenue": "#6366f1", "Spend": "#475569"})
        fig.update_layout(paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                          font=dict(color="#e8eaf0"), height=340,
                          xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        colors = ["#34d399" if p >= 0 else "#f87171" for p in buyer_df["Profit"]]
        fig2 = go.Figure(go.Bar(x=buyer_df["Media Buyer"], y=buyer_df["Profit"], marker_color=colors))
        fig2.update_layout(title="Profit by Media Buyer",
                           paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                           font=dict(color="#e8eaf0"), height=340,
                           xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
        st.plotly_chart(fig2, use_container_width=True)

    render_charts(df)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Media Buyer Summary</div>",
                unsafe_allow_html=True)
    display = buyer_df.copy()
    for c in ["Spend", "Revenue", "Profit"]:
        display[c] = display[c].apply(lambda x: f"₹{x:,.2f}")
    display["ROI"] = display["ROI"].apply(lambda x: f"{x:.2f}%")
    st.dataframe(display, use_container_width=True, hide_index=True)

# ── By Media Buyer (leader & admin) ───────────────────────────────────────────
def by_media_buyer_page():
    users = load_users()
    data = load_data()
    df = normalize_df(data)

    st.markdown("<div class='section-title'>👤 By Media Buyer</div>", unsafe_allow_html=True)

    if st.session_state.role == "leader":
        candidates = get_buyers_for_lead(st.session_state.username)
    else:
        candidates = [u for u, info in users.items() if info.get("role") == "member"]

    if not candidates:
        st.info("No media buyers available.")
        return

    labels = {u: f"{users[u].get('display_name', u.capitalize())}  ({u})" for u in candidates}
    pick = st.selectbox("Select Media Buyer", candidates, format_func=lambda u: labels[u])

    sub = df[df["added_by"] == pick] if not df.empty else df
    if sub.empty:
        st.info("No data for this media buyer yet.")
        return

    summary_kpis(sub)
    st.markdown("---")
    render_charts(sub)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Entries</div>", unsafe_allow_html=True)
    cols_show = ["Date", "Time Slot", "PML Code", "Vertical", "Traffic Source", "Platform",
                 "Spend", "Revenue", "Profit", "ROI", "Clicks", "Offer Clicks", "Conversions",
                 "timestamp"]
    st.dataframe(style_df_for_display(sub)[cols_show], use_container_width=True, hide_index=True)

# ── Admin: Master Dashboard ───────────────────────────────────────────────────
def master_dashboard_page():
    users = load_users()
    data = load_data()
    df = normalize_df(data)

    st.markdown("<div class='section-title'>📊 Master Dashboard — All Teams</div>",
                unsafe_allow_html=True)

    if df.empty:
        st.info("No data has been entered yet.")
        return

    summary_kpis(df)
    st.markdown("---")

    def lead_of(u):
        if u in users:
            if users[u]["role"] == "leader":
                return u
            return users[u].get("team_lead") or "— unassigned —"
        return "— unknown —"

    df_copy = df.copy()
    df_copy["Team Lead"] = df_copy["added_by"].apply(lead_of)
    df_copy["Team Lead Name"] = df_copy["Team Lead"].apply(
        lambda u: users.get(u, {}).get("display_name", u.capitalize()) if u in users else u
    )

    lead_df = df_copy.groupby("Team Lead Name").agg(
        Spend=("Spend", "sum"), Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"), Conversions=("Conversions", "sum")
    ).reset_index()
    lead_df["ROI"] = (lead_df["Profit"] / lead_df["Spend"].replace(0, pd.NA) * 100).round(2).fillna(0)

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(lead_df, x="Team Lead Name", y=["Revenue", "Spend"], barmode="group",
                     title="Revenue vs Spend by Team Lead",
                     color_discrete_map={"Revenue": "#6366f1", "Spend": "#475569"})
        fig.update_layout(paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                          font=dict(color="#e8eaf0"), height=340,
                          xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        colors = ["#34d399" if p >= 0 else "#f87171" for p in lead_df["Profit"]]
        fig2 = go.Figure(go.Bar(x=lead_df["Team Lead Name"], y=lead_df["Profit"], marker_color=colors))
        fig2.update_layout(title="Profit by Team Lead",
                           paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
                           font=dict(color="#e8eaf0"), height=340,
                           xaxis=dict(gridcolor="#1e2235"), yaxis=dict(gridcolor="#1e2235"))
        st.plotly_chart(fig2, use_container_width=True)

    render_charts(df)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Performance by Team Lead</div>",
                unsafe_allow_html=True)
    disp = lead_df.copy()
    for c in ["Spend", "Revenue", "Profit"]:
        disp[c] = disp[c].apply(lambda x: f"₹{x:,.2f}")
    disp["ROI"] = disp["ROI"].apply(lambda x: f"{x:.2f}%")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Daily Profit Pivot</div>",
                unsafe_allow_html=True)
    pivot_src = df_copy.groupby(["Team Lead Name", df_copy["Date"].dt.strftime("%d %b")]).agg(
        Profit=("Profit", "sum")
    ).reset_index()
    pivot_src.columns = ["Team Lead", "Date", "Profit"]
    pivot_table = pivot_src.pivot(index="Date", columns="Team Lead", values="Profit").fillna(0)
    pivot_table["Total"] = pivot_table.sum(axis=1)
    st.dataframe(pivot_table.style.format("₹{:.2f}"), use_container_width=True)

# ── Admin: By Team Lead ───────────────────────────────────────────────────────
def by_team_lead_page():
    users = load_users()
    data = load_data()
    df = normalize_df(data)

    st.markdown("<div class='section-title'>🎯 By Team Lead</div>", unsafe_allow_html=True)

    leads = [u for u, info in users.items() if info.get("role") == "leader"]
    if not leads:
        st.info("No team leads exist yet. Go to User Management to add one.")
        return

    labels = {u: users[u].get("display_name", u.capitalize()) for u in leads}
    pick = st.selectbox("Select Team Lead", leads, format_func=lambda u: labels[u])

    buyers = get_buyers_for_lead(pick)
    sub = df[df["added_by"].isin(buyers + [pick])] if not df.empty else df

    if sub.empty:
        st.info(f"No data yet for {labels[pick]}'s team.")
        return

    summary_kpis(sub)
    st.markdown("---")
    render_charts(sub)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Entries</div>",
                unsafe_allow_html=True)
    cols_show = ["Date", "Time Slot", "added_by", "PML Code", "Vertical", "Traffic Source",
                 "Spend", "Revenue", "Profit", "ROI", "Conversions", "timestamp"]
    st.dataframe(style_df_for_display(sub)[cols_show], use_container_width=True, hide_index=True)

# ── All Data / Team Data ──────────────────────────────────────────────────────
def all_data_page(scope="all"):
    data = load_data()
    df = normalize_df(data)

    title = "📋 All Data" if scope == "all" else "📋 Team Data"
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)

    if scope == "team":
        buyers = get_buyers_for_lead(st.session_state.username)
        df = df[df["added_by"].isin(buyers)] if not df.empty else df

    if df.empty:
        st.info("No data to show.")
        return

    f1, f2, f3 = st.columns(3)
    with f1:
        date_range = st.date_input(
            "Date range",
            value=(df["Date"].min().date(), df["Date"].max().date()),
        )
    with f2:
        verticals = sorted([v for v in df["Vertical"].dropna().unique() if str(v).strip()])
        vsel = st.multiselect("Vertical", options=verticals, default=[])
    with f3:
        slots_in_data = df["Time Slot"].dropna().unique().tolist()
        slots = [s for s in TIME_SLOTS if s in slots_in_data]
        ssel = st.multiselect("Time Slot", options=slots, default=[])

    if isinstance(date_range, tuple) and len(date_range) == 2:
        df = df[(df["Date"].dt.date >= date_range[0]) & (df["Date"].dt.date <= date_range[1])]
    if vsel:
        df = df[df["Vertical"].isin(vsel)]
    if ssel:
        df = df[df["Time Slot"].isin(ssel)]

    if df.empty:
        st.warning("No entries match your filters.")
        return

    summary_kpis(df)
    st.markdown("---")

    cols_show = ["Date", "Time Slot", "added_by", "team_lead", "PML Code", "Vertical",
                 "Traffic Source", "Platform", "Brands", "Spend", "Revenue", "Profit",
                 "ROI", "Impressions", "Clicks", "Offer Clicks", "Conversions",
                 "CPC", "EPC", "Offer CTR", "Cost per Conv", "timestamp"]
    st.dataframe(style_df_for_display(df)[cols_show], use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, file_name="perftrack_data.csv", mime="text/csv")

# ── Admin: User Management ────────────────────────────────────────────────────
def user_management_page():
    st.markdown("<div class='section-title'>👥 User Management</div>", unsafe_allow_html=True)
    users = load_users()

    rows = []
    for uname, info in users.items():
        lead_u = info.get("team_lead")
        lead_disp = "—"
        if lead_u and lead_u in users:
            lead_disp = users[lead_u].get("display_name", lead_u.capitalize())
        rows.append({
            "Username": uname,
            "Display Name": info.get("display_name", ""),
            "Role": {"member": "Media Buyer", "leader": "Team Leader", "admin": "Admin"}.get(info.get("role"), info.get("role")),
            "Reports To": lead_disp,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("<div class='section-title' style='margin-top:20px;'>➕ Add User</div>",
                unsafe_allow_html=True)

    leads = [u for u, info in users.items() if info.get("role") == "leader"]

    with st.form("add_user_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_username = st.text_input("Username (lowercase, no spaces)")
            new_display = st.text_input("Display Name")
        with c2:
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox(
                "Role", ["member", "leader", "admin"],
                format_func=lambda r: {"member": "Media Buyer", "leader": "Team Leader", "admin": "Admin"}[r],
            )
        with c3:
            assign_lead = st.selectbox(
                "Assign to Team Lead (Media Buyers only)",
                options=["—"] + leads,
                format_func=lambda u: "—" if u == "—" else users[u].get("display_name", u.capitalize()),
            )

        submitted = st.form_submit_button("Add User", use_container_width=True)
        if submitted:
            u = new_username.strip().lower()
            if not u or not new_password or not new_display.strip():
                st.error("Username, password, and display name are required.")
            elif " " in u or not u.isascii():
                st.error("Username must be lowercase ASCII with no spaces.")
            elif u in users:
                st.error(f"Username '{u}' already exists.")
            elif new_role == "member" and assign_lead == "—":
                st.error("Please assign this media buyer to a team lead.")
            else:
                users[u] = {
                    "password": new_password,
                    "role": new_role,
                    "display_name": new_display.strip(),
                    "team_lead": assign_lead if (new_role == "member" and assign_lead != "—") else None,
                }
                save_users(users)
                st.success(f"✅ Created {new_role} '{u}'")
                st.rerun()

    st.markdown("<div class='section-title' style='margin-top:20px;'>✏️ Edit / Delete User</div>",
                unsafe_allow_html=True)

    editable = [u for u in users.keys() if u != st.session_state.username]
    if not editable:
        st.info("No other users yet.")
        return

    target = st.selectbox(
        "Select user", editable,
        format_func=lambda u: f"{users[u].get('display_name', u.capitalize())}  ({u}, {users[u]['role']})",
    )
    tinfo = users[target]

    with st.form(f"edit_form_{target}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            e_display = st.text_input("Display Name", value=tinfo.get("display_name", ""))
            e_password = st.text_input("New Password (leave blank to keep)", type="password")
        with c2:
            e_role = st.selectbox(
                "Role", ["member", "leader", "admin"],
                index=["member", "leader", "admin"].index(tinfo["role"]),
                format_func=lambda r: {"member": "Media Buyer", "leader": "Team Leader", "admin": "Admin"}[r],
            )
        with c3:
            leads_now = [u for u, info in users.items() if info.get("role") == "leader" and u != target]
            current_lead = tinfo.get("team_lead") or "—"
            options = ["—"] + leads_now
            default_idx = options.index(current_lead) if current_lead in options else 0
            e_lead = st.selectbox(
                "Reports To (Media Buyers only)",
                options=options, index=default_idx,
                format_func=lambda u: "—" if u == "—" else users[u].get("display_name", u.capitalize()),
            )

        sc1, sc2 = st.columns(2)
        with sc1:
            save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
        with sc2:
            delete_btn = st.form_submit_button("🗑️ Delete User", use_container_width=True)

        if save_btn:
            tinfo["display_name"] = e_display.strip() or tinfo["display_name"]
            if e_password:
                tinfo["password"] = e_password
            tinfo["role"] = e_role
            tinfo["team_lead"] = e_lead if (e_role == "member" and e_lead != "—") else None
            users[target] = tinfo
            save_users(users)
            st.success(f"✅ Updated '{target}'")
            st.rerun()

        if delete_btn:
            if tinfo["role"] == "leader":
                for uname, info in users.items():
                    if info.get("team_lead") == target:
                        info["team_lead"] = None
            del users[target]
            save_users(users)
            st.success(f"🗑️ Deleted '{target}'")
            st.rerun()

# ── My Account (any user) ─────────────────────────────────────────────────────
def my_account_page():
    st.markdown("<div class='section-title'>🔑 My Account</div>", unsafe_allow_html=True)
    users = load_users()
    me = st.session_state.username
    info = users[me]

    st.markdown(f"""
    <div class='metric-card' style='margin-bottom:20px;'>
        <div class='metric-label'>Username</div>
        <div style='font-family:Syne,sans-serif; font-size:1.4rem; font-weight:700; color:#e8eaf0;'>{me}</div>
        <div style='color:#6b7280; font-size:0.85rem; margin-top:6px;'>Role: {info['role'].capitalize()}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("my_account_form"):
        new_display = st.text_input("Display Name", value=info.get("display_name", ""))
        current_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password (leave blank to keep)", type="password")
        confirm_pwd = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Save Changes", use_container_width=True)

        if submitted:
            if current_pwd != info["password"]:
                st.error("Current password is incorrect.")
            elif new_pwd and new_pwd != confirm_pwd:
                st.error("New passwords do not match.")
            else:
                info["display_name"] = new_display.strip() or info["display_name"]
                if new_pwd:
                    info["password"] = new_pwd
                users[me] = info
                save_users(users)
                st.session_state.display_name = info["display_name"]
                st.success("✅ Account updated.")
                st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    login_page()
else:
    page = sidebar()
    role = st.session_state.role

    if role == "admin":
        if page == "📊 Master Dashboard":
            master_dashboard_page()
        elif page == "🎯 By Team Lead":
            by_team_lead_page()
        elif page == "👤 By Media Buyer":
            by_media_buyer_page()
        elif page == "📋 All Data":
            all_data_page(scope="all")
        elif page == "👥 User Management":
            user_management_page()
        elif page == "🔑 My Account":
            my_account_page()

    elif role == "leader":
        if page == "📊 Team Dashboard":
            leader_team_dashboard()
        elif page == "👤 By Media Buyer":
            by_media_buyer_page()
        elif page == "📋 Team Data":
            all_data_page(scope="team")
        elif page == "🔑 My Account":
            my_account_page()

    else:  # member
        if page == "📥 Add Data":
            add_data_page()
        elif page == "📈 My Dashboard":
            my_dashboard_page()
        elif page == "🔑 My Account":
            my_account_page()
