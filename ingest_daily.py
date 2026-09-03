"""
증권사 "일일 매매일지" CSV 한 장을 반영하는 스크립트 (국내 KRW 거래용).

사용법:
    python ingest_daily.py <파일경로> <YYYY-MM-DD>

하는 일:
    1. 해당 파일을 파싱해서 그날의 매수/매도 내역을 뽑아낸다.
    2. transactions.csv에서 같은 날짜에 이미 이 방식으로 반영된 거래가 있으면
       지우고, 이번 내용으로 교체한다 (증권사 CSV는 "그날 하루 전체 누적"이라
       두 번 올려도 중복되지 않게 하기 위함).
    3. transactions.csv 전체를 처음부터 재생(replay)해서 holdings/현금/실현손익을
       다시 계산하고, portfolio_data.csv / transactions.csv / account_state.csv에 저장한다.
    4. 신규 종목의 종목코드를 네이버로 조회해 채운다(시세는 안 받음).
    5. 자산/섹터 + 지수(index_history)/국내주식평가(dom_asset_history) 스냅샷을 그 날짜
       기준으로 남긴다 (거래 캘린더/자산추이/"지수 대비 계좌" 그래프용). §6-4 참고.
    6. 결과 요약(보유종목 수, 총자산, 현금 등)을 출력한다 — 이 값을 실제
       메리츠 앱 화면과 대조해서 반영이 정확한지 확인할 것.

주의 — 이 스크립트는 국내(KRW) 매매일지 전용이다:
    parse_daily_trade_csv()/import_daily_trades()는 통화/환율 컬럼을 다루지 않고
    항상 원화(통화="원", 환율=1.0)로 거래를 기록한다. 나스닥/해외 거래가 섞인
    매매일지(환율 컬럼이 있는 다른 형식일 가능성이 높음)를 넣으면 환율이
    반영되지 않아 원화 환산 금액이 크게 틀어진다.
    해외 거래는 아직 이 스크립트로 반영하지 말 것 — 실제 해외 매매일지 CSV
    포맷을 확인한 뒤 별도로 처리 경로를 추가해야 한다 (claude.md 참고).
"""

import sys

import pandas as pd

import portfolio_core as core


def main():
    if len(sys.argv) != 3:
        print("사용법: python ingest_daily.py <파일경로> <YYYY-MM-DD>")
        sys.exit(1)

    file_path, trade_date = sys.argv[1], sys.argv[2]

    with open(file_path, "rb") as f:
        raw = f.read()

    try:
        parsed = core.parse_daily_trade_csv(raw)
    except Exception as e:
        print(f"[오류] CSV를 읽는 중 문제가 발생했습니다: {e}")
        sys.exit(1)

    if parsed.empty:
        print("[알림] 파일에서 종목 데이터를 찾지 못했습니다. 형식을 확인해주세요.")
        sys.exit(1)

    tx = core.load_transactions()
    tx2, n_new, n_replaced = core.import_daily_trades(parsed, tx, trade_date)

    if n_new == 0:
        print(f"[알림] {trade_date}: 이 파일에는 매수/매도 내역이 없습니다 (전량 0). 반영할 거래가 없어요.")
        sys.exit(0)

    state = core.load_state()
    prior_holdings = core.load_holdings()
    holdings2, state2, tx2 = core.rebuild_portfolio_from_transactions(
        tx2, state.get("initial", 10_000_000.0),
        state.get("fee_rate_krw", 0.0), state.get("fee_rate_usd", 0.0),
        prior_holdings=prior_holdings)

    # 신규 종목은 종목코드가 비어 있을 수 있음 — 네이버로 가볍게 조회해 채운다(시세는 안 받음,
    # 시세/등락률 보충은 §3-1대로 세션이 refresh_all_prices로 따로). 코드가 있어야 아래
    # dom_asset_history / 시장캐시가 그 종목을 잡는다.
    # 빈 값만 (레드와이어의 "RDW" 같은 미국 티커는 6자리가 아니어도 정상 코드라 건드리지 않음)
    missing_code = holdings2[holdings2["종목코드"].astype(str).str.strip().isin(["", "nan", "None"])]
    if not missing_code.empty:
        code_cache = core.load_code_cache()
        resolved = {}
        for nm in missing_code["종목명"].tolist():
            c = core.resolve_code(nm, code_cache)
            if c:
                resolved[nm] = c
                holdings2.loc[holdings2["종목명"] == nm, "종목코드"] = c
        if resolved:
            core.update_code_cache(resolved)
            core.save_holdings(holdings2)
            print("[코드보충] " + ", ".join(f"{n}={c}" for n, c in resolved.items()))

    core.save_transactions(tx2)
    core.save_holdings(holdings2)
    core.save_state(state2)

    fx_rate = core.fetch_fx_rate() or 1.0
    df, stock_val, total_assets, unrealized_loss = core.compute_metrics(holdings2, state2["cash"], fx_rate)
    core.snapshot_history(total_assets, total_assets + unrealized_loss, on_date=trade_date)
    core.snapshot_sector_history(core.compute_sector_weights(df), on_date=trade_date)

    # "지수 대비 계좌"(§6-4) 스냅샷 3종 — app.py 새로고침 핸들러와 같은 것. 실패해도(네트워크)
    # 매매일지 반영은 성공 처리하고 경고만. 시세는 carried price라 세션의 refresh_all_prices
    # 뒤에 한 번 더 스냅샷하면 그날치가 최신값으로 덮어써짐.
    try:
        q = core.fetch_index_quotes() or {}
        if q.get("KOSPI") and q.get("KOSDAQ"):
            core.snapshot_index_history(q["KOSPI"].get("price"), q["KOSDAQ"].get("price"), on_date=trade_date)
        _dom = df[df["통화"].fillna("원") != "USD"] if "통화" in df else df
        core.snapshot_dom_asset_history(
            float(pd.to_numeric(_dom["평가금액"], errors="coerce").fillna(0).sum()), on_date=trade_date)
        core.refresh_market_cache(
            holdings2[holdings2["통화"].fillna("원") != "USD"] if "통화" in holdings2 else holdings2)
    except Exception as e:
        print(f"[경고] 지수/국내평가 스냅샷 실패(매매일지 반영은 정상): {e}")

    print(f"[완료] {trade_date} 매매일지 반영: 신규 거래 {n_new}건"
          + (f" (기존 {n_replaced}건 교체)" if n_replaced else ""))
    print("---- 반영 후 상태 (실제 메리츠 앱 화면과 대조하세요) ----")
    print(f"보유종목 수: {len(holdings2)}개")
    print(f"예수금(현금): {state2['cash']:,.0f}원")
    print(f"보유종목 평가금액 합계(KRW 환산): {stock_val:,.0f}원")
    print(f"총자산(평가금액+현금): {total_assets:,.0f}원")
    print(f"적용 환율(USD/KRW): {fx_rate:,.2f}")
    if not holdings2.empty:
        print("보유종목:")
        for _, r in holdings2.sort_values("종목명").iterrows():
            price_str = f"${r['평단가']:,.2f}" if r.get("통화") == "USD" else f"{r['평단가']:,.0f}원"
            print(f"  - {r['종목명']}: {r['수량']:.0f}주 @ 평단가 {price_str}"
                  f" (종목코드 {r['종목코드'] or '미확인'}, 섹터 {r['섹터'] or '미분류'}, 통화 {r.get('통화') or '원'})")


if __name__ == "__main__":
    main()
