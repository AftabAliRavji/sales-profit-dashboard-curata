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
