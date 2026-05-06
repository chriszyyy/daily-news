import json, math

def sma(data, n):
    return [sum(data[i-n:i])/n if i>=n else None for i in range(len(data))]

def ema(data, n):
    k = 2/(n+1)
    result = [None]*(n-1)
    result.append(sum(data[:n])/n)
    for i in range(n, len(data)):
        result.append(data[i]*k + result[-1]*(1-k))
    return result

def rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d,0))
        losses.append(max(-d,0))
    ag = sum(gains[:period])/period
    al = sum(losses[:period])/period
    rs_list = []
    for i in range(period, len(gains)):
        ag = (ag*(period-1)+gains[i])/period
        al = (al*(period-1)+losses[i])/period
        rs = ag/al if al!=0 else 100
        rs_list.append(100 - 100/(1+rs))
    return rs_list

def macd_calc(closes, fast=12, slow=26, signal=9):
    e12 = ema(closes, fast)
    e26 = ema(closes, slow)
    dif = [e12[i]-e26[i] if e12[i] is not None and e26[i] is not None else None for i in range(len(closes))]
    dif_clean = [d for d in dif if d is not None]
    dea_raw = ema(dif_clean, signal)
    start = next(i for i,d in enumerate(dif) if d is not None)
    dea = [None]*start + dea_raw
    hist = [dif[i]-dea[i] if dif[i] is not None and dea[i] is not None else None for i in range(len(closes))]
    return dif, dea, hist

def bollinger(closes, n=20, k=2):
    mas = sma(closes, n)
    pct_b = []
    for i in range(len(closes)):
        if mas[i] is None:
            pct_b.append(None)
        else:
            std = math.sqrt(sum((closes[j]-mas[i])**2 for j in range(i-n+1,i+1))/n)
            upper = mas[i] + k*std
            lower = mas[i] - k*std
            bw = upper - lower
            pb = (closes[i]-lower)/bw if bw!=0 else 0.5
            pct_b.append(pb)
    return mas, pct_b

def analyze(name, ticker, closes, entry_note=""):
    ma20_all = sma(closes, 20)
    ma60_all = sma(closes, 60)
    ma20 = next((v for v in reversed(ma20_all) if v is not None), None)
    ma60 = next((v for v in reversed(ma60_all) if v is not None), None)
    rsi_vals = rsi(closes, 14)
    rsi_cur = rsi_vals[-1] if rsi_vals else None
    dif_all, dea_all, hist_all = macd_calc(closes)
    dif_cur = next((v for v in reversed(dif_all) if v is not None), None)
    dea_cur = next((v for v in reversed(dea_all) if v is not None), None)
    hist_clean = [v for v in hist_all if v is not None]
    cross = "金叉(DIF>DEA)" if dif_cur > dea_cur else "死叉(DIF<DEA)"
    momentum = "柱状体收窄" if len(hist_clean)>=2 and abs(hist_clean[-1]) < abs(hist_clean[-2]) else "柱状体扩大"
    _, pct_b_all = bollinger(closes, 20)
    pb_cur = next((v for v in reversed(pct_b_all) if v is not None), None)
    cur = closes[-1]

    if rsi_cur > 70:
        rsi_status = "超买"
    elif rsi_cur < 30:
        rsi_status = "超卖"
    else:
        rsi_status = "中性"

    if pb_cur > 1:
        bb_status = "超买区"
    elif pb_cur < 0:
        bb_status = "超卖区"
    elif pb_cur > 0.6:
        bb_status = "偏上轨"
    elif pb_cur < 0.4:
        bb_status = "偏下轨"
    else:
        bb_status = "中轨附近"

    print(f"\n{'='*58}")
    print(f"  {name} ({ticker})")
    print(f"{'='*58}")
    print(f"  最新收盘价  ¥{cur:.2f}")
    print(f"  MA20        ¥{ma20:.2f}  价格{'高于' if cur>ma20 else '低于'}MA20")
    print(f"  MA60        ¥{ma60:.2f}  价格{'高于' if ma60 and cur>ma60 else '低于'}MA60")
    print(f"  MA20 vs MA60  {'金叉(MA20>MA60)' if ma20>ma60 else '死叉(MA20<MA60)'}")
    print(f"  RSI14       {rsi_cur:.1f}  [{rsi_status}]")
    print(f"  MACD DIF    {dif_cur:.4f}  DEA {dea_cur:.4f}")
    print(f"  MACD方向    {cross}，{momentum}")
    print(f"  BB %B       {pb_cur:.3f}  [{bb_status}]")
    if entry_note:
        print(f"  备注        {entry_note}")

