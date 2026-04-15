import streamlit as st
import pandas as pd
import sqlite3
import json
import os
from datetime import datetime, date
from contextlib import contextmanager
import plotly.express as px
import plotly.graph_objects as go

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PerfTrack — Team Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_FILE = "perftrack.db"
USERS_FILE = "users.json"
LEGACY_DATA_FILE = "data.json"  # auto-migrated on first run

TIME_SLOTS = [
    "Entire Day",
    "1st Hr", "2nd Hr", "3rd Hr", "4th Hr", "5th Hr", "6th Hr", "7th Hr",
    "8th Hr", "9th Hr", "10th Hr", "11th Hr", "12th Hr", "13th Hr",
]

# Internal SQL column → friendly display name
COLUMN_MAP = {
    "id": "id",
    "date": "Date",
    "time_slot": "Time Slot",
    "timestamp": "Timestamp",
    "team_lead": "team_lead",
    "added_by": "added_by",
    "added_by_name": "Added By",
    "added_by_role": "Role",
    # Categorization
    "account": "Account",
    "campaign": "Campaign",
    "vertical": "Vertical",
    "pml_code": "PML Code",
    "traffic_source": "Traffic Source",
    "platform": "Platform",
    "brands": "Advertiser",
    # Traffic
    "impressions": "Impressions",
    "clicks": "Clicks",
    "ulc": "U.L.C.",
    "lp_views": "LP Views",
    "lp_clicks": "LP Clicks",
    "conversions": "Conversions",
    "initiate_checkout": "Initiate Checkout",
    # Financial
    "spend": "Spend",
    "revenue": "Revenue",
    "profit": "Profit",
    "roi": "ROI",
    "avg_payout": "Avg Payout",
    # Cost-per
    "cpc": "CPC",
    "u_cpc": "U.CPC",
    "cpm": "CPM",
    "cpl": "CPL",
    "epc": "EPC",
    "offer_epc": "Offer EPC",
    "rpl": "RPL",
    "appl": "APPL",
    "offer_cpc": "Offer CPC",
    "offer_page_cpc": "Offer Page CPC",
    # Rates
    "ulc_ctr": "U.L.C. CTR",
    "lp_ctr": "LP CTR",
    "offer_cr": "Offer CR",
}

CURRENCY_COLS = {"Spend", "Revenue", "Profit", "Avg Payout",
                 "CPC", "U.CPC", "CPM", "CPL", "EPC", "Offer EPC",
                 "RPL", "APPL", "Offer CPC", "Offer Page CPC"}
PERCENT_COLS  = {"ROI", "U.L.C. CTR", "LP CTR", "Offer CR"}
INT_COLS      = {"Impressions", "Clicks", "U.L.C.", "LP Views",
                 "LP Clicks", "Conversions", "Initiate Checkout"}

# ── Database layer ────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    time_slot TEXT,
    timestamp TEXT,
    team_lead TEXT,
    added_by TEXT,
    added_by_name TEXT,
    added_by_role TEXT,
    account TEXT,
    campaign TEXT,
    vertical TEXT,
    pml_code TEXT,
    traffic_source TEXT,
    platform TEXT,
    brands TEXT,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ulc INTEGER DEFAULT 0,
    lp_views INTEGER DEFAULT 0,
    lp_clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    initiate_checkout INTEGER DEFAULT 0,
    spend REAL DEFAULT 0,
    revenue REAL DEFAULT 0,
    profit REAL DEFAULT 0,
    roi REAL DEFAULT 0,
    avg_payout REAL DEFAULT 0,
    cpc REAL DEFAULT 0,
    u_cpc REAL DEFAULT 0,
    cpm REAL DEFAULT 0,
    cpl REAL DEFAULT 0,
    epc REAL DEFAULT 0,
    offer_epc REAL DEFAULT 0,
    rpl REAL DEFAULT 0,
    appl REAL DEFAULT 0,
    offer_cpc REAL DEFAULT 0,
    offer_page_cpc REAL DEFAULT 0,
    ulc_ctr REAL DEFAULT 0,
    lp_ctr REAL DEFAULT 0,
    offer_cr REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_team_lead ON entries(team_lead);
