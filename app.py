import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

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
        last_ex = divs.index[-1].strftime('%Y-%m-%d') if not divs.empty else "2025-10-31"
        
        data.append({
            "Ticker": ticker,
            "Margin": f"{META[ticker]['margin']*100:.3f}%",
            "Last Ex-Date": last_ex,
            "Market Price": round(price, 2),
            "Accrued Interest": 0.0, # Calculated below
            "Clean Price": 0.0,      # Calculated below
            "Yield on Clean": "",    # Calculated below
            "Next Ex-Date": "TBD",
            "Next Payout": 0.0,
            "Current Coupon": 0.0,
            "Projected Coupon": f"{(META[ticker]['margin'] + sofr_dec)*100:.3f}%",
            "Prev Coupon": f"${META[ticker]['prev_coupon']:.4f}"
        })
    return pd.DataFrame(data)

# 4. Calculation Engine (Runs on every edit)
def calculate_metrics(df, sofr):
    for i, row in df.iterrows():
        ticker = row['Ticker']
        margin = META[ticker]['margin']
        price = float(row['Market Price'])
        
        # Date Logic (Actual/360)
        last_ex = datetime.strptime(str(row['Last Ex-Date']), '%Y-%m-%d')
        days_elapsed = (datetime.now() - last_ex).days
        
        # Coupon Logic
        current_rate = margin + sofr
        df.at[i, 'Current Coupon'] = f"{current_rate*100:.3f}%"
        
        # Accrued & Clean Price
        accrued = (current_rate * 25) * (days_elapsed / 360)
        clean_price = price - accrued
        yoc = (current_rate * 25) / clean_price if clean_price > 0 else 0
        
        df.at[i, 'Accrued Interest'] = round(accrued, 4)
        df.at[i, 'Clean Price'] = round(clean_price, 2)
        df.at[i, 'Yield on Clean'] = f"{yoc*100:.2f}%"
        df.at[i, 'Next Payout'] = f"${(current_rate * 25 / 4):.4f}"
        
    return df

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = fetch_live_data()

st.title("🚢 Preferred Stock Tracker")
st.write("Edit **Last Ex-Date** or **Market Price** cells below to correct any data pull errors.")

# 5. The Editable Table
edited_df = st.data_editor(
    st.session_state.df,
    column_config={
        "Last Ex-Date": st.column_config.DateColumn("Last Ex-Date", format="YYYY-MM-DD"),
        "Market Price": st.column_config.NumberColumn("Market Price", format="$%.2f"),
        "Accrued Interest": st.column_config.NumberColumn("Accrued Interest", disabled=True),
        "Yield on Clean": st.column_config.TextColumn("Yield on Clean", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="main_editor"
)

# 6. Final Calculations based on (potentially edited) data
final_df = calculate_metrics(edited_df, sofr_dec)

# Update state so edits persist
st.session_state.df = final_df

if st.button("Reset to Live Data"):
    st.cache_data.clear()
    st.session_state.df = fetch_live_data()
    st.rerun()
