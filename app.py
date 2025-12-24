import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 1. Setup & Fixed Metadata
TICKERS = ["MFA-PC", "RITM-PA", "RITM-PB"]
META = {
    "MFA-PC": {"margin": 0.05345, "prev_coupon": 0.6139},
    "RITM-PA": {"margin": 0.05802, "prev_coupon": 0.6565},
    "RITM-PB": {"margin": 0.05640, "prev_coupon": 0.6461},
}

st.set_page_config(layout="wide", page_title="Preferred Stock Tracker")

# 2. Sidebar Economic Inputs
st.sidebar.header("Global Settings")
sofr_val = st.sidebar.number_input("3M Term SOFR (%)", value=3.6946, format="%.4f")
sofr_dec = sofr_val / 100

# 3. Data Fetching Function
@st.cache_data(ttl=3600)
def fetch_live_data():
    data = []
    for ticker in TICKERS:
        t = yf.Ticker(ticker)
        # Pull Price and Ex-Date (with fallbacks)
        price = t.fast_info.get('lastPrice', 25.00)
        divs = t.dividends
        
        # KEY FIX: Convert to date object immediately
        if not divs.empty:
            last_ex = divs.index[-1].to_pydatetime().date()
        else:
            last_ex = date(2025, 10, 31)
        
        data.append({
            "Ticker": ticker,
            "Margin": f"{META[ticker]['margin']*100:.3f}%",
            "Last Ex-Date": last_ex, # Now a date object
            "Market Price": round(price, 2),
            "Accrued Interest": 0.0,
            "Clean Price": 0.0,
            "Yield on Clean": "",
            "Next Ex-Date": "TBD",
            "Next Payout": "",
            "Current Coupon": "",
            "Projected Coupon": f"{(META[ticker]['margin'] + sofr_dec)*100:.3f}%",
            "Prev Coupon": f"${META[ticker]['prev_coupon']:.4f}"
        })
    return pd.DataFrame(data)

# 4. Calculation Engine
def calculate_metrics(df, sofr):
    # We work on a copy to avoid SettingWithCopyWarnings
    calc_df = df.copy()
    for i, row in calc_df.iterrows():
        ticker = row['Ticker']
        margin = META[ticker]['margin']
        price = float(row['Market Price'])
        
        # Logic for Accrual (Actual/360)
        last_ex = row['Last Ex-Date']
        # Convert to datetime for math if it's just a date object
        last_ex_dt = datetime.combine(last_ex, datetime.min.time())
        days_elapsed = (datetime.now() - last_ex_dt).days
        
        current_rate = margin + sofr
        calc_df.at[i, 'Current Coupon'] = f"{current_rate*100:.3f}%"
        
        accrued = (current_rate * 25) * (days_elapsed / 360)
        clean_price = price - accrued
        yoc = (current_rate * 25) / clean_price if clean_price > 0 else 0
        
        calc_df.at[i, 'Accrued Interest'] = round(accrued, 4)
        calc_df.at[i, 'Clean Price'] = round(clean_price, 2)
        calc_df.at[i, 'Yield on Clean'] = f"{yoc*100:.2f}%"
        calc_df.at[i, 'Next Payout'] = f"${(current_rate * 25 / 4):.4f}"
        
    return calc_df

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = fetch_live_data()

st.title("🚢 Preferred Stock Tracker")

# 5. The Editable Table
# We calculate metrics FIRST so the table shows live data on load
display_df = calculate_metrics(st.session_state.df, sofr_dec)

edited_df = st.data_editor(
    display_df,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
        "Last Ex-Date": st.column_config.DateColumn("Last Ex-Date", format="YYYY-MM-DD", required=True),
        "Market Price": st.column_config.NumberColumn("Market Price", format="$%.2f"),
        "Accrued Interest": st.column_config.NumberColumn("Accrued Interest", disabled=True),
        "Clean Price": st.column_config.NumberColumn("Clean Price", disabled=True),
        "Yield on Clean": st.column_config.TextColumn("Yield on Clean", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="main_editor"
)

# 6. Update logic: If user edits, update the base session state
if not edited_df.equals(display_df):
    st.session_state.df = edited_df
    st.rerun()

if st.sidebar.button("Reset to Live Data"):
    st.cache_data.clear()
    del st.session_state.df
    st.rerun()