CREATE INDEX IF NOT EXISTS idx_added_by ON entries(added_by);
CREATE INDEX IF NOT EXISTS idx_date ON entries(date);
CREATE INDEX IF NOT EXISTS idx_account ON entries(account);
"""

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    # one-time migration from legacy data.json if DB has no rows
    if os.path.exists(LEGACY_DATA_FILE):
        with get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM entries").fetchone()["c"]
        if count == 0:
            try:
                with open(LEGACY_DATA_FILE, "r") as f:
                    legacy = json.load(f)
                migrate_legacy(legacy)
            except Exception as e:
                print(f"Legacy migration skipped: {e}")

def migrate_legacy(rows):
    """Map old data.json shape into the new entries table."""
    for r in rows:
        clicks      = r.get("Clicks", r.get("FB Link Clicks", 0)) or 0
        lp_clicks   = r.get("LP Clicks", r.get("Offer Clicks", 0)) or 0
        spend       = float(r.get("Spend", 0) or 0)
        revenue     = float(r.get("Revenue", 0) or 0)
        impressions = int(r.get("Impressions", 0) or 0)
        conversions = int(r.get("Conversions", 0) or 0)
        team_lead   = r.get("team_lead") or r.get("team") or ""
        entry = {
            "Date": r.get("Date", str(date.today())),
            "Time Slot": r.get("Time Slot", ""),
            "Timestamp": r.get("Timestamp", ""),
            "team_lead": team_lead,
            "added_by": r.get("added_by", ""),
            "added_by_name": r.get("added_by_name", r.get("added_by", "")),
            "added_by_role": r.get("added_by_role", "member"),
            "Account": r.get("Accounts", r.get("Account", "")),
            "Campaign": r.get("Campaign", ""),
            "Vertical": r.get("Vertical", ""),
            "PML Code": r.get("PML Code", ""),
            "Traffic Source": r.get("Traffic Source", ""),
            "Platform": r.get("Platform", ""),
            "Brands": r.get("Brands", ""),
            "Impressions": impressions,
            "Clicks": int(clicks),
            "U.L.C.": 0,
            "LP Views": 0,
            "LP Clicks": int(lp_clicks),
            "Conversions": conversions,
            "Initiate Checkout": 0,
            "Spend": spend,
            "Revenue": revenue,
        }
        insert_entry(entry)

def insert_entry(entry: dict):
    """Compute auto-metrics and insert."""
    spend         = float(entry.get("Spend", 0) or 0)
    revenue       = float(entry.get("Revenue", 0) or 0)
    impressions   = int(entry.get("Impressions", 0) or 0)
    clicks        = int(entry.get("Clicks", 0) or 0)
    ulc           = int(entry.get("U.L.C.", 0) or 0)
    lp_views      = int(entry.get("LP Views", 0) or 0)
    lp_clicks     = int(entry.get("LP Clicks", 0) or 0)
    conversions   = int(entry.get("Conversions", 0) or 0)
    init_checkout = int(entry.get("Initiate Checkout", 0) or 0)

    profit         = revenue - spend
    roi            = (profit / spend * 100) if spend > 0 else 0
    avg_payout     = (revenue / conversions) if conversions > 0 else 0
    cpc            = (spend / clicks) if clicks > 0 else 0
    u_cpc          = (spend / ulc) if ulc > 0 else 0
    cpm            = (spend / impressions * 1000) if impressions > 0 else 0
    cpl            = (spend / conversions) if conversions > 0 else 0
    epc            = (revenue / clicks) if clicks > 0 else 0
    offer_epc      = (revenue / lp_clicks) if lp_clicks > 0 else 0
    rpl            = (revenue / conversions) if conversions > 0 else 0
    appl           = (profit / conversions) if conversions > 0 else 0
    offer_cpc      = (spend / lp_clicks) if lp_clicks > 0 else 0
    offer_page_cpc = (spend / lp_views) if lp_views > 0 else 0
    ulc_ctr        = (ulc / impressions * 100) if impressions > 0 else 0
    lp_ctr         = (lp_clicks / lp_views * 100) if lp_views > 0 else 0
    offer_cr       = (conversions / lp_clicks * 100) if lp_clicks > 0 else 0

    cols = [
        "date","time_slot","timestamp","team_lead","added_by","added_by_name","added_by_role",
        "account","campaign","vertical","pml_code","traffic_source","platform","brands",
        "impressions","clicks","ulc","lp_views","lp_clicks","conversions","initiate_checkout",
        "spend","revenue","profit","roi","avg_payout",
        "cpc","u_cpc","cpm","cpl","epc","offer_epc","rpl","appl","offer_cpc","offer_page_cpc",
        "ulc_ctr","lp_ctr","offer_cr",
    ]
    vals = [
        entry.get("Date"), entry.get("Time Slot",""), entry.get("Timestamp",""),
        entry.get("team_lead",""), entry.get("added_by",""),
        entry.get("added_by_name",""), entry.get("added_by_role",""),
        entry.get("Account",""), entry.get("Campaign",""), entry.get("Vertical",""),
        entry.get("PML Code",""), entry.get("Traffic Source",""),
        entry.get("Platform",""), entry.get("Brands",""),
        impressions, clicks, ulc, lp_views, lp_clicks, conversions, init_checkout,
        spend, revenue,
        round(profit, 2), round(roi, 2), round(avg_payout, 4),
        round(cpc, 4), round(u_cpc, 4), round(cpm, 4), round(cpl, 2),
        round(epc, 4), round(offer_epc, 4), round(rpl, 4), round(appl, 4),
        round(offer_cpc, 4), round(offer_page_cpc, 4),
        round(ulc_ctr, 2), round(lp_ctr, 2), round(offer_cr, 2),
    ]
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO entries ({','.join(cols)}) VALUES ({placeholders})"
    with get_conn() as conn:
        conn.execute(sql, vals)

def fetch_entries(team_lead=None, media_buyer=None, account=None) -> pd.DataFrame:
    sql = "SELECT * FROM entries WHERE 1=1"
    args = []
    if team_lead:
        sql += " AND team_lead = ?"; args.append(team_lead)
    if media_buyer:
        sql += " AND added_by = ?"; args.append(media_buyer)
    if account:
        sql += " AND account = ?"; args.append(account)
    sql += " ORDER BY date DESC, timestamp DESC"
    with get_conn() as conn:
        df = pd.read_sql_query(sql, conn, params=args)
    if df.empty:
        return df
    df = df.rename(columns=COLUMN_MAP)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

def list_accounts(team_lead=None, media_buyer=None) -> list:
    sql = "SELECT DISTINCT account FROM entries WHERE account != ''"
    args = []
    if team_lead:
        sql += " AND team_lead = ?"; args.append(team_lead)
    if media_buyer:
        sql += " AND added_by = ?"; args.append(media_buyer)
    sql += " ORDER BY account"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [r["account"] for r in rows]

# ── Users / Auth ─────────────────────────────────────────────────────────────
DEFAULT_USERS = {
    "admin": {"password": "admin123", "role": "admin", "display_name": "Admin", "team_lead": None}
}

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    save_users(DEFAULT_USERS)
    return dict(DEFAULT_USERS)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ── Per-user saved accounts & templates ──────────────────────────────────────
def get_user_accounts(username: str) -> list:
    users = load_users()
    return list(users.get(username, {}).get("accounts", []))

def add_user_account(username: str, account: str):
    account = (account or "").strip()
    if not account:
        return
    users = load_users()
    if username not in users:
        return
    accts = users[username].setdefault("accounts", [])
    if account not in accts:
        accts.append(account)
        save_users(users)

def remove_user_account(username: str, account: str):
    users = load_users()
    if username in users and "accounts" in users[username]:
        users[username]["accounts"] = [a for a in users[username]["accounts"] if a != account]
        save_users(users)

def get_user_templates(username: str) -> dict:
    users = load_users()
    return dict(users.get(username, {}).get("templates", {}))

def save_user_template(username: str, name: str, data: dict):
    name = (name or "").strip()
    if not name:
        return
    users = load_users()
    if username not in users:
        return
    users[username].setdefault("templates", {})[name] = data
    save_users(users)

def delete_user_template(username: str, name: str):
    users = load_users()
    if username in users and name in users[username].get("templates", {}):
        del users[username]["templates"][name]
        save_users(users)

# ── Boot ──────────────────────────────────────────────────────────────────────
init_db()

# ── Theme & CSS ───────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

THEMES = {
    "dark": {
        "bg":        "#0d0f14",
        "bg_alt":    "#111420",
        "card":      "#141824",
        "card_alt":  "#1a1f30",
        "border":    "#252a3d",
        "border_2":  "#1e2235",
        "text":      "#e8eaf0",
        "text_2":    "#c7cde8",
        "text_dim":  "#9ca3af",
        "accent":    "#7c8dff",
        "accent_2":  "#a78bfa",
        "input_bg":  "#0d0f14",
        "th_bg":     "#1a1f30",
    },
    "light": {
        "bg":        "#f5f6fa",
        "bg_alt":    "#ffffff",
        "card":      "#ffffff",
        "card_alt":  "#fafbff",
        "border":    "#e3e6ee",
        "border_2":  "#eef0f6",
        "text":      "#1a1d29",
        "text_2":    "#2d3142",
        "text_dim":  "#6b7280",
        "accent":    "#4f46e5",
        "accent_2":  "#7c3aed",
        "input_bg":  "#ffffff",
        "th_bg":     "#f0f2f8",
    },
}

def render_css(theme_name: str):
    t = THEMES[theme_name]
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    font-size: 15px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}
h1, h2, h3, h4, h5 {{ font-family: 'Inter', sans-serif; font-weight: 700; letter-spacing: -0.015em; }}
p, label, span, div {{ font-size: 0.94rem; line-height: 1.55; }}

.stApp {{ background: {t['bg']}; color: {t['text']}; }}

[data-testid="stSidebar"] {{
    background: {t['bg_alt']};
    border-right: 1px solid {t['border_2']};
}}

/* ── Metric Cards ── */
.metric-card {{
    background: {t['card']};
    border: 1px solid {t['border']};
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 12px;
    min-height: 96px;
    transition: transform 0.15s, box-shadow 0.15s;
}}
.metric-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px {('#00000040' if theme_name == 'dark' else '#0000001a')};
}}

.metric-value {{
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
    font-size: clamp(1.05rem, 1.5vw, 1.55rem);
    font-weight: 700;
    color: {t['accent']};
    letter-spacing: -0.02em;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.metric-label {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {t['text_dim']};
    margin-bottom: 8px;
    font-weight: 600;
}}

.profit-pos {{ color: #10b981; }}
.profit-neg {{ color: #ef4444; }}

/* ── Tables ── */
.stDataFrame {{ border-radius: 10px; overflow: hidden; }}
div[data-testid="stDataFrame"] table {{ font-size: 0.92rem !important; font-family: 'Inter', sans-serif; }}
div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {{
    padding: 10px 14px !important;
}}
div[data-testid="stDataFrame"] th {{
    background: {t['th_bg']} !important;
    color: {t['text_2']} !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
div[data-testid="stDataFrame"] td {{ color: {t['text']} !important; }}

/* Numeric columns get monospace for clean alignment */
div[data-testid="stDataFrame"] td:has-text("$"),
div[data-testid="stDataFrame"] td {{
    font-variant-numeric: tabular-nums;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
.stTabs [data-baseweb="tab"] {{
    font-family: 'Inter', sans-serif;
    font-size: 0.92rem;
    font-weight: 600;
    color: {t['text_dim']};
}}
.stTabs [aria-selected="true"] {{ color: {t['accent_2']} !important; }}

/* ── Badges ── */
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.badge-admin  {{ background: #dc262622; color: #ef4444; border: 1px solid #dc262655; }}
.badge-leader {{ background: #7c3aed22; color: {t['accent_2']}; border: 1px solid #7c3aed55; }}
.badge-member {{ background: #0891b222; color: #0891b2; border: 1px solid #0891b255; }}

/* ── Section headings ── */
.section-title {{
    font-family: 'Inter', sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: {t['text_2']};
    border-bottom: 1px solid {t['border']};
    padding-bottom: 12px;
    margin-bottom: 22px;
    letter-spacing: -0.015em;
}}

.subsection {{
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    font-weight: 700;
    color: {t['accent_2']};
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 18px 0 10px;
}}

/* ── Forms & Inputs ── */
div[data-testid="stForm"] {{
    background: {t['card']};
    border: 1px solid {t['border']};
    border-radius: 14px;
    padding: 24px;
}}

.stButton > button {{
    background: linear-gradient(135deg, {t['accent']}, {t['accent_2']});
    color: white;
    border: none;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    padding: 9px 22px;
    font-size: 0.92rem;
    transition: all 0.15s;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 18px {t['accent']}40;
}}

[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {{
    background: {t['input_bg']} !important;
    border: 1px solid {t['border']} !important;
    color: {t['text']} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
}}

/* Theme toggle button styling */
.theme-toggle button {{
    background: {t['card']} !important;
    color: {t['text_2']} !important;
    border: 1px solid {t['border']} !important;
    box-shadow: none !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: {t['bg']}; }}
::-webkit-scrollbar-thumb {{ background: {t['border']}; border-radius: 5px; }}
::-webkit-scrollbar-thumb:hover {{ background: {t['accent']}; }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

render_css(st.session_state.theme)

# ── Session state ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.display_name = ""
    st.session_state.team_lead = None

# ── Login ─────────────────────────────────────────────────────────────────────
def login_page():
    users = load_users()
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
                Team Performance Dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                u = username.strip().lower()
                if u in users and users[u]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = users[u]["role"]
                    st.session_state.display_name = users[u].get("display_name", u.capitalize())
                    st.session_state.team_lead = users[u].get("team_lead")
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

# ── Sidebar ────────────────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        t = THEMES[st.session_state.theme]
        st.markdown(f"""
        <div style='font-family:Inter,sans-serif; font-size:1.5rem; font-weight:800;
                    background:linear-gradient(135deg,{t['accent']},{t['accent_2']});
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                    padding: 10px 0 4px; letter-spacing: -0.02em;'>
            📊 PerfTrack
        </div>
        """, unsafe_allow_html=True)

        role = st.session_state.role
        role_badge = {"admin": "badge-admin", "leader": "badge-leader", "member": "badge-member"}[role]
        role_label = {"admin": "Admin", "leader": "Team Lead", "member": "Media Buyer"}[role]

        sub = ""
        if role == "member" and st.session_state.team_lead:
            sub = f" · under {st.session_state.team_lead.capitalize()}"

        st.markdown(f"""
        <div style='margin-bottom:20px;'>
            <div style='color:{t["text"]}; font-weight:600; font-size:1rem;'>
                {st.session_state.display_name}
            </div>
            <span class='badge {role_badge}'>{role_label}</span>
            <span style='color:{t["text_dim"]}; font-size:0.8rem;'>{sub}</span>
        </div>
        <hr style='border:none; border-top:1px solid {t["border_2"]}; margin:10px 0 16px;'>
        """, unsafe_allow_html=True)

        # Page list per role
        if role == "admin":
            pages = ["📊 Master Dashboard", "👥 Team Overview",
                     "🔬 Deep Analytics", "⚙️ User Management"]
        elif role == "leader":
            pages = ["📝 Add Metrics", "📈 My Dashboard", "👥 Team Overview",
                     "🎯 My Accounts"]
        else:  # member
            pages = ["📝 Add Metrics", "📈 My Dashboard", "🎯 My Accounts"]

        page = st.radio("Navigation", pages, label_visibility="collapsed")

        st.markdown("<hr style='border:none; border-top:1px solid; opacity:0.15; margin:20px 0;'>",
                    unsafe_allow_html=True)

        # Theme toggle
        is_light = st.session_state.theme == "light"
        new_is_light = st.toggle("☀️  Light Mode" if not is_light else "🌙  Dark Mode",
                                 value=is_light, key="theme_toggle")
        new_theme = "light" if new_is_light else "dark"
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()

        if st.button("🚪 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        return page

# ── Helpers ───────────────────────────────────────────────────────────────────
# ── Plotly theming helper ─────────────────────────────────────────────────────
def plotly_layout(theme_name=None, **extra):
    """Return common plotly layout kwargs that respect the active theme."""
    if theme_name is None:
        theme_name = st.session_state.get("theme", "dark")
    t = THEMES[theme_name]
    grid = t["border"] if theme_name == "dark" else t["border_2"]
    legend_bg = t["card"]
    base = dict(
        paper_bgcolor=t["bg"],
        plot_bgcolor=t["bg"],
        font=dict(color=t["text"], family="Inter, sans-serif", size=12),
        legend=dict(bgcolor=legend_bg, bordercolor=t["border"]),
        xaxis=dict(gridcolor=grid, zerolinecolor=grid),
        yaxis=dict(gridcolor=grid, zerolinecolor=grid),
        margin=dict(l=40, r=20, t=50, b=40),
    )
    base.update(extra)
    return base

def metric_card(col, label, value, color_val=None):
    with col:
        c = ""
        if color_val is not None:
            c = "profit-pos" if color_val >= 0 else "profit-neg"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>{label}</div>
            <div class='metric-value {c}'>{value}</div>
        </div>
        """, unsafe_allow_html=True)

