# -*- coding: utf-8 -*-
"""
Upper Limit Stock Screener for Korean Market (KOSPI/KOSDAQ)
Run: streamlit run upper_limit_screener.py
"""

import ssl
import urllib3
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
    from requests.adapters import HTTPAdapter
    _old_merge = requests.Session.merge_environment_settings
    def _merge_no_verify(self, url, proxies, stream, verify, cert):
        s = _old_merge(self, url, proxies, stream, verify, cert)
        s['verify'] = False
        return s
    requests.Session.merge_environment_settings = _merge_no_verify
except Exception:
    pass

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

try:
    from pykrx import stock as pykrx_stock
except ImportError:
    st.error("pykrx not installed: pip install pykrx")
    st.stop()

# ================================================================
# PAGE CONFIG & CSS
# ================================================================
st.set_page_config(
    page_title="Upper Limit Screener",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a;
    color: #e2e8f0;
    font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
}
[data-testid="stSidebar"] {
    background: #0f1527;
    border-right: 1px solid #1e2a45;
}
.main-title {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #f97316, #ef4444, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.sub-title {
    color: #64748b;
    font-size: 0.85rem;
    margin-top: 0.2rem;
    margin-bottom: 1.5rem;
}
.metric-card {
    background: #111827;
    border: 1px solid #1e2a45;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.5rem;
}
.metric-label { color: #64748b; font-size: 0.75rem; }
.metric-value { color: #f1f5f9; font-size: 1.4rem; font-weight: 700; }
.metric-up { color: #f87171; }
.metric-dn { color: #60a5fa; }
.ai-box {
    background: linear-gradient(135deg, #0f172a, #1a1040);
    border: 1px solid #7c3aed44;
    border-radius: 12px;
    padding: 1rem 1.3rem;
    margin-top: 0.8rem;
    font-size: 0.88rem;
    line-height: 1.7;
    color: #c4b5fd;
}
.ai-box strong { color: #a78bfa; }
.warn-box {
    background: #1c1008;
    border: 1px solid #92400e;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    color: #fbbf24;
    font-size: 0.8rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ================================================================
# DATE HELPERS
# ================================================================

def get_trading_date(offset=0):
    today = datetime.now()
    if today.hour < 15 or (today.hour == 15 and today.minute < 30):
        today -= timedelta(days=1)
    date = today + timedelta(days=offset)
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")


def business_days_ago(n):
    base = datetime.strptime(get_trading_date(), "%Y%m%d")
    count = 0
    cur = base
    while count < n:
        cur -= timedelta(days=1)
        if cur.weekday() < 5:
            count += 1
    return cur.strftime("%Y%m%d")

# ================================================================
# DATA FETCHING
# ================================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_market_tickers(market="ALL"):
    date = get_trading_date()
    dfs = []
    markets = ["KOSPI", "KOSDAQ"] if market == "ALL" else [market]
    for mkt in markets:
        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date, market=mkt)
            
            # 컬럼명 자동 정규화 (버전별 차이 대응)
            col_list = list(df.columns)
            rename_map = {}
            keywords = {
                "시가": "시가", "고가": "고가", "저가": "저가",
                "종가": "종가", "거래량": "거래량",
            }
            for col in col_list:
                for kw, target in keywords.items():
                    if kw in col:
                        rename_map[col] = target
            df.rename(columns=rename_map, inplace=True)

            # 시가총액/거래대금 별도 수집
            cap_df = pykrx_stock.get_market_cap_by_ticker(date, market=mkt)
            
            # 거래대금 컬럼 찾기
            td_col = None
            for c in cap_df.columns:
                if "거래대금" in c:
                    td_col = c
                    break
            cap_col = None
            for c in cap_df.columns:
                if "시가총액" in c:
                    cap_col = c
                    break

            if td_col and cap_col:
                df = df.join(cap_df[[cap_col, td_col]], how="left")
                df.rename(columns={cap_col: "시가총액", td_col: "거래대금"}, inplace=True)
            elif cap_col:
                df = df.join(cap_df[[cap_col]], how="left")
                df.rename(columns={cap_col: "시가총액"}, inplace=True)
                df["거래대금"] = 0

            # 필수 컬럼 없으면 0으로 채움
            for col in ["시가", "고가", "저가", "종가", "거래량", "시가총액", "거래대금"]:
                if col not in df.columns:
                    df[col] = 0

            df["시장"] = mkt
            names_fn = pykrx_stock.get_market_ticker_name
            df["종목명"] = [names_fn(t) for t in df.index]
            dfs.append(df)

        except Exception as e:
            st.warning(f"{mkt} data fetch failed: {e}")

    if not dfs:
        return pd.DataFrame()

    result = pd.concat(dfs)
    result.index.name = "티커"
    result.reset_index(inplace=True)
    return result

@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv_history(ticker, days=70):
    end = get_trading_date()
    start = business_days_ago(days + 10)
    try:
        df = pykrx_stock.get_market_ohlcv_by_date(start, end, ticker)
        df.index = pd.to_datetime(df.index)
        df.columns = ["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률"]
        return df.tail(days)
    except Exception:
        return pd.DataFrame()

# ================================================================
# TECHNICAL INDICATORS
# ================================================================

def compute_indicators(df):
    df = df.copy()
    for w in [5, 20, 60, 120, 240]:
        df[f"MA{w}"] = df["종가"].rolling(w).mean()
    df["BB_mid"]   = df["종가"].rolling(20).mean()
    df["BB_std"]   = df["종가"].rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * df["BB_std"]
    df["BB_lower"] = df["BB_mid"] - 2 * df["BB_std"]
    df["Vol_MA20"] = df["거래량"].rolling(20).mean()
    df["Vol_MAX60"]= df["거래량"].rolling(60).max()
    return df


def get_vwap_support(df, window=20):
    recent = df.tail(window).copy()
    if recent.empty or recent["거래량"].sum() == 0:
        return 0.0
    mid = (recent["고가"] + recent["저가"]) / 2
    return (mid * recent["거래량"]).sum() / recent["거래량"].sum()

# ================================================================
# SCORE ALGORITHM
# ================================================================

def compute_score(row, hist):
    """
    Score breakdown (0-100):
      Volume surge (>=500% of MA20)  : 25
      All-time 60d volume break       :  5
      Change rate (+10%~+22%)         : 15
      VWAP breakout                   : 10
      MA alignment (5>20>60)          : 15
      Bollinger upper breakout        : 10
      Gap from high (<=3%)            : 10
      Turnover >= 100B KRW            :  5
      Early session bonus             :  5
    """
    scores = {
        "거래량급증":   0,
        "역대급거래량": 0,
        "등락률":       0,
        "매물대돌파":   0,
        "정배열":       0,
        "볼린저돌파":   0,
        "고가이격":     0,
        "거래대금":     0,
        "장초반보너스": 0,
    }

    if hist.empty or len(hist) < 20:
        return scores

    hist = compute_indicators(hist)
    last = hist.iloc[-1]

    cur_price  = row.get("종가",     last["종가"])
    open_price = row.get("시가",     last["시가"])
    high_price = row.get("고가",     last["고가"])
    vol_today  = row.get("거래량",   last["거래량"])
    turnover   = row.get("거래대금", 0)

    vol_ma20  = last["Vol_MA20"]  if not pd.isna(last["Vol_MA20"])  else 1
    vol_max60 = last["Vol_MAX60"] if not pd.isna(last["Vol_MAX60"]) else 1

    # Volume surge
    if vol_ma20 > 0:
        vr = vol_today / vol_ma20
        if   vr >= 20: scores["거래량급증"] = 25
        elif vr >= 10: scores["거래량급증"] = 20
        elif vr >= 7:  scores["거래량급증"] = 15
        elif vr >= 5:  scores["거래량급증"] = 10
        elif vr >= 3:  scores["거래량급증"] = 5

    # All-time 60d volume
    if vol_today >= vol_max60:
        scores["역대급거래량"] = 5

    # Change rate
    if open_price > 0:
        chg = (cur_price - open_price) / open_price * 100
        if   18 <= chg <= 22: scores["등락률"] = 15
        elif 15 <= chg < 18:  scores["등락률"] = 12
        elif 12 <= chg < 15:  scores["등락률"] = 10
        elif 10 <= chg < 12:  scores["등락률"] = 7

    # VWAP breakout
    support = get_vwap_support(hist, window=20)
    if support > 0 and cur_price > support * 1.01:
        over = (cur_price - support) / support * 100
        if   over >= 10: scores["매물대돌파"] = 10
        elif over >= 5:  scores["매물대돌파"] = 7
        elif over >= 1:  scores["매물대돌파"] = 4

    # MA alignment
    ma5  = last.get("MA5",  np.nan)
    ma20 = last.get("MA20", np.nan)
    ma60 = last.get("MA60", np.nan)
    ma120= last.get("MA120",np.nan)
    ma240= last.get("MA240",np.nan)

    a = 0
    if not any(pd.isna(v) for v in [ma5, ma20, ma60]):
        if ma5 > ma20 > ma60:
            a += 8
    if not pd.isna(ma120) and cur_price > ma120: a += 4
    if not pd.isna(ma240) and cur_price > ma240: a += 3
    scores["정배열"] = min(a, 15)

    # Bollinger upper
    bb_up = last.get("BB_upper", np.nan)
    if not pd.isna(bb_up) and bb_up > 0:
        if cur_price >= bb_up * 1.01: scores["볼린저돌파"] = 10
        elif cur_price >= bb_up:       scores["볼린저돌파"] = 6

    # Gap from high
    if high_price > 0:
        gap = (high_price - cur_price) / high_price * 100
        if   gap <= 0.5: scores["고가이격"] = 10
        elif gap <= 1.5: scores["고가이격"] = 7
        elif gap <= 3.0: scores["고가이격"] = 4

    # Turnover
    if turnover >= 10_000_000_000: scores["거래대금"] = 5
    elif turnover >= 5_000_000_000: scores["거래대금"] = 2

    # Early session bonus (09:00 ~ 10:30)
    now = datetime.now()
    if (now.hour == 9) or (now.hour == 10 and now.minute <= 30):
        if scores["거래량급증"] >= 10:
            scores["장초반보너스"] = 5

    scores["합계"] = min(sum(scores.values()), 100)
    return scores

# ================================================================
# SCREENING
# ================================================================

def screen_stocks(market="ALL", min_cap=50_000_000_000,
                  max_cap=500_000_000_000, min_turnover=10_000_000_000,
                  progress_bar=None, status_text=None):

    all_tickers = fetch_market_tickers(market)
    if all_tickers.empty:
        return pd.DataFrame()

    filtered = all_tickers[
        (all_tickers["시가총액"] >= min_cap) &
        (all_tickers["시가총액"] <= max_cap) &
        (all_tickers["거래대금"] >= min_turnover) &
        (all_tickers["종가"]     > 0)
    ].copy()

    if filtered.empty:
        return pd.DataFrame()

    results = []
    total = len(filtered)

    for i, (_, row) in enumerate(filtered.iterrows()):
        ticker = row["티커"]
        name   = row["종목명"]

        if progress_bar:
            progress_bar.progress((i + 1) / total)
        if status_text:
            status_text.text(f"Analyzing: {name} ({i+1}/{total})")

        hist = fetch_ohlcv_history(ticker, days=70)
        if hist.empty or len(hist) < 20:
            continue

        open_p  = row["시가"]
        close_p = row["종가"]
        if open_p <= 0:
            continue
        chg = (close_p - open_p) / open_p * 100
        if not (10 <= chg <= 22):
            continue

        score_dict = compute_score(row, hist)
        total_score = score_dict["합계"]

        hist_ind = compute_indicators(hist)
        last = hist_ind.iloc[-1]

        results.append({
            "티커":        ticker,
            "종목명":      name,
            "시장":        row["시장"],
            "현재가":      int(close_p),
            "등락률(%)":   round(chg, 2),
            "거래량":      int(row["거래량"]),
            "거래대금(억)": round(row["거래대금"] / 1e8, 1),
            "시가총액(억)": round(row["시가총액"] / 1e8, 0),
            "상한가점수":  total_score,
            "_score_detail": score_dict,
            "_ma5":        round(float(last.get("MA5",  0) or 0), 1),
            "_ma20":       round(float(last.get("MA20", 0) or 0), 1),
            "_bb_upper":   round(float(last.get("BB_upper", 0) or 0), 1),
            "_vol_ma20":   int(last.get("Vol_MA20", 0) or 0),
        })
        time.sleep(0.05)

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_result.sort_values("상한가점수", ascending=False, inplace=True)
    df_result.reset_index(drop=True, inplace=True)
    return df_result

# ================================================================
# CANDLE CHART
# ================================================================

def draw_candle_chart(ticker, name):
    hist = fetch_ohlcv_history(ticker, days=70)
    if hist.empty:
        return go.Figure()

    hist = compute_indicators(hist)
    df = hist.tail(60).copy()

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.03,
        shared_xaxes=True,
    )

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["시가"], high=df["고가"], low=df["저가"], close=df["종가"],
        name="Price",
        increasing_line_color="#f87171", decreasing_line_color="#60a5fa",
        increasing_fillcolor="#f87171",  decreasing_fillcolor="#60a5fa",
        line=dict(width=1),
    ), row=1, col=1)

    for col, color, width, dash in [
        ("MA5",  "#fbbf24", 1.5, "solid"),
        ("MA20", "#34d399", 1.5, "solid"),
        ("MA60", "#a78bfa", 1.2, "dot"),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col], name=col,
                line=dict(color=color, width=width, dash=dash), opacity=0.9,
            ), row=1, col=1)

    if "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_upper"], name="BB Upper",
            line=dict(color="#f97316", width=1, dash="dash"), opacity=0.6,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_lower"], name="BB Lower",
            line=dict(color="#f97316", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(249,115,22,0.05)", opacity=0.6,
        ), row=1, col=1)

    colors_vol = ["#f87171" if c >= o else "#60a5fa"
                  for c, o in zip(df["종가"], df["시가"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["거래량"], name="Volume",
        marker_color=colors_vol, opacity=0.8,
    ), row=2, col=1)

    if "Vol_MA20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Vol_MA20"], name="Vol MA20",
            line=dict(color="#fbbf24", width=1.2, dash="dot"),
        ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"<b>{name}</b> ({ticker}) — 60-day Chart",
                   font=dict(size=16, color="#e2e8f0")),
        paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1527",
        legend=dict(bgcolor="#111827", bordercolor="#1e2a45",
                    font=dict(color="#94a3b8", size=11)),
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=20, t=55, b=10),
        height=540, font=dict(color="#94a3b8"),
    )
    fig.update_xaxes(gridcolor="#1e2a45", tickfont=dict(size=10))
    fig.update_yaxes(gridcolor="#1e2a45", tickfont=dict(size=10), tickformat=",")
    return fig

