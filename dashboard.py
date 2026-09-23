import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import ccxt
import time
from datetime import datetime, timedelta

# 1. ตั้งค่าหน้าเพจ Dashboard
st.set_page_config(page_title="Crypto Strategy Backtester", layout="wide")
st.title("📊 ศูนย์รวมระบบทดสอบกลยุทธ์เทรด (Advanced Trade Management)")

# --- ฐานข้อมูลกลยุทธ์และแหล่งที่มา ---
strategy_info = {
    "Ichimoku Breakout (Trend 4H)": {
        "desc": "ระบบกินคำใหญ่ (RR 1:3) ทะลุเมฆ Ichimoku กรองเทรนด์ด้วย EMA200 และความแรงเทรนด์ด้วย ADX > 25",
        "source": "YouTube: ORC Crypto",
        "link": "https://youtu.be/DM2Uh6n6e0g"
    },
    "SMC + Session Liquidity Sweep (ICT)": {
        "desc": "รอตลาดยุโรป/อเมริกาเปิด (15:00-04:00) -> กวาด Liquidity -> เบรคโครงสร้าง (MSS) ทิ้ง FVG -> เข้าทันที",
        "source": "YouTube: ORC Crypto",
        "link": "https://youtu.be/CUB7DRHKPsA"
    },
    "ATR Fibonacci Pocket (Pullback)": {
        "desc": "จับเทรนด์ด้วย WMA(100) และหาจังหวะย่อตัว (Pullback) เข้าสู่โซน Pocket (ATR+Fibo) เข้าเทรดเมื่อเบรค BOS",
        "source": "YouTube: ORC Crypto",
        "link": "https://youtu.be/bjjqlIAl7ec"
    },
    "Breakout + Volume Filter": {
        "desc": "เทรดตามเทรนด์ด้วย Bollinger Bands และใช้ Volume กรองสัญญาณหลอก",
        "source": "YouTube: ORC Crypto",
        "link": "https://youtu.be/Nie3xloSN6A"
    },
    "SMC (Smart Money Concepts)": {
        "desc": "เทรดแกะรอยเจ้าตลาด หาจังหวะเบรคโครงสร้าง (MSS) และตั้งรับที่ช่องว่างราคา (FVG)",
        "source": "YouTube: ORC Crypto",
        "link": "https://youtu.be/HT8wEj1hLsQ"
    },
    "EMA Crossover (Classic)": {
        "desc": "ระบบเทรดพื้นฐาน ตัดขึ้นซื้อ ตัดลงขาย (ใช้ EMA 12 ตัด EMA 26)",
        "source": "Investopedia (ความรู้พื้นฐาน)",
        "link": "https://www.investopedia.com/terms/m/movingaverage.asp"
    }
}

# --- ฟังก์ชันดึงรายชื่อเหรียญ ---
@st.cache_data(ttl=86400)
def get_binance_usdt_pairs():
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    return sorted([symbol for symbol, market in markets.items() if symbol.endswith('/USDT') and market.get('active', True)])

usdt_pairs = get_binance_usdt_pairs()

# 2. แถบตั้งค่าด้านข้าง (Sidebar)
st.sidebar.header("⚙️ ตั้งค่าระบบเทรด")
strategy_choice = st.sidebar.selectbox("🎯 เลือกกลยุทธ์เทรด", list(strategy_info.keys()))

st.sidebar.markdown("---")
default_index = usdt_pairs.index('BTC/USDT') if 'BTC/USDT' in usdt_pairs else 0
symbol = st.sidebar.selectbox("🔍 ค้นหาคู่เหรียญ (พิมพ์ชื่อได้เลย)", usdt_pairs, index=default_index)

# แนะนำ Timeframe ให้อัตโนมัติตามกลยุทธ์
if "Ichimoku" in strategy_choice:
    default_tf, default_yr = 2, 2 # แนะนำ 4h, 2 ปี
elif "SMC" in strategy_choice:
    default_tf, default_yr = 0, 0 # 15m, 6 เดือน
