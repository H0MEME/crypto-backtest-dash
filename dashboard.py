import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import ccxt
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Crypto All-in-One Platform", layout="wide")

@st.cache_data(ttl=86400)
def get_crypto_usdt_pairs():
    exchange = ccxt.binanceus({'enableRateLimit': True}) 
    retries = 3
    for attempt in range(retries):
        try:
            markets = exchange.load_markets()
            return sorted([symbol for symbol, market in markets.items() if symbol.endswith('/USDT') and market.get('active', True)])
        except Exception as e:
            if attempt == retries - 1: return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
            time.sleep(2)

usdt_pairs = get_crypto_usdt_pairs()

# ==========================================
# 📌 สร้างเมนูหลักด้านข้าง (Sidebar Navigation)
# ==========================================
st.sidebar.title("🧭 เมนูใช้งานหลัก")
app_mode = st.sidebar.radio("เลือกฟังก์ชันการทำงาน:", 
                            ["📊 ระบบทดสอบ (Backtester)", "🚀 เรดาร์หาเหรียญ (All-Market Screener)"])
st.sidebar.markdown("---")

strategy_info = {
    "Ichimoku Breakout (Trend 4H)": {"desc": "ทะลุเมฆ Ichimoku กรองเทรนด์ด้วย EMA200 และความแรงเทรนด์ด้วย ADX > 25", "source": "YouTube: ORC Crypto"},
    "Breakout + Volume Filter": {"desc": "เทรดตามเทรนด์ด้วย Bollinger Bands และใช้ Volume กรองสัญญาณหลอก", "source": "YouTube: ORC Crypto"},
    "EMA Crossover (Classic)": {"desc": "ระบบเทรดพื้นฐาน ตัดขึ้นซื้อ ตัดลงขาย (ใช้ EMA 12 ตัด EMA 26)", "source": "Investopedia"},
    "ATR Fibonacci Pocket (Pullback)": {"desc": "จับเทรนด์ด้วย WMA(100) และหาจังหวะย่อตัว (Pullback)", "source": "YouTube: ORC Crypto"},
    "SMC (Smart Money Concepts)": {"desc": "หาจังหวะเบรคโครงสร้าง (MSS) และตั้งรับที่ช่องว่างราคา (FVG)", "source": "YouTube: ORC Crypto"}
}

