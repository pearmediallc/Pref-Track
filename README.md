# 📊 PerfTrack — Pear Media Performance Dashboard

A Streamlit dashboard for tracking ad campaign performance across team leads and media buyers, with full role-based access and in-app user management.

## 🚀 Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 🔑 First Login

On first run, a bootstrap admin is created automatically:

| Username | Password |
|----------|----------|
| `admin`  | `admin123` |

**Change it immediately** from the "🔑 My Account" page after logging in.

## 👥 Roles

| Role | Can do |
|------|--------|
| **Admin** | Everything — create/edit/delete users, view master dashboard, drill into any team lead or media buyer, export all data. |
| **Team Leader** | View their own team's dashboard, drill into any of their media buyers, export their team's data. |
| **Media Buyer** | Add daily performance entries, view their own dashboard. |

## 👤 Creating Users

All user creation and management happens **inside the app** — no editing code.

1. Log in as `admin`
2. Go to **👥 User Management**
3. Add Team Leaders first, then add Media Buyers and assign each to a lead
4. You can edit display names, reset passwords, change roles, or delete users anytime

Deleting a Team Leader automatically unassigns their Media Buyers (the buyers are not deleted).

## 📝 Data Entry

Media Buyers log entries with:

- **Date** + **Time Slot** (Full Day or 1st Hr – 13th Hr, like the Pear Media tracker)
- **Auto-timestamp** — every entry records the exact moment it was submitted
- PML Code, Vertical, Traffic Source, Platform, Brands
- Spend, Revenue, Impressions, Clicks, Offer Clicks, Conversions

Auto-calculated: **Profit, ROI, CPC, EPC, Offer CTR, Cost per Conversion**

## 📁 Data Storage

Two JSON files are created next to `app.py`:

- `users.json` — all user accounts
- `data.json` — all performance entries

The app is **backward-compatible** with existing `data.json` files from the previous version — legacy fields (`FB Link Clicks`, `LP Clicks`, `Accounts`) are auto-mapped to `Clicks`, `Offer Clicks`, and `PML Code` so old entries keep working.

For production, consider moving to SQLite or Postgres.
