import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

import os

# --- SETTINGS ---
st.set_page_config(page_title="💰 Portfolio Tracker", layout="wide", page_icon="📈")
LEDGER_FILE = "portfolio_ledger.csv"

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
    }
    /* Black Metric Cards */
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important;
        border: 1px solid #333;
        padding: 15px 20px !important;
        border-radius: 15px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        min-height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="stMetricLabel"] p {
        color: #aaaaaa !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        margin-bottom: 0px !important;
    }
    [data-testid="stMetricValue"] div {
        color: #ffffff !important;
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricDelta"] {
        position: absolute;
        top: 15px;
        right: 20px;
    }
    [data-testid="stMetricDelta"] div {
        font-size: 0.85rem !important;
        font-weight: bold !important;
    }
    
    div[data-testid="stExpander"] {
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-radius: 15px;
    }
    .stDataFrame {
        border-radius: 15px;
        overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def load_data():
    if os.path.exists(LEDGER_FILE):
        df = pd.read_csv(LEDGER_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        return df
    return None

def save_data():
    st.session_state.ledger.to_csv(LEDGER_FILE, index=False)

def recalculate_state():
    """Recalculate portfolio and balance from scratch using the ledger."""
    ledger = st.session_state.ledger
    new_portfolio = pd.DataFrame({
        'Symbol': pd.Series(dtype='str'),
        'Buy Price': pd.Series(dtype='float'),
        'Quantity': pd.Series(dtype='float'),
        'CostTHB': pd.Series(dtype='float')
    })
    new_balance = 0.0
    
    # Sort by timestamp to ensure correct calculation
    ledger_sorted = ledger.sort_values('Timestamp')
    
    for _, txn in ledger_sorted.iterrows():
        new_balance += txn['CashDelta']
        
        if txn['Symbol'] != 'CASH':
            sym = txn['Symbol']
            qty = txn['Quantity'] # Positive for BUY, Negative for SELL
            price_local = txn['Price']
            
            mask = new_portfolio['Symbol'] == sym
            if mask.any():
                idx = new_portfolio.index[mask][0]
                old_p = new_portfolio.at[idx, 'Buy Price']
                old_q = new_portfolio.at[idx, 'Quantity']
                old_cost_thb = new_portfolio.at[idx, 'CostTHB']
                
                if txn['Type'] == 'BUY':
                    total_q = old_q + qty
                    if total_q > 0:
                        # Weighted average in local currency
                        new_p = ((old_p * old_q) + (price_local * qty)) / total_q
                        new_portfolio.at[idx, 'Buy Price'] = new_p
                        new_portfolio.at[idx, 'Quantity'] = total_q
                        new_portfolio.at[idx, 'CostTHB'] = old_cost_thb + abs(txn['CashDelta'])
                elif txn['Type'] == 'SELL':
                    total_q = old_q + qty
                    if total_q <= 0:
                        new_portfolio = new_portfolio.drop(idx).reset_index(drop=True)
                    else:
                        # Reduce cost basis proportionally
                        ratio = (old_q + qty) / old_q
                        new_portfolio.at[idx, 'Quantity'] = total_q
                        new_portfolio.at[idx, 'CostTHB'] = old_cost_thb * ratio
            else:
                if txn['Type'] == 'BUY':
                    new_row = pd.DataFrame([{
                        'Symbol': sym, 
                        'Buy Price': price_local, 
                        'Quantity': qty,
                        'CostTHB': abs(txn['CashDelta'])
                    }])
                    new_portfolio = pd.concat([new_portfolio, new_row], ignore_index=True)

    st.session_state.portfolio = new_portfolio
    st.session_state.balance = new_balance

if 'ledger' not in st.session_state:
    loaded_ledger = load_data()
    if loaded_ledger is not None:
        st.session_state.ledger = loaded_ledger
    else:
        # Default empty Ledger starting at 0
        st.session_state.ledger = pd.DataFrame({
            'Timestamp': pd.Series(dtype='datetime64[ns]'),
            'Symbol': pd.Series(dtype='str'),
            'Type': pd.Series(dtype='str'),
            'Price': pd.Series(dtype='float'),
            'Quantity': pd.Series(dtype='float'),
            'Fees': pd.Series(dtype='float'),
            'CashDelta': pd.Series(dtype='float')
        })
        starting_date = datetime.now() - timedelta(days=365 * 10)
        st.session_state.ledger = pd.concat([st.session_state.ledger, pd.DataFrame([{
            'Timestamp': starting_date, 'Symbol': 'CASH', 'Type': 'INITIAL',
            'Price': 0.0, 'Quantity': 0.0, 'Fees': 0.0, 'CashDelta': 0.0
        }])], ignore_index=True)
        save_data()
    recalculate_state()
elif 'portfolio' not in st.session_state or 'balance' not in st.session_state or 'CostTHB' not in st.session_state.portfolio.columns:
    recalculate_state()

def calculate_net_impact(price, qty, comm_rate_pct, type='BUY', rate=1.0):
    """Calculate Net Cash impact including Fees (0.007%) and VAT (7%), converted by rate."""
    gross = price * qty * rate
    trading_fees_rate = 0.007 / 100 # 0.007% per Pi note
    
    fare_comm = gross * (comm_rate_pct / 100)
    fare_others = gross * trading_fees_rate
    
    total_fee_ex_vat = fare_comm + fare_others
    vat = total_fee_ex_vat * 0.07
    total_fee_inc_vat = total_fee_ex_vat + vat
    
    if type == 'BUY':
        return -(gross + total_fee_inc_vat), total_fee_inc_vat
    else:
        return (gross - total_fee_inc_vat), total_fee_inc_vat

@st.cache_data(ttl=300) # Cache for 5 minutes
def get_stock_data(symbols):
    data = {}
    
    # 1. Fetch USD/THB Exchange Rate
    try:
        exch_ticker = yf.Ticker("USDTHB=X")
        # Use fast_info if available or tail of history
        usdthb_rate = exch_ticker.fast_info['last_price']
    except:
        usdthb_rate = 35.0 # Fallback
        
    data['EXCH_USDTHB'] = usdthb_rate
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            hist = ticker.history(period="1d")
            
            # Identify currency (Basic logic, .BK is THB, others check info)
            if symbol.endswith('.BK'):
                currency = 'THB'
            else:
                # Attempt to get currency from ticker info (cached by yf)
                currency = ticker.info.get('currency', 'USD')
                
            if not hist.empty:
                data[symbol] = {
                    'current_price': hist['Close'].iloc[-1],
                    'currency': currency,
                    'prev_close': fast_info_price if (fast_info_price := info.get('previous_close')) else hist['Open'].iloc[-1],
                    'name': ticker.info.get('shortName', symbol)
                }
            else:
                data[symbol] = None
        except:
            data[symbol] = None
    return data

# --- PRE-FETCH DATA ---
# This must happen before sidebar to avoid NameError if sidebar uses live_data
symbols = st.session_state.portfolio['Symbol'].unique() if not st.session_state.portfolio.empty else []
live_data = get_stock_data(symbols)

# --- SIDEBAR ---
with st.sidebar:
    st.title("➕ Manage Portfolio")
    
    st.subheader("⚙️ Fee Settings")
    default_comm = st.number_input("Commission Rate (%)", value=0.15, step=0.01, format="%.3f")

    if st.button("🔄 Sync with portfolio_ledger.csv"):
        loaded = load_data()
        if loaded is not None:
            st.session_state.ledger = loaded
            recalculate_state()
            st.success("Successfully synced with disk!")
            st.rerun()
        else:
            st.error("CSV file not found on disk.")

    if st.button("🛠️ Repair & Standardize Ledger (USD -> THB)"):
        with st.spinner("Standardizing ledger to THB..."):
            ledger = st.session_state.ledger.copy()
            # 1. Fetch deep history of USDTHB
            start_date = ledger['Timestamp'].min()
            exch_data = yf.download("USDTHB=X", start=start_date)['Close']
            
            # 2. Iterate and fix
            for idx, row in ledger.iterrows():
                symbol = str(row['Symbol'])
                if symbol != 'CASH' and not symbol.endswith('.BK'):
                    # It's a foreign stock
                    txn_date = pd.to_datetime(row['Timestamp']).normalize()
                    
                    # Try to find historical rate, else use current
                    try:
                        # Find closest available date in index
                        closest_date = exch_data.index[exch_data.index <= txn_date][-1]
                        rate = exch_data.loc[closest_date]
                    except:
                        rate = live_data.get('EXCH_USDTHB', 35.0)
                    
                    # Recalculate
                    cash_impact_thb, total_fees_thb = calculate_net_impact(
                        row['Price'], abs(row['Quantity']), default_comm, 
                        'BUY' if row['Type'] == 'BUY' else 'SELL', rate=rate
                    )
                    
                    ledger.at[idx, 'Fees'] = total_fees_thb
                    ledger.at[idx, 'CashDelta'] = cash_impact_thb
            
            st.session_state.ledger = ledger
            save_data()
            recalculate_state()
            st.success("Ledger standardized to THB using historical rates!")
            st.rerun()
    
    st.divider()
    with st.form("add_stock", clear_on_submit=True):
        new_symbol = st.text_input("Stock Symbol (e.g. PTT, NVDA, AAPL)").upper().strip()
        is_thai = st.checkbox("Thai Stock (auto-append .BK)", value=True)
        new_price = st.number_input("Buy Price", min_value=0.0, step=0.1, value=None)
        new_qty = st.number_input("Quantity", min_value=0.0, step=1.0, value=None)
        new_date = st.date_input("Purchase Date (Optional)", value=datetime.now())
        submit = st.form_submit_button("Add to Portfolio")
        
        if submit and new_symbol and new_price is not None and new_qty is not None:
            # Auto-append .BK for Thai stocks if checkbox is checked
            if is_thai and not new_symbol.endswith('.BK'):
                new_symbol = f"{new_symbol}.BK"
            
            # Use current USDTHB rate for conversion if not Thai
            rate = 1.0
            if not is_thai:
                rate = live_data.get('EXCH_USDTHB', 35.0)
            
            txn_time = datetime.combine(new_date, datetime.now().time())
            cash_impact_thb, total_fees_thb = calculate_net_impact(new_price, new_qty, default_comm, 'BUY', rate=rate)
            
            st.session_state.ledger = pd.concat([st.session_state.ledger, pd.DataFrame([{
                'Timestamp': txn_time,
                'Symbol': new_symbol,
                'Type': 'BUY',
                'Price': new_price,
                'Quantity': new_qty,
                'Fees': total_fees_thb,
                'CashDelta': cash_impact_thb
            }])], ignore_index=True)
            save_data()
            recalculate_state()
            st.success(f"✅ Bought {new_qty} shares (Fees: ฿{total_fees_thb:.2f})")
            st.rerun()

    st.markdown("---")
    st.title("🔻 Sell Stock")
    with st.form("sell_stock", clear_on_submit=True):
        sell_symbol = st.selectbox("Select Stock to Sell", options=st.session_state.portfolio['Symbol'].unique() if not st.session_state.portfolio.empty else ["No Stocks"])
        sell_price = st.number_input("Selling Price (฿)", min_value=0.0, step=0.1, value=None)
        sell_qty = st.number_input("Quantity to Sell", min_value=0.0, step=1.0, value=None)
        sell_date = st.date_input("Sale Date (Optional)", value=datetime.now())
        submit_sell = st.form_submit_button("Confirm Sale")
        
        if submit_sell and sell_symbol != "No Stocks" and sell_price is not None and sell_qty is not None and sell_qty > 0:
            # Detect rate
            rate = 1.0
            if not sell_symbol.endswith('.BK'):
                rate = live_data.get('EXCH_USDTHB', 35.0)
            
            txn_time = datetime.combine(sell_date, datetime.now().time())
            cash_impact_thb, total_fees_thb = calculate_net_impact(sell_price, sell_qty, default_comm, 'SELL', rate=rate)
            
            # Record Transaction
            st.session_state.ledger = pd.concat([st.session_state.ledger, pd.DataFrame([{
                'Timestamp': txn_time,
                'Symbol': sell_symbol,
                'Type': 'SELL',
                'Price': sell_price,
                'Quantity': -sell_qty,
                'Fees': total_fees_thb,
                'CashDelta': cash_impact_thb
            }])], ignore_index=True)
            save_data()
            recalculate_state()
            st.success(f"🔥 Sold shares (Fees: ฿{total_fees_thb:.2f})")
            st.rerun()

    st.markdown("---")
    st.title("💵 Set Cash Balance")
    new_balance_goal = st.number_input("Current Cash in Hand", value=float(st.session_state.balance), step=100.0)
    adj_date_input = st.date_input("Adjustment Date", value=datetime.now())
    
    if st.button("Update Balance"):
        diff = new_balance_goal - st.session_state.balance
        if diff != 0:
            # Combine the selected date with the current time
            final_date = datetime.combine(adj_date_input, datetime.now().time())
            st.session_state.ledger = pd.concat([st.session_state.ledger, pd.DataFrame([{
                'Timestamp': final_date,
                'Symbol': 'CASH',
                'Type': 'ADJUST',
                'Price': 0.0,
                'Quantity': 0.0,
                'Fees': 0.0,
                'CashDelta': diff
            }])], ignore_index=True)
            save_data()
            recalculate_state()
            st.success(f"Balance updated to ฿{new_balance_goal:,.2f} on {adj_date_input.strftime('%Y-%m-%d')}")
            st.rerun()

    st.markdown("---")
    st.title("� Backup & Restore")
    
    # Export CSV
    csv_data = st.session_state.ledger.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Ledger (CSV)",
        data=csv_data,
        file_name=f"portfolio_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        width="stretch"
    )
    
    # Import CSV
    uploaded_file = st.file_uploader("📤 Restore from CSV", type=["csv"])
    if uploaded_file is not None:
        try:
            restored_df = pd.read_csv(uploaded_file)
            # Basic validation
            required_cols = ['Timestamp', 'Symbol', 'Type', 'Price', 'Quantity', 'Fees', 'CashDelta']
            if all(col in restored_df.columns for col in required_cols):
                restored_df['Timestamp'] = pd.to_datetime(restored_df['Timestamp'])
                st.session_state.ledger = restored_df
                save_data()
                recalculate_state()
                st.success("✅ Data restored successfully!")
                st.rerun()
            else:
                st.error("❌ Invalid CSV format. Missing required columns.")
        except Exception as e:
            st.error(f"❌ Error restoring data: {e}")

    st.markdown("---")
    st.title("�🗑️ Reset")
    if st.button("Clear All Data"):
        if os.path.exists(LEDGER_FILE):
            os.remove(LEDGER_FILE)
        for key in ['portfolio', 'balance', 'ledger']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

# --- DASHBOARD LOGIC ---
# Process DataFrame
df = st.session_state.portfolio.copy()

# --- MAIN DASHBOARD ---
st.title("🚀 Smart Portfolio Tracker")
if not df.empty and 'EXCH_USDTHB' in live_data:
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Rate: 1 USD = ฿{live_data['EXCH_USDTHB']:.2f}")
else:
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not df.empty:
    usdthb = live_data.get('EXCH_USDTHB', 35.0)
    
    def calculate_metrics(row):
        data = live_data.get(row['Symbol'])
        if data:
            curr_price = data['current_price']
            currency = data.get('currency', 'THB')
            
            # Use the local Buy Price from ledger
            buy_price_local = row['Buy Price']
            
            # Value in THB
            usdthb = live_data.get('EXCH_USDTHB', 35.0)
            rate = usdthb if currency == 'USD' else 1.0
            value_thb = curr_price * row['Quantity'] * rate
            
            # Actual Cost in THB from the ledger (more accurate than using current rate)
            cost_thb = row['CostTHB']
            profit_thb = value_thb - cost_thb
            
            pct = (profit_thb / cost_thb * 100) if cost_thb > 0 else 0
            return pd.Series([data['name'], buy_price_local, curr_price, value_thb, profit_thb, pct, currency])
        return pd.Series([row['Symbol'], row['Buy Price'], 0, 0, 0, 0, 'THB'])

    df[['Name', 'Buy Price', 'Current Price', 'Market Value', 'Profit/Loss', '% Change', 'Currency']] = df.apply(calculate_metrics, axis=1)
else:
    # Empty Placeholder structure
    df = pd.DataFrame(columns=['Symbol', 'Name', 'Buy Price', 'Current Price', 'Quantity', 'Market Value', 'Profit/Loss', '% Change', 'Currency', 'CostTHB'])

# --- PORTFOLIO HISTORY LOGIC (Moved up to inform metrics) ---
h_col1, h_col2 = st.columns([2, 5])
with h_col1:
    st.subheader("📈 Portfolio History")
with h_col2:
    time_range = st.radio(
        "Range", 
        ["5D", "10D", "1M", "3M", "6M", "YTD", "1Y"], 
        index=2, 
        horizontal=True, 
        label_visibility="collapsed"
    )

# Mapping range to yfinance period
yf_period_map = {
    "5D": "5d", "10D": "1mo", "1M": "1mo", "3M": "3mo", "6M": "6mo", "YTD": "ytd", "1Y": "1y"
}
selected_period = yf_period_map[time_range]

# (Calculations follow...)
with st.spinner("Reconstructing history..."):
    # (History reconstruction logic - abbreviated here but must be complete in implementation)
    # 1. Get price history for all ever-held symbols
    all_ever_symbols = st.session_state.ledger[st.session_state.ledger['Symbol'] != 'CASH']['Symbol'].unique()
    if len(all_ever_symbols) > 0:
        hist_symbols = list(all_ever_symbols) + ["USDTHB=X"]
        hist_data = yf.download(hist_symbols, period=selected_period, interval="1d")['Close']
        if isinstance(hist_data, pd.Series):
            hist_prices = hist_data.to_frame(name=hist_symbols[0])
        else:
            hist_prices = hist_data
        hist_prices = hist_prices.ffill().bfill()
        if time_range == "10D":
            hist_prices = hist_prices.tail(10)
    else:
        num_days = 30
        if time_range == "5D": num_days = 5
        elif time_range == "10D": num_days = 10
        elif time_range == "YTD": num_days = (datetime.now() - datetime(datetime.now().year, 1, 1)).days + 1
        elif time_range == "1Y": num_days = 365
        hist_prices = pd.DataFrame(index=pd.date_range(end=datetime.now(), periods=num_days))

    # 2. Reconstruct daily state
    history_dates = hist_prices.index
    portfolio_values, cash_balances, market_profits, cost_basis_history = [], [], [], []
    
    current_cash, current_injected = 0.0, 0.0
    holdings, holdings_cost = {}, {} # Tracking qty and cost by symbol
    
    ledger_sorted = st.session_state.ledger.sort_values('Timestamp').copy()
    ledger_sorted['Timestamp'] = pd.to_datetime(ledger_sorted['Timestamp']).dt.tz_localize(None)
    l_ptr = 0
    usdthb_current = live_data.get('EXCH_USDTHB', 35.0)

    for date in history_dates:
        cutoff = date + pd.Timedelta(days=1)
        # Fast update for the current day
        while l_ptr < len(ledger_sorted) and ledger_sorted.iloc[l_ptr]['Timestamp'] < cutoff:
            txn = ledger_sorted.iloc[l_ptr]
            l_ptr += 1
            
            current_cash += txn['CashDelta']
            if txn['Type'] in ['INITIAL', 'ADJUST']:
                current_injected += txn['CashDelta']
            
            sym = str(txn['Symbol']).strip().upper()
            if sym != 'CASH':
                qty = txn['Quantity']
                if txn['Type'] == 'BUY':
                    holdings[sym] = holdings.get(sym, 0.0) + qty
                    holdings_cost[sym] = holdings_cost.get(sym, 0.0) + abs(txn['CashDelta'])
                elif txn['Type'] == 'SELL':
                    if sym in holdings and holdings[sym] > 0:
                        ratio = abs(qty) / holdings[sym]
                        holdings_cost[sym] -= holdings_cost.get(sym, 0.0) * ratio
                        holdings[sym] -= abs(qty)
        
        # Calculate market value for the day
        stock_value = 0.0
        rate_thb = hist_prices.loc[date, "USDTHB=X"] if "USDTHB=X" in hist_prices.columns else usdthb_current
        if pd.isna(rate_thb): rate_thb = usdthb_current

        for sym, qty in holdings.items():
            if qty > 0.0001 and sym in hist_prices.columns:
                price = hist_prices.loc[date, sym]
                if pd.notna(price):
                    current_rate = rate_thb if not sym.endswith('.BK') else 1.0
                    stock_value += price * current_rate * qty
        
        if stock_value < 0.01: stock_value = 0.0
        
        cost_total = sum(holdings_cost.values())
        total_val = stock_value + current_cash
        
        portfolio_values.append(total_val)
        cash_balances.append(current_cash)
        market_profits.append(total_val - current_injected)
        cost_basis_history.append(cost_total)

# Summary Metrics (Using Performance Data)
current_total_val = portfolio_values[-1] if portfolio_values else 0
range_start_val = portfolio_values[0] if portfolio_values else 0 # Fixed: Added back for chart baseline
# Profit change within the selected range (Market Gain/Loss)
profit_start = market_profits[0] if market_profits else 0
profit_end = market_profits[-1] if market_profits else 0
period_profit = profit_end - profit_start

# Calculate P/L % relative to Cost Basis (Profit / Capital invested in stocks)
total_cost_basis = df['CostTHB'].sum() if not df.empty else 0
period_pct = (period_profit / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Current Portfolio Value", f"฿{current_total_val:,.2f}")
col2.metric(f"Profit/Loss ({time_range})", f"฿{period_profit:,.2f}")
col3.metric("Cost Basis (THB)", f"฿{total_cost_basis:,.2f}")
col4.metric("Cash Balance", f"฿{st.session_state.balance:,.2f}")

# --- ADVANCED ANALYTICS CALCULATION ---
with st.expander("🏦 Advanced Analytics", expanded=True):
    # 1. Trade Performance (Filtered by selected timeframe)
    period_start_dt = pd.to_datetime(history_dates[0]).tz_localize(None) if len(history_dates) > 0 else datetime.min
    
    ledger_sorted = st.session_state.ledger.sort_values('Timestamp').copy()
    # Normalize timestamps for comparison
    ledger_sorted['Timestamp'] = pd.to_datetime(ledger_sorted['Timestamp']).dt.tz_localize(None)
    
    avg_costs = {} 
    wins, losses, total_realized_pl = 0, 0, 0
    win_sum, loss_sum = 0, 0
    
    for _, txn in ledger_sorted.iterrows():
        sym = txn['Symbol']
        if sym == 'CASH': continue
        
        if txn['Type'] == 'BUY':
            curr = avg_costs.get(sym, {'cost': 0.0, 'qty': 0.0})
            curr['cost'] += abs(txn['CashDelta'])
            curr['qty'] += abs(txn['Quantity'])
            avg_costs[sym] = curr
        elif txn['Type'] == 'SELL':
            if sym in avg_costs and avg_costs[sym]['qty'] > 0:
                sold_qty = abs(txn['Quantity'])
                ratio = sold_qty / avg_costs[sym]['qty']
                cost_basis_sold = avg_costs[sym]['cost'] * ratio
                profit = txn['CashDelta'] - cost_basis_sold
                
                # Filter metrics by timeframe
                if txn['Timestamp'] >= period_start_dt:
                    total_realized_pl += profit
                    if profit > 0: 
                        wins += 1
                        win_sum += profit
                    else: 
                        losses += 1
                        loss_sum += abs(profit)
                
                avg_costs[sym]['cost'] -= cost_basis_sold
                avg_costs[sym]['qty'] -= sold_qty

    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
    avg_pl = (total_realized_pl / total_closed) if total_closed > 0 else 0
    
    # Calculate RRR: Avg Win / Avg Loss
    avg_win = (win_sum / wins) if wins > 0 else 0
    avg_loss = (loss_sum / losses) if losses > 0 else 0
    rrr = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    
    # Calculate Maximum Drawdown (MDD)
    mdd = 0.0
    if len(portfolio_values) > 1:
        vals_series = pd.Series(portfolio_values)
        rolling_max = vals_series.cummax()
        drawdowns = (vals_series - rolling_max) / rolling_max
        mdd = drawdowns.min() * 100 # Convert to percentage
    
    a_col1, a_col2, a_col3, a_col4 = st.columns(4)
    a_col1.metric("Win Rate", f"{win_rate:.1f}%")
    a_col2.metric("Avg P/L", f"฿{avg_pl:,.2f}")
    a_col3.metric("Risk-Reward (RRR)", f"{rrr:.2f}", help="Avg Profit / Avg Loss. Measures if your winners are larger than losers.")
    a_col4.metric("Max Drawdown", f"{mdd:.1f}%", help="Largest peak-to-trough decline in this period.")

# 3. Plot (Single Line with Dynamic Color)
try:
    fig_history = go.Figure()

    # 1. Calculate Reactive Performance Segments (Continuous Green/Red)
    baseline = range_start_val
    green_x, green_y = [], []
    red_x, red_y = [], []

    for i in range(len(portfolio_values) - 1):
        v1, v2 = portfolio_values[i], portfolio_values[i+1]
        t1, t2 = history_dates[i], history_dates[i+1]
        
        if v1 >= baseline:
            green_x.append(t1); green_y.append(v1)
            if v2 < baseline:
                # Cross from Green to Red
                ratio = (baseline - v1) / (v2 - v1)
                t_cross = t1 + (t2 - t1) * ratio
                green_x.append(t_cross); green_y.append(baseline)
                red_x.append(t_cross); red_y.append(baseline)
                green_x.append(None); green_y.append(None) # Break green line
            else:
                red_x.append(None); red_y.append(None) # Gap in red
        else:
            red_x.append(t1); red_y.append(v1)
            if v2 >= baseline:
                # Cross from Red to Green
                ratio = (baseline - v1) / (v2 - v1)
                t_cross = t1 + (t2 - t1) * ratio
                red_x.append(t_cross); red_y.append(baseline)
                green_x.append(t_cross); green_y.append(baseline)
                red_x.append(None); red_y.append(None) # Break red line
            else:
                green_x.append(None); green_y.append(None) # Gap in green
                
    # Add final point
    v_last, t_last = portfolio_values[-1], history_dates[-1]
    if v_last >= baseline:
        green_x.append(t_last); green_y.append(v_last)
    else:
        red_x.append(t_last); red_y.append(v_last)

    # 2. Green Fill Area
    fig_history.add_trace(go.Scatter(
        x=green_x, y=[baseline if v is not None else None for v in green_y],
        line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig_history.add_trace(go.Scatter(
        x=green_x, y=green_y,
        fill='tonexty',
        fillcolor='rgba(46, 213, 115, 0.15)',
        line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))

    # 3. Red Fill Area
    fig_history.add_trace(go.Scatter(
        x=red_x, y=[baseline if v is not None else None for v in red_y],
        line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig_history.add_trace(go.Scatter(
        x=red_x, y=red_y,
        fill='tonexty',
        fillcolor='rgba(255, 71, 87, 0.15)',
        line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))

    # 4. Baseline Dashed Line (Visible)
    fig_history.add_trace(go.Scatter(
        x=history_dates, y=[baseline] * len(history_dates),
        line=dict(color='rgba(136,136,136,0.3)', width=1, dash='dash'),
        name="Baseline",
        showlegend=False, hoverinfo='skip'
    ))

    # 5. Reactive Performance Lines (Green/Red segments)
    fig_history.add_trace(go.Scatter(
        x=green_x, y=green_y,
        line=dict(color='#2ed573', width=1.5),
        connectgaps=False, showlegend=False, hoverinfo='skip'
    ))
    fig_history.add_trace(go.Scatter(
        x=red_x, y=red_y,
        line=dict(color='#ff4757', width=1.5),
        connectgaps=False, showlegend=False, hoverinfo='skip'
    ))

    # 6. Invisible Trace for Tooltip (Full Data)
    pct_changes = [round((v - range_start_val) / range_start_val * 100, 2) if range_start_val != 0 else 0 for v in portfolio_values]
    fig_history.add_trace(go.Scatter(
        x=history_dates, 
        y=portfolio_values,
        customdata=pct_changes,
        line=dict(width=0),
        name="Portfolio Value",
        hovertemplate='<b>Value</b>: ฿%{y:,.1f} (%{customdata:+.3f}%)<extra></extra>'
    ))

    # Calculate Min/Max for better zoom
    all_vals = portfolio_values + [range_start_val]
    y_min = min(all_vals)
    y_max = max(all_vals)
    padding = (y_max - y_min) * 0.15 if y_max != y_min else y_max * 0.01
    if padding == 0: padding = 1
    
    fig_history.update_layout(
        hovermode="x unified",
        dragmode=False,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(fixedrange=True, showgrid=False),
        yaxis=dict(
            fixedrange=True, 
            showgrid=True, 
            gridcolor='rgba(200,200,200,0.1)',
            range=[y_min - padding, y_max + padding]
        ),
        margin=dict(t=30, b=0, l=0, r=0)
    )
    
    st.plotly_chart(fig_history, width="stretch", config={'displayModeBar': False})
    
except Exception as e:
    st.warning(f"Waiting for more data to generate history chart... (Info: {e})")

# Data Display
st.subheader("📋 My Assets")

display_df = df.copy()
if not display_df.empty:
    def format_currency_value(row, col_name):
        symbol = '$' if row['Currency'] == 'USD' else '฿'
        return f"{symbol}{row[col_name]:,.2f}"
    
    display_df['Buy Price'] = display_df.apply(lambda r: format_currency_value(r, 'Buy Price'), axis=1)
    display_df['Current Price'] = display_df.apply(lambda r: format_currency_value(r, 'Current Price'), axis=1)
    display_df['Market Value'] = display_df['Market Value'].map('฿{:,.2f}'.format)
    display_df['Profit/Loss'] = display_df['Profit/Loss'].map('฿{:,.2f}'.format)
    display_df['% Change'] = display_df['% Change'].map('{:,.2f}%'.format)

st.dataframe(display_df, width="stretch", hide_index=True)

# Visualizations
if not df.empty:
    st.divider()
    v_col1, v_col2 = st.columns(2)
    with v_col1:
        st.subheader("🎡 Portfolio Allocation")
        fig_pie = px.pie(df, values='Market Value', names='Symbol', hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, width="stretch")
        
        # New: Asset Type Allocation (Cash vs Stocks)
        st.subheader("🏦 Asset Class Allocation")
        total_stocks = df['Market Value'].sum()
        total_cash = st.session_state.balance
        asset_df = pd.DataFrame({
            'Asset': ['Stocks', 'Cash'],
            'Value': [total_stocks, total_cash]
        })
        fig_asset = px.pie(asset_df, values='Value', names='Asset', hole=0.4,
                          color_discrete_map={'Stocks': '#2ed573', 'Cash': '#54a0ff'})
        fig_asset.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_asset, width="stretch")
    with v_col2:
        st.subheader("📊 Profit Contribution")
        # Determine the color range to center it at 0 (Red < 0 < Green)
        max_val = df['Profit/Loss'].abs().max()
        if max_val == 0: max_val = 1.0 # Prevent 0 range
        
        fig_bar = px.bar(df, x='Symbol', y='Profit/Loss', 
                         color='Profit/Loss',
                         color_continuous_scale='RdYlGn',
                         range_color=[-max_val, max_val])
        st.plotly_chart(fig_bar, width="stretch")

        # New: Cash Balance History (Moved here)
        st.subheader("🏦 Cash Balance History")
        try:
            fig_cash_only = go.Figure()
            fig_cash_only.add_trace(go.Scatter(
                x=history_dates, 
                y=cash_balances,
                line=dict(color='#54a0ff', width=3),
                fill='tozeroy',
                fillcolor='rgba(84, 160, 255, 0.1)',
                name="Cash Balance",
                hovertemplate='<b>Cash</b>: ฿%{y:,.2f}<extra></extra>'
            ))
            # Cost Basis Trace
            fig_cash_only.add_trace(go.Scatter(
                x=history_dates, 
                y=cost_basis_history,
                line=dict(color='#ffa502', width=2, dash='dash'),
                name="Cost Basis",
                hovertemplate='<b>Cost Basis</b>: ฿%{y:,.2f}<extra></extra>'
            ))
            fig_cash_only.update_layout(
                hovermode="x unified",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.1)'),
                margin=dict(t=30, b=0, l=0, r=0),
                height=350
            )
            st.plotly_chart(fig_cash_only, width="stretch", config={'displayModeBar': False})
        except:
            st.info("Additional history data loading...")
else:
    st.info("👋 Welcome! Use the sidebar to add stocks and see your metrics & charts here.")

# --- TRANSACTION HISTORY (LEDGER MANAGEMENT) ---
st.divider()
with st.expander("📜 Manage Transaction History (Edit/Delete)", expanded=True if st.session_state.portfolio.empty else False):
    st.info("You can edit values directly or select rows and press 'Delete' on your keyboard. Your portfolio will automatically recalculate.")
    
    # Display editable ledger
    edited_ledger = st.data_editor(
        st.session_state.ledger,
        width="stretch",
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Timestamp": st.column_config.DatetimeColumn("Date/Time", format="D MMM YYYY, HH:mm"),
            "Type": st.column_config.SelectboxColumn("Type", options=["BUY", "SELL", "ADJUST", "INITIAL"]),
            "Price": st.column_config.NumberColumn("Unit Price (Local)", format="%.2f"),
            "Quantity": st.column_config.NumberColumn("Qty"),
            "Fees": st.column_config.NumberColumn("Fees (฿)", format="฿%.2f"),
            "CashDelta": st.column_config.NumberColumn("Cash Change (฿)", format="฿%.2f", disabled=True)
        }
    )
    
    # If any data changed, update everything
    if not edited_ledger.equals(st.session_state.ledger):
        # We add a hidden column for original comm rate or we just re-calc based on CashDelta
        # For simplicity, we assume users update Price/Qty and we use the first transaction's comm rate if available
        # But a better way is to let them edit Fees too. Let's make Fees editable.
        
        st.session_state.ledger = edited_ledger
        save_data()
        recalculate_state()
        st.success("Changes saved and portfolio recalculated!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** ติ๊กช่อง 'Thai Stock' เพื่อให้ระบบเติม `.BK` ให้อัตโนมัติ (เช่น พิมพ์ `PTT` จะเป็น `PTT.BK`) หรือกรอกรหัสหุ้นต่างประเทศเองได้เลยครับ")
