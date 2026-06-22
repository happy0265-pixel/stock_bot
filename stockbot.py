# -*- coding: utf-8 -*-
"""
Upper Limit Stock Screener - Yahoo Finance + curl_cffi version
Run: streamlit run stockbot.py
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import time

try:
    import curl_cffi.requests as cf_requests
except ImportError:
    st.error("curl_cffi 미설치: pip install curl_cffi")
    st.stop()

# ================================================================
# PAGE CONFIG & CSS
# ================================================================
st.set_page_config(
    page_title="상한가 스크리너",
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
# KOSPI/KOSDAQ 주요 종목 리스트 (티커: 종목명)
# ================================================================

KOSPI_TICKERS = {
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "207940.KS": "삼성바이오로직스",
    "005380.KS": "현대차", "000270.KS": "기아", "051910.KS": "LG화학",
    "035420.KS": "NAVER", "035720.KS": "카카오", "028260.KS": "삼성물산",
    "068270.KS": "셀트리온", "105560.KS": "KB금융", "055550.KS": "신한지주",
    "012330.KS": "현대모비스", "066570.KS": "LG전자", "032830.KS": "삼성생명",
    "096770.KS": "SK이노베이션", "003550.KS": "LG", "017670.KS": "SK텔레콤",
    "030200.KS": "KT", "011200.KS": "HMM", "009540.KS": "HD한국조선해양",
    "042660.KS": "한화오션", "010130.KS": "고려아연", "011790.KS": "SKC",
    "001040.KS": "CJ", "097950.KS": "CJ제일제당", "000810.KS": "삼성화재",
    "086790.KS": "하나금융지주", "316140.KS": "우리금융지주", "024110.KS": "기업은행",
    "018260.KS": "삼성에스디에스", "009150.KS": "삼성전기", "006400.KS": "삼성SDI",
    "051900.KS": "LG생활건강", "161390.KS": "한국타이어앤테크놀로지", "047050.KS": "포스코인터내셔널",
    "003490.KS": "대한항공", "020150.KS": "율촌화학", "000720.KS": "현대건설",
    "004020.KS": "현대제철", "005940.KS": "NH투자증권", "071050.KS": "한국금융지주",
    "016360.KS": "삼성증권", "139480.KS": "이마트", "069960.KS": "현대백화점",
    "004990.KS": "롯데지주", "023530.KS": "롯데쇼핑", "011170.KS": "롯데케미칼",
}

KOSDAQ_TICKERS = {
    "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "373220.KQ": "LG에너지솔루션",
    "196170.KQ": "알테오젠", "263750.KQ": "펄어비스", "293490.KQ": "카카오게임즈",
    "112040.KQ": "위메이드", "095340.KQ": "ISC", "214150.KQ": "클래시스",
    "145020.KQ": "휴젤", "141080.KQ": "레고켐바이오", "226490.KQ": "에이치엘비생명과학",
    "182360.KQ": "큐리언트", "950200.KQ": "파나진", "091990.KQ": "셀트리온헬스케어",
    "036930.KQ": "주성엔지니어링", "357780.KQ": "솔브레인", "039030.KQ": "이오테크닉스",
    "109610.KQ": "에스씨아이평가정보", "053800.KQ": "안랩", "078600.KQ": "대주전자재료",
    "950130.KQ": "엑세스바이오", "302430.KQ": "이노뎁", "048410.KQ": "현대바이오",
    "028300.KQ": "HLB", "064550.KQ": "바이오니아", "013360.KQ": "일진머티리얼즈",
    "040350.KQ": "크레버스", "206560.KQ": "덱스터", "900290.KQ": "GRT",
    "041510.KQ": "에스엠", "035900.KQ": "JYP Ent.", "122870.KQ": "와이지엔터테인먼트",
    "058970.KQ": "엠플러스", "123690.KQ": "한국화장품제조", "214370.KQ": "케어젠",
    "005290.KQ": "동진쎄미켐", "222080.KQ": "씨아이에스", "066970.KQ": "엘앤에프",
    "347700.KQ": "스피어", "031980.KQ": "피에스케이홀딩스", "336570.KQ": "원익QnC",
    "900310.KQ": "컬러레이", "060370.KQ": "LS마린솔루션", "099430.KQ": "바이오플러스",
    "096530.KQ": "씨젠", "048530.KQ": "대한과학", "950160.KQ": "코오롱티슈진",
    "140410.KQ": "메지온", "237690.KQ": "에스티팜",
}

ALL_TICKERS = {**KOSPI_TICKERS, **KOSDAQ_TICKERS}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ================================================================
# 데이터 수집 함수
# ================================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_quote(ticker: str) -> dict:
    """야후 파이낸스에서 현재 시세 가져오기"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "1d"}
    try:
        resp = cf_requests.get(url, params=params, headers=HEADERS, verify=False, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return {}
        meta = result[0].get("meta", {})
        return {
            "ticker":        ticker,
            "name":          ALL_TICKERS.get(ticker, ticker),
            "price":         meta.get("regularMarketPrice", 0),
            "open":          meta.get("chartPreviousClose", 0),
            "prev_close":    meta.get("chartPreviousClose", 0),
            "day_high":      meta.get("regularMarketDayHigh", 0),
            "day_low":       meta.get("regularMarketDayLow", 0),
            "volume":        meta.get("regularMarketVolume", 0),
            "market_cap":    meta.get("marketCap", 0),
            "market":        "KOSPI" if ticker.endswith(".KS") else "KOSDAQ",
        }
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker: str, days: int = 70) -> pd.DataFrame:
    """야후 파이낸스에서 OHLCV 히스토리 가져오기"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "4mo"}
    try:
        resp = cf_requests.get(url, params=params, headers=HEADERS, verify=False, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return pd.DataFrame()

        timestamps = result[0].get("timestamp", [])
        ohlcv = result[0].get("indicators", {}).get("quote", [{}])[0]

        df = pd.DataFrame({
            "날짜":   pd.to_datetime(timestamps, unit="s").tz_localize("UTC").tz_convert("Asia/Seoul").tz_localize(None),
            "시가":   ohlcv.get("open", []),
            "고가":   ohlcv.get("high", []),
            "저가":   ohlcv.get("low", []),
            "종가":   ohlcv.get("close", []),
            "거래량": ohlcv.get("volume", []),
        })
        df.set_index("날짜", inplace=True)
        df.dropna(inplace=True)
        return df.tail(days)
    except Exception:
        return pd.DataFrame()

# ================================================================
# 기술지표 계산
# ================================================================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for w in [5, 20, 60, 120, 240]:
        df[f"MA{w}"] = df["종가"].rolling(w).mean()
    df["BB_mid"]    = df["종가"].rolling(20).mean()
    df["BB_std"]    = df["종가"].rolling(20).std()
    df["BB_upper"]  = df["BB_mid"] + 2 * df["BB_std"]
    df["BB_lower"]  = df["BB_mid"] - 2 * df["BB_std"]
    df["Vol_MA20"]  = df["거래량"].rolling(20).mean()
    df["Vol_MAX60"] = df["거래량"].rolling(60).max()
    return df

# ================================================================
# 상한가 점수 알고리즘
# ================================================================

def compute_score(quote: dict, hist: pd.DataFrame) -> dict:
    scores = {
        "거래량급증":   0,
        "역대급거래량": 0,
        "등락률":       0,
        "매물대돌파":   0,
        "정배열":       0,
        "볼린저돌파":   0,
        "고가이격":     0,
        "시가총액":     0,
        "장초반보너스": 0,
    }

    if hist.empty or len(hist) < 20:
        return scores

    hist = compute_indicators(hist)
    last = hist.iloc[-1]

    cur   = quote.get("price", 0)
    open_ = quote.get("open", 0)
    high  = quote.get("day_high", 0)
    vol   = quote.get("volume", 0)
    mcap  = quote.get("market_cap", 0)

    vol_ma20  = float(last.get("Vol_MA20",  1) or 1)
    vol_max60 = float(last.get("Vol_MAX60", 1) or 1)

    # 거래량 급증
    if vol_ma20 > 0:
        vr = vol / vol_ma20
        if   vr >= 20: scores["거래량급증"] = 25
        elif vr >= 10: scores["거래량급증"] = 20
        elif vr >= 7:  scores["거래량급증"] = 15
        elif vr >= 5:  scores["거래량급증"] = 10
        elif vr >= 3:  scores["거래량급증"] = 5

    # 60일 최고 거래량 돌파
    if vol >= vol_max60:
        scores["역대급거래량"] = 5

    # 등락률 +10% ~ +22%
    if open_ > 0:
        chg = (cur - open_) / open_ * 100
        if   18 <= chg <= 22: scores["등락률"] = 15
        elif 15 <= chg < 18:  scores["등락률"] = 12
        elif 12 <= chg < 15:  scores["등락률"] = 10
        elif 10 <= chg < 12:  scores["등락률"] = 7

    # 매물대(VWAP) 돌파
    recent = hist.tail(20)
    if not recent.empty and recent["거래량"].sum() > 0:
        mid = (recent["고가"] + recent["저가"]) / 2
        vwap = (mid * recent["거래량"]).sum() / recent["거래량"].sum()
        if cur > vwap * 1.01:
            over = (cur - vwap) / vwap * 100
            if   over >= 10: scores["매물대돌파"] = 10
            elif over >= 5:  scores["매물대돌파"] = 7
            elif over >= 1:  scores["매물대돌파"] = 4

    # 이동평균 정배열
    ma5   = float(last.get("MA5",  0) or 0)
    ma20  = float(last.get("MA20", 0) or 0)
    ma60  = float(last.get("MA60", 0) or 0)
    ma120 = float(last.get("MA120",0) or 0)
    ma240 = float(last.get("MA240",0) or 0)

    a = 0
    if ma5 > 0 and ma20 > 0 and ma60 > 0 and ma5 > ma20 > ma60:
        a += 8
    if ma120 > 0 and cur > ma120: a += 4
    if ma240 > 0 and cur > ma240: a += 3
    scores["정배열"] = min(a, 15)

    # 볼린저 밴드 상단 돌파
    bb_up = float(last.get("BB_upper", 0) or 0)
    if bb_up > 0:
        if cur >= bb_up * 1.01: scores["볼린저돌파"] = 10
        elif cur >= bb_up:       scores["볼린저돌파"] = 6

    # 고가 대비 현재가 이격
    if high > 0:
        gap = (high - cur) / high * 100
        if   gap <= 0.5: scores["고가이격"] = 10
        elif gap <= 1.5: scores["고가이격"] = 7
        elif gap <= 3.0: scores["고가이격"] = 4

    # 시가총액 500억~5000억
    if 50_000_000_000 <= mcap <= 500_000_000_000:
        scores["시가총액"] = 5
    elif mcap > 0:
        scores["시가총액"] = 2

    # 장 초반 보너스
    now = datetime.now()
    if (now.hour == 9) or (now.hour == 10 and now.minute <= 30):
        if scores["거래량급증"] >= 10:
            scores["장초반보너스"] = 5

    scores["합계"] = min(sum(v for k, v in scores.items() if k != "합계"), 100)
    return scores

# ================================================================
# 스크리닝
# ================================================================

def screen_stocks(market="ALL", progress_bar=None, status_text=None):
    if market == "KOSPI":
        tickers = KOSPI_TICKERS
    elif market == "KOSDAQ":
        tickers = KOSDAQ_TICKERS
    else:
        tickers = ALL_TICKERS

    results = []
    total = len(tickers)

    for i, (ticker, name) in enumerate(tickers.items()):
        if progress_bar:
            progress_bar.progress((i + 1) / total)
        if status_text:
            status_text.text(f"분석 중: {name} ({i+1}/{total})")

        quote = fetch_quote(ticker)
        if not quote:
            continue

        cur   = quote.get("price", 0)
        open_ = quote.get("open", 0)
        if cur <= 0 or open_ <= 0:
            continue

        chg = (cur - open_) / open_ * 100
        if not (10 <= chg <= 22):
            continue

        hist = fetch_history(ticker, days=70)
        if hist.empty or len(hist) < 20:
            continue

        score_dict = compute_score(quote, hist)
        hist_ind = compute_indicators(hist)
        last = hist_ind.iloc[-1]

        vol_ma20 = float(last.get("Vol_MA20", 1) or 1)

        results.append({
            "티커":        ticker,
            "종목명":      name,
            "시장":        quote["market"],
            "현재가":      int(cur),
            "등락률(%)":   round(chg, 2),
            "거래량":      int(quote.get("volume", 0)),
            "시가총액(억)": round(quote.get("market_cap", 0) / 1e8, 0),
            "상한가점수":  score_dict["합계"],
            "_score_detail": score_dict,
            "_ma5":        round(float(last.get("MA5",  0) or 0), 1),
            "_ma20":       round(float(last.get("MA20", 0) or 0), 1),
            "_bb_upper":   round(float(last.get("BB_upper", 0) or 0), 1),
            "_vol_ma20":   int(vol_ma20),
        })
        time.sleep(0.1)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df.sort_values("상한가점수", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# ================================================================
# 캔들 차트
# ================================================================

def draw_candle_chart(ticker: str, name: str) -> go.Figure:
    hist = fetch_history(ticker, days=70)
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
        x=df.index, open=df["시가"], high=df["고가"], low=df["저가"], close=df["종가"],
        name="주가",
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
            x=df.index, y=df["BB_upper"], name="BB상단",
            line=dict(color="#f97316", width=1, dash="dash"), opacity=0.6,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_lower"], name="BB하단",
            line=dict(color="#f97316", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(249,115,22,0.05)", opacity=0.6,
        ), row=1, col=1)

    colors_vol = ["#f87171" if c >= o else "#60a5fa"
                  for c, o in zip(df["종가"], df["시가"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["거래량"], name="거래량",
        marker_color=colors_vol, opacity=0.8,
    ), row=2, col=1)

    if "Vol_MA20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Vol_MA20"], name="거래량MA20",
            line=dict(color="#fbbf24", width=1.2, dash="dot"),
        ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"<b>{name}</b> ({ticker}) — 60일 차트",
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
# AI 의견 생성
# ================================================================

def generate_ai_opinion(row: pd.Series) -> str:
    detail   = row.get("_score_detail", {})
    chg      = row["등락률(%)"]
    vol      = row["거래량"]
    vol_ma   = row.get("_vol_ma20", 1)
    score    = row["상한가점수"]
    bb_up    = row.get("_bb_upper", 0)
    vol_ratio = round(vol / vol_ma, 1) if vol_ma > 0 else 0

    lines = []

    if detail.get("거래량급증", 0) >= 20:
        lines.append(f"📊 <strong>거래량 폭발</strong>: 20일 평균 대비 <strong>{vol_ratio}배</strong> 급증 — 강력한 수급 유입 확인.")
    elif detail.get("거래량급증", 0) >= 10:
        lines.append(f"📊 거래량이 20일 평균 대비 <strong>{vol_ratio}배</strong> 증가 — 유의미한 매집 신호.")
    else:
        lines.append(f"📊 거래량 20일 평균 대비 <strong>{vol_ratio}배</strong> 수준 — 급증 조건 근접 중.")

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
        lines.append(f"📈 +{chg:.1f}% 상승 중, 이평선 수렴 또는 볼린저 상단 접근 — 모멘텀 강화 여부 주시.")

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
        '<p class="sub-title">KOSPI · KOSDAQ 기술적 분석 — 당일 상한가 도달 가능성 점수 산출</p>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div class="warn-box">
    ⚠️ <strong>투자 유의</strong>: 본 앱은 기술적 지표 기반 참고용 스크리너이며,
    투자 권유 또는 수익을 보장하지 않습니다. 모든 투자 결정과 손익은 투자자 본인에게 있습니다.
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 설정")
        st.markdown("---")
        market_sel = st.selectbox("시장 선택", ["ALL (전체)", "KOSPI", "KOSDAQ"], index=0)
        market = "ALL" if "ALL" in market_sel else market_sel
        top_n = st.selectbox("상위 종목 수", [3, 5, 10], index=1)
        st.markdown("---")
        st.caption(f"데이터: Yahoo Finance")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
            df_result = screen_stocks(market=market, progress_bar=pbar, status_text=stat)
            pbar.empty()
            stat.empty()

        if df_result is None or df_result.empty:
            st.info("조건을 만족하는 종목이 없습니다. 장중(09:00~15:30)에 실행해보세요.")
        else:
            st.session_state.result_df = df_result

    if st.session_state.result_df is not None and not st.session_state.result_df.empty:
        df = st.session_state.result_df
        top_df = df.head(top_n).copy()

        st.markdown(f"#### 🏆 상한가 유력 상위 {top_n}개 종목")
        display_cols = ["종목명", "시장", "현재가", "등락률(%)", "거래량", "시가총액(억)", "상한가점수"]
        st.dataframe(
            top_df[display_cols].style
            .background_gradient(subset=["상한가점수"], cmap="YlOrRd")
            .format({
                "현재가":      "{:,}",
                "등락률(%)":   "{:+.2f}%",
                "거래량":      "{:,}",
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
                    st.markdown(f"""<div class="metric-card">
                        <div class="metric-label">현재가</div>
                        <div class="metric-value">{row['현재가']:,}원</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    cls = "metric-up" if row["등락률(%)"] >= 0 else "metric-dn"
                    st.markdown(f"""<div class="metric-card">
                        <div class="metric-label">등락률</div>
                        <div class="metric-value {cls}">{row['등락률(%)']:+.2f}%</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""<div class="metric-card">
                        <div class="metric-label">거래량</div>
                        <div class="metric-value">{row['거래량']:,}</div>
                    </div>""", unsafe_allow_html=True)
                with c4:
                    color = "#f87171" if row["상한가점수"] >= 70 else \
                            "#fbbf24" if row["상한가점수"] >= 50 else "#93c5fd"
                    st.markdown(f"""<div class="metric-card">
                        <div class="metric-label">상한가 점수</div>
                        <div class="metric-value" style="color:{color}">{row['상한가점수']}점</div>
                    </div>""", unsafe_allow_html=True)

                detail  = row.get("_score_detail", {})
                s_labels = [k for k in detail.keys() if k != "합계"]
                s_vals   = [detail[k] for k in s_labels]

                fig_score = go.Figure(go.Bar(
                    x=s_labels, y=s_vals, text=s_vals, textposition="outside",
                    marker=dict(color=s_vals,
                                colorscale=[[0,"#1e3a5f"],[0.5,"#78350f"],[1,"#7f1d1d"]],
                                cmin=0, cmax=25),
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
            <div style="font-size:0.8rem; margin-top:0.8rem; color:#475569;">
                장중(09:00~15:30) 실행 시 당일 데이터 반영
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()