def fmt_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Format numeric columns ($ / % / int) on a copy for st.dataframe."""
    if df.empty:
        return df
    out = df.copy()
    # Drop columns we never want to show
    out = out.drop(columns=["Traffic Source"], errors="ignore")
    if "Date" in out.columns and pd.api.types.is_datetime64_any_dtype(out["Date"]):
        out["Date"] = out["Date"].dt.strftime("%d %b %Y")
    for c in CURRENCY_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "")
    for c in PERCENT_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").apply(
                lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    for c in INT_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else "")
    return out

# ── Add Data Page ─────────────────────────────────────────────────────────────
def add_data_page():
    st.markdown("<div class='section-title'>📝 Metrics</div>", unsafe_allow_html=True)

    users = load_users()
    role = st.session_state.role
    username = st.session_state.username

    attach_lead = None
    if role == "member":
        attach_lead = st.session_state.team_lead
        if not attach_lead:
            st.warning("You're not assigned to a team lead. Ask the admin to assign you.")
            return
    elif role == "leader":
        attach_lead = st.session_state.username

    # ── Templates panel (outside form so Apply can rerun) ────────────────────
    saved_accounts = get_user_accounts(username)
    templates = get_user_templates(username)

    if templates or saved_accounts:
        with st.expander("📋 Quick Apply Template", expanded=False):
            if templates:
                tcol1, tcol2, tcol3 = st.columns([3, 1, 1])
                with tcol1:
                    sel = st.selectbox("Select a saved template",
                                       ["(none)"] + list(templates.keys()),
                                       key="tpl_select")
                with tcol2:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("Apply", use_container_width=True, key="tpl_apply"):
                        if sel != "(none)":
                            tpl = templates[sel]
                            st.session_state["form_account"]   = tpl.get("account", "")
                            st.session_state["form_campaign"]  = tpl.get("campaign", "")
                            st.session_state["form_vertical"]  = tpl.get("vertical", "")
                            st.session_state["form_pml"]       = tpl.get("pml_code", "")
                            st.session_state["form_platform"]  = tpl.get("platform", "")
                            st.session_state["form_advertiser"]= tpl.get("advertiser", "")
                            st.success(f"✅ Template '{sel}' applied")
                            st.rerun()
                with tcol3:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️ Delete", use_container_width=True, key="tpl_delete"):
                        if sel != "(none)":
                            delete_user_template(username, sel)
                            st.success(f"Deleted '{sel}'")
                            st.rerun()
            else:
                st.caption("No templates saved yet — save one from the form below.")

    # ── Main entry form ──────────────────────────────────────────────────────
    with st.form("add_data_form", clear_on_submit=False):
        st.markdown("<div class='subsection'>📁 Categorization</div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            entry_date = st.date_input("Date", value=date.today())
            time_slot = st.selectbox("Time Slot", TIME_SLOTS,
                                     help="Pick 'Entire Day' for a single end-of-day entry")

        with c2:
            # Account picker — saved accounts dropdown + new option
            ADD_NEW = "➕ Add new account"
            options = saved_accounts + [ADD_NEW] if saved_accounts else [ADD_NEW]
            default_account = st.session_state.get("form_account", "")
            if default_account and default_account in saved_accounts:
                acct_idx = saved_accounts.index(default_account)
            else:
                acct_idx = 0
            acct_choice = st.selectbox("Account *", options, index=acct_idx, key="acct_choice")
            new_acct_input = ""
            if acct_choice == ADD_NEW:
                new_acct_input = st.text_input("New account name",
                                               value=default_account if default_account not in saved_accounts else "",
                                               placeholder="e.g. Plum-0902226-001",
                                               key="new_acct_input")
            campaign = st.text_input("Campaign",
                                     value=st.session_state.get("form_campaign", ""),
                                     placeholder="e.g. Spring-Sale-CA",
                                     key="form_campaign_inp")

        with c3:
            vertical = st.text_input("Vertical",
                                     value=st.session_state.get("form_vertical", ""),
                                     placeholder="e.g. Finance",
                                     key="form_vertical_inp")
            pml_code = st.text_input("PML Code",
                                     value=st.session_state.get("form_pml", ""),
                                     placeholder="e.g. PML-0912",
                                     key="form_pml_inp")

        c4, c5 = st.columns(2)
        with c4:
            platform = st.text_input("Platform",
                                     value=st.session_state.get("form_platform", ""),
                                     placeholder="e.g. Meta",
                                     key="form_platform_inp")
        with c5:
            advertiser = st.text_input("Advertiser",
                                       value=st.session_state.get("form_advertiser", ""),
                                       placeholder="e.g. Acme Corp",
                                       key="form_advertiser_inp")

        # Lead attachment
        if role == "admin":
            leads = [u for u, v in users.items() if v["role"] == "leader"]
            lead_options = ["(none)"] + leads
            chosen = st.selectbox("Attach to Team Lead", lead_options)
            attach_lead = None if chosen == "(none)" else chosen
        else:
            st.caption(f"Team Lead: **{attach_lead}**")

        # ── Financial ──
        st.markdown("<div class='subsection'>💰 Financial</div>", unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        with f1:
            spend = st.number_input("Spend ($)", min_value=0.0, step=0.01, format="%.2f")
        with f2:
            revenue = st.number_input("Revenue ($)", min_value=0.0, step=0.01, format="%.2f")

        # ── Traffic & Engagement ──
        st.markdown("<div class='subsection'>📊 Traffic & Engagement</div>", unsafe_allow_html=True)
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            impressions = st.number_input("Impressions", min_value=0, step=1)
            clicks      = st.number_input("Clicks", min_value=0, step=1)
        with t2:
            ulc         = st.number_input("U.L.C. (Unique Link Clicks)", min_value=0, step=1)
            lp_views    = st.number_input("LP Views", min_value=0, step=1)
        with t3:
            lp_clicks   = st.number_input("LP Clicks", min_value=0, step=1)
            conversions = st.number_input("Conversions", min_value=0, step=1)
        with t4:
            init_checkout = st.number_input("Initiate Checkout (optional)",
                                            min_value=0, step=1,
                                            help="Leave 0 if not tracked")

        st.info("Auto-calculated: Profit, ROI, Avg Payout, CPC, U.CPC, CPM, CPL, EPC, Offer EPC, "
                "RPL, APPL, Offer CPC, Offer Page CPC, U.L.C. CTR, LP CTR, Offer CR.")

        # ── Save as template (inside form) ──
        st.markdown("<div class='subsection'>💾 Save as Template (optional)</div>",
                    unsafe_allow_html=True)
        s1, s2 = st.columns([2, 3])
        with s1:
            save_as_tpl = st.checkbox("Save these categorization fields as a template",
                                      key="save_tpl_chk")
        with s2:
            tpl_name = st.text_input("Template name", placeholder="e.g. Daily Finance/Meta",
                                     key="save_tpl_name")

        submitted = st.form_submit_button("➕ Add Entry", use_container_width=True)

        if submitted:
            account = new_acct_input.strip() if acct_choice == ADD_NEW else acct_choice
            if not account or account == ADD_NEW:
                st.error("Account Name is required.")
            elif spend == 0 and revenue == 0:
                st.warning("Both Spend and Revenue are 0. Please check your data.")
            else:
                # Auto-save new account into user's saved list
                if account not in saved_accounts:
                    add_user_account(username, account)

                entry = {
                    "Date": str(entry_date),
                    "Time Slot": time_slot,
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "team_lead": attach_lead or "",
                    "added_by": username,
                    "added_by_name": st.session_state.display_name,
                    "added_by_role": role,
                    "Account": account,
                    "Campaign": campaign.strip(),
                    "Vertical": vertical.strip(),
                    "PML Code": pml_code.strip(),
                    "Traffic Source": "",
                    "Platform": platform.strip(),
                    "Brands": advertiser.strip(),
                    "Impressions": impressions,
                    "Clicks": clicks,
                    "U.L.C.": ulc,
                    "LP Views": lp_views,
                    "LP Clicks": lp_clicks,
                    "Conversions": conversions,
                    "Initiate Checkout": init_checkout,
                    "Spend": spend,
                    "Revenue": revenue,
                }
                insert_entry(entry)

                msgs = [f"✅ Entry saved — {account} · {time_slot} · {entry_date}"]

                # Save template if requested
                if save_as_tpl:
                    if not tpl_name.strip():
                        st.warning("Template was not saved — name is empty.")
                    else:
                        save_user_template(username, tpl_name.strip(), {
                            "account": account,
                            "campaign": campaign.strip(),
                            "vertical": vertical.strip(),
                            "pml_code": pml_code.strip(),
                            "platform": platform.strip(),
                            "advertiser": advertiser.strip(),
                        })
                        msgs.append(f"📋 Template '{tpl_name.strip()}' saved.")

                st.success("  ".join(msgs))

    # Recent entries for this user
    df = fetch_entries(media_buyer=username)
    if not df.empty:
        st.markdown("<div class='section-title' style='margin-top:30px;'>Your Recent Entries</div>",
                    unsafe_allow_html=True)
        cols = ["Date","Time Slot","Timestamp","Account","Campaign","Spend","Revenue",
                "Profit","ROI","Conversions"]
        cols = [c for c in cols if c in df.columns]
        st.dataframe(fmt_df_for_display(df.head(10)[cols]),
                     use_container_width=True, hide_index=True)


# ── My Accounts page (members & leaders) ──────────────────────────────────────
def my_accounts_page():
    username = st.session_state.username
    st.markdown("<div class='section-title'>🎯 My Ad Accounts & Templates</div>",
                unsafe_allow_html=True)

    tab_acct, tab_tpl = st.tabs(["💼 Ad Accounts", "📋 Templates"])

    # ── Accounts tab ──
    with tab_acct:
        st.caption("Save your ad accounts here — they'll appear as a dropdown in the Add Metrics form.")
        accts = get_user_accounts(username)

        with st.form("add_acct_form", clear_on_submit=True):
            new_acct = st.text_input("Add a new ad account",
                                     placeholder="e.g. Plum-0902226-001")
            if st.form_submit_button("➕ Add Account"):
                if new_acct.strip():
                    if new_acct.strip() in accts:
                        st.warning(f"'{new_acct.strip()}' is already saved.")
                    else:
                        add_user_account(username, new_acct.strip())
                        st.success(f"✅ Added '{new_acct.strip()}'.")
                        st.rerun()
                else:
                    st.error("Account name is required.")

        st.markdown("**Your saved accounts**")
        if not accts:
            st.info("No saved accounts yet.")
        else:
            for a in accts:
                col_a, col_b = st.columns([5, 1])
                col_a.markdown(f"<div style='padding:10px 14px; background:#141824; "
                               f"border:1px solid #252a3d; border-radius:10px; margin-bottom:6px;'>"
                               f"<code style='color:#a78bfa;'>{a}</code></div>",
                               unsafe_allow_html=True)
                if col_b.button("🗑️", key=f"del_acct_{a}", help=f"Remove {a}"):
                    remove_user_account(username, a)
                    st.rerun()

    # ── Templates tab ──
    with tab_tpl:
        st.caption("Templates pre-fill the Categorization fields on the Add Metrics form. "
                   "Save the most-used field combinations to enter data faster.")
        tpls = get_user_templates(username)

        if not tpls:
            st.info("No templates saved yet. Tick **'Save as template'** at the bottom of the "
                    "Add Metrics form to create one.")
        else:
            for name, data in tpls.items():
                with st.container():
                    col_a, col_b = st.columns([5, 1])
                    with col_a:
                        st.markdown(f"<div style='padding:14px; background:#141824; "
                                    f"border:1px solid #252a3d; border-radius:12px; "
                                    f"margin-bottom:10px;'>"
                                    f"<div style='font-family:Syne; font-weight:700; "
                                    f"color:#a78bfa; font-size:1.05rem; margin-bottom:8px;'>"
                                    f"📋 {name}</div>"
                                    f"<div style='color:#9ca3af; font-size:0.9rem; line-height:1.7;'>"
                                    f"<b>Account:</b> {data.get('account','—')} &nbsp;·&nbsp; "
                                    f"<b>Campaign:</b> {data.get('campaign','—')} &nbsp;·&nbsp; "
                                    f"<b>Vertical:</b> {data.get('vertical','—')}<br>"
                                    f"<b>PML:</b> {data.get('pml_code','—')} &nbsp;·&nbsp; "
                                    f"<b>Platform:</b> {data.get('platform','—')} &nbsp;·&nbsp; "
                                    f"<b>Advertiser:</b> {data.get('advertiser','—')}"
                                    f"</div></div>",
                                    unsafe_allow_html=True)
                    with col_b:
                        st.markdown("<div style='height:34px;'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_tpl_{name}", help=f"Delete template {name}"):
                            delete_user_template(username, name)
                            st.rerun()

# ── KPI block ──────────────────────────────────────────────────────────────────
def render_kpis(df):
    spend   = df["Spend"].sum()       if "Spend"       in df else 0
    revenue = df["Revenue"].sum()     if "Revenue"     in df else 0
    profit  = df["Profit"].sum()      if "Profit"      in df else 0
    conv    = df["Conversions"].sum() if "Conversions" in df else 0
    impr    = df["Impressions"].sum() if "Impressions" in df else 0
    clicks  = df["Clicks"].sum()      if "Clicks"      in df else 0
    roi     = (profit / spend * 100) if spend > 0 else 0
    cpc_o   = (spend / clicks)       if clicks > 0 else 0
    cpm_o   = (spend / impr * 1000)  if impr > 0 else 0
    cpl_o   = (spend / conv)         if conv > 0 else 0
    epc_o   = (revenue / clicks)     if clicks > 0 else 0
    appl_o  = (profit / conv)        if conv > 0 else 0

    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    metric_card(r1c1, "Total Spend",   f"${spend:,.2f}")
    metric_card(r1c2, "Total Revenue", f"${revenue:,.2f}")
    metric_card(r1c3, "Total Profit",  f"${profit:,.2f}", profit)
    metric_card(r1c4, "ROI",           f"{roi:.1f}%", roi)
    metric_card(r1c5, "Conversions",   f"{int(conv):,}")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    metric_card(r2c1, "Impressions",   f"{int(impr):,}")
    metric_card(r2c2, "Clicks",        f"{int(clicks):,}")
    metric_card(r2c3, "Avg CPC",       f"${cpc_o:,.2f}")
    metric_card(r2c4, "Avg CPM",       f"${cpm_o:,.2f}")
    metric_card(r2c5, "Avg CPL",       f"${cpl_o:,.2f}")

    r3c1, r3c2, _, _, _ = st.columns(5)
    metric_card(r3c1, "Avg EPC",       f"${epc_o:,.2f}")
    metric_card(r3c2, "APPL",          f"${appl_o:,.2f}", appl_o)

# ── Filters helper ─────────────────────────────────────────────────────────────
def account_filter(scope_lead=None, scope_buyer=None, key="acct_filter"):
    accounts = list_accounts(team_lead=scope_lead, media_buyer=scope_buyer)
    options = ["(All accounts)"] + accounts
    pick = st.selectbox("🎯 Filter by Account", options, key=key)
    return None if pick == "(All accounts)" else pick

# ── Daily combo chart ──────────────────────────────────────────────────────────
def daily_combo_chart(df, title):
    daily = df.groupby(df["Date"].dt.date).agg(
        Spend=("Spend", "sum"),
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"),
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
        title=title, barmode="group",
        **plotly_layout(height=380)
)
    st.plotly_chart(fig, use_container_width=True)

# ── My Dashboard ───────────────────────────────────────────────────────────────
def my_dashboard_page():
    role = st.session_state.role

    if role == "member":
        df_all = fetch_entries(media_buyer=st.session_state.username)
        header = f"📈 {st.session_state.display_name} — My Dashboard"
        scope_lead, scope_buyer = None, st.session_state.username
    elif role == "leader":
        df_all = fetch_entries(team_lead=st.session_state.username)
        header = f"📈 {st.session_state.display_name}'s Team Dashboard"
        scope_lead, scope_buyer = st.session_state.username, None
    else:
        df_all = fetch_entries()
        header = "📈 Admin Dashboard — All Data"
        scope_lead, scope_buyer = None, None

    st.markdown(f"<div class='section-title'>{header}</div>", unsafe_allow_html=True)

    if df_all.empty:
        st.info("No data yet. Go to 'Add Data' to get started!")
        return

    # Account filter for everyone
    picked_account = account_filter(scope_lead=scope_lead, scope_buyer=scope_buyer,
                                     key="my_acct_filter")
    df = df_all if not picked_account else df_all[df_all["Account"] == picked_account]

    if df.empty:
        st.info("No entries match this filter.")
        return

    render_kpis(df)
    st.markdown("---")
    daily_combo_chart(df, "Daily Revenue vs Spend vs Profit")

    if "Account" in df.columns and df["Account"].notna().any():
        col_a, col_b = st.columns(2)
        acc_df = df.groupby("Account").agg(
            Spend=("Spend", "sum"),
            Revenue=("Revenue", "sum"),
            Profit=("Profit", "sum"),
        ).reset_index().sort_values("Profit", ascending=False)

        with col_a:
            fig2 = px.bar(acc_df, x="Account", y="Profit", color="Profit",
                          color_continuous_scale=["#f87171", "#fbbf24", "#34d399"],
                          title="Profit by Account")
            fig2.update_layout(**plotly_layout(height=320)
)
            st.plotly_chart(fig2, use_container_width=True)
        with col_b:
            fig3 = px.pie(acc_df, names="Account", values="Revenue",
                          title="Revenue Share by Account",
                          color_discrete_sequence=px.colors.sequential.Plasma_r)
            fig3.update_layout(**plotly_layout(height=320))
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("<div class='section-title' style='margin-top:10px;'>Full Data Table</div>",
                unsafe_allow_html=True)
    drop_cols = [c for c in ["id","Added By","Role","added_by","team_lead"] if c in df.columns]
    st.dataframe(fmt_df_for_display(df.drop(columns=drop_cols, errors="ignore")),
                 use_container_width=True, hide_index=True)

# ── Team Overview ──────────────────────────────────────────────────────────────
def team_overview_page():
    users = load_users()
    role = st.session_state.role

    st.markdown("<div class='section-title'>👥 Team Overview</div>", unsafe_allow_html=True)

    if role == "leader":
        selected_lead = st.session_state.username
        st.caption(f"Viewing your team — **{st.session_state.display_name}**")
    else:
        leads = [u for u, v in users.items() if v["role"] == "leader"]
        if not leads:
            st.info("No team leads exist yet. Create one in ⚙️ User Management.")
            return
        selected_lead = st.selectbox(
            "Select Team Lead", leads,
            format_func=lambda u: users[u].get("display_name", u.capitalize()))

    df_all = fetch_entries(team_lead=selected_lead)
    if df_all.empty:
        st.info(f"No data yet for {users[selected_lead].get('display_name', selected_lead)}'s team.")
        return

    # Filters: media buyer + account
    fc1, fc2 = st.columns(2)
    with fc1:
        buyers = sorted(df_all["added_by"].dropna().unique().tolist())
        buyer_options = ["(All buyers)"] + buyers
        picked_buyer = st.selectbox(
            "👤 Filter by Media Buyer", buyer_options,
            format_func=lambda u: u if u == "(All buyers)"
                                    else users.get(u, {}).get("display_name", u))
    with fc2:
        picked_account = account_filter(scope_lead=selected_lead, key="team_acct_filter")

    df = df_all
    if picked_buyer != "(All buyers)":
        df = df[df["added_by"] == picked_buyer]
    if picked_account:
        df = df[df["Account"] == picked_account]

    if df.empty:
        st.info("No entries match these filters.")
        return

    render_kpis(df)
    st.markdown("---")
    daily_combo_chart(df, f"{users[selected_lead].get('display_name', selected_lead)} — Daily Performance")

    # Per-buyer breakdown (always from team-scoped, account-filtered df)
    df_for_buyers = df_all if not picked_account else df_all[df_all["Account"] == picked_account]
    buyer_df = df_for_buyers.groupby("added_by").agg(
        Spend=("Spend", "sum"),
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"),
        Conversions=("Conversions", "sum"),
    ).reset_index()
    buyer_df["ROI %"] = (buyer_df["Profit"] / buyer_df["Spend"] * 100).round(2)
    buyer_df["Media Buyer"] = buyer_df["added_by"].apply(
        lambda u: users.get(u, {}).get("display_name", u))
    buyer_df = buyer_df[["Media Buyer","Spend","Revenue","Profit","ROI %","Conversions"]]

    st.markdown("<div class='section-title'>Media Buyer Breakdown</div>", unsafe_allow_html=True)
    st.dataframe(
        buyer_df.style.format({
            "Spend": "${:,.2f}", "Revenue": "${:,.2f}",
            "Profit": "${:,.2f}", "ROI %": "{:.2f}%",
        }),
        use_container_width=True, hide_index=True,
    )

    # Per-account breakdown
    if "Account" in df_all.columns and df_all["Account"].notna().any():
        acct_df = df_all.groupby("Account").agg(
            Spend=("Spend","sum"), Revenue=("Revenue","sum"),
            Profit=("Profit","sum"), Conversions=("Conversions","sum"),
        ).reset_index()
        acct_df["ROI %"] = (acct_df["Profit"] / acct_df["Spend"] * 100).round(2)
        st.markdown("<div class='section-title'>Account Breakdown</div>", unsafe_allow_html=True)
        st.dataframe(
            acct_df.style.format({
                "Spend":"${:,.2f}","Revenue":"${:,.2f}",
                "Profit":"${:,.2f}","ROI %":"{:.2f}%",
            }),
            use_container_width=True, hide_index=True,
        )

    st.markdown("<div class='section-title' style='margin-top:20px;'>All Team Entries</div>",
                unsafe_allow_html=True)
    drop_cols = [c for c in ["id","Added By","Role","added_by","team_lead"] if c in df.columns]
    st.dataframe(fmt_df_for_display(df.drop(columns=drop_cols, errors="ignore")),
                 use_container_width=True, hide_index=True)

# ── Master Dashboard ───────────────────────────────────────────────────────────
def master_dashboard_page():
    users = load_users()
    df_all = fetch_entries()

    st.markdown("<div class='section-title'>📊 Master Dashboard — All Teams Combined</div>",
                unsafe_allow_html=True)

    if df_all.empty:
        st.info("No data has been entered yet.")
        return

    # Show everything combined — no filters here. Use Deep Analytics for slicing.
    df = df_all
    base = df_all

    st.caption(f"📈 Aggregated across **{df['team_lead'].nunique()} teams**, "
               f"**{df['added_by'].nunique()} media buyers**, "
               f"**{df['Account'].nunique()} accounts** — "
               f"**{len(df):,}** entries total. "
               f"For filtering & deep dives, use **🔬 Deep Analytics**.")

    render_kpis(df)
    st.markdown("---")

    # Team comparison
    team_df = base.groupby("team_lead").agg(
        Spend=("Spend", "sum"),
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"),
        Conversions=("Conversions", "sum"),
    ).reset_index()
    team_df["Team"] = team_df["team_lead"].apply(
        lambda u: users.get(u, {}).get("display_name", u or "—"))

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(team_df, x="Team", y=["Revenue", "Spend"], barmode="group",
                     title="Revenue vs Spend by Team",
                     color_discrete_map={"Revenue": "#6366f1", "Spend": "#475569"})
        fig.update_layout(**plotly_layout(height=320)
)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        colors = ["#34d399" if p >= 0 else "#f87171" for p in team_df["Profit"]]
        fig2 = go.Figure(go.Bar(x=team_df["Team"], y=team_df["Profit"],
                                marker_color=colors, name="Profit"))
        fig2.update_layout(title="Profit by Team",
                           **plotly_layout(height=320)
)
        st.plotly_chart(fig2, use_container_width=True)

    daily_team = base.groupby(["team_lead", base["Date"].dt.date]).agg(
        Profit=("Profit", "sum")).reset_index()
    daily_team.columns = ["team_lead", "Date", "Profit"]
    daily_team["Team"] = daily_team["team_lead"].apply(
        lambda u: users.get(u, {}).get("display_name", u or "—"))

    fig3 = px.line(daily_team, x="Date", y="Profit", color="Team",
                   title="Daily Profit by Team",
                   color_discrete_sequence=["#7c8dff","#34d399","#f59e0b",
                                            "#f472b6","#22d3ee","#a78bfa"])
    fig3.update_layout(**plotly_layout(height=360))
    st.plotly_chart(fig3, use_container_width=True)

    # Account-level summary across all teams (or filtered)
    st.markdown("<div class='section-title'>Account-Level Summary</div>", unsafe_allow_html=True)
    acct_df = df.groupby("Account").agg(
        Spend=("Spend","sum"), Revenue=("Revenue","sum"),
        Profit=("Profit","sum"), Conversions=("Conversions","sum"),
    ).reset_index().sort_values("Profit", ascending=False)
    acct_df["ROI %"] = (acct_df["Profit"] / acct_df["Spend"] * 100).round(2)
    st.dataframe(
        acct_df.style.format({
            "Spend":"${:,.2f}","Revenue":"${:,.2f}",
            "Profit":"${:,.2f}","ROI %":"{:.2f}%",
        }),
        use_container_width=True, hide_index=True,
    )

    # Daily profit pivot
    st.markdown("<div class='section-title'>Daily Profit Summary</div>", unsafe_allow_html=True)
    pivot = base.copy()
    pivot["DateLabel"] = pivot["Date"].dt.strftime("%d %b")
    pivot["Team"] = pivot["team_lead"].apply(
        lambda u: users.get(u, {}).get("display_name", u or "—"))
    pivot_table = pivot.pivot_table(index="DateLabel", columns="Team",
                                    values="Profit", aggfunc="sum").fillna(0)
    pivot_table["Total"] = pivot_table.sum(axis=1)
    st.dataframe(pivot_table.style.format("${:,.2f}"), use_container_width=True)

    st.markdown("<div class='section-title' style='margin-top:20px;'>All Entries</div>",
                unsafe_allow_html=True)
    drop_cols = [c for c in ["id","Added By","Role","added_by","team_lead"] if c in df.columns]
    st.dataframe(fmt_df_for_display(df.drop(columns=drop_cols, errors="ignore")),
                 use_container_width=True, hide_index=True)

# ── CSV download helper ───────────────────────────────────────────────────────
def csv_download_button(df: pd.DataFrame, filename: str, label: str = "⬇️ Download CSV", key=None):
    if df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, file_name=filename, mime="text/csv",
                       use_container_width=False, key=key)

# ── Date range helper ─────────────────────────────────────────────────────────
def date_range_filter(df: pd.DataFrame, key="date_range"):
    if df.empty or "Date" not in df.columns:
        return df
    min_d = df["Date"].min().date()
    max_d = df["Date"].max().date()
    picked = st.date_input("📅 Date Range", value=(min_d, max_d),
                           min_value=min_d, max_value=max_d, key=key)
    if isinstance(picked, tuple) and len(picked) == 2:
        start, end = picked
        mask = (df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)
        return df[mask]
    return df

# ── Deep Analytics (admin) ─────────────────────────────────────────────────────
def analytics_page():
    users = load_users()
    df_all = fetch_entries()

    st.markdown("<div class='section-title'>🔬 Deep Analytics</div>", unsafe_allow_html=True)
    st.caption("Slice & dice all entries across any dimension. Filters stack — pick what you need.")

    if df_all.empty:
        st.info("No data yet.")
        return

    # ── Filters ──
    st.markdown("<div class='subsection'>🎛️ Filters</div>", unsafe_allow_html=True)

    df_all = date_range_filter(df_all, key="ana_date")

    f1, f2, f3 = st.columns(3)
    with f1:
        leads = sorted([x for x in df_all["team_lead"].dropna().unique().tolist() if x])
        sel_leads = st.multiselect(
            "Team Lead", leads,
            format_func=lambda u: users.get(u, {}).get("display_name", u))
        verticals = sorted([x for x in df_all["Vertical"].dropna().unique().tolist() if x])
        sel_verticals = st.multiselect("Vertical", verticals)
    with f2:
        buyers = sorted([x for x in df_all["added_by"].dropna().unique().tolist() if x])
        sel_buyers = st.multiselect(
            "Media Buyer", buyers,
            format_func=lambda u: users.get(u, {}).get("display_name", u))
        platforms = sorted([x for x in df_all["Platform"].dropna().unique().tolist() if x])
        sel_platforms = st.multiselect("Platform", platforms)
    with f3:
        accounts = sorted([x for x in df_all["Account"].dropna().unique().tolist() if x])
        sel_accounts = st.multiselect("Account", accounts)
        advertisers = sorted([x for x in df_all["Advertiser"].dropna().unique().tolist() if x])
        sel_advertisers = st.multiselect("Advertiser", advertisers)

    df = df_all.copy()
    if sel_leads:       df = df[df["team_lead"].isin(sel_leads)]
    if sel_buyers:      df = df[df["added_by"].isin(sel_buyers)]
    if sel_verticals:   df = df[df["Vertical"].isin(sel_verticals)]
    if sel_platforms:   df = df[df["Platform"].isin(sel_platforms)]
    if sel_accounts:    df = df[df["Account"].isin(sel_accounts)]
    if sel_advertisers: df = df[df["Advertiser"].isin(sel_advertisers)]

    if df.empty:
        st.warning("No entries match the current filter combination.")
        return

    st.caption(f"Showing **{len(df):,}** of {len(df_all):,} entries")
    st.markdown("---")

    # ── KPIs ──
    render_kpis(df)
    st.markdown("---")

    # ── Breakdown tabs ──
    def breakdown(df_in, group_col, label_col=None, color="#7c8dff"):
        """Render a breakdown bar chart + table for the given grouping."""
        if group_col not in df_in.columns:
            st.info(f"No '{group_col}' data available.")
            return
        bdf = df_in.copy()
        bdf[group_col] = bdf[group_col].fillna("(blank)").replace("", "(blank)")
        if label_col:
            bdf[group_col] = bdf[group_col].apply(
                lambda u: users.get(u, {}).get("display_name", u))
        agg = bdf.groupby(group_col).agg(
            Spend=("Spend","sum"),
            Revenue=("Revenue","sum"),
            Profit=("Profit","sum"),
            Conversions=("Conversions","sum"),
            Impressions=("Impressions","sum"),
            Clicks=("Clicks","sum"),
            Entries=("Spend","count"),
        ).reset_index()
        agg["ROI %"] = (agg["Profit"] / agg["Spend"] * 100).round(2)
        agg["CPL"]   = (agg["Spend"] / agg["Conversions"]).round(2)
        agg = agg.sort_values("Profit", ascending=False)

        col_chart, col_pie = st.columns([2, 1])
        with col_chart:
            colors = ["#34d399" if p >= 0 else "#f87171" for p in agg["Profit"]]
            fig = go.Figure(go.Bar(x=agg[group_col], y=agg["Profit"],
                                   marker_color=colors, name="Profit",
                                   text=agg["Profit"].apply(lambda x: f"${x:,.0f}"),
                                   textposition="outside"))
            fig.update_layout(title=f"Profit by {group_col}",
                              **plotly_layout(height=380)
)
            st.plotly_chart(fig, use_container_width=True)
        with col_pie:
            fig2 = px.pie(agg, names=group_col, values="Revenue",
                          title=f"Revenue Share by {group_col}",
                          color_discrete_sequence=px.colors.sequential.Plasma_r,
                          hole=0.4)
            fig2.update_layout(**plotly_layout(height=380, legend=dict(font=dict(size=10))))
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(
            agg.style.format({
                "Spend":"${:,.2f}", "Revenue":"${:,.2f}",
                "Profit":"${:,.2f}", "ROI %":"{:.2f}%", "CPL":"${:,.2f}",
                "Conversions":"{:,}", "Impressions":"{:,}",
                "Clicks":"{:,}", "Entries":"{:,}",
            }),
            use_container_width=True, hide_index=True,
        )
        csv_download_button(agg, f"breakdown_{group_col.lower().replace(' ','_')}.csv",
                            key=f"dl_{group_col}")

    tabs = st.tabs(["📅 By Date", "🏷️ By Vertical", "📱 By Platform",
                    "🏢 By Advertiser", "🎯 By Account", "👥 By Team", "👤 By Buyer"])

    with tabs[0]:
        # Daily trend
        daily = df.copy()
        daily["DateOnly"] = daily["Date"].dt.date
        daily_agg = daily.groupby("DateOnly").agg(
            Spend=("Spend","sum"), Revenue=("Revenue","sum"),
            Profit=("Profit","sum"), Conversions=("Conversions","sum"),
        ).reset_index()
        daily_agg["ROI %"] = (daily_agg["Profit"] / daily_agg["Spend"] * 100).round(2)
        daily_combo_chart(df, "Daily Revenue · Spend · Profit")
        st.dataframe(
            daily_agg.style.format({
                "Spend":"${:,.2f}","Revenue":"${:,.2f}",
                "Profit":"${:,.2f}","ROI %":"{:.2f}%","Conversions":"{:,}",
            }),
            use_container_width=True, hide_index=True,
        )
        csv_download_button(daily_agg, "daily_breakdown.csv", key="dl_date")

    with tabs[1]: breakdown(df, "Vertical")
    with tabs[2]: breakdown(df, "Platform")
    with tabs[3]: breakdown(df, "Advertiser")
    with tabs[4]: breakdown(df, "Account")
    with tabs[5]:
        df_team = df.copy()
        df_team["Team"] = df_team["team_lead"].apply(
            lambda u: users.get(u, {}).get("display_name", u or "—"))
        breakdown(df_team, "Team")
    with tabs[6]:
        df_buy = df.copy()
        df_buy["Buyer"] = df_buy["added_by"].apply(
            lambda u: users.get(u, {}).get("display_name", u or "—"))
        breakdown(df_buy, "Buyer")

    # Top / Bottom performers
    st.markdown("---")
    st.markdown("<div class='subsection'>🏆 Top & Bottom Entries by Profit</div>",
                unsafe_allow_html=True)
    cols_show = ["Date","Account","Vertical","Platform","Advertiser","Spend",
                 "Revenue","Profit","ROI","Conversions"]
    cols_show = [c for c in cols_show if c in df.columns]
    tcol, bcol = st.columns(2)
    with tcol:
        st.caption("**Top 5 — most profitable**")
        st.dataframe(fmt_df_for_display(df.nlargest(5, "Profit")[cols_show]),
                     use_container_width=True, hide_index=True)
    with bcol:
        st.caption("**Bottom 5 — biggest losses**")
        st.dataframe(fmt_df_for_display(df.nsmallest(5, "Profit")[cols_show]),
                     use_container_width=True, hide_index=True)

    # Full export
    st.markdown("---")
    st.markdown("<div class='subsection'>⬇️ Export Filtered Entries</div>",
                unsafe_allow_html=True)
    drop_cols = [c for c in ["id","Added By","Role","added_by","team_lead","Traffic Source"]
                 if c in df.columns]
    export_df = df.drop(columns=drop_cols, errors="ignore")
    csv_download_button(export_df, "perftrack_filtered_entries.csv",
                        label="⬇️ Download Filtered Entries (CSV)", key="dl_full")




# ── User Management ────────────────────────────────────────────────────────────
def user_management_page():
    st.markdown("<div class='section-title'>⚙️ User Management</div>", unsafe_allow_html=True)
    users = load_users()

    tab_list, tab_add, tab_edit = st.tabs(["👥 All Users", "➕ Add User", "✏️ Edit / Delete"])

    with tab_list:
        rows = [{
            "Username": u,
            "Display Name": info.get("display_name", ""),
            "Role": info.get("role", ""),
            "Team Lead": info.get("team_lead") or "—",
        } for u, info in users.items()]
        st.dataframe(pd.DataFrame(rows).sort_values(["Role","Username"]),
                     use_container_width=True, hide_index=True)

    with tab_add:
        with st.form("add_user_form", clear_on_submit=True):
            st.markdown("**Create a new user**")
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Username", placeholder="lowercase, no spaces").strip().lower()
                new_display = st.text_input("Display Name", placeholder="e.g. Rajat Sharma")
            with col2:
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["member","leader","admin"],
                                         format_func=lambda r: {"member":"Media Buyer",
                                                                "leader":"Team Lead",
                                                                "admin":"Admin"}[r])

            assigned_lead = None
            if new_role == "member":
                leads = [u for u, v in users.items() if v["role"] == "leader"]
                if not leads:
                    st.warning("No team leads exist yet — create a team lead first before adding media buyers.")
                else:
                    assigned_lead = st.selectbox(
                        "Assign to Team Lead", leads,
                        format_func=lambda u: users[u].get("display_name", u.capitalize()))

            create = st.form_submit_button("Create User", use_container_width=True)
            if create:
                if not new_username or not new_password or not new_display:
                    st.error("All fields are required.")
                elif " " in new_username:
                    st.error("Username cannot contain spaces.")
                elif new_username in users:
                    st.error(f"Username '{new_username}' already exists.")
                elif new_role == "member" and not assigned_lead:
                    st.error("Media buyers must be assigned to a team lead.")
                else:
                    users[new_username] = {
                        "password": new_password,
                        "role": new_role,
                        "display_name": new_display.strip(),
                        "team_lead": assigned_lead if new_role == "member" else None,
                    }
                    save_users(users)
                    st.success(f"✅ User '{new_username}' created.")
                    st.rerun()

    with tab_edit:
        editable = [u for u in users.keys() if u != st.session_state.username]
        if not editable:
            st.info("No other users to edit yet.")
            return
        target = st.selectbox("Select a user to edit", editable,
                              format_func=lambda u: f"{users[u].get('display_name', u)} ({u})")
        info = users[target]

        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                e_display = st.text_input("Display Name", value=info.get("display_name", ""))
                e_password = st.text_input("Password", value=info.get("password", ""))
            with col2:
                e_role = st.selectbox(
                    "Role", ["member","leader","admin"],
                    index=["member","leader","admin"].index(info.get("role","member")),
                    format_func=lambda r: {"member":"Media Buyer","leader":"Team Lead","admin":"Admin"}[r])
                e_lead = None
                if e_role == "member":
                    leads = [u for u, v in users.items() if v["role"] == "leader" and u != target]
                    if leads:
                        current_lead = info.get("team_lead")
                        idx = leads.index(current_lead) if current_lead in leads else 0
                        e_lead = st.selectbox("Team Lead", leads, index=idx,
                                              format_func=lambda u: users[u].get("display_name", u))
                    else:
                        st.warning("No team leads available to assign.")

            col_s, col_d = st.columns(2)
            save_btn = col_s.form_submit_button("💾 Save Changes", use_container_width=True)
            del_btn  = col_d.form_submit_button("🗑️ Delete User", use_container_width=True)

            if save_btn:
                users[target] = {
                    "password": e_password,
                    "role": e_role,
                    "display_name": e_display.strip(),
                    "team_lead": e_lead if e_role == "member" else None,
                }
                save_users(users)
                st.success(f"✅ Updated '{target}'.")
                st.rerun()
            if del_btn:
                del users[target]
                save_users(users)
                st.success(f"🗑️ Deleted '{target}'.")
                st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    login_page()
else:
    page = sidebar()

    if page == "📝 Add Metrics":
        add_data_page()
    elif page == "📈 My Dashboard":
        my_dashboard_page()
    elif page == "👥 Team Overview":
        team_overview_page()
    elif page == "📊 Master Dashboard":
        master_dashboard_page()
    elif page == "🔬 Deep Analytics":
        analytics_page()
    elif page == "🎯 My Accounts":
        my_accounts_page()
    elif page == "⚙️ User Management":
        user_management_page()