# ================================================================
# AI OPINION (rule-based, no external API)
# ================================================================

def generate_ai_opinion(row):
    detail   = row.get("_score_detail", {})
    chg      = row["등락률(%)"]
    vol      = row["거래량"]
    vol_ma   = row.get("_vol_ma20", 1)
    score    = row["상한가점수"]
    bb_up    = row.get("_bb_upper", 0)
    vol_ratio = round(vol / vol_ma, 1) if vol_ma > 0 else 0

    lines = []

    # Volume comment
    if detail.get("거래량급증", 0) >= 20:
        lines.append(
            f"📊 <strong>거래량 폭발</strong>: 20일 평균 대비 <strong>{vol_ratio}배</strong> 급증 — 강력한 수급 유입 확인."
        )
    elif detail.get("거래량급증", 0) >= 10:
        lines.append(
            f"📊 거래량이 20일 평균 대비 <strong>{vol_ratio}배</strong> 증가 — 유의미한 매집 신호."
        )
    else:
        lines.append(
            f"📊 거래량 20일 평균 대비 <strong>{vol_ratio}배</strong> 수준 — 급증 조건 근접 중."
        )

    # Pattern comment
    parts = []
    if detail.get("정배열", 0) >= 8:
        parts.append("5/20/60일 이평선 완전 정배열")
    if detail.get("볼린저돌파", 0) >= 10:
        parts.append(f"볼린저 밴드 상단({int(bb_up):,}원) 돌파")
    if detail.get("매물대돌파", 0) >= 7:
        parts.append("단기 매물대 강하게 돌파")
    if detail.get("역대급거래량", 0) == 5:
        parts.append("60일 최고 거래량 경신")

    if parts:
        lines.append(f"📈 <strong>차트 패턴</strong>: {', '.join(parts)} — 추가 상승 탄력 유지 중.")
    else:
        lines.append(
            f"📈 +{chg}% 상승 중, 이평선 수렴 또는 볼린저 상단 접근 — 모멘텀 강화 여부 주시."
        )

    # Conclusion
    if score >= 70:
        conclusion = f"종합 <strong>{score}점</strong> — 당일 상한가 진입 가능성 높음."
    elif score >= 50:
        conclusion = f"종합 <strong>{score}점</strong> — 추가 거래량 확인 후 판단 권장."
    else:
        conclusion = f"종합 <strong>{score}점</strong> — 추가 모니터링 필요."

    lines.append(f"⚠️ {conclusion}")
    return "<br>".join(lines)

