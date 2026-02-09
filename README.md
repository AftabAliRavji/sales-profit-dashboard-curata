# Curata Daily Performance Dashboard

A Streamlit-based dashboard for tracking daily sales, profit, ad spend, ROAS, and conversion rate.  
Includes session saving/loading, JSON backup, export tools, and summary charts.

## 🚀 Features

- Daily inputs for sales, profit, ad spend, and orders
- Global visitors-per-day input
- Automatic FX conversion (USD → GBP)
- KPIs and profitability metrics
- Weekly, monthly, and yearly summaries
- Summary charts:
  - Sales vs Net Profit – Ad Spend
  - ROAS & Conversion Rate
- Session save/load (server file)
- JSON backup + restore
- CSV export
- Dark mode UI with custom CSS

## 📦 Installation on command line

Clone the repo:
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
pip install -r requirements.txt
streamlit run app.py

## if want to build dockerfile locally
docker build -t curata-dashboard .
docker run -p 8501:8501 curata-dashboard

## open on browser
http://localhost:8501

## using docker-compose
docker-compose up --build

## open on browser
http://localhost:8501

## secrets in secrets.toml (it is named _secrets.toml and _st.secrets as it is currently reading from actual StreamLit files not github)
[auth]
user1 = "aravji"
pass1 = "cuarataAdmin1214"

user2 = "mravji"
pass2 = "curataAdmin786"
SUPABASE_URL ="https://nrlibotwtsenhidyzhvt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ybGlib3R3dHNlbmhpZHl6aHZ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg4Mzc2MzQsImV4cCI6MjA4NDQxMzYzNH0.zmRpn3MBZoSni-Eefk2SOy_o9WZYAPpFPJhHkBOsopo"

## reuirements.txt for dependencies
streamlit>=1.30
pandas>=1.5
plotly>=5.0
requests>=2.0
python-dateutil
pytz
numpy

# Supabase + dependencies (pinned for Streamlit Cloud)
supabase-py==2.4.3
postgrest==0.13.0
gotrue==2.4.3
storage3==0.7.3
realtime==1.0.0

## DB schema
# below statement redundant
create table curata_sessions (
  user_id text primary key,
  session_json jsonb not null,
  updated_at timestamptz default now()
);


create table if not exists curata_global_state ( id text primary key, session_json jsonb );


ALTER TABLE curata_global_state
ADD COLUMN last_updated timestamptz DEFAULT now();

alter table curata_global_state
alter column last_updated set default now();


create table if not exists curata_global_versions (
    version_id bigint generated always as identity primary key,
    created_at timestamptz default now(),
    saved_by text,
    session_json jsonb
);

create table if not exists curata_global_audit (
    audit_id bigint generated always as identity primary key,
    timestamp timestamptz default now(),
    user_id text,
    action text,
    details jsonb
);

alter table curata_global_versions
add column if not exists locked boolean default false;

create table if not exists curata_withdrawals (
    id bigint generated always as identity primary key,
    date date not null,
    amount numeric not null,
    created_at timestamp with time zone default now()
);

# select statements
select * from  curata_global_state;
select * from curata_global_audit;
select * from curata_global_versions;
select * from curata_withdrawals;

---new tables for complete store and retrieval architecture----
create table if not exists public.curata_daily_data (
    id bigint generated always as identity primary key,
    date date not null,
    ad_spend_usd numeric default 0,
    visitors integer default 0,
    orders integer default 0,
    sales_usd numeric default 0,
    profit_usd numeric default 0,
    profit_after_ads_usd numeric default 0,
    profit_after_ads_gbp numeric default 0,
    profit_percent numeric default 0,
    created_at timestamp with time zone default timezone('utc', now())
);

-- Ensure one row per date (per user in future)
create unique index if not exists idx_curata_daily_data_date
on public.curata_daily_data (date);

create table if not exists public.curata_daily_orders (
    id bigint generated always as identity primary key,
    day_id bigint not null references public.curata_daily_data(id) on delete cascade,
    order_index integer not null,
    sales_usd numeric default 0,
    profit_usd numeric default 0,
    created_at timestamp with time zone default timezone('utc', now())
);

-- Ensure each order_index is unique per day
create unique index if not exists idx_curata_daily_orders_day_order
on public.curata_daily_orders (day_id, order_index);

drop table if exists public.curata_sessions cascade;

--amendments to tables
alter table public.curata_daily_data
add column updated_at timestamp with time zone default now();

alter table public.curata_daily_orders
add column updated_at timestamp with time zone default now();

create index if not exists idx_daily_data_created_at
on public.curata_daily_data (created_at);

create index if not exists idx_daily_orders_day_id
on public.curata_daily_orders (day_id);

alter table public.curata_daily_orders
add constraint chk_order_index check (order_index >= 1);

alter table public.curata_daily_data
add constraint chk_visitors check (visitors >= 0);

alter table public.curata_daily_data
add constraint chk_ad_spend check (ad_spend_usd >= 0);

## under storage buckets
Files
Buckets
curata_backups


## old comments - of breakdown od updates in this app
This file contains python code for an app which creates the following - 
1. allows each day inputs
2. adding number of orders with sales
3. adding number of orders with profit
4. total order value for each day
5. total order profit for each day
6. total profit - ad spend
7. total percentage profit using following formula - Percentage profit (profit/total sales * 100)
8. profit converted from $ to £ (default 0.79)
9. Having weekly average
10. having monthly average
11. having yearly average
12. having charts shown.
13. CSv exporter.
14. Cleaned/minified structure
15. Dark-themed, mobile-friendly styling
16. Tabs instead of long scroll
17. All logic from the last version is preserved.
18. Add order button fixed.
19. user login - please note the username and password is stored in secrets which is uploaded in Streamlit settings under secrets.
20. real fx conversion of USD to GBP