# ==========================================
# โหมดที่ 1: BACKTESTER
# ==========================================
if app_mode == "📊 ระบบทดสอบ (Backtester)":
    st.title("📊 ระบบทดสอบกลยุทธ์เทรด (Interactive Table)")
    
    st.sidebar.header("⚙️ ตั้งค่าระบบเทรด")
    strategy_choice = st.sidebar.selectbox("🎯 เลือกกลยุทธ์เทรด", list(strategy_info.keys()))
    default_index = usdt_pairs.index('BTC/USDT') if 'BTC/USDT' in usdt_pairs else 0
    symbol = st.sidebar.selectbox("🔍 ค้นหาคู่เหรียญ (พิมพ์ชื่อได้เลย)", usdt_pairs, index=default_index)

    if "Ichimoku" in strategy_choice: default_tf, default_yr = 2, 2
    elif "SMC" in strategy_choice: default_tf, default_yr = 0, 0
    elif "ATR" in strategy_choice: default_tf, default_yr = 1, 1
    else: default_tf, default_yr = 1, 2

    timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=default_tf)
    years_back = st.sidebar.selectbox("ระยะเวลาย้อนหลัง", ["6 เดือน", "1 ปี", "2 ปี", "3 ปี"], index=default_yr)
    days_back = {"6 เดือน": 180, "1 ปี": 365, "2 ปี": 730, "3 ปี": 1095}[years_back]

    st.sidebar.markdown("---")
    st.sidebar.subheader("💰 การจัดการเงิน")
    initial_capital = st.sidebar.number_input("ทุนเริ่มต้น ($)", min_value=10.0, value=5000.0, step=100.0)
    risk_per_trade = st.sidebar.slider("ความเสี่ยงเมื่อขาดทุน (%)", 1.0, 10.0, 3.0, step=0.5)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ การจัดการออเดอร์")
    enable_advanced_tm = st.sidebar.checkbox("เปิดใช้ระบบแบ่งปิดกำไร และเลื่อน SL บังทุน", value=False)
    if enable_advanced_tm:
        be_rr = st.sidebar.slider("จุดเลื่อน Stop Loss บังหน้าทุน (RR)", 0.5, 3.0, 1.0, 0.1)
        partial_rr = st.sidebar.slider("จุดแบ่งปิดกำไร 50% (RR)", 1.0, 4.0, 1.5, 0.1)
        final_rr = st.sidebar.slider("เป้าหมายกำไรที่เหลือ (Final RR)", 2.0, 10.0, 3.0, 0.5)
    else:
        default_rr = 3.0 if "Ichimoku" in strategy_choice else 2.0
        standard_rr = st.sidebar.slider("เป้าหมายกำไรตายตัว (RR)", 1.0, 10.0, default_rr, 0.5)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_historical_data(sym, tf, days):
        exchange = ccxt.binanceus({'enableRateLimit': True})
        start_time = datetime.now() - timedelta(days=days)
        since = int(start_time.timestamp() * 1000)
        all_bars = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        while True:
            try:
                bars = exchange.fetch_ohlcv(sym, timeframe=tf, since=since, limit=1000)
                if not bars: break
                all_bars.extend(bars)
                since = bars[-1][0] + 1 
                percent_done = min(100, int((len(all_bars) / (days * 24 * (60/int(tf.replace('m','').replace('h','60').replace('d','1440'))))) * 100))
                progress_bar.progress(percent_done / 100.0)
                status_text.text(f"⏳ กำลังโหลดข้อมูล {sym}... ได้มาแล้ว {len(all_bars)} แท่ง")
                if len(bars) < 1000: break
                time.sleep(0.5) 
            except Exception:
                status_text.text(f"⚠️ API จำกัดการเชื่อมต่อชั่วคราว รอ 3 วินาที...")
                time.sleep(3)
        progress_bar.empty()
        status_text.empty()
        if not all_bars: return pd.DataFrame()
        df = pd.DataFrame(all_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=7) 
        df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        return df

    df = load_historical_data(symbol, timeframe, days_back)
    if df.empty:
        st.error("ไม่พบข้อมูล กรุณาลองเปลี่ยนเหรียญหรือลดเวลาลง")
        st.stop()

    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr_14'] = df['tr'].ewm(alpha=1/14, adjust=False).mean()

    if strategy_choice == "Ichimoku Breakout (Trend 4H)":
        df['tenkan'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2
        df['kijun'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
        df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift(26)
        df['senkou_b'] = ((df['high'].rolling(window=52).max() + df['low'].rolling(window=52).min()) / 2).shift(26)
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['up_move'] = df['high'].diff()
        df['down_move'] = df['low'].shift(1) - df['low']
        df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0.0)
        df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0.0)
        df['+di'] = 100 * (pd.Series(df['+dm']).ewm(alpha=1/14, adjust=False).mean() / df['atr_14'])
        df['-di'] = 100 * (pd.Series(df['-dm']).ewm(alpha=1/14, adjust=False).mean() / df['atr_14'])
        df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'] + 1e-10)
        df['adx'] = df['dx'].ewm(alpha=1/14, adjust=False).mean()

    elif strategy_choice == "ATR Fibonacci Pocket (Pullback)":
        weights = np.arange(1, 101)
        weights = weights / weights.sum()
        wma_100 = np.convolve(df['close'].values, weights, mode='valid')
        df['wma_100'] = np.concatenate((np.full(99, np.nan), wma_100))
        df['atr_100'] = df['tr'].ewm(alpha=1/100, adjust=False).mean()

    elif strategy_choice == "Breakout + Volume Filter":
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['std_20'] = df['close'].rolling(window=20).std()
        df['upper_bb'] = df['sma_20'] + (df['std_20'] * 2)
        df['lower_bb'] = df['sma_20'] - (df['std_20'] * 2)
        df['vol_ma_20'] = df['volume'].rolling(window=20).mean()

    elif "SMC" in strategy_choice: 
        window = 3
        df['swing_low'] = df['low'] == df['low'].rolling(window=window*2+1, center=True).min()
        df['swing_high'] = df['high'] == df['high'].rolling(window=window*2+1, center=True).max()
        df['fvg_bullish'] = df['low'] > df['high'].shift(2)
        df['fvg_bearish'] = df['high'] < df['low'].shift(2)

    elif strategy_choice == "EMA Crossover (Classic)":
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

    df = df.dropna().reset_index(drop=True)

    capital = initial_capital
    in_position, position_type = False, None
    entry_price, sl_price, position_size = 0, 0, 0
    current_entry_time, initial_sl_price = None, 0
    remaining_size, trade_pnl = 0, 0.0
    is_partial, is_breakeven = False, False
    be_trigger_price, partial_tp_price, final_tp_price = 0, 0, 0
    pending_order, order_timeout = False, 0
    last_swing_low, last_swing_high = 0, float('inf')
    pullback_long, pullback_short = False, False
    bos_high, bos_low, sl_point = 0, float('inf'), 0
    equity_curve, trade_history = [initial_capital], []

    for i in range(10, len(df)):
        row = df.iloc[i]
        just_entered = False
        
        if "SMC" in strategy_choice:
            if df['swing_low'].iloc[i-3]: last_swing_low = df['low'].iloc[i-3]
            if df['swing_high'].iloc[i-3]: last_swing_high = df['high'].iloc[i-3]

        if in_position:
            if position_type == 'LONG':
                if row['low'] <= sl_price:
                    trade_pnl += remaining_size * (sl_price - entry_price)
                    capital += remaining_size * (sl_price - entry_price)
                    equity_curve.append(capital)
                    res_str = 'ชนะ (Win)' if trade_pnl > 0 else ('เสมอ (Breakeven)' if trade_pnl == 0 else 'แพ้ (Loss)')
                    trade_history.append({'entry_date': current_entry_time, 'exit_date': row['timestamp'], 'type': 'LONG', 'result': res_str, 'pnl': trade_pnl, 'balance': capital, 'entry_price': entry_price, 'initial_sl': initial_sl_price, 'exit_price': sl_price})
                    in_position = False
                    continue
                if enable_advanced_tm and not is_breakeven and row['high'] >= be_trigger_price:
                    sl_price, is_breakeven = entry_price, True
                if enable_advanced_tm and not is_partial and row['high'] >= partial_tp_price:
                    trade_pnl += (remaining_size * 0.5) * (partial_tp_price - entry_price)
                    capital += (remaining_size * 0.5) * (partial_tp_price - entry_price)
                    remaining_size *= 0.5 
                    is_partial, is_breakeven, sl_price = True, True, max(sl_price, entry_price) 
                if row['high'] >= final_tp_price:
                    trade_pnl += remaining_size * (final_tp_price - entry_price)
                    capital += remaining_size * (final_tp_price - entry_price)
                    equity_curve.append(capital)
                    trade_history.append({'entry_date': current_entry_time, 'exit_date': row['timestamp'], 'type': 'LONG', 'result': 'ชนะ (Win)', 'pnl': trade_pnl, 'balance': capital, 'entry_price': entry_price, 'initial_sl': initial_sl_price, 'exit_price': final_tp_price})
                    in_position = False
                    
            elif position_type == 'SHORT':
                if row['high'] >= sl_price:
                    trade_pnl += remaining_size * (entry_price - sl_price)
                    capital += remaining_size * (entry_price - sl_price)
                    equity_curve.append(capital)
                    res_str = 'ชนะ (Win)' if trade_pnl > 0 else ('เสมอ (Breakeven)' if trade_pnl == 0 else 'แพ้ (Loss)')
                    trade_history.append({'entry_date': current_entry_time, 'exit_date': row['timestamp'], 'type': 'SHORT', 'result': res_str, 'pnl': trade_pnl, 'balance': capital, 'entry_price': entry_price, 'initial_sl': initial_sl_price, 'exit_price': sl_price})
                    in_position = False
                    continue
                if enable_advanced_tm and not is_breakeven and row['low'] <= be_trigger_price:
                    sl_price, is_breakeven = entry_price, True
                if enable_advanced_tm and not is_partial and row['low'] <= partial_tp_price:
                    trade_pnl += (remaining_size * 0.5) * (entry_price - partial_tp_price)
                    capital += (remaining_size * 0.5) * (entry_price - partial_tp_price)
                    remaining_size *= 0.5
                    is_partial, is_breakeven, sl_price = True, True, min(sl_price, entry_price)
                if row['low'] <= final_tp_price:
                    trade_pnl += remaining_size * (entry_price - final_tp_price)
                    capital += remaining_size * (entry_price - final_tp_price)
                    equity_curve.append(capital)
                    trade_history.append({'entry_date': current_entry_time, 'exit_date': row['timestamp'], 'type': 'SHORT', 'result': 'ชนะ (Win)', 'pnl': trade_pnl, 'balance': capital, 'entry_price': entry_price, 'initial_sl': initial_sl_price, 'exit_price': final_tp_price})
                    in_position = False
            continue

        if pending_order:
            order_timeout -= 1
            if row['low'] <= entry_price and position_type == 'LONG':
                in_position, pending_order, just_entered = True, False, True
            elif order_timeout <= 0 or row['close'] < sl_price:
                pending_order = False

        if not in_position and not pending_order:
            if strategy_choice == "Ichimoku Breakout (Trend 4H)":
                if row['close'] > max(row['senkou_a'], row['senkou_b']) and row['tenkan'] > row['kijun'] and row['close'] > row['ema_200'] and row['adx'] > 25:
                    entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                    position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                    in_position, position_type, just_entered = True, 'LONG', True
                elif row['close'] < min(row['senkou_a'], row['senkou_b']) and row['tenkan'] < row['kijun'] and row['close'] < row['ema_200'] and row['adx'] > 25:
                    entry_price, sl_price = row['close'], row['close'] + (row['atr_14'] * 2)
                    position_size = (capital * (risk_per_trade / 100)) / (sl_price - entry_price)
                    in_position, position_type, just_entered = True, 'SHORT', True

            elif strategy_choice == "SMC + Session Liquidity Sweep (ICT)":
                if (row['timestamp'].hour >= 15) or (row['timestamp'].hour <= 4):
                    if row['low'] < last_swing_low and row['close'] > last_swing_high and (df['fvg_bullish'].iloc[i] or df['fvg_bullish'].iloc[i-1]):
                        entry_price, sl_price = row['close'], row['low']      
                        if entry_price > sl_price:
                            position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                            in_position, position_type, just_entered = True, 'LONG', True
                    if row['high'] > last_swing_high and row['close'] < last_swing_low and (df['fvg_bearish'].iloc[i] or df['fvg_bearish'].iloc[i-1]):
                        entry_price, sl_price = row['close'], row['high']
                        if sl_price > entry_price:
                            position_size = (capital * (risk_per_trade / 100)) / (sl_price - entry_price)
                            in_position, position_type, just_entered = True, 'SHORT', True
                            
            elif strategy_choice == "ATR Fibonacci Pocket (Pullback)":
                trend = 1 if row['close'] > row['wma_100'] else -1
                if trend == 1:
                    pocket_top, pocket_bottom = row['wma_100'] - (row['atr_100'] * 3 * 0.5), row['wma_100'] - (row['atr_100'] * 3 * 0.786)
                    if row['low'] <= pocket_top and row['close'] > (row['wma_100'] - row['atr_100']*3):
                        if not pullback_long: pullback_long, bos_high, sl_point = True, df['high'].iloc[i-10:i].max(), row['low']
                        else: sl_point = min(sl_point, row['low'])
                    if pullback_long and row['close'] > bos_high:
                        entry_price, sl_price = row['close'], sl_point - (row['atr_14'] * 0.5)
                        if entry_price > sl_price:
                            position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                            in_position, position_type, just_entered = True, 'LONG', True
                        pullback_long = False
                    elif row['close'] < pocket_bottom: pullback_long = False
                elif trend == -1:
                    pocket_bottom, pocket_top = row['wma_100'] + (row['atr_100'] * 3 * 0.5), row['wma_100'] + (row['atr_100'] * 3 * 0.786)
                    if row['high'] >= pocket_bottom and row['close'] < (row['wma_100'] + row['atr_100']*3):
                        if not pullback_short: pullback_short, bos_low, sl_point = True, df['low'].iloc[i-10:i].min(), row['high']
                        else: sl_point = max(sl_point, row['high'])
                    if pullback_short and row['close'] < bos_low:
                        entry_price, sl_price = row['close'], sl_point + (row['atr_14'] * 0.5)
                        if sl_price > entry_price:
                            position_size = (capital * (risk_per_trade / 100)) / (sl_price - entry_price)
                            in_position, position_type, just_entered = True, 'SHORT', True
                        pullback_short = False
                    elif row['close'] > pocket_top: pullback_short = False

            elif strategy_choice == "Breakout + Volume Filter":
                if row['close'] > row['ema_200'] and row['close'] > row['upper_bb'] and row['volume'] > row['vol_ma_20']:
                    entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                    position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                    in_position, position_type, just_entered = True, 'LONG', True
                elif row['close'] < row['ema_200'] and row['close'] < row['lower_bb'] and row['volume'] > row['vol_ma_20']:
                    entry_price, sl_price = row['close'], row['close'] + (row['atr_14'] * 2)
                    position_size = (capital * (risk_per_trade / 100)) / (sl_price - entry_price)
                    in_position, position_type, just_entered = True, 'SHORT', True
                    
            elif strategy_choice == "EMA Crossover (Classic)":
                if df['ema_12'].iloc[i-1] <= df['ema_26'].iloc[i-1] and row['ema_12'] > row['ema_26']:
                    entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                    position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                    in_position, position_type, just_entered = True, 'LONG', True

        if just_entered:
            current_entry_time, initial_sl_price = row['timestamp'], sl_price
            risk_distance = abs(entry_price - sl_price)
            remaining_size, trade_pnl = position_size, 0.0
            is_partial, is_breakeven = False, False
            if enable_advanced_tm:
                be_trigger_price = entry_price + (risk_distance * be_rr) if position_type == 'LONG' else entry_price - (risk_distance * be_rr)
                partial_tp_price = entry_price + (risk_distance * partial_rr) if position_type == 'LONG' else entry_price - (risk_distance * partial_rr)
                final_tp_price = entry_price + (risk_distance * final_rr) if position_type == 'LONG' else entry_price - (risk_distance * final_rr)
            else:
                final_tp_price = entry_price + (risk_distance * standard_rr) if position_type == 'LONG' else entry_price - (risk_distance * standard_rr)
                partial_tp_price, be_trigger_price = final_tp_price, float('inf') if position_type == 'LONG' else 0

    trades = len(trade_history)
    wins = sum(1 for t in trade_history if t['pnl'] > 0)
    losses = sum(1 for t in trade_history if t['pnl'] < 0)
    breakevens = sum(1 for t in trade_history if t['pnl'] == 0)
    win_rate = (wins / trades * 100) if trades > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("ทุนสุดท้าย (Final Capital)", f"${capital:,.2f}", f"{(capital-initial_capital)/initial_capital*100:,.2f}%")
    col2.metric("จำนวนไม้เทรด (Total Trades)", f"{trades} ไม้", f"ชนะ: {wins} | แพ้: {losses} | เสมอตัว: {breakevens}", delta_color="off")
    col3.metric("อัตราชนะ (Win Rate)", f"{win_rate:.0f}%")

    st.divider()
    st.subheader("📈 กราฟการเติบโตของพอร์ต (Equity Curve)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, mode='lines', name='Capital ($)', line=dict(color='#00ff88', width=2), fill='tozeroy', fillcolor='rgba(0, 255, 136, 0.1)'))
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="จำนวนออเดอร์ที่ปิด (Trades)", yaxis_title="ยอดเงินในพอร์ต ($)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------
    # ส่วนประวัติการเทรดและ Trade Visualizer 
    # ----------------------------------------------------
    st.subheader("📋 ประวัติการเข้าเทรด")
    if trades > 0:
        df_history = pd.DataFrame(trade_history)
        df_show = df_history.copy()
        df_show['entry_date'] = df_show['entry_date'].dt.strftime('%d/%m/%Y %H:%M')
        df_show['exit_date'] = df_show['exit_date'].dt.strftime('%d/%m/%Y %H:%M')
        df_show['pnl'] = df_show['pnl'].apply(lambda x: f"{'+' if x>0 else ''}${x:,.2f}")
        df_show['balance'] = df_show['balance'].apply(lambda x: f"${x:,.2f}")
        df_show = df_show[['entry_date', 'exit_date', 'type', 'result', 'pnl', 'balance']]
        df_show.columns = ['วัน/เวลาเข้า', 'วัน/เวลาออก', 'ฝั่งเทรด', 'ผลลัพธ์', 'กำไร/ขาดทุน', 'เงินคงเหลือ']
        
        st.markdown("💡 **Tip:** คุณสามารถ **คลิกเลือกแถวในตารางด้านล่างนี้** เพื่อเปลี่ยนกราฟวิเคราะห์ไม้เทรดด้านล่างได้ทันทีครับ")
        
        if 'selectbox_idx' not in st.session_state:
            st.session_state.selectbox_idx = 0
        if 'last_clicked_row' not in st.session_state:
            st.session_state.last_clicked_row = None

        selection_event = st.dataframe(
            df_show, 
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if selection_event.selection.rows:
            clicked_row = selection_event.selection.rows[0]
            if st.session_state.last_clicked_row != clicked_row:
                st.session_state.selectbox_idx = clicked_row
                st.session_state.last_clicked_row = clicked_row
        else:
            st.session_state.last_clicked_row = None
            
        st.divider()
        st.subheader("🔎 เจาะลึกกราฟแต่ละไม้เทรด (Trade Visualizer)")
        
        trade_options = []
        for i, t in enumerate(trade_history):
            emoji = "🟢" if t['pnl'] > 0 else ("🔴" if t['pnl'] < 0 else "⚪")
            trade_options.append(f"ไม้ที่ {i+1} : {emoji} {t['type']} | PnL: ${t['pnl']:.2f} | วันที่เข้า: {t['entry_date'].strftime('%d %b %Y')}")
        
        current_val = st.session_state.get('selectbox_idx', 0)
        try:
            valid_idx = int(current_val)
        except:
            valid_idx = 0 
            
        if valid_idx >= trades or valid_idx < 0:
            valid_idx = 0
            
        st.session_state.selectbox_idx = valid_idx
            
        selected_idx = st.selectbox(
            "🎯 เลื่อนเพื่อดูไม้เทรดที่ต้องการ (ตัวเลือกนี้ซิงค์กับตารางด้านบน):", 
            range(trades),
            format_func=lambda i: trade_options[i],
            key="selectbox_idx" 
        )
        
        t_data = trade_history[selected_idx]
        
        idx_start = df.index[df['timestamp'] == t_data['entry_date']].tolist()[0]
        idx_end = df.index[df['timestamp'] == t_data['exit_date']].tolist()[0]
        
        plot_start = max(0, idx_start - 30)
        plot_end = min(len(df) - 1, idx_end + 30)
        df_plot = df.iloc[plot_start:plot_end+1]
        
        fig2 = go.Figure(data=[go.Candlestick(x=df_plot['timestamp'],
                        open=df_plot['open'], high=df_plot['high'],
                        low=df_plot['low'], close=df_plot['close'],
                        name='Candles')])
                        
        fig2.add_trace(go.Scatter(x=[t_data['entry_date']], y=[t_data['entry_price']],
                                  mode='markers', marker=dict(size=14, color='cyan', symbol='star'),
                                  name='🌟 จุดเข้า (Entry)'))
        fig2.add_trace(go.Scatter(x=[t_data['exit_date']], y=[t_data['exit_price']],
                                  mode='markers', marker=dict(size=14, color='magenta', symbol='x'),
                                  name='❌ จุดออก (Exit)'))
                                  
        fig2.add_shape(type="line", x0=df_plot['timestamp'].iloc[0], y0=t_data['initial_sl'],
                       x1=df_plot['timestamp'].iloc[-1], y1=t_data['initial_sl'],
                       line=dict(color="red", width=2, dash="dash"))
        fig2.add_annotation(x=df_plot['timestamp'].iloc[15], y=t_data['initial_sl'],
                            text="เส้น Stop Loss", showarrow=False, yshift=15, font=dict(color="red"))
                            
        fig2.add_shape(type="line", x0=df_plot['timestamp'].iloc[0], y0=t_data['entry_price'],
                       x1=df_plot['timestamp'].iloc[-1], y1=t_data['entry_price'],
                       line=dict(color="cyan", width=1, dash="dot"))
                       
        fig2.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False,
                           title=f"วิเคราะห์ไม้เทรดที่ {selected_idx+1} (สถานะ: {t_data['result']})")
        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.warning("ไม่พบสัญญาณการเข้าเทรด หรือข้อมูลเหรียญในอดีตมีไม่เพียงพอ กรุณาปรับเงื่อนไขให้ผ่อนคลายขึ้น")

# ==========================================
# โหมดที่ 2: ALL-MARKET SCREENER
# ==========================================
elif app_mode == "🚀 เรดาร์หาเหรียญ (All-Market Screener)":
    st.title("🚀 All-Market Strategy Screener")
    st.write("ระบบจะกวาดข้อมูลเหรียญทั้งตลาด เพื่อหาสัญญาณการเข้าเทรด **'ณ เวลานี้'** ตามกลยุทธ์ที่คุณเลือก พร้อมลิงก์เปิดกราฟ TradingView")
    
    screen_mode = st.radio("เลือกรูปแบบการสแกน:", ["1. สแกนหาสัญญาณเข้าเทรดรายกลยุทธ์ (Signal Finder)", "2. สแกนภาพรวมตลาด (Market Overview)"], horizontal=True)
    st.markdown("---")

    if screen_mode == "1. สแกนหาสัญญาณเข้าเทรดรายกลยุทธ์ (Signal Finder)":
        st.sidebar.header("🎯 ตั้งค่า Screener หาสัญญาณ")
        selected_strategy = st.sidebar.selectbox("เลือกกลยุทธ์ที่ต้องการสแกน", list(strategy_info.keys()))
        
        if "Ichimoku" in selected_strategy: default_tf_scan = 2
        elif "SMC" in selected_strategy: default_tf_scan = 1
        else: default_tf_scan = 1
        
        tf_screen = st.sidebar.selectbox("Timeframe (กราฟ)", ['15m', '1h', '4h', '1d'], index=default_tf_scan)
        min_vol = st.sidebar.number_input("คัดเฉพาะเหรียญที่มี Volume (USDT) มากกว่า:", min_value=0.0, value=3000000.0, step=1000000.0, help="คัดเหรียญสภาพคล่องต่ำออก เพื่อให้บอทสแกนได้เร็วขึ้น")
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("ตัวกรองพิเศษ (Extra Filters)")
        use_rsi_filter = st.sidebar.checkbox("เปิดใช้ตัวกรอง RSI (หลีกเลี่ยงการไล่ราคา)", value=True, help="Long: RSI ต้อง < 70 (ไม่ Overbought) | Short: RSI ต้อง > 30 (ไม่ Oversold)")

        if st.button(f"🔍 เริ่มสแกนหาสัญญาณ {selected_strategy} ทั้งตลาด", type="primary"):
            exchange = ccxt.binanceus({'enableRateLimit': True})
            
            with st.spinner('⏳ [ขั้นตอนที่ 1/2] กำลังดึงรายชื่อเหรียญที่มี Volume ผ่านเกณฑ์...'):
                try:
                    tickers = exchange.fetch_tickers()
                    filtered_symbols = []
                    for symbol, data in tickers.items():
                        if symbol.endswith('/USDT') and data.get('quoteVolume', 0) >= min_vol:
                            filtered_symbols.append(symbol)
                    st.toast(f"เจอเหรียญที่ผ่านเกณฑ์ Volume {len(filtered_symbols)} เหรียญ")
                except Exception as e:
                    st.error(f"เชื่อมต่อกระดานเทรดล้มเหลว: {e}")
                    st.stop()

            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            status_text.text(f"⏳ [ขั้นตอนที่ 2/2] กำลังคำนวณกราฟ {tf_screen} ตามสูตร {selected_strategy}...")
            
            for i, sym in enumerate(filtered_symbols):
                try:
                    ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf_screen, limit=250)
                    if len(ohlcv) < 200: continue
                    
                    df_scan = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    delta = df_scan['close'].diff()
                    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                    rs = gain / (loss + 1e-10)
                    df_scan['rsi_14'] = 100 - (100 / (1 + rs))
                    
                    df_scan['tr0'] = abs(df_scan['high'] - df_scan['low'])
                    df_scan['tr1'] = abs(df_scan['high'] - df_scan['close'].shift())
                    df_scan['tr2'] = abs(df_scan['low'] - df_scan['close'].shift())
                    df_scan['tr'] = df_scan[['tr0', 'tr1', 'tr2']].max(axis=1)
                    df_scan['atr_14'] = df_scan['tr'].ewm(alpha=1/14, adjust=False).mean()

                    latest = df_scan.iloc[-1] 
                    prev = df_scan.iloc[-2]   
                    signal = None
                    
                    if selected_strategy == "Ichimoku Breakout (Trend 4H)":
                        df_scan['tenkan'] = (df_scan['high'].rolling(window=9).max() + df_scan['low'].rolling(window=9).min()) / 2
                        df_scan['kijun'] = (df_scan['high'].rolling(window=26).max() + df_scan['low'].rolling(window=26).min()) / 2
                        df_scan['senkou_a'] = ((df_scan['tenkan'] + df_scan['kijun']) / 2).shift(26)
                        df_scan['senkou_b'] = ((df_scan['high'].rolling(window=52).max() + df_scan['low'].rolling(window=52).min()) / 2).shift(26)
                        df_scan['ema_200'] = df_scan['close'].ewm(span=200, adjust=False).mean()
                        df_scan['up_move'] = df_scan['high'].diff()
                        df_scan['down_move'] = df_scan['low'].shift(1) - df_scan['low']
                        df_scan['+dm'] = np.where((df_scan['up_move'] > df_scan['down_move']) & (df_scan['up_move'] > 0), df_scan['up_move'], 0.0)
                        df_scan['-dm'] = np.where((df_scan['down_move'] > df_scan['up_move']) & (df_scan['down_move'] > 0), df_scan['down_move'], 0.0)
                        df_scan['+di'] = 100 * (pd.Series(df_scan['+dm']).ewm(alpha=1/14, adjust=False).mean() / df_scan['atr_14'])
                        df_scan['-di'] = 100 * (pd.Series(df_scan['-dm']).ewm(alpha=1/14, adjust=False).mean() / df_scan['atr_14'])
                        df_scan['dx'] = 100 * abs(df_scan['+di'] - df_scan['-di']) / (df_scan['+di'] + df_scan['-di'] + 1e-10)
                        df_scan['adx'] = df_scan['dx'].ewm(alpha=1/14, adjust=False).mean()
                        
                        curr = df_scan.iloc[-1]
                        if curr['close'] > max(curr['senkou_a'], curr['senkou_b']) and curr['tenkan'] > curr['kijun'] and curr['close'] > curr['ema_200'] and curr['adx'] > 25:
                            signal = 'LONG 🟢'
                        elif curr['close'] < min(curr['senkou_a'], curr['senkou_b']) and curr['tenkan'] < curr['kijun'] and curr['close'] < curr['ema_200'] and curr['adx'] > 25:
                            signal = 'SHORT 🔴'
                            
                    elif selected_strategy == "Breakout + Volume Filter":
                        df_scan['ema_200'] = df_scan['close'].ewm(span=200, adjust=False).mean()
                        df_scan['sma_20'] = df_scan['close'].rolling(window=20).mean()
                        df_scan['std_20'] = df_scan['close'].rolling(window=20).std()
                        df_scan['upper_bb'] = df_scan['sma_20'] + (df_scan['std_20'] * 2)
                        df_scan['lower_bb'] = df_scan['sma_20'] - (df_scan['std_20'] * 2)
                        df_scan['vol_ma_20'] = df_scan['volume'].rolling(window=20).mean()
                        
                        curr = df_scan.iloc[-1]
                        if curr['close'] > curr['ema_200'] and curr['close'] > curr['upper_bb'] and curr['volume'] > curr['vol_ma_20'] * 1.5:
                            signal = 'LONG 🟢'
                        elif curr['close'] < curr['ema_200'] and curr['close'] < curr['lower_bb'] and curr['volume'] > curr['vol_ma_20'] * 1.5:
                            signal = 'SHORT 🔴'

                    elif selected_strategy == "EMA Crossover (Classic)":
                        df_scan['ema_12'] = df_scan['close'].ewm(span=12, adjust=False).mean()
                        df_scan['ema_26'] = df_scan['close'].ewm(span=26, adjust=False).mean()
                        if df_scan['ema_12'].iloc[-2] <= df_scan['ema_26'].iloc[-2] and df_scan['ema_12'].iloc[-1] > df_scan['ema_26'].iloc[-1]:
                            signal = 'LONG 🟢'
                        elif df_scan['ema_12'].iloc[-2] >= df_scan['ema_26'].iloc[-2] and df_scan['ema_12'].iloc[-1] < df_scan['ema_26'].iloc[-1]:
                            signal = 'SHORT 🔴'
                            
                    elif selected_strategy == "ATR Fibonacci Pocket (Pullback)":
                        weights = np.arange(1, 101)
                        wma_100 = np.convolve(df_scan['close'].values, weights / weights.sum(), mode='valid')
                        df_scan['wma_100'] = np.concatenate((np.full(99, np.nan), wma_100))
                        curr = df_scan.iloc[-1]
                        if curr['close'] > curr['wma_100'] and curr['low'] < (curr['wma_100'] - (curr['atr_14'] * 1.5)) and curr['close'] > curr['open']:
                            signal = 'PULLBACK LONG 🟢'

                    rsi_val = latest['rsi_14']
                    if signal and use_rsi_filter:
                        if 'LONG' in signal and rsi_val >= 70:
                            signal = None 
                        elif 'SHORT' in signal and rsi_val <= 30:
                            signal = None 

                    if signal:
                        # สร้างลิงก์ TradingView แบบตัดเครื่องหมาย / ออก เช่น BTCUSDT
                        tv_symbol = sym.replace("/", "")
                        tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCEUS:{tv_symbol}"
                        
                        results.append({
                            'เหรียญ (Symbol)': sym,
                            'สัญญาณ (Signal)': signal,
                            'ราคา (Price)': f"${latest['close']:.4f}",
                            'RSI (14)': f"{rsi_val:.1f}",
                            'คำแนะนำ': "เทรดได้เลย (RSI ปลอดภัย)" if use_rsi_filter else ("Overbought ระวัง!" if rsi_val > 70 else ("Oversold ระวัง!" if rsi_val < 30 else "ปกติ")),
                            'ดูกราฟ (Chart)': tv_link
                        })
                        
                except Exception:
                    pass
                    
                progress_bar.progress((i + 1) / len(filtered_symbols))
                time.sleep(0.1) 

            progress_bar.empty()
            status_text.empty()
            
            if results:
                st.success(f"🎉 แจ็คพอต! เจอเหรียญที่มีสัญญาณ {selected_strategy} กำลังเกิด ณ เวลานี้ จำนวน {len(results)} ตัว!")
                
                # แสดงผลแบบมี LinkColumn เพื่อให้คลิกเปิด TradingView ได้เลย
                st.dataframe(
                    pd.DataFrame(results), 
                    use_container_width=True,
                    column_config={
                        "ดูกราฟ (Chart)": st.column_config.LinkColumn("ดูกราฟ (Chart)", display_text="📈 เปิด TradingView")
                    }
                )
                st.info("💡 **นำชื่อเหรียญที่ได้ ไปกรอกในบอทยิงออเดอร์ (Bot.py) ของคุณได้เลยครับ!**")
            else:
                st.warning(f"😅 ขณะนี้ตลาดนิ่ง ไม่มีเหรียญไหนเกิดสัญญาณ {selected_strategy} เลยครับ (ระบบบอทที่ดีคือการ 'นั่งทับมือ' ในเวลาที่ไม่มีสัญญาณครับ)")

    elif screen_mode == "2. สแกนภาพรวมตลาด (Market Overview)":
        st.sidebar.header("🎯 ฟิลเตอร์กรองภาพรวม (Filters)")
        min_vol_usdt = st.sidebar.number_input("วอลุ่มเทรดขั้นต่ำ (USDT)", min_value=0.0, value=1000000.0, step=500000.0)
        price_change_min = st.sidebar.slider("ราคาเปลี่ยนไปขั้นต่ำ (%)", -50.0, 100.0, 5.0, 1.0)
        
        if st.button("🔍 สแกนตลาด (Scan Market)", type="primary"):
            with st.spinner('⏳ กำลังกวาดข้อมูลทุกเหรียญ...'):
                try:
                    exchange = ccxt.binanceus({'enableRateLimit': True})
                    tickers = exchange.fetch_tickers() 
                    market_data = []
                    for symbol, data in tickers.items():
                        if symbol.endswith('/USDT') and data.get('quoteVolume') and data.get('percentage'):
                            tv_symbol = symbol.replace("/", "")
                            tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCEUS:{tv_symbol}"
                            
                            market_data.append({
                                'Symbol': symbol,
                                'Price': data['last'],
                                '24h Change (%)': data['percentage'],
                                '24h Volume': data['quoteVolume'],
                                'ดูกราฟ (Chart)': tv_link
                            })
                    df_market = pd.DataFrame(market_data)
                    filtered_df = df_market[(df_market['24h Volume'] >= min_vol_usdt) & (df_market['24h Change (%)'] >= price_change_min)].copy()
                    filtered_df = filtered_df.sort_values(by='24h Change (%)', ascending=False).reset_index(drop=True)
                    
                    styled_df = filtered_df.copy()
                    styled_df['Price'] = styled_df['Price'].apply(lambda x: f"${x:,.4f}")
                    styled_df['24h Change (%)'] = styled_df['24h Change (%)'].apply(lambda x: f"🔥 +{x:.2f}%" if x > 0 else f"{x:.2f}%")
                    styled_df['24h Volume'] = styled_df['24h Volume'].apply(lambda x: f"${x:,.0f}")
                    
                    st.success(f"✅ เจอเหรียญทะลุกรอบกระดานทั้งหมด {len(filtered_df)} ตัว")
                    
                    # แสดงผลแบบมี LinkColumn 
                    st.dataframe(
                        styled_df, 
                        use_container_width=True,
                        column_config={
                            "ดูกราฟ (Chart)": st.column_config.LinkColumn("ดูกราฟ (Chart)", display_text="📈 เปิด TradingView")
                        }
                    )
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
