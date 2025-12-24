import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta

# 1. Setup & Fixed Metadata
TICKERS = ["MFA-PC", "RITM-PA", "RITM-PB"]
ISDA_SPREAD = 0.002616

META = {
    "MFA-PC": {"margin": 0.05345, "prev_coupon": 0.6139, "declared": None},
    "RITM-PA": {"margin": 0.05802, "prev_coupon": 0.6565, "declared": 0.09915},
    "RITM-PB": {"margin": 0.05640, "prev_coupon": 0.6461, "declared": 0.09753},
}

st.set_page_config(layout="wide", page_title="Preferred Stock Tracker")

# 2. Header UI
st.title("🚢 Preferred Stock Floating Rate Tracker")
col_input, col_btn, col_spacer = st.columns([2, 1, 4])
with col_input:
    sofr_val = st.number_input("3M Term SOFR (%)", value=3.6946, format="%.4f")
    sofr_dec = sofr_val / 100
with col_btn:
    st.write(" ") # Alignment
    refresh = st.button("Refresh Live Prices", use_container_width=True)

# 3. Data Fetching
@st.cache_data(ttl=300)
def fetch_live_data():
    data = []
    for ticker in TICKERS:
        t = yf.Ticker(ticker)
        # Reliable Price Pull
        hist = t.history(period="1d")
        price = hist['Close'].iloc[-1] if not hist.empty else 25.00
        
        divs = t.dividends
        if not divs.empty:
            last_ex = divs.index[-1].to_pydatetime().date()
            next_ex = (divs.index[-1] + timedelta(days=91)).date() # Estimated 3-month cycle
        else:
            last_ex = date(2025, 10, 31)
            next_ex = date(2026, 1, 30)
        
        data.append({
            "Ticker": ticker,
            "Margin": f"{META[ticker]['margin']*100:.3f}%",
            "Last Ex-Date": last_ex,
            "Market Price": round(float(price), 2),
            "Accrued Interest": 0.0,
            "Clean Price": 0.0,
            "Yield on Clean": "",
            "Next Ex-Date": next_ex,
            "Next Payout": "",
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
        
        # Rate Logic
        current_rate = m['declared'] if m['declared'] else (sofr + m['margin'] + ISDA_SPREAD)
        projected_rate = sofr + m['margin'] + ISDA_SPREAD
        
        # Days Elapsed
        last_ex = row['Last Ex-Date']
        last_ex_dt = datetime.combine(last_ex, datetime.min.time())
        days_elapsed = (datetime.now() - last_ex_dt).days
        
        # Financial Math
        accrued = (25.0 * current_rate) * (days_elapsed / 360)
        clean_price = price - accrued
        annual_payout = 25.0 * current_rate
        yoc = annual_payout / clean_price if clean_price > 0 else 0
        
        calc_df.at[i, 'Current Coupon'] = f"{current_rate*100:.4f}%"
        calc_df.at[i, 'Projected Coupon'] = f"{projected_rate*100:.4f}%"
        calc_df.at[i, 'Accrued Interest'] = round(accrued, 4)
        calc_df.at[i, 'Clean Price'] = round(clean_price, 3)
        calc_df.at[i, 'Yield on Clean'] = f"{yoc*100:.3f}%"
        calc_df.at[i, 'Next Payout'] = f"${(annual_payout / 4):.4f}"
        
    return calc_df

if refresh:
    st.cache_data.clear()
    if 'df' in st.session_state: del st.session_state.df
    st.rerun()

if 'df' not in st.session_state:
    st.session_state.df = fetch_live_data()

# 5. Render Final Table
display_df = calculate_metrics(st.session_state.df, sofr_dec)

# Full 12-Column Specification
column_order = [
    "Ticker", "Margin", "Last Ex-Date", "Market Price", "Accrued Interest", 
    "Clean Price", "Yield on Clean", "Next Ex-Date", "Next Payout", 
    "Current Coupon", "Projected Coupon", "Prev Coupon"
]

edited_df = st.data_editor(
    display_df[column_order],
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
        "Last Ex-Date": st.column_config.DateColumn("Last Ex-Date", format="YYYY-MM-DD"),
        "Next Ex-Date": st.column_config.DateColumn("Next Ex-Date", format="YYYY-MM-DD"),
        "Market Price": st.column_config.NumberColumn("Market Price", format="$%.2f"),
        "Accrued Interest": st.column_config.NumberColumn("Accrued Interest", format="%.4f", disabled=True),
        "Clean Price": st.column_config.NumberColumn("Clean Price", format="%.3f", disabled=True),
        "Yield on Clean": st.column_config.TextColumn("Yield on Clean", disabled=True),
        "Next Payout": st.column_config.TextColumn("Next Payout", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="main_editor"
)

# Sync edits back to state
if not edited_df.equals(display_df[column_order]):
    st.session_state.df = edited_df
    st.rerun()

# --- SENSITIVITY TABLE SECTION ---
st.divider()
st.subheader("📊 Yield Sensitivity Analysis (Based on Projected Coupons)")
st.write("This table shows the **Yield on Clean Price** if SOFR shifts from your current input.")

# Define the shifts requested
shifts = [-0.0075, -0.0050, -0.0025, 0.0, 0.0100, 0.0125, 0.0150]
shift_labels = ["SOFR -75bps", "SOFR -50bps", "SOFR -25bps", "Current SOFR", "SOFR +100bps", "SOFR +125bps", "SOFR +150bps"]

sensitivity_data = []

for i, row in st.session_state.df.iterrows():
    ticker = row['Ticker']
    m = META[ticker]
    
    # We use the Clean Price calculated in the main table to keep it consistent
    # We must pull it from display_df to ensure we have the calculated float
    clean_p = display_df.loc[display_df['Ticker'] == ticker, 'Clean Price'].values[0]
    
    ticker_yields = {"Ticker": ticker}
    
    for shift, label in zip(shifts, shift_labels):
        scenario_sofr = sofr_dec + shift
        # Scenario Coupon = Scenario SOFR + Margin + ISDA Spread
        scenario_coupon = scenario_sofr + m['margin'] + ISDA_SPREAD
        
        # Scenario Yield = (Par * Coupon) / Clean Price
        if clean_p > 0:
            s_yield = (25.0 * scenario_coupon) / clean_p
            ticker_yields[label] = f"{s_yield*100:.3f}%"
        else:
            ticker_yields[label] = "N/A"
            
    sensitivity_data.append(ticker_yields)

sens_df = pd.DataFrame(sensitivity_data)

# Display the Sensitivity Table
st.dataframe(
    sens_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Current SOFR": st.column_config.TextColumn("Current SOFR", help="Matches Yield on Clean from the top table")
    }
)
