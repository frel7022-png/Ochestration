"""
"지수 대비 계좌"(국내주식만) 지표에 필요한 히스토리 CSV를 소급 생성한다 (new1 §6-17 포팅).

만드는 것:
  1. index_history.csv        — 코스피/코스닥 일별 종가 (asset_history 시작일부터)
  2. dom_asset_history.csv    — 날짜별 "국내주식(통화=원) 평가금액 원화 합계"
                                (레드와이어/USD 제외). asset_history.csv에 있는 날짜마다 한 줄.
  3. stock_market_cache.csv   — 보유 국내종목의 KOSPI/KOSDAQ 구분 (혼합지수 가중치용)

재실행 가능. index_history · stock_market_cache는 통째로 다시 만들고, dom_asset_history는 **있는 날은 안 덮고 빈 날만**
넣는다(2026-11-27부터 — 그 전엔 통째로 다시 만들어 ingest 그날 스냅숏 값이 재생 값으로 바뀌었다). 인자: `--dry`면 저장하지 않고
무엇을 메울지만 찍는다(시세는 받음 — 오프라인 시험이 아님).
결과 CSV는 로컬 데이터 파일이라 세션이 git commit/push 해야 유지된다.

2026-11-27(new1 9시 보고 B 6번 칸 (나) · 대표 부재 위임 11-27 17:02:59): dom_asset_history를 asset_history 날짜만이
아니라 **마지막 반영일(asset_history 끝 날짜)까지의 모든 거래일(index 날짜)**로 만든다 — 매매일지를 몰아 넣어도 매매 없던
날이 비지 않게. 그 날의 값 = 그날까지 거래로 재생한 보유 × 그날 종가(new1 daily_close 꼴). 마지막 반영일 뒤는 안 만든다
(그 뒤 보유를 모르니 — 매매일지가 들어온 날 다시 돌린다). 지난 종가 출처는 실행 끝에 찍는다.
그래서 dom_asset_history 한 파일 안에 두 셈이 섞인다 — 있던 날 = ingest 그날 스냅숏(당시 시세) · 메운 날 = 재생 보유 × 일별 종가.
있던 날을 다시 계산하지 않는 건 지난 값 그대로(new1 원-2026-10-22-12 결 · new1 9시 보고 B 4번 칸)와 같은 쪽이다.
"""

import sys

import pandas as pd

import portfolio_core as core


def _closes_map(code: str, start: str, end: str) -> dict:
    rows = core.fetch_daily_price_history(str(code), start, end)
    return {r["날짜"]: r["종가"] for r in rows}


def _close_on(cmap: dict, date: str):
    prior = [d for d in cmap if d <= date]
    return cmap[max(prior)] if prior else None


def fill_dates(asset_dates: list, idx_dates: list) -> list:
    """dom_asset_history를 만들 날짜 — asset_history 날짜 ∪ (첫날 ~ asset_history 끝 날짜 사이의 index 거래일).
    끝 날짜 뒤 거래일은 넣지 않는다(마지막 반영일 뒤 보유를 모름)."""
    a = sorted(str(d) for d in asset_dates)
    if not a:
        return []
    lo, hi = a[0], a[-1]
    return sorted(set(a) | {str(d) for d in idx_dates if lo <= str(d) <= hi})


def dom_values(dates: list, krw_tx: pd.DataFrame, closes: dict) -> list:
    """날짜마다 {날짜, 국내주식평가} — 그날까지(포함) 거래로 재생한 수량 × 그날 이전 마지막 종가. 수량 ≤ 0 · 종가 없음은 0으로 셈."""
    tx = krw_tx.sort_values("날짜")
    rows = []
    for d in dates:
        qty = tx.loc[tx["날짜"].astype(str) <= d].groupby("종목명")["_signed"].sum()
        val = 0.0
        for nm, q in qty.items():
            if q <= 0:
                continue
            c = _close_on(closes.get(nm, {}), d)
            if c is not None:
                val += float(q) * c
        rows.append({"날짜": d, "국내주식평가": round(val, 2)})
    return rows


def main():
    dry = "--dry" in sys.argv[1:]
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
    if not dry:
        core.save_index_history(idx_df)
    print(f"[{'dry' if dry else '완료'}] index_history.csv {len(idx_df)}일치 ({idx_dates[0]}~{idx_dates[-1]})")

    # 2) dom_asset_history.csv — 국내(통화=원) 거래만으로 각 날짜의 보유수량 × 종가 합
    tx = core.load_transactions()
    tx["수량"] = pd.to_numeric(tx["수량"], errors="coerce").fillna(0.0)
    krw_tx = tx[(tx.get("통화").fillna("원") != "USD")].copy()
    krw_tx = krw_tx[krw_tx["구분"].isin(["매수", "매도"])]   # 입금 · 배당 줄(종목명 · 수량 1)이 들어와도 판 것으로 안 세게(옛 뇌 11-27 — 지금 meritz엔 0줄이라 값 그대로)
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

    old_dom = core.load_dom_asset_history()
    have = set(old_dom["날짜"].astype(str)) if old_dom is not None and not old_dom.empty else set()
    dom_dates = fill_dates(dates, idx_dates)
    filled = [d for d in dom_dates if d not in have]          # 있는 날은 안 덮는다 — 빈 날만
    new_rows = dom_values(filled, krw_tx, closes)
    merged = pd.concat([old_dom, pd.DataFrame(new_rows, columns=["날짜", "국내주식평가"])]) if have else pd.DataFrame(new_rows)
    if not dry and new_rows:
        core.save_dom_asset_history(merged.sort_values("날짜").reset_index(drop=True))
    print(f"[{'dry' if dry else '완료'}] dom_asset_history.csv 있던 {len(have)}일 그대로 · 빈 거래일 {len(filled)}일 메움"
          + (f"({filled[0]}~{filled[-1]})" if filled else "") + f" — 끝 날짜 {dom_dates[-1] if dom_dates else '-'}(asset_history 마지막)")
    if filled:
        print("[출처] 메운 날 값 = 그날까지 거래로 재생한 보유 × 네이버 일별시세 종가(fetch_daily_price_history) — "
              "09-14 ~ 10-22 구간 일별 종가엔 애프터장(NXT) 값이 섞였을 수 있음(new1 쪽 기록 기준 · meritz 쪽은 안 잼). "
              f"한 파일에 두 셈이 섞인다 — 있던 {len(have)}줄 = ingest 그날 스냅숏 그대로 · 메운 {len(filled)}줄 = 재생 × 일별 종가. "
              "메운 날 ↔ 다음 있던 날 사이 하루 등락에 두 셈의 차이(2% 안팎)가 낄 수 있다. 보고 · 커밋 메시지에 이 줄을 밝힌다.")
    if missing_code:
        print(f"[주의] 종목코드 못 찾은 종목(평가에서 빠짐): {', '.join(missing_code)}")

    # 3) stock_market_cache.csv
    if dry:
        return
    dom_h = h[(h.get("통화").fillna("원") != "USD")]
    mm = core.refresh_market_cache(dom_h)
    from collections import Counter
    print(f"[완료] stock_market_cache.csv — {dict(Counter(mm.values()))}, 총 {len(mm)}종목")


if __name__ == "__main__":
    main()
