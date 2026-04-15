# 📊 PerfTrack — Team Performance Dashboard

A Streamlit dashboard for tracking ad campaign performance across team leads, media buyers, and an admin who sees everything. Backed by SQLite for persistent storage.

## 🚀 Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

On first run the app:
1. Creates `perftrack.db` (SQLite) for entries.
2. Creates `users.json` bootstrapped with a single admin account.
3. Auto-migrates any existing `data.json` from the old version into the database (one-time).

## 👤 Roles

| Role | Access |
|------|--------|
| **Admin** | Sees everything. Filters by team and account. Full user CRUD. Can attach entries to any team lead. |
| **Team Lead** | Sees their own team. Filters by media buyer and account. |
| **Media Buyer** | Sees only their own entries. Filters by account. |

## 🔐 First Login

| Username | Password |
|----------|----------|
| `admin`  | `admin123` |

Log in, go to **⚙️ User Management**, change the admin password, then create your team leads and media buyers.

## 📋 Entry Fields

### Required
- **Date**, **Time Slot** (1st Hr → 13th Hr)
- **Account Name**
- **Spend ($)**, **Revenue ($)** — at least one > 0

### Optional categorization
Campaign, Vertical, PML Code, Traffic Source, Platform, Brands

### Traffic & engagement
Impressions, Clicks, U.L.C. (Unique Link Clicks), LP Views, LP Clicks, Conversions, **Initiate Checkout** (optional)

### Auto-stamped
- **Timestamp** — exact submission time
- **Team Lead** — auto-attached based on who submits

### Auto-calculated metrics
| Group | Metrics |
|-------|---------|
| Financial | Profit, ROI, Avg Payout |
| Cost-per | CPC, U.CPC, CPM, CPL, Offer CPC, Offer Page CPC |
| Earnings | EPC, Offer EPC, RPL, APPL |
| Rates | U.L.C. CTR, LP CTR, Offer CR |

## 🎯 Filtering

- **My Dashboard** — everyone can filter by Account
- **Team Overview** (leads + admin) — filter by Media Buyer + Account
- **Master Dashboard** (admin) — filter by Team Lead + Account

## 📁 Storage

- `perftrack.db` — SQLite database with all entries (single source of truth, persistent)
- `users.json` — user accounts
- `data.json` — *legacy*; only read once on first boot for auto-migration. Safe to delete after.

### Backup
Copy `perftrack.db` and `users.json` regularly. SQLite is a single file — easy to back up.

### Resetting
Delete `perftrack.db` to start fresh on entries. Delete `users.json` to reset to admin-only.