elif strategy_choice == "ATR Fibonacci Pocket (Pullback)":
    default_tf, default_yr = 1, 1 # 1h, 1 ปี
else:
    default_tf, default_yr = 1, 2 # 1h, 2 ปี

timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=default_tf)
years_back = st.sidebar.selectbox("ระยะเวลาย้อนหลัง", ["6 เดือน", "1 ปี", "2 ปี", "3 ปี", "4 ปี"], index=default_yr)
days_back = {"6 เดือน": 180, "1 ปี": 365, "2 ปี": 730, "3 ปี": 1095, "4 ปี": 1460}[years_back]

st.sidebar.markdown("---")
st.sidebar.subheader("💰 การจัดการเงิน (Money Management)")
initial_capital = st.sidebar.number_input("ทุนเริ่มต้น ($)", min_value=10.0, value=5000.0, step=100.0)
risk_per_trade = st.sidebar.slider("ความเสี่ยงเมื่อขาดทุน (%)", 1.0, 10.0, 3.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ การจัดการออเดอร์ (Trade Management)")
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

# 4. ฟังก์ชันดึงข้อมูลย้อนหลัง
@st.cache_data(ttl=3600, show_spinner=False)
def load_historical_data(sym, tf, days):
    exchange = ccxt.binance()
    start_time = datetime.now() - timedelta(days=days)
    since = int(start_time.timestamp() * 1000)
    all_bars = []
    
    while True:
        try:
            bars = exchange.fetch_ohlcv(sym, timeframe=tf, since=since, limit=1000)
            if not bars: break
            all_bars.extend(bars)
            since = bars[-1][0] + 1 
            if len(bars) < 1000: break
            time.sleep(0.1)
        except Exception:
            break
            
    if not all_bars: return pd.DataFrame()
    df = pd.DataFrame(all_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=7) 
    df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
    return df

with st.spinner(f'⏳ กำลังโหลดข้อมูล {symbol}...'):
    df = load_historical_data(symbol, timeframe, days_back)

if df.empty:
    st.error("ไม่พบข้อมูล กรุณาลองเปลี่ยนเหรียญหรือลดเวลาลง")
    st.stop()

# 5. คำนวณ Indicator (ครอบคลุมทุกระบบ)
df['tr0'] = abs(df['high'] - df['low'])
df['tr1'] = abs(df['high'] - df['close'].shift())
df['tr2'] = abs(df['low'] - df['close'].shift())
df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
df['atr_14'] = df['tr'].ewm(alpha=1/14, adjust=False).mean()

if strategy_choice == "Ichimoku Breakout (Trend 4H)":
    # คำนวณ Ichimoku Cloud (9, 26, 52)
    df['tenkan'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2
    df['kijun'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
    df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift(26)
    df['senkou_b'] = ((df['high'].rolling(window=52).max() + df['low'].rolling(window=52).min()) / 2).shift(26)
    
    # คำนวณ EMA 200
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # คำนวณ ADX (14)
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

# 6. ลอจิก Backtest 
capital = initial_capital
in_position = False
position_type = None
entry_price, sl_price, position_size = 0, 0, 0

remaining_size, trade_pnl = 0, 0.0
is_partial, is_breakeven = False, False
be_trigger_price, partial_tp_price, final_tp_price = 0, 0, 0

pending_order, order_timeout = False, 0
last_swing_low, last_swing_high = 0, float('inf')
pullback_long, pullback_short = False, False
bos_high, bos_low, sl_point = 0, float('inf'), 0

equity_curve = [initial_capital]
trade_history = []

for i in range(10, len(df)):
    row = df.iloc[i]
    just_entered = False
    
    if "SMC" in strategy_choice:
        if df['swing_low'].iloc[i-3]: last_swing_low = df['low'].iloc[i-3]
        if df['swing_high'].iloc[i-3]: last_swing_high = df['high'].iloc[i-3]

    if in_position:
        if position_type == 'LONG':
            if row['low'] <= sl_price:
                pnl_this_exit = remaining_size * (sl_price - entry_price)
                trade_pnl += pnl_this_exit
                capital += pnl_this_exit
                equity_curve.append(capital)
                res_str = 'ชนะ (Win)' if trade_pnl > 0 else ('เสมอ (Breakeven)' if trade_pnl == 0 else 'แพ้ (Loss)')
                trade_history.append({'date': row['timestamp'], 'type': 'LONG', 'result': res_str, 'pnl': trade_pnl, 'balance': capital})
                in_position = False
                continue

            if enable_advanced_tm and not is_breakeven and row['high'] >= be_trigger_price:
                sl_price = entry_price 
                is_breakeven = True
            if enable_advanced_tm and not is_partial and row['high'] >= partial_tp_price:
                pnl_this_exit = (remaining_size * 0.5) * (partial_tp_price - entry_price)
                trade_pnl += pnl_this_exit
                capital += pnl_this_exit
                remaining_size *= 0.5 
                is_partial, is_breakeven, sl_price = True, True, max(sl_price, entry_price) 
            if row['high'] >= final_tp_price:
                pnl_this_exit = remaining_size * (final_tp_price - entry_price)
                trade_pnl += pnl_this_exit
                capital += pnl_this_exit
                equity_curve.append(capital)
                trade_history.append({'date': row['timestamp'], 'type': 'LONG', 'result': 'ชนะ (Win)', 'pnl': trade_pnl, 'balance': capital})
                in_position = False
                
        elif position_type == 'SHORT':
            if row['high'] >= sl_price:
                pnl_this_exit = remaining_size * (entry_price - sl_price)
                trade_pnl += pnl_this_exit
                capital += pnl_this_exit
                equity_curve.append(capital)
                res_str = 'ชนะ (Win)' if trade_pnl > 0 else ('เสมอ (Breakeven)' if trade_pnl == 0 else 'แพ้ (Loss)')
                trade_history.append({'date': row['timestamp'], 'type': 'SHORT', 'result': res_str, 'pnl': trade_pnl, 'balance': capital})
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
                pnl_this_exit = remaining_size * (entry_price - final_tp_price)
                trade_pnl += pnl_this_exit
                capital += pnl_this_exit
                equity_curve.append(capital)
                trade_history.append({'date': row['timestamp'], 'type': 'SHORT', 'result': 'ชนะ (Win)', 'pnl': trade_pnl, 'balance': capital})
                in_position = False
        continue

    if pending_order:
        order_timeout -= 1
        if row['low'] <= entry_price and position_type == 'LONG':
            in_position, pending_order, just_entered = True, False, True
        elif order_timeout <= 0 or row['close'] < sl_price:
            pending_order = False

    # --- การหาจุดเข้า (Entry Logic) ---
    if not in_position and not pending_order:
        
        # ระบบใหม่ที่ 6: Ichimoku Breakout
        if strategy_choice == "Ichimoku Breakout (Trend 4H)":
            is_adx_strong = row['adx'] > 25
            
            # Setup Long: ทะลุเมฆบน + น้ำเงินตัดแดงขึ้น + ยืนเหนือ EMA200 + เทรนด์ ADX แข็ง
            cloud_top = max(row['senkou_a'], row['senkou_b'])
            if row['close'] > cloud_top and row['tenkan'] > row['kijun'] and row['close'] > row['ema_200'] and is_adx_strong:
                entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                risk_amount = capital * (risk_per_trade / 100)
                position_size = risk_amount / (entry_price - sl_price)
                in_position, position_type, just_entered = True, 'LONG', True
                
            # Setup Short: ทะลุเมฆล่าง + น้ำเงินตัดแดงลง + อยู่ใต้ EMA200 + เทรนด์ ADX แข็ง
            cloud_bottom = min(row['senkou_a'], row['senkou_b'])
            if row['close'] < cloud_bottom and row['tenkan'] < row['kijun'] and row['close'] < row['ema_200'] and is_adx_strong:
                entry_price, sl_price = row['close'], row['close'] + (row['atr_14'] * 2)
                risk_amount = capital * (risk_per_trade / 100)
                position_size = risk_amount / (sl_price - entry_price)
                in_position, position_type, just_entered = True, 'SHORT', True

        elif strategy_choice == "SMC + Session Liquidity Sweep (ICT)":
            hour = row['timestamp'].hour
            if (hour >= 15) or (hour <= 4):
                if row['low'] < last_swing_low and row['close'] > last_swing_high and (df['fvg_bullish'].iloc[i] or df['fvg_bullish'].iloc[i-1]):
                    entry_price, sl_price = row['close'], row['low']      
                    if entry_price > sl_price:
                        risk_amount = capital * (risk_per_trade / 100)
                        position_size = risk_amount / (entry_price - sl_price)
                        in_position, position_type, just_entered = True, 'LONG', True
                if row['high'] > last_swing_high and row['close'] < last_swing_low and (df['fvg_bearish'].iloc[i] or df['fvg_bearish'].iloc[i-1]):
                    entry_price, sl_price = row['close'], row['high']
                    if sl_price > entry_price:
                        risk_amount = capital * (risk_per_trade / 100)
                        position_size = risk_amount / (sl_price - entry_price)
                        in_position, position_type, just_entered = True, 'SHORT', True
                        
        elif strategy_choice == "ATR Fibonacci Pocket (Pullback)":
            trend = 1 if row['close'] > row['wma_100'] else -1
            if trend == 1:
                pocket_top = row['wma_100'] - (row['atr_100'] * 3 * 0.5)
                pocket_bottom = row['wma_100'] - (row['atr_100'] * 3 * 0.786)
                if row['low'] <= pocket_top and row['close'] > (row['wma_100'] - row['atr_100']*3):
                    if not pullback_long: pullback_long, bos_high, sl_point = True, df['high'].iloc[i-10:i].max(), row['low']
                    else: sl_point = min(sl_point, row['low'])
                if pullback_long and row['close'] > bos_high:
                    entry_price, sl_price = row['close'], sl_point - (row['atr_14'] * 0.5)
                    if entry_price > sl_price:
                        risk_amount = capital * (risk_per_trade / 100)
                        position_size = risk_amount / (entry_price - sl_price)
                        in_position, position_type, just_entered = True, 'LONG', True
                    pullback_long = False
                elif row['close'] < pocket_bottom: pullback_long = False
                    
            elif trend == -1:
                pocket_bottom = row['wma_100'] + (row['atr_100'] * 3 * 0.5)
                pocket_top = row['wma_100'] + (row['atr_100'] * 3 * 0.786)
                if row['high'] >= pocket_bottom and row['close'] < (row['wma_100'] + row['atr_100']*3):
                    if not pullback_short: pullback_short, bos_low, sl_point = True, df['low'].iloc[i-10:i].min(), row['high']
                    else: sl_point = max(sl_point, row['high'])
                if pullback_short and row['close'] < bos_low:
                    entry_price, sl_price = row['close'], sl_point + (row['atr_14'] * 0.5)
                    if sl_price > entry_price:
                        risk_amount = capital * (risk_per_trade / 100)
                        position_size = risk_amount / (sl_price - entry_price)
                        in_position, position_type, just_entered = True, 'SHORT', True
                    pullback_short = False
                elif row['close'] > pocket_top: pullback_short = False

        elif strategy_choice == "Breakout + Volume Filter":
            if row['close'] > row['ema_200'] and row['close'] > row['upper_bb'] and row['volume'] > row['vol_ma_20']:
                entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                risk_amount = capital * (risk_per_trade / 100)
                position_size = risk_amount / (entry_price - sl_price)
                in_position, position_type, just_entered = True, 'LONG', True
            elif row['close'] < row['ema_200'] and row['close'] < row['lower_bb'] and row['volume'] > row['vol_ma_20']:
                entry_price, sl_price = row['close'], row['close'] + (row['atr_14'] * 2)
                risk_amount = capital * (risk_per_trade / 100)
                position_size = risk_amount / (sl_price - entry_price)
                in_position, position_type, just_entered = True, 'SHORT', True
                
        elif strategy_choice == "SMC (Smart Money Concepts)":
            if row['close'] > last_swing_high and (df['fvg_bullish'].iloc[i] or df['fvg_bullish'].iloc[i-1]):
                fvg_top_price, proposed_sl = df['high'].iloc[i-2], last_swing_low
                if 0 < (fvg_top_price - proposed_sl) / fvg_top_price < 0.05: 
                    entry_price, sl_price = fvg_top_price, proposed_sl
                    risk_amount = capital * (risk_per_trade / 100)
                    position_size = risk_amount / (entry_price - sl_price)
                    pending_order, position_type, order_timeout = True, 'LONG', 10 
                    
        elif strategy_choice == "EMA Crossover (Classic)":
            if df['ema_12'].iloc[i-1] <= df['ema_26'].iloc[i-1] and row['ema_12'] > row['ema_26']:
                entry_price, sl_price = row['close'], row['close'] - (row['atr_14'] * 2)
                risk_amount = capital * (risk_per_trade / 100)
                position_size = risk_amount / (entry_price - sl_price)
                in_position, position_type, just_entered = True, 'LONG', True

    if just_entered:
        risk_distance = abs(entry_price - sl_price)
        remaining_size = position_size
        trade_pnl = 0.0
        is_partial, is_breakeven = False, False
        
        if enable_advanced_tm:
            be_trigger_price = entry_price + (risk_distance * be_rr) if position_type == 'LONG' else entry_price - (risk_distance * be_rr)
            partial_tp_price = entry_price + (risk_distance * partial_rr) if position_type == 'LONG' else entry_price - (risk_distance * partial_rr)
            final_tp_price = entry_price + (risk_distance * final_rr) if position_type == 'LONG' else entry_price - (risk_distance * final_rr)
        else:
            final_tp_price = entry_price + (risk_distance * standard_rr) if position_type == 'LONG' else entry_price - (risk_distance * standard_rr)
            partial_tp_price = final_tp_price
            be_trigger_price = float('inf') if position_type == 'LONG' else 0

# 7. สรุปผลลัพธ์
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

# 8. วาดกราฟการเติบโตของพอร์ต
st.subheader("📈 กราฟการเติบโตของพอร์ต (Equity Curve)")
fig = go.Figure()
fig.add_trace(go.Scatter(
    y=equity_curve, mode='lines', name='Capital ($)',
    line=dict(color='#00ff88', width=2), fill='tozeroy', fillcolor='rgba(0, 255, 136, 0.1)'
))
fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="จำนวนออเดอร์ที่ปิด (Trades)", yaxis_title="ยอดเงินในพอร์ต ($)", template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

# 9. ตารางแสดงประวัติการเทรด
st.subheader("📋 ประวัติการเข้าเทรด")
if trades > 0:
    df_history = pd.DataFrame(trade_history)
    df_history['date'] = df_history['date'].dt.strftime('%d/%m/%Y %H:%M')
    df_history['pnl'] = df_history['pnl'].apply(lambda x: f"{'+' if x>0 else ''}${x:,.2f}")
    df_history['balance'] = df_history['balance'].apply(lambda x: f"${x:,.2f}")
    df_history.columns = ['วัน/เวลาที่ออกออเดอร์', 'ฝั่งเทรด', 'ผลลัพธ์', 'กำไร/ขาดทุนสุทธิ', 'เงินคงเหลือ']
    st.dataframe(df_history, use_container_width=True)
else:
    st.warning("ไม่พบสัญญาณการเข้าเทรด กรุณาปรับเงื่อนไขให้ผ่อนคลายขึ้น")
    