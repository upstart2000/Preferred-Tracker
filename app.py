import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 1. Setup & Metadata
TICKERS = ["MFA-PC", "RITM-PA", "RITM-PB"]
META = {
    "MFA-PC": {"margin": 0.05345, "prev_coupon": 0.6139},
    "RITM-PA": {"margin": 0.05802, "prev_coupon": 0.6565},
    "RITM-PB": {"margin": 0.05640, "prev_coupon": 0.6461},
}

st.set_page_config(layout="wide", page_title="Preferred Stock Tracker")

st.title("🚢 Preferred Stock Tracker")

# 2. Main Pane Inputs (instead of Sidebar)
col_input, col_btn, col_spacer = st.columns([2, 1, 4])
with col_input:
    sofr_val = st.number_input("3M Term SOFR (%)", value=3.6946, format="%.4f")
    sofr_dec = sofr_val / 100
with col_btn:
    st.write(" ") # Padding
    st.write(" ") # Padding
    reset = st.button("Reset to Live Data", use_container_width=True)

# 3. Data Fetching
@st.cache_data(ttl=3600)
def fetch_live_data():
    data = []
    for ticker in TICKERS:
        t = yf.Ticker(ticker)
        price = t.fast_info.get('lastPrice', 25.00)
        divs = t.dividends
        
        # Pull last ex-date or default
        last_ex = divs.index[-1].to_pydatetime().date() if not divs.empty else date(2025, 10, 31)
        
        data.append({
            "Ticker": ticker,
            "Margin": f"{META[ticker]['margin']*100:.3f}%",
            "Last Ex-Date": last_ex,
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

# 4. Calculation Engine (Actual/360)
def calculate_metrics(df, sofr):
    calc_df = df.copy()
    for i, row in calc_df.iterrows():
        ticker = row['Ticker']
        margin = META[ticker]['margin']
        price = float(row['Market Price'])
        
        # Day Count: Actual days since last ex-date
        last_ex = row['Last Ex-Date']
        last_ex_dt = datetime.combine(last_ex, datetime.min.time())
        days_elapsed = (datetime.now() - last_ex_dt).days
        
        # Formula: (SOFR + Margin)
        current_rate = margin + sofr
        calc_df.at[i, 'Current Coupon'] = f"{current_rate*100:.3f}%"
        calc_df.at[i, 'Projected Coupon'] = f"{current_rate*100:.3f}%"
        
        # Accrued Interest (Actual/360): Principal * Rate * (Days / 360)
        accrued = (25.0 * current_rate) * (days_elapsed / 360)
        clean_price = price - accrued
        
        # Yield on Clean: (Annual Payout) / Clean Price
        # Annual Payout = 25 * current_rate
        annual_payout = 25.0 * current_rate
        yoc = annual_payout / clean_price if clean_price > 0 else 0
        
        calc_df.at[i, 'Accrued Interest'] = round(accrued, 4)
        calc_df.at[i, 'Clean Price'] = round(clean_price, 3)
        calc_df.at[i, 'Yield on Clean'] = f"{yoc*100:.2f}%"
        calc_df.at[i, 'Next Payout'] = f"${(annual_payout / 4):.4f}"
        
    return calc_df

# Logic for Reset
if reset:
    st.cache_data.clear()
    if 'df' in st.session_state:
        del st.session_state.df
    st.rerun()

# Init Session State
if 'df' not in st.session_state:
    st.session_state.df = fetch_live_data()

# 5. The Editable Table
display_df = calculate_metrics(st.session_state.df, sofr_dec)

edited_df = st.data_editor(
    display_df,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
        "Last Ex-Date": st.column_config.DateColumn("Last Ex-Date", format="YYYY-MM-DD", required=True),
        "Market Price": st.column_config.NumberColumn("Market Price", format="$%.2f"),
        "Accrued Interest": st.column_config.NumberColumn("Accrued Interest", format="%.4f", disabled=True),
        "Clean Price": st.column_config.NumberColumn("Clean Price", format="%.3f", disabled=True),
        "Yield on Clean": st.column_config.TextColumn("Yield on Clean", disabled=True),
        "Prev Coupon": st.column_config.TextColumn("Prev Coupon", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="main_editor"
)

# Sync edits back to session state
if not edited_df.equals(display_df):
    st.session_state.df = edited_df
    st.rerun()
