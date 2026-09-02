"""
한국 주식 포트폴리오 트래커 (Streamlit) — Meritz Orchestra
------------------------------------------------------------------
    streamlit run app.py

시세는 네이버 금융 비공식 공개 API를 사용합니다(종목코드 자동 검색 포함).
데이터 계층(로드/저장/replay/시세조회)은 portfolio_core.py에 있음 —
일일 매매일지 반영 스크립트(ingest_daily.py)와 로직을 공유하기 위해서다.
"""

import calendar

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from portfolio_core import (
    group_sector,
    now_kst, today_kst_str, now_kst_str,
    load_holdings, load_transactions,
    load_state,
    load_history, snapshot_history,
    load_sector_history, snapshot_sector_history,
    refresh_all_prices, fetch_index_quotes, fetch_fx_rate, get_current_prices_for_names, get_closed_out_last_sells,
    compute_metrics, compute_sector_weights,
    get_holding_trade_summary, get_holding_trade_summary_all_time,
    get_holding_trade_points, get_holding_avg_price_path,
    load_index_history, snapshot_index_history,
    load_dom_asset_history, snapshot_dom_asset_history,
    load_market_cache, refresh_market_cache,
    compute_index_vs_account, _index_day_moves,
)

UP_COLOR = "#d9364f"    # 국내 관례: 상승/이익 = 빨강
DOWN_COLOR = "#2b6cd4"  # 하락/손실 = 파랑
NEW_COLOR = "#22c55e"   # 초록 — 민감도 그래프 "5일" 선 색
KOSPI_COLOR = "#f59e0b"   # 지수 대비 계좌 그래프: 코스피 참조선(앰버)
KOSDAQ_COLOR = "#14b8a6"  # 코스닥 참조선(틸)
CASH_LABEL = "현금(예수금)"

SECTOR_PALETTE = [
    "#2DD4BF", "#F5A623", "#A78BFA", "#34D399", "#F472B6",
    "#FBBF24", "#60A5FA", "#F87171", "#C084FC", "#38BDF8", "#FB923C",
]

# 섹터별 목표 비중(주식 총자산 대비, %). 아직 정하지 않은 섹터는 포함하지 않음 — 추후 추가.
SECTOR_TARGETS = {
    "식품": 30.0,
    "소비재": 20.0,
}

THEMES = {
    "dark": {
        "bg": "#0a0c10", "card": "#12151c", "card2": "#20242e", "border": "#2b303c",
        "text": "#e8eaed", "muted": "#9aa4b2", "muted2": "#6b7280", "cash_dot": "#4b5563",
    },
    "light": {
        "bg": "#f4f5f7", "card": "#ffffff", "card2": "#eceef1", "border": "#e2e4e9",
        "text": "#1a1d23", "muted": "#5b6472", "muted2": "#7a8290", "cash_dot": "#9aa0ab",
    },
}


def theme() -> dict:
    return THEMES[st.session_state.get("theme", "light")]



# ------------------------------------------------------------------ #
# 페이지 설정
# ------------------------------------------------------------------ #
st.set_page_config(page_title="Meritz Orchestra", page_icon="◆", layout="centered")

if "theme" not in st.session_state:
    st.session_state["theme"] = "light"
