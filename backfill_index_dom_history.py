"""
"지수 대비 계좌"(국내주식만) 지표에 필요한 히스토리 CSV를 소급 생성한다 (new1 §6-17 포팅).

만드는 것:
  1. index_history.csv        — 코스피/코스닥 일별 종가 (asset_history 시작일부터)
  2. dom_asset_history.csv    — 날짜별 "국내주식(통화=원) 평가금액 원화 합계"
                                (레드와이어/USD 제외). asset_history.csv에 있는 날짜마다 한 줄.
  3. stock_market_cache.csv   — 보유 국내종목의 KOSPI/KOSDAQ 구분 (혼합지수 가중치용)

재실행 가능 — 매번 통째로 다시 만든다. 인자 없음.
결과 CSV는 로컬 데이터 파일이라 세션이 git commit/push 해야 유지된다.
"""

import pandas as pd

import portfolio_core as core


def _closes_map(code: str, start: str, end: str) -> dict:
    rows = core.fetch_daily_price_history(str(code), start, end)
    return {r["날짜"]: r["종가"] for r in rows}


def _close_on(cmap: dict, date: str):
    prior = [d for d in cmap if d <= date]
    return cmap[max(prior)] if prior else None


def main():
    asset_hist = core.load_history()
    if asset_hist.empty:
        print("[중단] asset_history.csv가 비어있음.")
        return
    dates = sorted(asset_hist["날짜"].astype(str).unique())
    anchor, today = dates[0], core.today_kst_str()
    fetch_start = (pd.Timestamp(anchor) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")

    # 1) index_history.csv
    kk = _closes_map("KOSPI", fetch_start, today)
    qq = _closes_map("KOSDAQ", fetch_start, today)
    idx_dates = sorted(d for d in (set(kk) & set(qq)) if d >= anchor)
    idx_df = pd.DataFrame({"날짜": idx_dates,
                           "KOSPI": [kk[d] for d in idx_dates],
                           "KOSDAQ": [qq[d] for d in idx_dates]})
    core.save_index_history(idx_df)
    print(f"[완료] index_history.csv {len(idx_df)}일치 ({idx_dates[0]}~{idx_dates[-1]})")

    # 2) dom_asset_history.csv — 국내(통화=원) 거래만으로 각 날짜의 보유수량 × 종가 합
    tx = core.load_transactions()
    tx["수량"] = pd.to_numeric(tx["수량"], errors="coerce").fillna(0.0)
    krw_tx = tx[(tx.get("통화").fillna("원") != "USD")].copy()
    krw_tx["_signed"] = krw_tx["수량"].where(krw_tx["구분"] == "매수", -krw_tx["수량"])

    # 종목명 → 종목코드 (현재 holdings + 코드 캐시)
    h = core.load_holdings()
    name2code = {r["종목명"]: str(r["종목코드"]) for _, r in h.iterrows() if r["종목코드"]}
    name2code.update({k: v for k, v in core.load_code_cache().items() if v})

    names = sorted(krw_tx["종목명"].dropna().unique())
    closes = {}
    missing_code = []
    for nm in names:
        code = name2code.get(nm)
        if not code or len(code) < 6:
            code = core.resolve_code(nm, core.load_code_cache())
        if not code:
            missing_code.append(nm)
            continue
        closes[nm] = _closes_map(code, fetch_start, today)

    dom_rows = []
    for d in dates:
        val = 0.0
        for nm in names:
            qty = float(krw_tx.loc[krw_tx["날짜"] <= d].groupby("종목명")["_signed"].sum().get(nm, 0.0))
            if qty <= 0:
                continue
            c = _close_on(closes.get(nm, {}), d)
            if c is not None:
                val += qty * c
        dom_rows.append({"날짜": d, "국내주식평가": round(val, 2)})
    core.save_dom_asset_history(pd.DataFrame(dom_rows))
    print(f"[완료] dom_asset_history.csv {len(dom_rows)}일치")
    if missing_code:
        print(f"[주의] 종목코드 못 찾은 종목(평가에서 빠짐): {', '.join(missing_code)}")

    # 3) stock_market_cache.csv
    dom_h = h[(h.get("통화").fillna("원") != "USD")]
    mm = core.refresh_market_cache(dom_h)
    from collections import Counter
    print(f"[완료] stock_market_cache.csv — {dict(Counter(mm.values()))}, 총 {len(mm)}종목")


if __name__ == "__main__":
    main()
