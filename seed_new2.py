"""
2번째 계좌(new2) 최초 세팅 스크립트 — 오늘 매수한 국내 4종목 + 레드와이어(미국주식)를
transactions.csv에 1일차 매수로 기록하고 replay해서 holdings/현금을 계산한다.

사용법:
    python seed_new2.py            # 미리보기만 (파일 저장 안 함)
    python seed_new2.py --save     # 실제로 저장
"""
import sys
import uuid

import pandas as pd

import portfolio_core as core

INITIAL_CAPITAL = 10_000_000.0
FEE_RATE_KRW = 0.0        # 국내: 수수료 없음. 세금은 첫 매도 후 실제 예수금으로 역산 예정.
FEE_RATE_USD = 0.00007    # 레드와이어: 매수/매도 공통 0.007%
TRADE_DATE = core.today_kst_str()

# 국내 4종목 (portfolio.csv 기준)
DOMESTIC_BUYS = [
    # 종목명,       수량, 매입가,   종목코드,   섹터
    ("삼아알미늄",   1,  53000,   "A006110", "금속철강"),
    ("서흥",         3,  25000,   "A008490", "제약바이오"),
    ("성광벤드",     3,  26050,   "A014620", "기계"),
    ("CJ제일제당",   1, 185200,   "A097950", "식품"),
]

# 레드와이어 (portfolionasdaq.csv 기준: 매입환율 1,414.89)
REDWIRE = {
    "종목명": "레드와이어", "수량": 40, "매입가_usd": 13.15,
    "환율": 1414.89, "종목코드": "RDW", "섹터": "항공우주",
}


def build_rows():
    rows = []
    for name, qty, price, code, sector in DOMESTIC_BUYS:
        rows.append({
            "id": str(uuid.uuid4())[:8], "날짜": TRADE_DATE, "종목명": name, "구분": "매수",
            "수량": qty, "단가": price, "통화": "원", "환율": 1.0,
            "실현손익": "", "메모": "최초 세팅", "정산반영": True,
        })
    r = REDWIRE
    rows.append({
        "id": str(uuid.uuid4())[:8], "날짜": TRADE_DATE, "종목명": r["종목명"], "구분": "매수",
        "수량": r["수량"], "단가": r["매입가_usd"], "통화": "USD", "환율": r["환율"],
        "실현손익": "", "메모": "최초 세팅", "정산반영": True,
    })
    return pd.DataFrame(rows)[core.TX_COLUMNS]


def main():
    save = "--save" in sys.argv

    # 종목코드/섹터 캐시 미리 채워서(네트워크 없이) replay가 바로 정확한 값을 쓰게 함
    code_map = {name: code for name, _, _, code, _ in DOMESTIC_BUYS}
    code_map[REDWIRE["종목명"]] = REDWIRE["종목코드"]
    sector_map = {name: sector for name, _, _, _, sector in DOMESTIC_BUYS}
    sector_map[REDWIRE["종목명"]] = REDWIRE["섹터"]
    core.update_code_cache(code_map)
    core.update_sector_cache(sector_map)

    tx = build_rows()
    holdings, state, tx = core.rebuild_portfolio_from_transactions(
        tx, INITIAL_CAPITAL, FEE_RATE_KRW, FEE_RATE_USD)

    print(f"거래 {len(tx)}건 반영 (날짜: {TRADE_DATE})")
    print(f"보유종목 {len(holdings)}개, 예수금 {state['cash']:,.2f}원")
    print()
    for _, r in holdings.sort_values("종목명").iterrows():
        unit = "$" if r["통화"] == "USD" else "원"
        print(f"  - {r['종목명']} ({r['통화']}): {r['수량']:.0f}주 @ {unit}{r['평단가']:,.2f}  "
              f"[매입금액KRW={r['매입금액KRW']:,.0f}원, 섹터={r['섹터']}, 코드={r['종목코드']}]")

    total_cost_check = 391350 + 40 * 13.15 * 1414.89
    print()
    print(f"검산: 국내+레드와이어 매입금액 합계 = {total_cost_check:,.0f}원")
    print(f"      예상 예수금(초기자본-매입금액-수수료) = {state['cash']:,.2f}원")

    if not save:
        print()
        print("[미리보기 모드] 저장 안 함. 문제 없으면 'python seed_new2.py --save'로 다시 실행하세요.")
        return

    core.save_transactions(tx)
    core.save_holdings(holdings)
    core.save_state(state)

    df, val, total, unreal = core.compute_metrics(holdings, state["cash"], fx_rate=REDWIRE["환율"])
    core.snapshot_history(total, total + unreal)
    core.snapshot_sector_history(core.compute_sector_weights(df))
    print()
    print("[저장 완료] transactions.csv / portfolio_data.csv / account_state.csv")
    print(f"총자산(환산): {total:,.0f}원")


if __name__ == "__main__":
    main()