# ================================================================
# STREAMLIT UI
# ================================================================

def main():
    st.markdown('<p class="main-title">🔥 상한가 유력 종목 스크리너</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">KOSPI · KOSDAQ 실시간 기술적 분석 — 당일 상한가 도달 가능성 점수 산출</p>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div class="warn-box">
    ⚠️ <strong>투자 유의</strong>: 본 앱은 기술적 지표 기반 참고용 스크리너이며,
    투자 권유 또는 수익을 보장하지 않습니다. 모든 투자 결정과 손익은 투자자 본인에게 있습니다.
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### ⚙️ 스크리닝 설정")
        st.markdown("---")
        market_sel = st.selectbox("시장 선택", ["ALL (전체)", "KOSPI", "KOSDAQ"], index=0)
        market = "ALL" if "ALL" in market_sel else market_sel
        min_cap = st.slider("최소 시가총액 (억)", 100, 2000, 500, step=100) * 100_000_000
        max_cap = st.slider("최대 시가총액 (억)", 1000, 20000, 5000, step=500) * 100_000_000
        min_turnover = st.slider("최소 거래대금 (억)", 10, 500, 100, step=10) * 100_000_000
        top_n = st.selectbox("상위 종목 수", [3, 5, 10], index=1)
        st.markdown("---")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        st.caption(f"기준 영업일: {get_trading_date()}")
        run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")

    if "result_df" not in st.session_state:
        st.session_state.result_df = None

    if run_btn:
        st.session_state.result_df = None
        with st.spinner(""):
            c1, c2 = st.columns([3, 7])
            with c1:
                pbar = st.progress(0)
            with c2:
                stat = st.empty()
            df_result = screen_stocks(
                market=market,
                min_cap=int(min_cap), max_cap=int(max_cap),
                min_turnover=int(min_turnover),
                progress_bar=pbar, status_text=stat,
            )
            pbar.empty()
            stat.empty()

        if df_result is None or df_result.empty:
            st.info("조건을 만족하는 종목이 없습니다. 필터 조건을 완화해 보세요.")
        else:
            st.session_state.result_df = df_result

    if st.session_state.result_df is not None and not st.session_state.result_df.empty:
        df = st.session_state.result_df
        top_df = df.head(top_n).copy()

        st.markdown(f"#### 🏆 상한가 유력 상위 {top_n}개 종목")
        display_cols = ["종목명", "시장", "현재가", "등락률(%)", "거래량", "거래대금(억)", "시가총액(억)", "상한가점수"]
        st.dataframe(
            top_df[display_cols].style
            .background_gradient(subset=["상한가점수"], cmap="YlOrRd")
            .format({
                "현재가":      "{:,}",
                "등락률(%)":   "{:+.2f}%",
                "거래량":      "{:,}",
                "거래대금(억)": "{:,.1f}",
                "시가총액(억)": "{:,.0f}",
            }),
            use_container_width=True,
            height=min(60 + 40 * top_n, 420),
        )
        st.markdown("---")

        tabs = st.tabs([f"{r['종목명']}" for _, r in top_df.iterrows()])
        for tab, (_, row) in zip(tabs, top_df.iterrows()):
            with tab:
                ticker = row["티커"]
                name   = row["종목명"]

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">현재가</div>
                        <div class="metric-value">{row['현재가']:,}원</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    cls = "metric-up" if row["등락률(%)"] >= 0 else "metric-dn"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">등락률 (시가대비)</div>
                        <div class="metric-value {cls}">{row['등락률(%)']:+.2f}%</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">거래대금</div>
                        <div class="metric-value">{row['거래대금(억)']:.1f}억원</div>
                    </div>""", unsafe_allow_html=True)
                with c4:
                    color = "#f87171" if row["상한가점수"] >= 70 else \
                            "#fbbf24" if row["상한가점수"] >= 50 else "#93c5fd"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">상한가 점수</div>
                        <div class="metric-value" style="color:{color}">
                            {row['상한가점수']}점
                        </div>
                    </div>""", unsafe_allow_html=True)

                # Score bar chart
                detail = row.get("_score_detail", {})
                s_labels = [k for k in detail.keys() if k != "합계"]
                s_vals   = [detail[k] for k in s_labels]

                fig_score = go.Figure(go.Bar(
                    x=s_labels, y=s_vals, text=s_vals,
                    textposition="outside",
                    marker=dict(
                        color=s_vals,
                        colorscale=[[0,"#1e3a5f"],[0.5,"#78350f"],[1,"#7f1d1d"]],
                        cmin=0, cmax=25,
                    ),
                ))
                fig_score.update_layout(
                    paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1527",
                    height=220, margin=dict(l=20, r=20, t=30, b=40),
                    yaxis=dict(gridcolor="#1e2a45", color="#64748b"),
                    xaxis=dict(color="#94a3b8", tickfont=dict(size=11)),
                    font=dict(color="#94a3b8"),
                    title=dict(text="항목별 점수", font=dict(size=13, color="#e2e8f0")),
                )
                st.plotly_chart(fig_score, use_container_width=True)

                opinion_html = generate_ai_opinion(row)
                st.markdown(
                    f'<div class="ai-box">🤖 <strong>AI 기술적 의견</strong><br><br>{opinion_html}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("&nbsp;", unsafe_allow_html=True)

                with st.spinner(f"{name} 차트 로딩 중..."):
                    fig_candle = draw_candle_chart(ticker, name)
                if fig_candle.data:
                    st.plotly_chart(fig_candle, use_container_width=True)
                else:
                    st.warning("차트 데이터를 불러올 수 없습니다.")

    elif st.session_state.result_df is None:
        st.markdown("""
        <div style="text-align:center; padding:4rem 0; color:#334155;">
            <div style="font-size:3rem;">🔍</div>
            <div style="font-size:1.1rem; margin-top:1rem;">
                사이드바에서 조건을 설정하고<br>
                <strong style="color:#f97316;">분석 시작</strong> 버튼을 누르세요.
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()