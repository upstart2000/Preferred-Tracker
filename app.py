import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 1. Configuration & Metadata
# margins are stored as decimals (e.g., 5.345% = 0.05345)
TICKER_DATA = {
    "MFA-PC": {"margin": 0.05345, "spread": 0.0, "name": "MFA Financial Inc. Ser C"},
    "RITM-PA": {"margin": 0.05802, "spread": 0.0, "name": "Rithm Capital Corp. Ser A"},
    "RITM-PB": {"margin": 0.05640, "spread": 0.0, "name": "Rithm Capital Corp. Ser B"},
}

st.set_page_config(layout="wide", page_title="Preferred Yield Tracker")

# 2. Sidebar Inputs
st.sidebar.header("Economic Inputs")
sofr_input = st.sidebar.number_input("3M Term SOFR (%)", value=3.6946, format="%.4f") / 100

st.title("🚢 Preferred Stock Floating Rate Tracker")
st.caption(f"Day Count Convention: Actual/360 | Current SOFR: {sofr_input*100:.4f}%")

# 3. Data Fetching & Calculation Logic
def get_stock_data(tickers, sofr):
    rows = []
    for ticker_symbol, meta in tickers.items():
        t = yf.Ticker(ticker_symbol)
        
        # Fetch Price & Last Ex-Date
        price = t.fast_info['lastPrice']
        divs = t.dividends
        last_ex_date = divs.index[-1] if not divs.empty else datetime.now()
        
        # Actual/360 Accrued Interest Calculation
        days_elapsed = (datetime.now() - last_ex_date.replace(tzinfo=None)).days
        
        # Current Coupon (Logic for RITM vs MFA)
        # Note: In a real app, you might pull 'current rate' from a field, 
        # but here we use the SOFR + Margin projection
        current_coupon = meta['margin'] + sofr
        accrued = (current_coupon * 25) * (days_elapsed / 360)
        
        clean_price = price - accrued
        yield_on_clean = (current_coupon * 25) / clean_price
        
        rows.append({
            "Ticker": ticker_symbol,
            "Margin": f"{meta['margin']*100:.3f}%",
            "Last Ex-Date": last_ex_date.strftime('%Y-%m-%d'),
            "Market Price": f"${price:.2f}",
            "Accrued Interest": f"${accrued:.3f}",
            "Clean Price": f"${clean_price:.2f}",
            "Yield on Clean": f"{yield_on_clean*100:.2f}%",
            "Projected Coupon": f"{current_coupon*100:.3f}%"
        })
    return pd.DataFrame(rows)

# 4. Render Table
if st.sidebar.button("Refresh Market Data"):
    df = get_stock_data(TICKER_DATA, sofr_input)
    st.table(df)
else:
    st.info("Adjust SOFR in the sidebar and click 'Refresh' to load the table.")
