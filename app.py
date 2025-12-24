import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 1. Setup & Metadata
TICKERS = ["MFA-PC", "RITM-PA", "RITM-PB"]
ISDA_SPREAD = 0.002616

META = {
    "MFA-PC": {"margin": 0.05345, "prev_coupon": 0.6139, "declared": None},
    "RITM-PA": {"margin": 0.05802, "prev_coupon": 0.6565, "declared": 0.09915},
    "RITM-PB": {"margin": 0.05640, "prev_coupon": 0.6461, "declared": 0.09753},
}

st.set_page_config(layout="wide", page_title="Preferred Stock Tracker")

# 2. Header UI
st.title("🚢 Preferred Stock Tracker")
col_input, col_btn, col_spacer = st.columns([2, 1, 4])
with col_input:
    sofr_val = st.number_input("3M Term SOFR (%)", value=3.6946, format="%.4f")
    sofr_dec = sofr_val / 100
with col_btn:
    st.write(" ") # Vertical alignment
    refresh = st.button("Refresh", use_container_width=True)

# 3. Data Fetching
@st.cache_data(ttl=300) # 5 minute cache
def fetch_live_data():
    data = []
    for ticker in TICKERS:
        t = yf.Ticker(ticker)
        
        # RELIABLE PRICE PULL: Get the most recent closing price
        hist = t.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
        else:
            price = 25.00 # Absolute fallback if API fails
            
        divs = t.dividends
        last_ex = divs.index[-1].to_pydatetime().date() if not divs.empty else date(2025, 10, 31)
        
        data.append({
            "Ticker": ticker,
            "Margin": f"{META[ticker]['margin']*100:.3f}%",
            "Last Ex-Date": last_ex,
            "Market Price": round(float(price), 2),
            "Accrued Interest": 0.0,
            "Clean Price": 0.0,
            "Yield on Clean": "",
            "Current Coupon": "",
            "Projected Coupon": "",
            "Prev Coupon": f"${META[ticker]['prev_coupon']:.4f}"
        })
    return pd.DataFrame(data)

# 4. Calculation Engine (Actual/360)
def calculate_metrics(df, sofr):
    calc_df = df.copy()
    for i, row in calc_df.iterrows():
        ticker = row['Ticker']
        m = META[ticker]
        price = float(row['Market Price'])
        
        # Current Accrual Rate Logic
        current_rate = m['declared'] if m['declared'] else (sofr + m['margin'] + ISDA_SPREAD)
        # Future Reset Rate Logic
        projected_rate = sofr + m['margin'] + ISDA_SPREAD
        
        # Day Count: Actual/360
        last_ex = row['Last Ex-Date']
        last_ex_dt = datetime.combine(last_ex, datetime.min.time())
        days_elapsed = (datetime.now() - last_ex_dt).days
        
        # Math
        accrued = (25.0 * current_rate) * (days_elapsed / 360)
        clean_price = price - accrued
        annual_payout = 25.0 * current_rate
        yoc = annual_payout / clean_price if clean_price > 0 else 0
        
        calc_df.at[i, 'Current Coupon'] = f"{current_rate*100:.4f}%"
        calc_df.at[i, 'Projected Coupon'] = f"{projected_rate*100:.4f}%"
        calc_df.at[i, 'Accrued Interest'] = round(accrued, 4)
        calc_df.at[i, 'Clean Price'] = round(clean_price, 3)
        calc_df.at[i, 'Yield on Clean'] = f"{yoc*100:.3f}%"
        
    return calc_df

if refresh:
    st.cache_data.clear()
    if 'df' in st.session_state: del st.session_state.df
    st.rerun()

if 'df' not in st.session_state:
    st.session_state.df = fetch_live_data()

# 5. Render
display_df = calculate_metrics(st.session_state.df, sofr_dec)

# Set column order to match your requested layout
column_order = ["Ticker", "Margin", "Last Ex-Date", "Market Price", "Accrued Interest", 
                "Clean Price", "Yield on Clean", "Current Coupon", "Projected Coupon", "Prev Coupon"]

edited_df = st.data_editor(
    display_df[column_order],
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
        "Last Ex-Date": st.column_config.DateColumn("Last Ex-Date", format="YYYY-MM-DD", required=True),
        "Market Price": st.column_config.NumberColumn("Market Price", format="$%.2f"),
        "Accrued Interest": st.column_config.NumberColumn("Accrued Interest", format="%.4f", disabled=True),
        "Clean Price": st.column_config.NumberColumn("Clean Price", format="%.3f", disabled=True),
    },
    use_container_width=True, hide_index=True, key="main_editor"
)

if not edited_df.equals(display_df[column_order]):
    # Sync edits back (keeping all columns)
    updated_full_df = edited_df.copy()
    # If other hidden columns existed, merge them back here
    st.session_state.df = updated_full_df
    st.rerun()