# ---- Data ----
wol = [28.26,27.69,27.69,27.18,26.82,27.50,27.17,26.92,26.90,25.67,25.96,25.70,25.72,25.31,25.23,25.09,24.00,24.45,24.80,24.78,24.78,25.08,25.46,25.82,26.61,26.03,26.22,26.55,26.55,26.90,26.90,28.04,26.78,25.86,26.57,25.68,26.04,26.55,26.61,27.00,26.91,26.96,26.28,26.76,26.32,26.95,27.16,27.57,27.42,27.97,28.26,26.95,27.07,29.78,31.11,29.69,30.62,30.95,32.73,31.44,33.34,32.58,29.32,27.43,26.99,27.17,27.57,27.75,27.51,27.27,27.32,28.41,27.98,28.18,27.36,27.45,27.90,28.73,28.53,27.82,25.56,25.64,26.69,26.25,25.49,26.38,26.28,25.78,25.58,26.64,27.51,26.50,25.20,24.61,23.13,23.70,24.62,23.69,23.80,23.71,23.47,23.85,23.18,22.89,23.00,24.43,24.30,24.63,25.13,25.64,25.20,25.57,25.62,26.20,26.00,26.27,26.06,23.62,23.70,22.86,22.90,22.74]
tj  = [8.97,8.67,9.54,9.34,9.51,9.88,9.70,9.93,9.48,9.73,9.61,9.04,8.80,8.73,8.27,8.15,7.62,7.71,7.90,7.79,7.93,7.99,8.14,7.98,7.84,7.81,7.90,8.01,7.84,7.81,7.66,7.80,7.67,7.44,7.55,7.66,7.65,7.77,8.12,8.34,8.18,8.09,8.04,8.03,7.97,8.30,8.58,8.56,8.48,8.42,8.55,8.34,8.28,8.60,9.30,9.42,9.64,9.88,9.64,9.67,9.28,9.85,10.26,10.20,11.22,10.10,10.16,9.85,9.50,9.27,9.88,9.66,9.44,9.67,9.79,10.76,10.80,11.29,11.08,10.70,9.78,9.92,10.32,10.18,9.92,10.71,10.61,10.36,10.24,11.26,11.59,11.66,11.23,10.68,9.97,10.24,10.48,9.77,9.81,9.72,8.94,9.17,8.80,8.56,8.81,9.49,9.63,9.52,9.61,10.19,9.85,9.98,9.95,10.02,9.99,10.24,9.90,9.71,9.88,9.51,9.63,9.59]
cd  = [41.60,40.02,39.45,39.82,38.88,39.69,38.92,39.19,38.52,37.69,38.24,37.05,37.08,37.17,36.59,36.12,34.85,35.05,35.51,35.80,35.75,35.91,37.10,36.46,36.61,36.99,36.74,37.28,36.90,37.19,36.41,36.82,36.04,35.38,35.93,35.67,35.76,36.79,36.63,37.12,37.13,36.80,36.62,37.10,36.78,38.36,38.44,39.08,38.98,41.18,43.68,42.20,41.98,43.99,48.39,48.83,49.49,52.61,49.40,49.02,47.31,48.20,50.05,48.98,49.48,46.34,47.69,45.87,44.66,44.06,46.76,46.24,46.19,46.63,46.13,46.74,46.92,48.72,48.16,46.77,47.57,47.86,48.70,47.04,45.00,46.00,46.81,45.73,45.48,45.75,43.75,45.77,44.19,42.03,39.08,39.45,40.64,39.43,39.53,39.84,38.75,39.49,38.48,38.29,38.82,41.98,41.91,43.02,42.85,44.34,43.59,43.73,43.98,44.49,44.03,45.51,44.41,44.89,46.32,45.10,44.36,45.56]

analyze("沃尔核材", "002130.SZ", wol, "计划5/6入场¥22.74，目标¥30，止损¥18")
analyze("太极实业", "600667.SS", tj, "观察MA20突破，当前~¥9.59")
analyze("长电科技", "600584.SS", cd, "关注清单，当前~¥45.56")