T = theme()

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&display=swap');
    .stApp {{ background-color: {T['bg']}; }}
    .brand {{
        font-family: 'Sora', sans-serif;
        font-weight: 800;
        font-size: 18px;
        letter-spacing: 0.01em;
        color: {T['text']};
        padding: 6px 0;
        white-space: nowrap;
    }}
    .block-container {{ padding-top: 1.1rem; padding-bottom: 2rem; padding-left: 1rem; padding-right: 1rem; max-width: 480px; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    h1, h2, h3, h4, h5, p, span, label, div {{ color: {T['text']}; }}

    .summary-box {{ background:{T['card']}; border:1px solid {T['border']}; border-radius:14px; padding:18px 20px; margin-bottom:14px; }}
    .summary-label {{ color:{T['muted']}; font-size:13px; margin-bottom:4px; }}
    .summary-main {{ font-size:28px; font-weight:800; line-height:1.2; }}
    .summary-sub {{ font-size:14px; font-weight:600; margin-left:6px; }}
    .summary-grid {{ display:flex; flex-wrap:wrap; justify-content:space-between; margin-top:14px; gap:8px; }}
    .summary-grid div {{ font-size:12.5px; color:{T['muted']}; min-width:29%; }}
    .summary-grid b {{ display:block; font-size:15px; color:{T['text']}; margin-top:2px; }}
    .capital-line {{ margin-top:10px; padding-top:10px; border-top:1px solid {T['border']}; font-size:12.5px; color:{T['muted']}; }}
    .capital-line b {{ font-size:14px; }}

    .daily-trade-box {{ margin-top:10px; padding-top:10px; border-top:1px solid {T['border']}; font-size:12.5px; color:{T['muted']}; }}
    .daily-trade-count {{ font-size:13px; color:{T['text']}; font-weight:700; margin-bottom:6px; }}
    .daily-trade-count span {{ font-weight:400; color:{T['muted']}; margin-left:4px; }}
    .daily-trade-row {{ display:flex; flex-wrap:wrap; gap:6px 8px; align-items:baseline; margin-top:4px; }}
    .daily-trade-row .tag-label {{ font-size:12px; font-weight:700; min-width:30px; }}
    .trade-chip {{ font-size:12px; background:{T['bg']}; border:1px solid {T['border']}; border-radius:99px; padding:2px 9px; color:{T['text']}; }}
    .trade-chip b {{ font-weight:600; }}

    .legend-wrap {{ display:flex; flex-wrap:wrap; gap:7px 14px; margin-top:10px; justify-content:center; }}
    .legend-item {{ display:flex; align-items:center; gap:5px; font-size:12px; color:{T['text']}; }}
    .legend-dot {{ width:8px; height:8px; border-radius:99px; flex-shrink:0; }}
    .legend-pct {{ color:{T['muted']}; font-family: ui-monospace, monospace; }}

    .sector-bar-list {{ margin-top:10px; }}
    .sector-bar-row {{ display:flex; align-items:center; gap:6px; margin-bottom:14px; }}
    .sector-bar-label {{ font-size:11px; font-weight:600; color:{T['text']}; width:64px; flex-shrink:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .sector-bar-track {{ position:relative; flex:1; height:14px; background:{T['card']}; border:1px solid {T['border']}; border-radius:999px; overflow:visible; }}
    .sector-bar-fill {{ position:absolute; left:1px; top:1px; bottom:1px; border-radius:999px; }}
    .sector-target-marker {{ position:absolute; top:-2px; bottom:-2px; width:2px; background:{T['text']}; opacity:0.55; }}
    .sector-target-label {{ position:absolute; top:100%; margin-top:2px; transform:translateX(-50%); font-size:9.5px; color:{T['muted2']}; white-space:nowrap; }}
    .sector-bar-pct {{ font-size:12px; color:{T['muted']}; width:64px; flex-shrink:0; text-align:right; font-family: ui-monospace, monospace; white-space:nowrap; }}
    .sector-bar-pct .cur {{ font-weight:700; color:{T['text']}; }}
    .sector-bar-pct .delta {{ margin-left:3px; }}
    .sector-stock-names {{ font-size:10.5px; color:{T['muted2']}; margin:2px 0 0 2px; }}

    .updown-row {{ display:flex; align-items:center; gap:8px; padding:7px 2px; border-bottom:1px solid {T['border']}; font-size:12.5px; }}
    .updown-row:last-child {{ border-bottom:none; }}
    .updown-row .name {{ font-weight:700; color:{T['text']}; flex:1; }}
    .updown-row .pct {{ font-weight:700; font-family: ui-monospace, monospace; width:62px; text-align:right; }}
    .updown-row .detail {{ font-size:11px; color:{T['muted']}; font-family: ui-monospace, monospace; width:118px; text-align:right; }}


    .stock-card {{ background:{T['card']}; border:1px solid {T['border']}; border-radius:12px; padding:10px 16px; margin-bottom:7px; }}
    .stock-top {{ display:flex; justify-content:space-between; align-items:baseline; }}
    .stock-title-group {{ flex:1 1 auto; min-width:0; max-width:calc(100% - 180px); }}
    .stock-name {{ font-size:13px; font-weight:700; color:{T['text']}; white-space:nowrap; }}
    .sector-tag {{ font-size:10.5px; padding:2px 7px; border-radius:5px; font-weight:600; flex-shrink:0; }}
    .stock-grid {{ display:grid; grid-template-columns: 0.7fr 1.05fr 1.05fr 1.3fr; gap:6px; margin-top:7px; }}
    .cell .top {{ font-size:12.5px; font-weight:700; color:{T['text']}; }}
    .cell .bottom {{ font-size:11px; color:{T['muted']}; margin-top:2px; }}
    .stock-foot {{ display:flex; justify-content:flex-end; margin-top:6px; font-size:10px; color:{T['muted2']}; }}
    .trade-summary {{ display:flex; flex-wrap:wrap; gap:3px 16px; font-size:11px; color:{T['muted']}; margin:10px 2px 6px; }}
    .trade-summary + .trade-summary {{ margin-top:2px; }}
    .trade-summary b {{ color:{T['text']}; font-weight:700; }}
    .trade-summary-label {{
        font-size:10px; font-weight:700; color:{T['muted2']}; text-transform:uppercase;
        letter-spacing:0.3px; flex-basis:100%;
    }}

    /* 보유종목 카드 우측상단 "WATERING" 칩(=매수/매도 내역·물타기 그래프 토글) — new1의
       동일 CSS를 그대로 포팅함(2026-08-28). */
    [class*="st-key-holding_wrap_"] {{ position:relative; }}
    [class*="st-key-watering_"] {{
        position:absolute; top:11px; right:108px; z-index:5; width:auto !important;
    }}
    [class*="st-key-watering_"] button {{
        padding:2px 7px !important; min-height:0 !important;
        height:auto !important; border-radius:5px !important;
        line-height:1.4 !important; border:none !important;
        box-shadow:none !important;
    }}
    [class*="st-key-watering_"] button p {{
        font-size:10.5px !important; font-weight:400 !important; line-height:1.4 !important;
    }}
    [class*="st-key-watering_"] button[kind="secondary"] {{
        background:{T['muted']}22 !important; color:{T['text']} !important;
    }}
    [class*="st-key-watering_"] button[kind="secondary"] p {{ color:{T['text']} !important; }}
    [class*="st-key-watering_"] button[kind="primary"] {{
        background:{T['muted']} !important; color:#fff !important;
    }}
    [class*="st-key-watering_"] button[kind="primary"] p {{ color:#fff !important; }}

    /* "종목별 보유현황" 타이틀 옆 등락률순 토글 — 라벨 없이 점 하나만, 아래 정렬 라디오
       알약과 같은 계열의 작은 크기(new1에서 먼저 만들고 포팅함, 2026-08-28). */
    [class*="st-key-change_sort_toggle"] {{ width:auto !important; }}
    [class*="st-key-change_sort_toggle"] button {{
        background:transparent !important; border:none !important; box-shadow:none !important;
        padding:2px 4px !important; min-height:0 !important; height:auto !important;
        line-height:1 !important;
    }}
    [class*="st-key-change_sort_toggle"] button p {{
        font-size:15px !important; line-height:1 !important;
    }}
    [class*="st-key-change_sort_toggle"] button[kind="secondary"] p {{ color:{T['muted2']} !important; }}
    [class*="st-key-change_sort_toggle"] button[kind="primary"] p {{ color:{UP_COLOR} !important; }}

    /* "종목별 보유현황" 타이틀 줄 3칸만 전역 등폭 규칙을 덮어써서 원하는 비율로 */
    [class*="st-key-holdings_title_row"] div[data-testid="stColumn"]:nth-of-type(1) {{
        flex: 6 1 0 !important;
    }}
    [class*="st-key-holdings_title_row"] div[data-testid="stColumn"]:nth-of-type(2) {{
        flex: 1 1 0 !important;
    }}
    [class*="st-key-holdings_title_row"] div[data-testid="stColumn"]:nth-of-type(3) {{
        flex: 3 1 0 !important;
    }}

    .tx-card {{ background:{T['card']}; border:1px solid {T['border']}; border-radius:10px; padding:10px 14px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; }}
    .tx-left {{ font-size:13px; }}
    .tx-left .name {{ font-weight:700; color:{T['text']}; }}
    .tx-left .meta {{ color:{T['muted']}; font-size:11.5px; }}
    .tx-right {{ text-align:right; font-size:13px; font-weight:700; }}

    /* ---- 옅은/짙은 회색 버튼: 눌러도 색 안 바뀌게 강제 고정 ---- */
    div.stButton > button,
    div.stButton > button:hover,
    div.stButton > button:active,
    div.stButton > button:focus,
    div.stButton > button:focus:not(:active) {{
        background-color: {T['card2']} !important;
        color: {T['text']} !important;
        border: 1px solid {T['border']} !important;
        box-shadow: none !important;
        border-radius: 8px;
        font-weight: 600;
        font-size: 11px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding: 0.2rem 0.35rem;
        min-height: 1.7rem;
    }}
    div.stButton > button p {{ color: {T['text']} !important; }}
    div.stFormSubmitButton > button,
    div.stFormSubmitButton > button:hover,
    div.stFormSubmitButton > button:active,
    div.stFormSubmitButton > button:focus {{
        background-color: {T['card2']} !important;
        color: {T['text']} !important;
        border: 1px solid {T['border']} !important;
        box-shadow: none !important;
    }}
    div[data-testid="stPopover"] > div > button,
    div[data-testid="stPopover"] > div > button:hover,
    div[data-testid="stPopover"] > div > button:active,
    div[data-testid="stPopover"] > div > button:focus {{
        background-color: {T['card2']} !important;
        color: {T['text']} !important;
        border: 1px solid {T['border']} !important;
        box-shadow: none !important;
    }}

    [data-testid="stExpander"],
    [data-testid="stExpander"] > details,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary > div,
    [data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{
        background-color: {T['card']} !important;
        border-color: {T['border']} !important;
        border-radius: 12px !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary:hover,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] svg {{
        color: {T['text']} !important;
        fill: {T['text']} !important;
        background-color: {T['card']} !important;
    }}

    div[data-testid="stTextInput"] div,
    div[data-testid="stNumberInput"] div,
    div[data-testid="stSelectbox"] div,
    div[data-testid="stDateInput"] div,
    div[data-testid="stTextArea"] div,
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"] {{
        background-color: {T['card2']} !important;
        border-color: {T['border']} !important;
        box-shadow: none !important;
    }}
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stSelectbox"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stTextArea"] textarea,
    input, textarea, select {{
        background-color: transparent !important;
        color: {T['text']} !important;
        border: none !important;
    }}
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="select"] > div:first-child {{
        border: 1px solid {T['border']} !important;
        border-radius: 8px !important;
    }}

    /* 드롭다운을 눌렀을 때 뜨는 목록(팝업)은 별도 레이어라 위 규칙이 안 먹어서 따로 지정 */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] div,
    div[data-baseweb="menu"],
    ul[role="listbox"] {{
        background-color: {T['card2']} !important;
    }}
    li[role="option"] {{
        background-color: {T['card2']} !important;
        color: {T['text']} !important;
    }}
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {{
        background-color: {T['border']} !important;
        color: {T['text']} !important;
    }}
    button[data-testid="stNumberInputStepDown"],
    button[data-testid="stNumberInputStepUp"],
    button[data-testid="stNumberInputStepDown"]:hover,
    button[data-testid="stNumberInputStepUp"]:hover {{
        background-color: {T['card2']} !important;
        border: 1px solid {T['border']} !important;
        color: {T['text']} !important;
    }}
    svg {{ fill: {T['muted']} !important; }}

    /* 라디오/토글: 동그라미 표시를 완전히 숨기고 텍스트 알약(pill)만 남김 */
    div[data-testid="stToggle"] label,
    div[data-testid="stToggle"] span,
    div[data-testid="stToggle"] div,
    div[data-testid="stToggle"] [role="switch"] {{
        background-color: {T['card2']} !important;
        border-color: {T['border']} !important;
    }}
    div[data-testid="stToggle"] [role="switch"][aria-checked="true"] {{
        background-color: {T['muted2']} !important;
    }}
    div[data-testid="stToggle"] [role="switch"] > div {{
        background-color: #fff !important;
    }}
    div[role="radiogroup"] {{
        flex-wrap: nowrap !important;
        gap: 3px 4px !important;
    }}
    div[role="radiogroup"] label {{
        background-color: {T['card2']} !important;
        border: 1px solid {T['border']} !important;
        border-radius: 7px !important;
        padding: 2px 6px !important;
        margin: 0 !important;
        min-height: 0 !important;
        flex-shrink: 1 !important;
    }}
    div[role="radiogroup"] label > *:first-child,
    div[role="radiogroup"] label svg,
    div[role="radiogroup"] [data-baseweb="radio"] > div:first-child {{
        display: none !important;
        width: 0 !important;
        height: 0 !important;
    }}
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {{
        font-size: 11px !important;
        color: {T['text']} !important;
        white-space: nowrap;
    }}
    div[role="radiogroup"] label[aria-checked="true"] {{
        border: 1.5px solid {T['muted2']} !important;
        font-weight: 700;
    }}
    /* 모든 가로 배치(달력 포함)를 어떤 화면 크기에서도 한 줄로 강제 */
    div[data-testid="stHorizontalBlock"] {{
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 3px !important;
    }}
    div[data-testid="column"],
    div[data-testid="stColumn"] {{
        width: 0 !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        padding: 0 1px !important;
    }}
    div.stButton > button {{
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
    }}
</style>
""", unsafe_allow_html=True)


def check_password() -> bool:
    if "app_password" not in st.secrets:
        return True
    if st.session_state.get("authed"):
        return True
    st.markdown('<div class="brand">Meritz Orchestra</div>', unsafe_allow_html=True)
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if pw:
        if pw == st.secrets["app_password"]:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False


def _render_holding_detail(r: dict, tx: pd.DataFrame, T: dict):
    """보유종목 카드를 눌렀을 때 펼쳐지는 상세 — 매수/매도 요약 + "물타기 적정성" 그래프.
    new1의 동일 함수를 포팅함(2026-08-28) — meritz는 종목마다 통화(원/USD)가 달라서, 금액
    표시 단위(원 vs $)만 종목의 통화에 맞춰 분기함. 실현손익은 통화와 무관하게 항상 원화
    (apply_transaction이 매수/매도 시점에 원화로 환산해서 저장하므로)."""
    name = r["종목명"]
    is_usd = r.get("통화") == "USD"
    unit = "$" if is_usd else "원"
    amt_fmt = (lambda v: f"${v:,.2f}") if is_usd else (lambda v: f"{v:,.0f}원")
    price_fmt = (lambda v: f"${v:,.2f}") if is_usd else (lambda v: f"{v:,.0f}원")

    trades = get_holding_trade_points(tx, name)
    buys = trades[trades["구분"] == "매수"]
    if buys.empty:
        st.caption("매수 기록을 찾을 수 없습니다.")
        return

    all_time = get_holding_trade_summary_all_time(tx, name)
    all_time_color = UP_COLOR if all_time["realized_pnl"] >= 0 else DOWN_COLOR
    summary = get_holding_trade_summary(tx, name)
    realized_color = UP_COLOR if summary["realized_pnl"] >= 0 else DOWN_COLOR
    st.markdown(f"""
    <div class="trade-summary">
        <span class="trade-summary-label">누적</span>
        <span>매수 <b>{all_time['buy_count']}건</b> · {amt_fmt(all_time['buy_amount'])}</span>
        <span>매도 <b>{all_time['sell_count']}건</b> · {amt_fmt(all_time['sell_amount'])}
            (실현손익 <span style="color:{all_time_color}">{all_time['realized_pnl']:,.0f}원</span>)</span>
    </div>
    <div class="trade-summary">
        <span class="trade-summary-label">이번 사이클</span>
        <span>매수 <b>{summary['buy_count']}건</b> · {amt_fmt(summary['buy_amount'])}</span>
        <span>매도 <b>{summary['sell_count']}건</b> · {amt_fmt(summary['sell_amount'])}
            (실현손익 <span style="color:{realized_color}">{summary['realized_pnl']:,.0f}원</span>)</span>
    </div>
    """, unsafe_allow_html=True)

    entry_date = buys.iloc[0]["날짜"]
    entry_price = float(buys.iloc[0]["단가"])
    current_price = float(r["현재가"])
    avg_price = float(r["평단가"])
    today = today_kst_str()
    sells = trades[trades["구분"] == "매도"]

    avg_path = get_holding_avg_price_path(tx, name)
    avg_x = list(avg_path["날짜"]) + [today]
    avg_y = list(avg_path["평단가"]) + [avg_price]

    hover_price = "%{x}<br>%{y:,.2f}" + unit + "<extra></extra>" if is_usd else "%{x}<br>%{y:,.0f}" + unit + "<extra></extra>"
    hover_avg = ("%{x}<br>평단가 %{y:,.2f}" + unit + "<extra></extra>") if is_usd else ("%{x}<br>평단가 %{y:,.0f}" + unit + "<extra></extra>")
    hover_buy = ("%{x}<br>매수 %{y:,.2f}" + unit + " · %{customdata:.0f}주<extra></extra>") if is_usd else ("%{x}<br>매수 %{y:,.0f}" + unit + " · %{customdata:.0f}주<extra></extra>")
    hover_sell = ("%{x}<br>매도 %{y:,.2f}" + unit + " · %{customdata:.0f}주<extra></extra>") if is_usd else ("%{x}<br>매도 %{y:,.0f}" + unit + " · %{customdata:.0f}주<extra></extra>")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[entry_date, today], y=[entry_price, current_price], mode="lines+markers",
        name="현재가", line=dict(color=T["muted"], width=2, dash="dot"),
        marker=dict(size=6, color=T["muted"]),
        hovertemplate=hover_price,
    ))
    fig.add_trace(go.Scatter(
        x=avg_x, y=avg_y, mode="lines", name="평단가",
        line=dict(color=DOWN_COLOR, width=2, shape="hv"),
        hovertemplate=hover_avg,
    ))
    fig.add_trace(go.Scatter(
        x=buys["날짜"], y=buys["단가"], mode="markers", name="매수",
        marker=dict(size=11, color=DOWN_COLOR, symbol="triangle-up"),
        customdata=buys["수량"],
        hovertemplate=hover_buy,
    ))
    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells["날짜"], y=sells["단가"], mode="markers", name="매도",
            marker=dict(size=11, color=UP_COLOR, symbol="triangle-down"),
            customdata=sells["수량"],
            hovertemplate=hover_sell,
        ))
    fig.add_hline(y=entry_price, line_dash="dash", line_color=T["muted2"], line_width=1,
                  annotation_text="최초진입가", annotation_font_size=10,
                  annotation_font_color=T["muted2"])
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=20, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=T["text"], size=11),
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5,
                    bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, tickfont=dict(size=9, color=T["muted"]), fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor=T["border"], tickfont=dict(size=9, color=T["muted"]),
                   tickformat=(",.2f" if is_usd else ",.0f"), fixedrange=True),
        hovermode="closest",
        dragmode=False,
    )
    st.plotly_chart(fig, width="stretch", config={
        "displayModeBar": False, "scrollZoom": False, "doubleClick": False,
    }, key=f"holding_chart_{r['종목코드']}")

    pct_current = (current_price - entry_price) / entry_price * 100 if entry_price else 0.0
    pct_avg = (avg_price - entry_price) / entry_price * 100 if entry_price else 0.0
    cur_c = UP_COLOR if pct_current >= 0 else DOWN_COLOR
    avg_c = UP_COLOR if pct_avg >= 0 else DOWN_COLOR
    st.markdown(
        f"<div style='font-size:12px;color:{T['muted']};display:flex;justify-content:space-between;"
        f"margin-bottom:12px;'>"
        f"<span>현재가는 최초진입가 대비 <span style='color:{cur_c}'>{pct_current:+.1f}%</span></span>"
        f"<span>내 평단가는 최초진입가 대비 <span style='color:{avg_c}'>{pct_avg:+.1f}%</span></span>"
        f"</div>", unsafe_allow_html=True)


if not check_password():
    st.stop()

col_title, col_label, col_theme = st.columns([2.2, 1, 0.9])
with col_title:
    st.markdown('<div class="brand">Meritz Orchestra</div>', unsafe_allow_html=True)
with col_label:
    st.markdown(
        f"<div style='text-align:right;font-size:11px;color:{T['muted']};padding-top:12px;'>화면</div>",
        unsafe_allow_html=True,
    )
with col_theme:
    is_dark = st.session_state["theme"] == "dark"
    new_dark = st.toggle("다크", value=is_dark, key="theme_switch", label_visibility="collapsed")
    if new_dark != is_dark:
        st.session_state["theme"] = "dark" if new_dark else "light"
        st.rerun()

holdings = load_holdings()
state = load_state()
tx = load_transactions()

if "index_quotes" not in st.session_state:
    st.session_state["index_quotes"] = fetch_index_quotes()
if "fx_rate" not in st.session_state:
    st.session_state["fx_rate"] = fetch_fx_rate() or 1.0

fx_rate = st.session_state["fx_rate"]

# 앱을 새로 열었을 때(세션당 1회) 자동으로 시세를 한 번 새로고침 — new1에서 먼저 만들고
# 포팅함(2026-08-28). "시세 새로고침" 버튼과 완전히 같은 로직을 세션 시작 시 1회 자동
# 실행하는 것 — 버튼은 그대로 남아있어 이후에도 수동으로 또 쓸 수 있음.
auto_refresh_triggered = False
if "auto_refreshed" not in st.session_state:
    st.session_state["auto_refreshed"] = True
    auto_refresh_triggered = True

top_l, top_r = st.columns([5, 2])
with top_r:
    refresh_clicked_top = st.button("시세 새로고침", use_container_width=True, key="refresh_btn_top")

if refresh_clicked_top or auto_refresh_triggered:
    with st.spinner("종목명으로 시세를 찾는 중..."):
        holdings, refresh_report = refresh_all_prices(holdings)
        st.session_state["index_quotes"] = fetch_index_quotes()
        st.session_state["fx_rate"] = fetch_fx_rate() or fx_rate
        fx_rate = st.session_state["fx_rate"]
        df_top, stock_val_top, total_assets_top, unreal_top = compute_metrics(holdings, state["cash"], fx_rate)
        snapshot_history(total_assets_top, total_assets_top + unreal_top)
        snapshot_sector_history(compute_sector_weights(df_top))
        # ---- 지수 대비 계좌(국내주식만) 스냅샷: 지수 종가 + 국내주식 평가금액 + 시장캐시 ----
        _iq = st.session_state.get("index_quotes") or {}
        if _iq.get("KOSPI") and _iq.get("KOSDAQ"):
            snapshot_index_history(_iq["KOSPI"].get("price"), _iq["KOSDAQ"].get("price"))
        _dom = df_top[df_top["통화"].fillna("원") != "USD"] if "통화" in df_top else df_top
        snapshot_dom_asset_history(float(pd.to_numeric(_dom["평가금액"], errors="coerce").fillna(0).sum()))
        refresh_market_cache(holdings[holdings["통화"].fillna("원") != "USD"] if "통화" in holdings else holdings)
    if refresh_report["updated"]:
        st.toast(f"{refresh_report['updated']}개 종목 시세 갱신 완료")
    if refresh_report["unresolved"]:
        st.warning("종목명을 찾지 못했어요(직접 입력 필요): " + ", ".join(refresh_report["unresolved"]))
    if refresh_report["failed"]:
        st.warning("시세를 못 가져왔어요(직접 입력 필요): " + ", ".join(refresh_report["failed"]))
    for err in refresh_report["quote_errors"]:
        st.warning(err)
    st.rerun()

tab_port, tab_tx = st.tabs(["포트폴리오", "거래 기록"])

# ==================================================================== #
# 탭 1: 포트폴리오
# ==================================================================== #
with tab_port:
    df, stock_valuation, total_assets, unrealized_loss = compute_metrics(holdings, state["cash"], fx_rate)
    total_cost = df["매입금액"].sum()
    stock_profit = stock_valuation - total_cost
    stock_profit_pct = (stock_profit / total_cost * 100) if total_cost else 0

    capital_return = total_assets - state["initial"]
    capital_return_pct = (capital_return / state["initial"] * 100) if state["initial"] else 0

    today_str = today_kst_str()
    today_tx = tx[tx["날짜"].astype(str) == today_str]
    daily_pnl = pd.to_numeric(
        today_tx.loc[today_tx["구분"] == "매도", "실현손익"], errors="coerce"
    ).sum()

    color = UP_COLOR if stock_profit >= 0 else DOWN_COLOR
    sign = "+" if stock_profit >= 0 else ""
    cap_color = UP_COLOR if capital_return >= 0 else DOWN_COLOR
    cap_sign = "+" if capital_return >= 0 else ""
    daily_color = UP_COLOR if daily_pnl > 0 else (DOWN_COLOR if daily_pnl < 0 else T["muted"])
    daily_sign = "+" if daily_pnl > 0 else ""

    # ---- 오늘의 거래 요약 (매수/매도 총금액) ----
    buy_tx = today_tx[today_tx["구분"] == "매수"].copy()
    sell_tx = today_tx[today_tx["구분"] == "매도"].copy()
    buy_total_amt = (pd.to_numeric(buy_tx["수량"], errors="coerce") * pd.to_numeric(buy_tx["단가"], errors="coerce")).sum()
    sell_total_amt = (pd.to_numeric(sell_tx["수량"], errors="coerce") * pd.to_numeric(sell_tx["단가"], errors="coerce")).sum()
    total_trade_count = len(today_tx)

    daily_trade_html = f"""
    <div class="daily-trade-box">
        <div class="daily-trade-count">일일거래 총 {total_trade_count}회
            <span>(매수 {len(buy_tx)}건 · 매도 {len(sell_tx)}건)</span>
        </div>
        <div class="daily-trade-row"><span class="tag-label" style="color:{UP_COLOR}">매수</span>
            <span class="trade-chip"><b>{buy_total_amt:,.0f}원</b></span></div>
        <div class="daily-trade-row"><span class="tag-label" style="color:{DOWN_COLOR}">매도</span>
            <span class="trade-chip"><b>{sell_total_amt:,.0f}원</b></span></div>
    </div>
    """

    st.markdown(f"""
    <div class="summary-box">
        <div class="summary-label">보유종목 평가손익</div>
        <span class="summary-main" style="color:{color}">{sign}{stock_profit:,.0f}원</span>
        <span class="summary-sub" style="color:{color}">{sign}{stock_profit_pct:.2f}%</span>
        <div class="summary-grid">
            <div>예수금<b>{state['cash']:,.0f}원</b></div>
            <div>총 매입<b>{total_cost:,.0f}원</b></div>
            <div>총 평가<b>{stock_valuation:,.0f}원</b></div>
            <div>총자산<b>{total_assets:,.0f}원</b></div>
            <div>일일손익<b style="color:{daily_color}">{daily_sign}{daily_pnl:,.0f}원</b></div>
            <div>보유종목<b>{len(df)}개</b></div>
        </div>
        <div class="capital-line">최초 자본 10,000,000원 대비&nbsp;
            <b style="color:{cap_color}">{cap_sign}{capital_return:,.0f}원 ({cap_sign}{capital_return_pct:.2f}%)</b>
        </div>
        {daily_trade_html}
    </div>
    """, unsafe_allow_html=True)

    # ---- 섹터 비중 도넛 + 목표 비중 관리 ----
    with st.expander("섹터 비중 보기", expanded=False):
        include_cash = st.toggle("예수금 포함", value=st.session_state.get("include_cash", True), key="cash_toggle")
        st.session_state["include_cash"] = include_cash

        # 도넛/막대 공통 색상: 주식(예수금 제외) 비중 기준으로 순위를 매겨 고정 배정
        stock_weights = compute_sector_weights(df)  # {섹터그룹: 주식 총자산 대비 %}
        stock_weight_rank = sorted(stock_weights.items(), key=lambda x: x[1], reverse=True)
        color_map = {name: SECTOR_PALETTE[i % len(SECTOR_PALETTE)] for i, (name, _) in enumerate(stock_weight_rank)}

        df_grp = df.copy()
        df_grp["섹터그룹"] = df_grp["섹터"].apply(group_sector)
        sector_val = df_grp.groupby("섹터그룹")["평가금액"].sum().to_dict()
        if include_cash and state["cash"] > 0:
            sector_val[CASH_LABEL] = state["cash"]
        sector_items = sorted(sector_val.items(), key=lambda x: x[1], reverse=True)
        denom = sum(v for _, v in sector_items)

        if denom > 0 and sector_items:
            labels = [s for s, _ in sector_items]
            values = [v for _, v in sector_items]
            colors = [color_map.get(lbl, T["cash_dot"] if lbl == CASH_LABEL else T["muted2"]) for lbl in labels]

            fig, ax = plt.subplots(figsize=(4.6, 4.6))
            fig.patch.set_alpha(0)
            ax.pie(values, colors=colors, startangle=90, counterclock=False,
                   wedgeprops=dict(width=0.38, edgecolor=T["card"], linewidth=1.2))
            ax.set(aspect="equal")
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            legend_html = '<div class="legend-wrap">'
            for lbl, val, c in zip(labels, values, colors):
                pct = val / denom * 100
                legend_html += (f'<div class="legend-item"><span class="legend-dot" '
                                 f'style="background:{c}"></span>{lbl} '
                                 f'<span class="legend-pct">{pct:.1f}%</span></div>')
            legend_html += "</div>"
            st.markdown(legend_html, unsafe_allow_html=True)
        else:
            st.info("종목/예수금 데이터가 있으면 섹터 비중이 표시됩니다.")

        # ---- 섹터별 현재 비중 막대 (주식 총자산 대비, 예수금 제외) + 목표 비중 ----
        if stock_weight_rank:
            sec_hist = load_sector_history()
            prev_weights = {}
            if not sec_hist.empty:
                today_str_ = today_kst_str()
                past_dates = sorted(d for d in sec_hist["날짜"].unique() if d < today_str_)
                if past_dates:
                    prev_date = past_dates[-1]
                    prev_weights = sec_hist[sec_hist["날짜"] == prev_date].set_index("섹터그룹")["비중"].to_dict()

            if st.session_state.get("sector_trend_pick") not in stock_weights:
                st.session_state.sector_trend_pick = None

            SCALE_MAX = 40.0  # 종목 특성상 한 섹터가 40%를 넘지 않는다는 전제의 고정 스케일(배터리 게이지 방식)

            for name, pct in stock_weight_rank:
                color = color_map.get(name, "#888")
                width_pct = max(min(pct / SCALE_MAX * 100, 100), 0)
                target = SECTOR_TARGETS.get(name)
                target_marker = ""
                target_sublabel = ""
                if target is not None:
                    target_pos = max(min(target / SCALE_MAX * 100, 100), 0)
                    target_marker = f'<div class="sector-target-marker" style="left:{target_pos}%"></div>'
                    target_sublabel = f'<div class="sector-target-label" style="left:{target_pos}%">{target:.0f}%</div>'
                delta_html = ""
                if name in prev_weights:
                    delta = pct - prev_weights[name]
                    if abs(delta) >= 0.05:
                        dcolor = UP_COLOR if delta > 0 else DOWN_COLOR
                        dsign = "+" if delta > 0 else ""
                        delta_html = f'<span class="delta" style="color:{dcolor}">{dsign}{delta:.1f}%p</span>'

                is_open = st.session_state.sector_trend_pick == name
                c1, c2, c3 = st.columns([1.05, 3.1, 1.4])
                with c1:
                    label = f"▾ {name}" if is_open else name
                    if st.button(label, key=f"sector_pick_{name}", use_container_width=True):
                        st.session_state.sector_trend_pick = None if is_open else name
                        st.rerun()
                with c2:
                    st.markdown(
                        f'<div class="sector-bar-track">'
                        f'<div class="sector-bar-fill" style="background:{color}; width:{width_pct}%"></div>'
                        f'{target_marker}{target_sublabel}</div>',
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown(
                        f'<div class="sector-bar-pct"><span class="cur">{pct:.1f}%</span>{delta_html}</div>',
                        unsafe_allow_html=True,
                    )

                if is_open:
                    if not sec_hist.empty and name in sec_hist["섹터그룹"].unique():
                        series = sec_hist[sec_hist["섹터그룹"] == name].sort_values("날짜")
                        dates = series["날짜"].tolist()
                        vals = series["비중"].tolist()

                        fig2, ax2 = plt.subplots(figsize=(4.6, 2.2))
                        fig2.patch.set_alpha(0)
                        ax2.set_facecolor("none")
                        x2 = list(range(len(dates)))
                        ax2.plot(x2, vals, color=color, linewidth=2.0, marker="o", markersize=3)
                        ax2.plot([x2[-1]], [vals[-1]], marker="o", markersize=7, color=color)
                        for xi, yi in zip(x2, vals):
                            ax2.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 7),
                                         ha="center", fontsize=8, color=T["text"])
                        if target is not None:
                            ax2.axhline(target, color=T["muted2"], linewidth=1, linestyle="--")
                        ax2.set_ylim(0, 40)
                        ax2.set_xticks(x2)
                        ax2.set_xticklabels([d[5:] for d in dates], fontsize=8, color=T["muted"])
                        ax2.tick_params(axis="y", labelsize=8, colors=T["muted"])
                        for spine in ax2.spines.values():
                            spine.set_visible(False)
                        ax2.grid(axis="y", color=T["border"], linewidth=0.6)
                        st.pyplot(fig2, use_container_width=True)
                        plt.close(fig2)
                    else:
                        st.info("시세 새로고침 또는 거래 기록을 하면 그날의 섹터 비중이 저장되어 추이가 쌓입니다.")

    # ---- Up/Down: 청산 종목 추적 ----
    with st.expander("Up/Down", expanded=False):
        updown_mode = st.radio("모드", ["DOWN", "UP"], horizontal=True,
                                label_visibility="collapsed", key="updown_mode")

        if st.button("새로고침", key="updown_refresh", use_container_width=True):
            closed = get_closed_out_last_sells(holdings, tx)
            results = []
            if not closed.empty:
                with st.spinner("청산 종목 현재가 조회 중..."):
                    prices = get_current_prices_for_names(closed["종목명"].tolist())
                for _, row in closed.iterrows():
                    cp = prices.get(row["종목명"])
                    if cp is None:
                        continue
                    pct = (cp - row["매도가"]) / row["매도가"] * 100
                    results.append({
                        "종목명": row["종목명"], "매도일": row["매도일"],
                        "매도가": row["매도가"], "현재가": cp, "pct": pct,
                    })
            st.session_state["updown_results"] = results
            st.session_state["updown_checked_at"] = now_kst_str()
            st.rerun()

        updown_results = st.session_state.get("updown_results")
        updown_checked_at = st.session_state.get("updown_checked_at")

        if updown_results is None:
            st.caption("새로고침을 누르면 청산(완전 매도)된 종목의 현재가를 마지막 매도가와 비교합니다.")
        else:
            if updown_checked_at:
                st.caption(f"마지막 조회: {updown_checked_at}")
            threshold = 3.0
            if updown_mode == "DOWN":
                filtered = sorted([r for r in updown_results if r["pct"] <= -threshold], key=lambda r: r["pct"])
                updown_color = DOWN_COLOR
            else:
                filtered = sorted([r for r in updown_results if r["pct"] >= threshold], key=lambda r: -r["pct"])
                updown_color = UP_COLOR

            if not filtered:
                st.caption("조건에 해당하는 종목이 없습니다.")
            else:
                rows_html = "".join(
                    f'<div class="updown-row"><span class="name">{r["종목명"]}</span>'
                    f'<span class="pct" style="color:{updown_color}">{"+" if r["pct"] >= 0 else ""}{r["pct"]:.1f}%</span>'
                    f'<span class="detail">{r["매도가"]:,.0f} → {r["현재가"]:,.0f}</span></div>'
                    for r in filtered
                )
                st.markdown(rows_html, unsafe_allow_html=True)

    # ---- 종목별 보유현황 ----
    SORT_OPTIONS = {"비중": "weight", "섹터": "sector", "현재가": "price",
                     "평가금액": "valuation", "손익": "profit"}
    if "sort_mode" not in st.session_state:
        st.session_state.sort_mode = "weight"
    if "change_sort_active" not in st.session_state:
        st.session_state.change_sort_active = False

    last_updated = ""
    updated_vals = [v for v in df["업데이트시각"].tolist() if v]
    if updated_vals:
        last_updated = max(updated_vals)

    # 전역 CSS(`div[data-testid="stColumn"] { flex:1 1 0 !important; }`)가 모든 st.columns()
    # 비율을 강제로 동일폭으로 만들어버리므로, 이 줄만 st.container(key=...)로 감싸서
    # [class*="st-key-holdings_title_row"] 스코프 CSS로 비율을 다시 덮어씀(new1에서 먼저
    # 발견·수정하고 포팅함, 2026-08-28).
    with st.container(key="holdings_title_row"):
        col_title2, col_change_toggle, col_updated = st.columns(3)
        with col_title2:
            st.markdown("##### 종목별 보유현황")
        with col_change_toggle:
            # 매일 가장 먼저 확인하는 기준이라 타이틀 옆에서 바로 토글할 수 있게 함. 라벨
            # 없이 동그라미 점 하나만 — 안 눌림=옅은 회색, 눌림=빨강. 아래 정렬 라디오와는
            # 독립된 별도 상태(change_sort_active)로 두고, 라디오 옵션 목록엔 "등락률"을
            # 안 넣음(중복 노출 방지).
            is_change_sort = st.session_state.change_sort_active
            if st.button("●", key="change_sort_toggle",
                         type="primary" if is_change_sort else "secondary",
                         help="등락률순 정렬"):
                st.session_state.change_sort_active = not is_change_sort
                st.rerun()
        with col_updated:
            st.markdown(
                f"<div style='text-align:right;font-size:11px;color:{T['muted2']};padding-top:10px;'>{last_updated}</div>",
                unsafe_allow_html=True,
            )

    # ---- 코스피 / 코스닥 지수 (상단 새로고침에 같이 갱신됨) ----
    idx = st.session_state.get("index_quotes") or {}
    if idx:
        idx_col1, idx_col2 = st.columns(2)
        for idx_col, (code, label) in zip((idx_col1, idx_col2), (("KOSPI", "코스피"), ("KOSDAQ", "코스닥"))):
            d = idx.get(code)
            if not d:
                continue
            ic = UP_COLOR if d["change"] >= 0 else DOWN_COLOR
            isign = "+" if d["change"] >= 0 else ""
            with idx_col:
                st.markdown(f"""
                <div style="background:{T['card']}; border:1px solid {T['border']}; border-radius:8px;
                            padding:5px 10px; margin-bottom:8px; display:flex; align-items:center;
                            justify-content:space-between; gap:6px;">
                    <span style="font-size:11px; color:{T['muted']}; flex-shrink:0;">{label}</span>
                    <span style="font-size:13px; font-weight:700; color:{T['text']};">{d['price']:,.2f}</span>
                    <span style="font-size:10px; color:{ic}; line-height:1.25; text-align:right; flex-shrink:0;">
                        {isign}{d['change']:,.1f}<br>{isign}{d['change_pct']:.2f}%
                    </span>
                </div>
                """, unsafe_allow_html=True)

    labels = list(SORT_OPTIONS.keys())
    cur_label = next(k for k, v in SORT_OPTIONS.items() if v == st.session_state.sort_mode)
    chosen = st.radio("정렬 기준", labels, index=labels.index(cur_label),
                       horizontal=True, label_visibility="collapsed", key="sort_radio")
    st.session_state.sort_mode = SORT_OPTIONS[chosen]

    sector_color_map = {}
    for i, s in enumerate(df.sort_values("평가금액", ascending=False)["섹터"].unique()):
        sector_color_map[s] = SECTOR_PALETTE[i % len(SECTOR_PALETTE)]

    mode = "change" if st.session_state.change_sort_active else st.session_state.sort_mode
    if mode == "change":
        df_sorted = df.sort_values("등락률", ascending=False)
    elif mode == "sector":
        sector_totals = df.groupby("섹터")["평가금액"].sum().sort_values(ascending=False)
        sector_order = {s: i for i, s in enumerate(sector_totals.index)}
        df_sorted = df.copy()
        df_sorted["_rank"] = df_sorted["섹터"].map(sector_order)
        df_sorted = df_sorted.sort_values(["_rank", "평가금액"], ascending=[True, False])
    elif mode == "price":
        df_sorted = df.sort_values("현재가", ascending=False)
    elif mode == "valuation":
        df_sorted = df.sort_values("평가금액", ascending=False)
    elif mode == "profit":
        df_sorted = df.sort_values("손익", ascending=False)
    else:
        df_sorted = df.sort_values("비중", ascending=False)

    rows = df_sorted.to_dict("records")

    if not rows:
        st.info("보유 종목이 없습니다. '거래 기록' 탭에서 매수를 기록해보세요.")
    else:
        if "holding_detail_open" not in st.session_state:
            st.session_state.holding_detail_open = None

        for r in rows:
            pc = UP_COLOR if r["손익"] >= 0 else DOWN_COLOR
            psign = "+" if r["손익"] >= 0 else ""
            cc = UP_COLOR if r["등락률"] >= 0 else DOWN_COLOR
            csign = "+" if r["등락률"] >= 0 else ""
            sc = sector_color_map.get(r["섹터"], "#6b7280")
            is_usd = r.get("통화") == "USD"
            price_str = f"${r['현재가']:,.2f}" if is_usd else f"{r['현재가']:,.0f}"
            avg_str = f"${r['평단가']:,.2f}" if is_usd else f"{r['평단가']:,.0f}"

            code = r["종목코드"]
            is_open = st.session_state.holding_detail_open == code

            with st.container(key=f"holding_wrap_{code}"):
                st.markdown(f"""
                <div class="stock-card">
                    <div class="stock-top">
                        <span class="stock-title-group"><span class="stock-name">{r['종목명']}</span></span>
                        <span class="sector-tag" style="background:{sc}22;color:{sc}">{r['섹터']}</span>
                    </div>
                    <div class="stock-grid">
                        <div class="cell"><div class="top">{r['수량']:.0f}주</div><div class="bottom">{r['비중']:.1f}%</div></div>
                        <div class="cell"><div class="top">{price_str}</div><div class="bottom">{avg_str}</div></div>
                        <div class="cell"><div class="top">{r['평가금액']:,.0f}</div><div class="bottom">{r['매입금액']:,.0f}</div></div>
                        <div class="cell">
                            <div class="top" style="color:{pc}">{psign}{r['손익']:,.0f}</div>
                            <div class="bottom"><span style="color:{pc}">{psign}{r['손익률']:.1f}%</span> <span style="color:{cc}">{csign}{r['등락률']:.1f}%</span></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("WATERING", key=f"watering_{code}",
                             type="primary" if is_open else "secondary"):
                    st.session_state.holding_detail_open = None if is_open else code
                    st.rerun()
            if is_open:
                _render_holding_detail(r, tx, T)

# ==================================================================== #
# 탭 2: 거래 기록 + 자산 추이
# ==================================================================== #
with tab_tx:
    df3, stock_val3, total_assets3, unreal3 = compute_metrics(holdings, state["cash"], fx_rate)
    cap_return3 = total_assets3 - state["initial"]
    cap_return_pct3 = (cap_return3 / state["initial"] * 100) if state["initial"] else 0
    c3 = UP_COLOR if cap_return3 >= 0 else DOWN_COLOR
    s3 = "+" if cap_return3 >= 0 else ""

    total_realized = pd.to_numeric(tx.loc[tx["구분"] == "매도", "실현손익"], errors="coerce").sum()
    rc = UP_COLOR if total_realized >= 0 else DOWN_COLOR
    rs = "+" if total_realized >= 0 else ""

    st.markdown(f"""
    <div class="summary-box">
        <div class="summary-label">최초 자본 10,000,000원 대비</div>
        <span class="summary-main" style="color:{c3}">{s3}{cap_return3:,.0f}원</span>
        <span class="summary-sub" style="color:{c3}">{s3}{cap_return_pct3:.2f}%</span>
        <div class="summary-grid">
            <div>현재 총자산<b>{total_assets3:,.0f}원</b></div>
            <div>실현손익 누적<b style="color:{rc}">{rs}{total_realized:,.0f}원</b></div>
            <div>미실현 손실<b style="color:{DOWN_COLOR}">-{unreal3:,.0f}원</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 실현손익 그래프: 누적 실현손익(호버 시 그날 실현손익도 표시) vs 미실현손실 ----
    st.markdown("##### 실현손익 그래프")

    tx_realized = tx[tx["구분"] == "매도"].copy()
    tx_realized["실현손익"] = pd.to_numeric(tx_realized["실현손익"], errors="coerce").fillna(0)
    hist = load_history()

    if tx_realized.empty and hist.empty:
        st.info("거래 기록이 쌓이거나 시세를 새로고침하면 그래프가 그려집니다.")
    else:
        start_candidates = []
        if not tx_realized.empty:
            start_candidates.append(tx_realized["날짜"].min())
        if not hist.empty:
            start_candidates.append(hist["날짜"].min())
        all_dates = pd.date_range(min(start_candidates), today_kst_str()).strftime("%Y-%m-%d").tolist()

        daily_realized = tx_realized.groupby("날짜")["실현손익"].sum()
        daily_values = [float(daily_realized.get(d, 0.0)) for d in all_dates]
        cum_values = list(pd.Series(daily_values).cumsum())

        hist_sorted = hist.sort_values("날짜")
        unreal_dates = hist_sorted["날짜"].tolist()
        unreal_series = (hist_sorted["조정자산"] - hist_sorted["총자산"]).tolist()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=all_dates, y=cum_values, mode="lines+markers", name="실현손익(누적)",
            line=dict(color=UP_COLOR, width=2.5), marker=dict(size=5),
            customdata=daily_values,
            hovertemplate="%{x}<br>누적 실현손익 %{y:,.0f}원<br>이날 실현손익 %{customdata:,.0f}원<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=unreal_dates, y=unreal_series, mode="lines+markers", name="미실현손실",
            line=dict(color=DOWN_COLOR, width=2.5), marker=dict(size=5),
            hovertemplate="%{x}<br>미실현손실 %{y:,.0f}원<extra></extra>",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color=T["muted2"], line_width=1)
        fig.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=45),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=T["text"], size=11),
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5,
                        bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(showgrid=False, tickfont=dict(size=9, color=T["muted"]), fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor=T["border"], zeroline=False,
                       tickfont=dict(size=9, color=T["muted"]), tickformat=",.0f", fixedrange=True),
            hovermode="x unified",
            dragmode=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={
            "displayModeBar": False,
            "scrollZoom": False,
            "doubleClick": False,
        })

    st.divider()

    # ==================================================================== #
    # 지수 대비 계좌 (국내주식만, 레드와이어/USD 제외) — new1 §6-17 포팅
    #  · 코스피(노랑)/코스닥(초록) = anchor일 종가 대비 누적등락(0 중심)
    #  · 내 주식(검정)  = 국내주식 100% 투자로 환산한 누적수익 Rs — 지수와 1:1
    #  · 내 계좌(점선)  = (국내주식평가 + 실제예수금) / D0 − 1
    #    D0 = 10,000,000 − 그 시점까지 레드와이어 순투입 원화액
    # ==================================================================== #
    idx_hist = load_index_history()
    dom_hist = load_dom_asset_history()

    mc = load_market_cache()
    hv = holdings[holdings["통화"].fillna("원") != "USD"].copy() if "통화" in holdings else holdings.copy()
    hv["_v"] = (pd.to_numeric(hv["수량"], errors="coerce").fillna(0)
                * pd.to_numeric(hv["현재가"], errors="coerce").fillna(0))
    hv["_m"] = hv["종목명"].map(mc)
    ks_val = float(hv.loc[hv["_m"] == "KOSPI", "_v"].sum())
    kq_val = float(hv.loc[hv["_m"] == "KOSDAQ", "_v"].sum())
    wk = ks_val / (ks_val + kq_val) if (ks_val + kq_val) > 0 else None

    _wtag = "" if wk is None else (
        f" <span style='font-size:11px;font-weight:400;color:{T['muted']}'>"
        f"보유비중 코스피 {wk * 100:.0f}% · 코스닥 {(1 - wk) * 100:.0f}%</span>"
    )
    st.markdown(f"##### 지수 대비 계좌 <span style='font-size:12px;color:{T['muted2']}'>(국내주식만)</span>{_wtag}",
                unsafe_allow_html=True)

    iva = compute_index_vs_account(tx, dom_hist, idx_hist, state["initial"],
                                    state.get("fee_rate_krw", 0.0), state.get("fee_rate_usd", 0.0),
                                    kospi_weight=wk)
    me, idxc, latest = iva["me"], iva["index"], iva["latest"]

    if me.empty or idxc.empty:
        st.info("시세를 새로고침하면 국내 지수·자산 스냅샷이 쌓여서 그래프가 그려집니다.")
    else:
        def _pct(v):
            return "—" if v is None else f"{v * 100:+.2f}%"

        bench = latest.get("벤치") or (None, None)

        def _color_vs_bench(v, ref):
            if v is None or ref is None:
                return T["text"]
            return UP_COLOR if v >= ref else DOWN_COLOR

        def _row(label, dot_color, dashed, key, color_by_bench):
            cum, day = latest.get(key, (None, None))
            if color_by_bench:
                cc, dc = _color_vs_bench(cum, bench[0]), _color_vs_bench(day, bench[1])
            else:
                cc = dc = T["muted"]
            mark = "┈" if dashed else "●"
            return (
                f"<tr><td style='color:{dot_color}'>{mark}&nbsp;{label}</td>"
                f"<td style='text-align:right;color:{cc}'>{_pct(cum)}</td>"
                f"<td style='text-align:right;color:{dc}'>{_pct(day)}</td></tr>"
            )

        st.markdown(
            "<table style='width:100%;font-size:12px;border-collapse:collapse;margin:-2px 0 4px'>"
            f"<tr style='color:{T['muted2']};font-size:10px'>"
            "<th style='text-align:left'>&nbsp;</th><th style='text-align:right'>누적</th>"
            "<th style='text-align:right'>당일</th></tr>"
            + _row("코스피", KOSPI_COLOR, False, "코스피", False)
            + _row("코스닥", KOSDAQ_COLOR, False, "코스닥", False)
            + _row("내 주식", T["text"], False, "주식", True)
            + _row("내 계좌", T["muted2"], True, "계좌", True)
            + "</table>",
            unsafe_allow_html=True,
        )

        b_cum, b_day = latest.get("벤치", (None, None))
        my_cum, my_day = latest.get("주식", (None, None))

        def _p(v):
            return "—" if v is None or pd.isna(v) else f"{v * 100:+.2f}%"

        st.markdown(
            f"<div style='font-size:11px;color:{T['muted']};margin:0 0 2px'>"
            f"당일  혼합지수 <b>{_p(b_day)}</b>  /  내 주식 <b>{_p(my_day)}</b>"
            f"<span style='color:{T['muted2']}'> · 누적 {_p(b_cum)} / {_p(my_cum)}</span></div>",
            unsafe_allow_html=True,
        )

        basis = iva["sensitivity_basis"]

        def _s(v):
            return "—" if v is None else f"{v:+.2f}"

        def _sens_line(label, a, r, t):
            return (
                f"<div style='font-size:11px;color:{T['muted']};margin:0 0 3px'>"
                f"RP·{label} <span style='color:{T['muted2']}'>({basis})</span>  "
                f"<b style='color:{T['text']}'>누적 {_s(a)}</b> · "
                f"<b style='color:{NEW_COLOR}'>5일 {_s(r)}</b> · "
                f"<b style='color:{UP_COLOR}'>당일 {_s(t)}</b></div>"
            )

        st.markdown(
            "<div style='font-size:10px;color:" + T["muted2"] + ";margin:2px 0 1px'>"
            "RP (relative performance) — 0=시장과 동일, 양수=시장보다 잘함</div>"
            + _sens_line("내 주식", iva["sens_all"], iva["sens_recent"], iva["sens_today"])
            + _sens_line("내 계좌", iva["acct_sens_all"], iva["acct_sens_recent"], iva["acct_sens_today"]),
            unsafe_allow_html=True,
        )

        moves = _index_day_moves(idx_hist).set_index("날짜")
        kd_map = moves["코스피d"].to_dict()
        qd_map = moves["코스닥d"].to_dict()

        def _fmt(v):
            return "—" if v is None or pd.isna(v) else f"{v * 100:+.2f}%"

        def _cell(v, ref):
            if v is None or pd.isna(v):
                return "—"
            s = f"{v * 100:+.2f}%"
            if ref is None or pd.isna(ref):
                return s
            return f"<span style='color:{UP_COLOR if v >= ref else DOWN_COLOR}'>{s}</span>"

        def _ht(label):
            return ("<b>" + label + "</b>  누적 %{customdata[0]} · 당일 %{customdata[1]}<extra></extra>")

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=idxc["날짜"], y=idxc["코스피"], name="코스피", mode="lines",
            line=dict(color=KOSPI_COLOR, width=1.6),
            customdata=[[_fmt(c), _fmt(kd_map.get(d))] for c, d in zip(idxc["코스피"], idxc["날짜"])],
            hovertemplate=_ht("코스피"),
        ))
        fig2.add_trace(go.Scatter(
            x=idxc["날짜"], y=idxc["코스닥"], name="코스닥", mode="lines",
            line=dict(color=KOSDAQ_COLOR, width=1.6),
            customdata=[[_fmt(c), _fmt(qd_map.get(d))] for c, d in zip(idxc["코스닥"], idxc["날짜"])],
            hovertemplate=_ht("코스닥"),
        ))
        fig2.add_trace(go.Scatter(
            x=me["날짜"], y=me["주식수익"], name="내 주식", mode="lines+markers",
            line=dict(color=T["text"], width=2.8), marker=dict(size=5),
            customdata=[[_cell(cr, br), _cell(dr, bd)] for cr, dr, br, bd
                        in zip(me["주식수익"], me["주식당일"], me["벤치누적"], me["벤치당일"])],
            hovertemplate=_ht("내 주식"),
        ))
        fig2.add_trace(go.Scatter(
            x=me["날짜"], y=me["계좌수익"], name="내 계좌", mode="lines",
            line=dict(color=T["muted2"], width=1.8, dash="dot"),
            customdata=[[_cell(cr, br), _cell(dr, bd)] for cr, dr, br, bd
                        in zip(me["계좌수익"], me["계좌당일"], me["벤치누적"], me["벤치당일"])],
            hovertemplate=_ht("내 계좌"),
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color=T["muted2"], line_width=1)
        fig2.update_layout(
            height=275, margin=dict(l=40, r=8, t=8, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=T["text"], size=11), showlegend=False,
            hoverlabel=dict(bgcolor=T["card"], bordercolor=T["border"], align="left",
                            font=dict(size=11, color=T["text"])),
            xaxis=dict(showgrid=False, tickfont=dict(size=9, color=T["muted"]), fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor=T["border"], zeroline=False,
                       tickfont=dict(size=9, color=T["muted"]), tickformat=".1%", fixedrange=True),
            hovermode="x unified", dragmode=False,
        )

        fig_s = go.Figure()
        for col, nm, color, w in (
            ("상대성과누적", "누적", T["text"], 2.6),
            ("상대성과최근", "5일", NEW_COLOR, 2.0),
            ("상대성과당일", "당일", UP_COLOR, 1.4),
        ):
            cd = ["—" if pd.isna(v) else f"{v:+.2f}" for v in me[col]]
            fig_s.add_trace(go.Scatter(
                x=me["날짜"], y=me[col], name=nm, mode="lines+markers",
                line=dict(color=color, width=w), marker=dict(size=4),
                connectgaps=True, customdata=cd,
                hovertemplate="<b>" + nm + "</b> RP %{customdata}<extra></extra>",
            ))
        fig_s.add_hline(y=0, line_dash="dash", line_color=T["muted2"], line_width=1)  # y=0 = 시장 동일
        fig_s.update_layout(
            height=275, margin=dict(l=40, r=8, t=8, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=T["text"], size=11), showlegend=False,
            hoverlabel=dict(bgcolor=T["card"], bordercolor=T["border"], align="left",
                            font=dict(size=11, color=T["text"])),
            xaxis=dict(showgrid=False, tickfont=dict(size=9, color=T["muted"]), fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor=T["border"], zeroline=False,
                       range=[-3.2, 3.2], dtick=1.0,
                       tickfont=dict(size=9, color=T["muted"]), tickformat="+.0f", fixedrange=True,
                       hoverformat="+.2f"),
            hovermode="x unified", dragmode=False,
        )

        cfg = {"displayModeBar": False, "responsive": True, "scrollZoom": False, "doubleClick": False}
        h1 = fig2.to_html(include_plotlyjs="cdn", full_html=False, config=cfg, default_width="100%")
        h2 = fig_s.to_html(include_plotlyjs=False, full_html=False, config=cfg, default_width="100%")
        components.html(
            f"""
<div id="cwrap">
  <div class="track">
    <div class="slide">{h1}</div>
    <div class="slide">{h2}</div>
  </div>
  <div class="dots"><span class="dot on"></span><span class="dot"></span></div>
</div>
<style>
  body {{ margin:0; background:transparent; }}
  #cwrap .track {{ display:flex; overflow-x:auto; scroll-snap-type:x mandatory; overscroll-behavior-x:contain;
    -webkit-overflow-scrolling:touch; scrollbar-width:none; }}
  #cwrap .track::-webkit-scrollbar {{ display:none; }}
  #cwrap .slide {{ flex:0 0 100%; min-width:0; scroll-snap-align:center; scroll-snap-stop:always; }}
  #cwrap .dots {{ display:flex; justify-content:center; gap:7px; padding:4px 0 0; }}
  #cwrap .dot {{ width:7px; height:7px; border-radius:50%; background:{T['muted2']};
    opacity:.3; transition:opacity .18s, background .18s; }}
  #cwrap .dot.on {{ opacity:1; background:{T['text']}; }}
