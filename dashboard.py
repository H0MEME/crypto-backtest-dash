import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import ccxt
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Crypto All-in-One Platform", layout="wide")

# --- ดึงข้อมูลรายชื่อเหรียญ (ใช้ Binance.US เพื่อรองรับ Streamlit Cloud) ---
@st.cache_data(ttl=86400)
def get_crypto_usdt_pairs():
    exchange = ccxt.binanceus({'enableRateLimit': True}) 
    retries = 3
    for attempt in range(retries):
        try:
            markets = exchange.load_markets()
            return sorted([symbol for symbol, market in markets.items() if symbol.endswith('/USDT') and market.get('active', True)])
        except Exception as e:
            if attempt == retries - 1:
                return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT']
            time.sleep(2)

usdt_pairs = get_crypto_usdt_pairs()

# ==========================================
# 📌 สร้างเมนูหลักด้านข้าง (Sidebar Navigation)
# ==========================================
st.sidebar.title("🧭 เมนูใช้งานหลัก")
app_mode = st.sidebar.radio("เลือกฟังก์ชันการทำงาน:", 
                            ["📊 ระบบทดสอบ (Backtester)", "🚀 เรดาร์หาเหรียญ (Screener)"])
st.sidebar.markdown("---")

# ==========================================
# โหมดที่ 1: BACKTESTER (ระบบทดสอบกลยุทธ์)
# ==========================================
if app_mode == "📊 ระบบทดสอบ (Backtester)":
    st.title("📊 ระบบทดสอบกลยุทธ์เทรด (Interactive Table)")
    
    strategy_info = {
        "Ichimoku Breakout (Trend 4H)": {"desc": "ระบบกินคำใหญ่ (RR 1:3) ทะลุเมฆ Ichimoku กรองเทรนด์ด้วย EMA200 และความแรงเทรนด์ด้วย ADX > 25", "source": "YouTube: ORC Crypto", "link": "https://youtu.be/DM2Uh6n6e0g"},
        "SMC + Session Liquidity Sweep (ICT)": {"desc": "รอตลาดยุโรป/อเมริกาเปิด (15:00-04:00) -> กวาด Liquidity -> เบรคโครงสร้าง (MSS) ทิ้ง FVG -> เข้าทันที", "source": "YouTube: ORC Crypto", "link": "https://youtu.be/CUB7DRHKPsA"},
        "ATR Fibonacci Pocket (Pullback)": {"desc": "จับเทรนด์ด้วย WMA(100) และหาจังหวะย่อตัว (Pullback) เข้าสู่โซน Pocket (ATR+Fibo) เข้าเทรดเมื่อเบรค BOS", "source": "YouTube: ORC Crypto", "link": "https://youtu.be/bjjqlIAl7ec"},
        "Breakout + Volume Filter": {"desc": "เทรดตามเทรนด์ด้วย Bollinger Bands และใช้ Volume กรองสัญญาณหลอก", "source": "YouTube: ORC Crypto", "link": "https://youtu.be/Nie3xloSN6A"},
        "SMC (Smart Money Concepts)": {"desc": "เทรดแกะรอยเจ้าตลาด หาจังหวะเบรคโครงสร้าง (MSS) และตั้งรับที่ช่องว่างราคา (FVG)", "source": "YouTube: ORC Crypto", "link": "https://youtu.be/HT8wEj1hLsQ"},
        "EMA Crossover (Classic)": {"desc": "ระบบเทรดพื้นฐาน ตัดขึ้นซื้อ ตัดลงขาย (ใช้ EMA 12 ตัด EMA 26)", "source": "Investopedia", "link": "#"}
    }

    st.sidebar.header("⚙️ ตั้งค่าระบบเทรด")
    strategy_choice = st.sidebar.selectbox("🎯 เลือกกลยุทธ์เทรด", list(strategy_info.keys()))

    default_index = usdt_pairs.index('BTC/USDT') if 'BTC/USDT' in usdt_pairs else 0
    symbol = st.sidebar.selectbox("🔍 ค้นหาคู่เหรียญ (พิมพ์ชื่อได้เลย)", usdt_pairs, index=default_index)

    if "Ichimoku" in strategy_choice: default_tf, default_yr = 2, 2
    elif "SMC" in strategy_choice: default_tf, default_yr = 0, 0
    elif strategy_choice == "ATR Fibonacci Pocket (Pullback)": default_tf, default_yr = 1, 1
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

    st.info(f"💡 **หลักการทำงาน:** {strategy_info[strategy_choice]['desc']}\n\n"
            f"🔗 **แหล่งอ้างอิงคลิป/บทความ:** [{strategy_info[strategy_choice]['source']}]({strategy_info[strategy_choice]['link']})")

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
                current_date = datetime.fromtimestamp(since/1000)
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
                    pnl_this_exit = (remaining_size * 0.5) * (partial_tp_price - entry_price)
                    trade_pnl += pnl_this_exit
                    capital += pnl_this_exit
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
                    pnl_this_exit = (remaining_size * 0.5) * (entry_price - partial_tp_price)
                    trade_pnl += pnl_this_exit
                    capital += pnl_this_exit
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
                hour = row['timestamp'].hour
                if (hour >= 15) or (hour <= 4):
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
                    
            elif strategy_choice == "SMC (Smart Money Concepts)":
                if row['close'] > last_swing_high and (df['fvg_bullish'].iloc[i] or df['fvg_bullish'].iloc[i-1]):
                    fvg_top_price, proposed_sl = df['high'].iloc[i-2], last_swing_low
                    if 0 < (fvg_top_price - proposed_sl) / fvg_top_price < 0.05: 
                        entry_price, sl_price = fvg_top_price, proposed_sl
                        position_size = (capital * (risk_per_trade / 100)) / (entry_price - sl_price)
                        pending_order, position_type, order_timeout = True, 'LONG', 10 
                        
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
        
        if 'selectbox_idx' not in st.session_state: st.session_state.selectbox_idx = 0
        if 'last_clicked_row' not in st.session_state: st.session_state.last_clicked_row = None

        selection_event = st.dataframe(df_show, use_container_width=True, on_select="rerun", selection_mode="single-row")
        
        if selection_event.selection.rows:
            clicked_row = selection_event.selection.rows[0]
            if st.session_state.last_clicked_row != clicked_row:
                st.session_state.selectbox_idx = clicked_row
                st.session_state.last_clicked_row = clicked_row
        else:
            st.session_state.last_clicked_row = None
            
        st.divider()
        st.subheader("🔎 เจาะลึกกราฟแต่ละไม้เทรด (Trade Visualizer)")
        trade_options = [f"ไม้ที่ {i+1} : {'🟢' if t['pnl']>0 else ('🔴' if t['pnl']<0 else '⚪')} {t['type']} | PnL: ${t['pnl']:.2f} | วันที่: {t['entry_date'].strftime('%d %b %Y')}" for i, t in enumerate(trade_history)]
        
        if st.session_state.selectbox_idx >= trades: st.session_state.selectbox_idx = 0
            
        selected_idx = st.selectbox("🎯 เลื่อนเพื่อดูไม้เทรดที่ต้องการ:", range(trades), format_func=lambda i: trade_options[i], key="selectbox_idx")
        t_data = trade_history[selected_idx]
        idx_start = df.index[df['timestamp'] == t_data['entry_date']].tolist()[0]
        idx_end = df.index[df['timestamp'] == t_data['exit_date']].tolist()[0]
        plot_start, plot_end = max(0, idx_start - 30), min(len(df) - 1, idx_end + 30)
        df_plot = df.iloc[plot_start:plot_end+1]
        
        fig2 = go.Figure(data=[go.Candlestick(x=df_plot['timestamp'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name='Candles')])
        fig2.add_trace(go.Scatter(x=[t_data['entry_date']], y=[t_data['entry_price']], mode='markers', marker=dict(size=14, color='cyan', symbol='star'), name='🌟 จุดเข้า'))
        fig2.add_trace(go.Scatter(x=[t_data['exit_date']], y=[t_data['exit_price']], mode='markers', marker=dict(size=14, color='magenta', symbol='x'), name='❌ จุดออก'))
        fig2.add_shape(type="line", x0=df_plot['timestamp'].iloc[0], y0=t_data['initial_sl'], x1=df_plot['timestamp'].iloc[-1], y1=t_data['initial_sl'], line=dict(color="red", width=2, dash="dash"))
        fig2.add_shape(type="line", x0=df_plot['timestamp'].iloc[0], y0=t_data['entry_price'], x1=df_plot['timestamp'].iloc[-1], y1=t_data['entry_price'], line=dict(color="cyan", width=1, dash="dot"))
        fig2.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, title=f"วิเคราะห์ไม้เทรดที่ {selected_idx+1}")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("ไม่พบสัญญาณการเข้าเทรด กรุณาปรับเงื่อนไขให้ผ่อนคลายขึ้น")