</style>
<script>
  (function() {{
    var track = document.querySelector('#cwrap .track');
    var dots = document.querySelectorAll('#cwrap .dot');
    function sync() {{
      var i = Math.round(track.scrollLeft / Math.max(track.clientWidth, 1));
      dots.forEach(function(d, j) {{ d.classList.toggle('on', j === i); }});
    }}
    track.addEventListener('scroll', sync, {{passive: true}});
    function rz() {{
      var w = document.querySelector('#cwrap .track').clientWidth;
      if (!w) return;
      document.querySelectorAll('#cwrap .plotly-graph-div').forEach(function(g) {{
        if (window.Plotly) window.Plotly.relayout(g, {{width: w, height: 275}});
      }});
    }}
    window.addEventListener('resize', rz);
    setTimeout(rz, 50); setTimeout(rz, 250); setTimeout(rz, 700);
  }})();
</script>
""",
            height=315,
        )

    st.divider()

    # ---- 거래 내역 (캘린더) ----
    st.markdown("##### 거래 내역")

    if "cal_year" not in st.session_state:
        st.session_state.cal_year = now_kst().year
        st.session_state.cal_month = now_kst().month
    if "selected_tx_date" not in st.session_state:
        st.session_state.selected_tx_date = today_kst_str()

    tx_dates = set(tx["날짜"].astype(str))
    year, month = st.session_state.cal_year, st.session_state.cal_month

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        if st.button("◀", key="cal_prev", use_container_width=True):
            m, y = month - 1, year
            if m < 1:
                m, y = 12, y - 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()
    with nav2:
        st.markdown(
            f"<div style='text-align:center;font-weight:700;padding-top:6px;color:{T['text']}'>"
            f"{year}년 {month}월</div>",
            unsafe_allow_html=True,
        )
    with nav3:
        if st.button("▶", key="cal_next", use_container_width=True):
            m, y = month + 1, year
            if m > 12:
                m, y = 1, y + 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()

    last_day = calendar.monthrange(year, month)[1]

    if st.session_state.selected_tx_date.startswith(f"{year:04d}-{month:02d}"):
        cur_day = int(st.session_state.selected_tx_date.split("-")[2])
    else:
        cur_day = min(now_kst().day, last_day) if (year, month) == (now_kst().year, now_kst().month) else 1

    st.markdown('<div class="cal-grid">', unsafe_allow_html=True)
    wd_cols = st.columns(7)
    for i, wd in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
        wd_cols[i].markdown(
            f"<div style='text-align:center;font-size:10.5px;color:{T['muted2']}'>{wd}</div>",
            unsafe_allow_html=True,
        )

    cal_obj = calendar.Calendar(firstweekday=6)
    weeks = cal_obj.monthdayscalendar(year, month)
    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.write("")
                    continue
                d_str = f"{year:04d}-{month:02d}-{day:02d}"
                has_tx = d_str in tx_dates
                is_sel = day == cur_day
                label = f"{day}●" if has_tx else f"{day}"
                if st.button(label, key=f"day_{d_str}", use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    st.session_state.selected_tx_date = d_str
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    sel = st.session_state.selected_tx_date
    day_tx = tx[tx["날짜"].astype(str) == sel]
    day_realized = pd.to_numeric(day_tx.loc[day_tx["구분"] == "매도", "실현손익"], errors="coerce").sum()

    head_html = f"<b style='color:{T['text']}'>{sel}</b>"
    if day_realized:
        rc = UP_COLOR if day_realized >= 0 else DOWN_COLOR
        rs = "+" if day_realized >= 0 else ""
        head_html += f" <span style='color:{rc};font-size:13px'>({rs}{day_realized:,.0f}원)</span>"
    st.markdown(head_html, unsafe_allow_html=True)

    if day_tx.empty:
        st.info("이 날짜엔 기록된 거래가 없습니다.")
    else:
        for _, r in day_tx.iterrows():
            realized = r["실현손익"]
            right_html = ""
            if r["구분"] == "매도" and str(realized) not in ("", "nan"):
                rv = float(realized)
                rc = UP_COLOR if rv >= 0 else DOWN_COLOR
                rs = "+" if rv >= 0 else ""
                right_html = f'<span style="color:{rc}">{rs}{rv:,.0f}원</span>'
            memo_html = f' · {r["메모"]}' if str(r["메모"]) not in ("", "nan") else ""
            st.markdown(f"""
            <div class="tx-card">
                <div class="tx-left">
                    <span class="name">{r['종목명']}</span>
                    <span class="meta">{r['구분']} {float(r['수량']):.0f}주 @ {float(r['단가']):,.0f}원{memo_html}</span>
                </div>
                <div class="tx-right">{right_html}</div>
            </div>
            """, unsafe_allow_html=True)