# ==========================================
# โหมดที่ 2: SCREENER (สแกนหาเหรียญน่าเทรด)
# ==========================================
elif app_mode == "🚀 เรดาร์หาเหรียญ (Screener)":
    st.title("🚀 เรดาร์หาเหรียญ (Breakout + Volume Screener)")
    st.write("สแกนหาเหรียญที่ราคากำลังทำ New High ยืนเหนือ EMA200 พร้อมวอลุ่มซื้อที่พุ่งสูงกว่าปกติ (ตามระบบ Breakout + Volume Filter)")
    
    st.sidebar.header("⚙️ ตั้งค่า Screener")
    tf_screen = st.sidebar.selectbox("Timeframe (กราฟ)", ['15m', '1h', '4h', '1d'], index=1)
    vol_multiplier = st.sidebar.slider("วอลุ่มต้องพุ่งสูงกว่าค่าเฉลี่ยกี่เท่า?", 1.1, 5.0, 1.5)
    
    # เลือกเหรียญที่จะสแกน (ดึงรายชื่อเหรียญยอดฮิตมาเป็นค่าตั้งต้น)
    default_scan_list = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT']
    selected_symbols = st.multiselect("เลือกเหรียญที่ต้องการให้เรดาร์กวาดหาสัญญาณ:", usdt_pairs, default=[s for s in default_scan_list if s in usdt_pairs])
    
    if st.button("🔍 เริ่มการสแกนเรดาร์ (Scan Now)", type="primary"):
        if not selected_symbols:
            st.error("กรุณาเลือกเหรียญอย่างน้อย 1 ตัวครับ")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            exchange = ccxt.binanceus({'enableRateLimit': True})
            
            # ต้องดึงข้อมูลย้อนหลังอย่างน้อย 250 แท่ง เพื่อให้คำนวณ EMA200 ได้
            for i, sym in enumerate(selected_symbols):
                status_text.text(f"⏳ กำลังสแกน {sym}... ({i+1}/{len(selected_symbols)})")
                try:
                    ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf_screen, limit=250)
                    if len(ohlcv) >= 200:
                        df_scan = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        # คำนวณ Indicator เหมือนระบบ Breakout + Volume Filter เป๊ะๆ
                        df_scan['ema_200'] = df_scan['close'].ewm(span=200, adjust=False).mean()
                        df_scan['sma_20'] = df_scan['close'].rolling(window=20).mean()
                        df_scan['std_20'] = df_scan['close'].rolling(window=20).std()
                        df_scan['upper_bb'] = df_scan['sma_20'] + (df_scan['std_20'] * 2)
                        df_scan['vol_ma_20'] = df_scan['volume'].rolling(window=20).mean()
                        
                        latest = df_scan.iloc[-1]
                        
                        # เงื่อนไข: ยืนเหนือ EMA200 + ทะลุขอบบน Bollinger + วอลุ่มต้องมากกว่าค่าเฉลี่ย x เท่า
                        is_breakout = (latest['close'] > latest['ema_200']) and (latest['close'] > latest['upper_bb'])
                        is_vol_surge = latest['volume'] > (latest['vol_ma_20'] * vol_multiplier)
                        
                        if is_breakout and is_vol_surge:
                            results.append({
                                'เหรียญ (Symbol)': sym,
                                'ราคาล่าสุด': f"${latest['close']:.4f}",
                                'เส้น EMA 200': f"${latest['ema_200']:.4f}",
                                'ขอบบน BB': f"${latest['upper_bb']:.4f}",
                                'ระดับความแรงวอลุ่ม': f"🔥 {latest['volume'] / latest['vol_ma_20']:.2f} เท่า"
                            })
                except Exception:
                    pass 
                
                progress_bar.progress((i + 1) / len(selected_symbols))
                time.sleep(0.2) 
            
            status_text.empty()
            progress_bar.empty()
            
            if results:
                st.success(f"🎉 สแกนเสร็จสิ้น! พบเหรียญที่มีสัญญาณ 'กระทิงดุ' (Bullish Breakout) จำนวน {len(results)} ตัว")
                res_df = pd.DataFrame(results)
                st.dataframe(res_df, use_container_width=True)
                st.info("💡 นำเหรียญเหล่านี้ไปเปิดในโหมด Backtest เพื่อดูประวัติการทำกำไรย้อนหลังต่อได้เลยครับ!")
            else:
                st.warning("😅 สแกนเสร็จสิ้น แต่ช่วงเวลานี้ตลาดยังนิ่งอยู่ ไม่มีเหรียญไหนระเบิดกรอบขึ้นมาเลยครับ (ลองเปลี่ยน Timeframe ให้สั้นลงดูครับ)")
