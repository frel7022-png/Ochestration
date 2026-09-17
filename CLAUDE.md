# 한국 주식 + 나스닥 혼합 포트폴리오 트래커 — 프로젝트 개요

개인용 Streamlit 웹앱. `C:\Users\frel\Desktop\new1`(국내 전용 버전, GitHub `orchestra` 레포)의
사촌 프로젝트로, **국내(KRW) 종목과 나스닥(USD) 종목을 하나의 포트폴리오로 함께 관리**한다는 점이
다르다. 만든 지 얼마 안 된 프로젝트라(2026-08-14 최초 세팅) 아직 실전에서 겪은 버그가 쌓여있진
않음 — 이 문서는 코드를 처음부터 읽어서 파악한 내용을 정리한 것.

GitHub 원격 저장소: `https://github.com/frel7022-png/Ochestration.git` (main 브랜치). 2026-08-18에
로컬(`C:\Users\frel\Desktop\meritz`)이 git 저장소가 아니었던 걸 발견해서, 기존 원격 커밋 히스토리
(`e907923`, `fc7b909` — 둘 다 GitHub 웹에서 "Add files via upload"로 올라간 것)에 로컬을 연결해뒀다.
new1과 마찬가지로 **GitHub 동기화는 세션이 수동으로 git add/commit/push** 하는 방식이다(앱 코드에
GitHub 연동 로직 없음).

---

## 1. new1과 다른 점 — 통화(KRW/USD) 혼합 처리 구조

### 1-1. 캐시(원화)는 하나뿐, USD 잔고는 따로 없다
- `account_state.csv`의 `예수금`은 **원화 단일 풀(pool)**이다. USD 매매도 전부 이 원화 캐시로
  결제된다 — "달러가 계좌에 남아있다가 재투자된다" 같은 개념이 없다.
- USD 종목을 사고팔 때마다 그 거래 시점의 환율(`transactions.csv`의 `환율` 컬럼)로 즉시 원화
  환산되어 캐시에서 빠지거나 들어온다. **`환율` 값이 틀리면 캐시 잔액이 바로 틀어진다** —
  매매일지에서 USD 거래를 반영할 땐 그 날짜의 정확한 체결 환율을 넣어야 한다.

### 1-2. 매입원가(평단가)는 원화 누적, 평가금액은 그날그날 환율로 재평가
- `평단가`/`현재가`는 종목의 **원래 통화**로 저장(달러는 달러 그대로).
- 매입원가는 `매입금액KRW`라는 별도 누적값으로 관리 — 매수 시점 환율로 원화 환산해서 더해가는
  방식(`apply_transaction`). `평단가 × 현재환율`로 재계산하는 게 아니라 독립적인 누적치라서,
  손으로 잘못 건드리면 평단가/수량과 어긋날 수 있다.
- 반면 평가금액(시가총액)은 **현재 실시간 환율**로 계산한다(`compute_metrics`). 그래서 평가손익에는
  주가 변동분과 환율 변동분이 같이 섞여 들어간다 — **의도된 설계**(원화 기준 정확한 손익을 보려는
  목적), 버그 아님.
- 실시간 환율은 `fetch_fx_rate()`가 네이버(`m.stock.naver.com` FX_USDKRW)에서 가져온다. app.py는
  세션당 한 번 가져와서 세션에 캐싱하고, "시세 새로고침" 버튼 누를 때만 갱신한다.

### 1-2-1. 실제로 겪은 버그 두 건 (2026-08-18, 발견 즉시 수정함)
- **`rebuild_portfolio_from_transactions`에 new1의 `prior_holdings` 보존 기능이 없었음.** new1은
  재계산할 때마다 직전 실시간 시세(현재가/등락률/업데이트시각)를 이어붙이는데, meritz 버전엔 이게
  아예 없어서 **재계산할 때마다 모든 종목의 현재가가 매수가로, 등락률이 0%로 리셋**됐다. 실제로
  나스닥 스냅샷 반영(§3-2) 직후 사용자가 "현재가가 다 이상하다"고 지적해서 발견함 — 14개 종목
  전부 영향받고 있었음. `portfolio_core.py`의 `rebuild_portfolio_from_transactions`에
  `prior_holdings` 파라미터와 보존 로직을 new1에서 그대로 포팅해서 고침, `ingest_daily.py`도
  `prior_holdings=core.load_holdings()`를 넘기도록 수정. **앞으로 holdings를 재계산하는 스크립트를
  새로 짤 땐 반드시 `prior_holdings`를 넘길 것** — 안 그러면 이 버그가 재발한다.
- **`stock_code_cache.csv`에 "A" 접두사가 붙은 종목코드가 섞여있었음**(CJ제일제당=A097950,
  서흥=A008490, 성광벤드=A014620, 삼아알미늄=A006110) — `seed_new2.py`가 증권사 원본 잔고
  export(`portfolio.csv`)의 코드 표기(`A006110` 식)를 그대로 하드코딩해서 생긴 것. 네이버 실시간
  시세 API(`fetch_quotes`)는 접두사 없는 6자리 코드만 인식해서, 이 4종목만 시세 조회가 계속
  실패했다(현재가가 매수가에 고정, 다른 종목은 정상 갱신되는데 이 몇 개만 안 됨 — 눈치채기
  까다로운 패턴). 캐시와 `portfolio_data.csv` 양쪽의 "A" 접두사를 제거해서 해결. 앞으로 잔고
  export를 보고 코드를 직접 손으로 채워 넣을 일이 있으면, 반드시 접두사(A) 없이 6자리 숫자만
  넣을 것.

### 1-3. 알려진 약한 지점 (코드 읽어서 발견함, 아직 실제로 안 터진 문제)
- **`fetch_fx_rate()`가 처음부터 실패하면 환율이 조용히 1.0으로 폴백된다** (app.py, 세션 최초 진입
  시). USD 종목 평가금액이 실제 환율(~1,400원)이 아니라 1:1로 계산되어 크게 틀어지는데, 사용자에게
  경고가 전혀 안 뜬다(`refresh_all_prices`의 실패 리포트와 달리 이건 조용히 넘어감). 언젠가 손볼
  가치 있음 — 지금은 알고만 있음.
- **`compute_metrics`의 `매입금액KRW` 폴백**: 이 값이 비어있으면 `수량 × 평단가`로 대체하는데,
  **환율 곱하기를 안 한다.** USD 종목에서 이 폴백 경로를 타면 매입원가가 실제보다 ~1,400배
  작게 계산된다. 지금은 항상 `매입금액KRW`가 정상적으로 채워지고 있어서 안 터졌지만, 재계산
  로직을 손댈 때 이 폴백 분기를 건드리게 되면 조심할 것.
- **app.py에 "최초 자본 10,000,000원"이라는 문구가 두 군데(줄 ~449, ~751) 하드코딩**돼 있음.
  실제 `account_state.csv`의 `최초자본` 값이 바뀌어도 이 텍스트는 안 바뀜(옆의 %는 정확히 계산됨).
- `seed_new2.py`에 그 날 한 번 손으로 검산한 상수(`total_cost_check = 391350 + 40*13.15*1414.89`)가
  죽은 코드로 남아있음 — 정리해도 됨, 지금 당장은 무해.

---

## 2. 파일 구조

```
app.py                # 진입점 겸 전체 UI. 924줄, 함수 거의 없는 절차형 스크립트(new1 리팩터 전과 동일한 상태).
                       #   탭 2개: "포트폴리오"(요약/섹터비중/Up-Down/종목현황), "거래 기록"(실현손익 그래프/캘린더).
                       #   앱 자체엔 거래 입력/CSV 업로드 UI가 없음 — 전부 스크립트로 반영.
portfolio_core.py      # 데이터 계층. new1의 portfolio_core.py와 거의 동일한 구조 + 통화/환율 처리 추가.
                        #   parse_daily_trade_csv / import_daily_trades / rebuild_portfolio_from_transactions
                        #   전부 이미 구현되어 있었음(2026-08-18 기준 app.py/seed_new2.py 어디서도 안 부르고 있었음 —
                        #   ingest_daily.py를 위해 미리 준비해둔 것으로 보여서 이번에 그 스크립트를 작성함).
seed_new2.py            # "최초 세팅" 1회용 스크립트. portfolio.csv(국내 잔고)/portfolionasdaq.csv(해외 잔고)를
                         #   사람이 눈으로 보고 손으로 옮겨적은 하드코딩 상수(DOMESTIC_BUYS, REDWIRE)를 반영.
                         #   다시 실행하면 안 됨 — 재실행 시 같은 5건이 새 id로 중복 추가됨.
ingest_daily.py           # 신규(2026-08-18, 이번에 작성). new1의 ingest_daily.py와 같은 패턴이지만
                           #   국내(KRW) 매매일지 전용 — 나스닥 매매일지는 아직 처리 못 함, 아래 §3 참고.
```

## 3. 데이터 파일 스키마 (new1과 다른 컬럼만 표시)

| 파일 | new1과 다른 점 |
|---|---|
| `transactions.csv` | `통화`(원/USD), `환율`(그 거래 시점 환율, KRW 거래는 1.0) 컬럼 추가 |
| `portfolio_data.csv` | `통화`, `매입금액KRW`(원화 환산 누적 매입원가) 컬럼 추가 |
| `account_state.csv` | `수수료율_원화`, `수수료율_달러` — 국내/해외 수수료율을 따로 관리 (new1은 `수수료율` 하나) |
| `portfolio.csv` (로컬 전용, git 제외) | 메리츠 국내 잔고현황 원본 export(cp949). 프로그램이 파싱 안 함 — `seed_new2.py` 만들 때 사람이 보고 베낀 참고용. |
| `portfolionasdaq.csv` (로컬 전용, git 제외) | 메리츠 해외(나스닥) 잔고현황 원본 export(cp949). 위와 동일한 용도. |

---

## 3-1. 일일 매매일지 반영 흐름 (todaytrans/) — new1과 동일 패턴

- `todaytrans/` 폴더는 로컬 전용(`.gitignore`), 사용자가 최신 매매일지 CSV를 여기 덮어써서 넣는다.
  **세션은 실시간 감지를 못 하니, 사용자가 "넣었어" 하고 알려줘야 한다.**
- 반영: `python ingest_daily.py todaytrans/파일명.csv <YYYY-MM-DD>` → 그 날짜의 기존 반영분 교체 →
  전체 재계산 → 결과(보유종목/현금/평가금액/총자산/적용환율) 확인 → 코드 미확인 종목 있으면
  `core.refresh_all_prices()`로 보충 → git commit/push.
- new1의 확립된 원칙을 그대로 따름: **문제없이 잘 도는 흐름이면 매 단계 사용자에게 묻지 말고
  바로 진행**, 숫자가 크게 이상하거나 파싱 실패 같은 실제 문제가 있을 때만 멈추고 확인.

### 3-2. 나스닥(해외) 쪽은 "매매일지"가 아니라 "잔고 스냅샷"으로 옴 (2026-08-18 확인)
- `nasdaqtrans/` 폴더(로컬 전용, `.gitignore`)에 사용자가 나스닥 잔고 파일을 넣는다. 첫 샘플
  파일명이 `firstsetting.csv`였음 — 국내 `todaytrans/`처럼 매일 갈아끼우는 "그날 거래 누적"
  포맷이 아니라, **그 시점의 보유 잔고 스냅샷**(컬럼 구조가 `portfolionasdaq.csv`와 동일:
  종목코드/종목명/보유수량/평균가/현재가/매입금액/평가금액/매입환율/현재환율 등)이었다.
  즉 **`parse_daily_trade_csv`(그날 매수/매도 누적) 방식으로는 못 씀** — 이 파일엔애초에
  "금일매수/금일매도" 개념이 없고 그냥 "지금 몇 주 보유 중, 평단가 얼마"만 있음.
- **반영 방식(2026-08-18 첫 사례로 확정)**: 스냅샷의 수량/평균단가를 기존 holdings와 비교해서
  차이(수량 증감)를 계산 → 가중평균 공식으로 역산한 매수(또는 매도) 단가로 `transactions.csv`에
  거래 1건을 추가 → `rebuild_portfolio_from_transactions`로 전체 재계산. 환율은 스냅샷의
  `매입환율` 컬럼 값을 그대로 씀(정밀한 역산과 차이가 거의 없었음 — 실제 사례: 40주→62주로
  늘었을 때 역산 환율 산출해보니 스냅샷의 매입환율과 거의 동일해서 그냥 스냅샷 값 사용).
  예시 계산: `추가수량 = 새수량 - 기존수량`, `역산단가 = (새수량×새평단가 - 기존수량×기존평단가) / 추가수량`.
  **주의**: 이건 근사치다 — 실제 개별 체결 내역(며칠에 얼마씩 샀는지)과는 다를 수 있음. 정확한
  체결 내역을 알 수 있으면 그걸 우선한다.
- **수량이 줄어든(매도) 경우**도 같은 논리로 역산 가능하지만, 그 경우 실현손익 계산에 매도가가
  직접 들어가므로 근사치 리스크가 더 크다 — 이 경우엔 특히 사용자에게 실제 체결 정보를 먼저
  물어보는 게 안전함.
- 처음엔 "매매일지 포맷일 것"이라고 추측하고 파서를 미리 만들지 않기로 해뒀었는데(아래 문단
  참고), 실제로 받아보니 스냅샷 포맷이었음 — **추측하지 않고 기다린 게 맞았음.** 앞으로 이
  폴더에 새 파일이 오면 위 "잔고 스냅샷 역산" 절차를 그대로 적용하면 됨.

### 3-3. 나스닥도 실제 "매매일지"(체결 내역) 포맷으로 올 수 있다 (2026-08-27 확인, §3-2 갱신)
- 2026-08-27에 처음으로 §3-2가 예상했던 "실제 개별 체결 내역" 파일을 받음 — 폴더는
  `nasdaqtrans/`가 아니라 **`todaytrans/`**에 한글 파일명(`레드와이어 나스닥 주식.csv`)으로
  들어왔음. 컬럼: `상품구분,결제일자,거래소,국가,통화,매매,체결수량,매매금액,수수료,제비용,
  결제금액,대출구분,상환금액(원),대출이자(원)` — **`매매금액`은 그 거래 전체의 총액(USD)이지
  1주당 단가가 아님**, `단가 = 매매금액 / 체결수량`으로 직접 계산해야 함. cp949 인코딩.
  환율 컬럼은 없음.
- **환율은 그 결제일자의 네이버 일별 매매기준율로 보충**한다 —
  `https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd=FX_USDKRW&page=N`
  (page를 늘려가며 필요한 날짜까지 뒤로 감, BeautifulSoup으로 `table.tbl_exchange tbody tr`의
  1번째 td가 날짜, 2번째 td가 매매기준율). 실제 결제 시 브로커가 적용한 환율과 정확히 같지는
  않을 수 있지만(스프레드 차이), 시장 종가 기준이라 근사 오차는 무시할 만한 수준.
  `apply_transaction`은 어차피 CSV의 실제 수수료 컬럼을 쓰지 않고 `fee_rate_usd` 설정값으로
  수수료를 추정하는 구조라(§1 상단 코드 참고), 이 CSV의 `수수료`/`결제금액` 컬럼도 실제로는
  안 씀 — `체결수량`과 `단가`만 있으면 충분.
- **이 방식이 나오면 §3-2의 "잔고 스냅샷 역산"보다 항상 우선한다** — 실제로 레드와이어를
  비교해보니 스냅샷 역산으로는 62주(평단가 $13.36)로 계산됐던 게, 실제 체결 내역 7건을 다
  받아보니 79주(평단가 $13.14)가 진짜였음. 역산은 "그럭저럭 비슷한 근사치"였지 정답이 아니었다는
  뜻 — §3-2 문서에 이미 "정확한 체결 내역을 알 수 있으면 그걸 우선한다"고 적어뒀던 원칙이
  실제로 확인된 사례.
- 반영 절차: 기존에 해당 종목으로 들어가 있던 근사치 거래(스냅샷 역산분 등)를 전부 지우고,
  이 실제 체결 내역으로 교체 → `rebuild_portfolio_from_transactions(prior_holdings=...)`로
  전체 재계산 → `refresh_all_prices()` → `snapshot_history`/`snapshot_sector_history`를 오늘
  날짜로 한 번 더 호출(이 경로는 `ingest_daily.py`를 안 거치므로 스냅샷 갱신을 빠뜨리기 쉬움,
  직접 챙길 것) → commit/push. 전용 스크립트는 아직 없음(1회성 스크립트로 처리) — 이 패턴이
  반복되면 `ingest_nasdaq_journal.py`로 정리해도 됨.

<details>
<summary>(참고, 더 이상 유효하지 않음) 원래 세워뒀던 원칙: 포맷 모를 땐 미리 만들지 말 것</summary>

- `ingest_daily.py`가 쓰는 `parse_daily_trade_csv`/`import_daily_trades`는 **국내용 컬럼 레이아웃
  전용**이고 통화/환율을 전혀 다루지 않는다(항상 원/1.0으로 기록하도록 이번에 명시적으로 고정함,
  §1-3의 NaN 버그 참고). 메리츠가 해외 매매일지를 국내와 똑같은 포맷으로 주는지, 아니면
  `portfolio.csv` vs `portfolionasdaq.csv`처럼 별도 포맷(환율 컬럼 포함)으로 주는지 아직 실제
  파일을 못 봐서 모른다.
- **사용자가 실제 나스닥 매매일지 CSV를 주면, 그 컬럼 구조를 먼저 확인하고 나서 별도 파서를
  추가할 것.** 포맷을 추측해서 파서를 미리 만들지 말 것 — 환율 처리를 잘못 넣으면 원화 캐시가
  조용히 틀어지는 게 이 프로젝트에서 제일 위험한 실패 모드다(§1-1 참고).

</details>

---

## 4. 스타일/UX 원칙
- new1과 동일: 모바일 웹뷰 기준, 컴팩트/심플, 밝은 테마 기본, 상승=빨강/하락=파랑.
- USD 종목은 가격/평단가만 `$`로 표시되고 나머지(평가금액/손익/총자산/섹터비중)는 전부 원화 환산
  기준으로 통일 — 통화가 섞여도 총자산 숫자 하나로 볼 수 있게 하려는 의도.

## 5. 다음에 할 일 (2026-08-18 기준 미해결)
1. ~~실제 나스닥 매매일지 CSV 포맷 확인~~ → 완료, §3-2에 "잔고 스냅샷 역산" 절차로 정리됨.
   다음 나스닥 파일이 오면 그 절차를 따르면 됨.
2. `fetch_fx_rate()` 실패 시 조용히 1.0 폴백되는 문제 — 새로고침 실패 리포트처럼 사용자에게
   보이게 할지 논의.
3. app.py가 new1처럼 924줄 절차형 스크립트 상태 — new1에서 했던 모듈 분리 리팩터를 여기도
   적용할지는 아직 안 정함(요청받으면 new1 리팩터 패턴 그대로 재사용 가능).
4. ~~로컬 개발용 빈 `.streamlit/secrets.toml`~~ → 완료, 2026-08-18에 추가함.

---

## 6. 운영 흐름 확정 (2026-08-18, new1과 동일한 모양으로 굳힘)

new1과 거의 같은 모양으로 운영하기로 확정함 — 새 세션은 new1의 `CLAUDE.md` §6을 먼저 읽으면
전체 그림 이해가 빠르다. meritz만 다른 부분은 국내/나스닥 두 스테이징 폴더가 있다는 것뿐.

### 6-1. 스테이징 폴더 두 개 (둘 다 로컬 전용, `.gitignore` 처리됨)
- **`todaytrans/`** — 국내(KRW) 매매일지. new1과 완전히 동일한 "그날 하루 전체 누적" 방식.
  `python ingest_daily.py todaytrans/파일명.csv <YYYY-MM-DD>`로 반영.
- **`nasdaqtrans/`** — 나스닥(USD) 잔고 스냅샷. §3-2의 "가중평균 역산" 절차로 반영(전용 스크립트
  없음 — 매번 스냅샷 수량/평단가를 보고 즉석에서 거래를 역산해 추가하고 `rebuild_portfolio_
  from_transactions`를 부르는 방식. 파일 수가 아직 많지 않아서 스크립트로 안 굳혔음, 패턴이
  반복되면 `ingest_nasdaq_snapshot.py` 같은 걸로 정리해도 됨).
- 두 폴더 다 **세션이 실시간으로 감지 못 하므로 사용자가 "넣었어"라고 알려줘야** 함.
- new1과 동일하게: **이 반영→확인→push 흐름은 문제없이 도는 걸로 확인됐으니 매번 물어보지 말고
  바로 진행**. 숫자가 크게 이상하거나 파싱/역산이 이상할 때만 멈추고 확인.

### 6-2. 바탕화면 `backup_meritz` 폴더
- `C:\Users\frel\Desktop\backup_meritz` — git 저장소 아님, `meritz`의 단순 스냅샷 복사본.
  new1의 `C:\Users\frel\Desktop\backup`과 같은 역할(리스키한 수정 직전 안전망), 이름만 구분해서
  new1 백업과 안 헷갈리게 함(new1 쪽은 그냥 `backup`이라 이미 이름이 선점돼 있었음). 2026-08-18에
  처음 만듦.
- 리스키한 수정 전에 최신화할지는 new1과 같은 기준으로 판단(사용자 확인 후 진행).

### 6-3. 매매일지로 들어오는 신규 종목이 "미분류"로 안 남게 — new1 섹터 리스트 통합해둠
- `portfolio_core.py`의 `load_holdings()`는 원래부터 종목명이 `stock_sector_cache.csv`에 있으면
  자동으로 섹터를 채워주는 로직이 있었다(재계산 때마다 실행됨) — 그래서 **캐시 파일 자체를
  채워두기만 하면 앞으로 들어오는 매매일지의 겹치는 종목은 자동으로 분류된다.**
- 2026-08-18에 new1의 `stock_sector_cache.csv`(69개 종목) 전체를 meritz의 캐시에 병합함(meritz
  전용 항목인 레드와이어/삼아알미늄은 그대로 유지, 겹치는 이름은 meritz 값 우선). 병합 후
  meritz 캐시 71개 종목.
- **그래도 여전히 미분류로 남을 수 있는 경우**: new1에도 없는 완전히 새로운 종목(둘 다 안
  가진 적 없는 종목)이 매매일지로 들어올 때뿐이다. 이때는 어쩔 수 없이 섹터를 수동으로
  정해줘야 함(new1의 "섹터 일괄 수정" 같은 UI가 meritz app.py엔 아직 없음 — 필요하면
  `core.update_sector_cache({"종목명": "섹터"})`로 캐시에 직접 넣고 재계산하면 됨).
- 매매일지 반영(`ingest_daily.py`) 직후엔 **미분류 종목이 남아있는지 항상 확인**하고, 남아있으면
  new1 캐시에 있는지부터 찾아보고, 없으면 사용자에게 섹터를 물어볼 것.

### 6-4. "지수 대비 계좌" 지표 — 국내 전용 (2026-09-08 기준, new1 §6-17 포팅)
- **위치**: "거래 기록" 탭, 실현손익 그래프 바로 아래. new1 §6-17과 UI 동일 —
  **2장 스와이프 캐러셀**: 1장 [5줄 지수 표(코스피/코스닥/혼합지수/내 주식/내 계좌, 누적·5일·당일,
  내 주식/계좌는 혼합지수 대비 빨강/파랑) + 선그래프], 2장 [하락/상승/even 캡처 표 3개 + 일별 캡처 막대].
- **하락/상승/even 캡처 (new1 §6-17 2026-09-07 설계 — CR·국면막대·RP 전부 폐기)**:
  스냅샷 구간마다 벤치당일 부호로 3분류. 하락일(<−0.1%)·상승일(>+0.1%) 캡처 `c = 내당일/벤치당일`,
  even일(|·|≤0.1%) 초과수익 `e = 내당일−벤치당일`(%p). 누적: DC/UC `= Σ내당일/Σ벤치당일`,
  even `= e 단순평균`. 승률: ERA(하락일 c<1) / PCT(상승일 c≥1) / evr(even e≥+0.1%).
  내 계좌·내 주식 각각. 캡처 막대는 내 계좌 기준, 하락일 빨강/상승일 파랑, y=1 선.
  `compute_index_vs_account` 반환 = `cap{acct,stock}` / `n{down,up,even}` / `even_anomalies`.
  `append_capture_anomalies`는 even일 로그(날짜, 벤치당일, 초과_계좌, 초과_주식).
- **레드와이어(USD) 배제 후 국내 전용 (2026-09-08 §0단계)**: RDW 거래 8행 제거 →
  `redwire_archive.csv`, **최초자본 10M → 8,000,000**(200만원 달러 환전분). 이제 전 거래 통화="원".
  - `D0(t) = initial_capital − _usd_invested_on(...)` 로직은 남아 있으나 USD 거래가 0이라
    `D0 = initial_capital = 8,000,000` 고정(휴면).
  - **내 계좌수익(t) = (국내주식평가(t) + 예수금(t)) / 8,000,000 − 1**.
  - **내 주식 Rs(t)** = 국내주식 100% 투자 환산 누적수익, flow는 국내 거래대금.
  - 통화/환율/`fee_rate_usd`/`fetch_usd_quotes`/`apply_transaction` 통화분기 = 죽은 코드로 남김.
- **데이터 파일 (전부 git에 커밋 — asset_history.csv와 같은 성격)**:
  - `index_history.csv` (날짜, KOSPI, KOSDAQ)
  - `dom_asset_history.csv` (날짜, 국내주식평가) — RDW 제외한 국내주식 원화 평가금액
  - `stock_market_cache.csv` (종목명, 시장) — 국내종목 KOSPI/KOSDAQ 구분, §1-3 영구 캐시 패턴
  - 하루치 갱신: `app.py` "시세 새로고침" 핸들러에서 `snapshot_index_history` /
    `snapshot_dom_asset_history` / `refresh_market_cache` 호출 (별도 cron 없음).
  - 최초 백필: `python backfill_index_dom_history.py` (재실행 가능, 인자 없음) — 세 파일을
    통째로 다시 만든다. `fetch_daily_price_history`(네이버 일별시세, KOSPI/KOSDAQ 심볼도 동작)로
    소급. asset_history.csv에 있는 날짜마다 국내주식평가 한 줄.
- **함수** (`portfolio_core.py`, new1에서 이식): `load/save/snapshot_index_history`,
  `load/save/snapshot_dom_asset_history`, `load/update_market_cache`, `fetch_stock_markets`,
  `refresh_market_cache`, `fetch_daily_price_history`, `_cash_by_date`(전체 거래 재생 → 실제
  예수금), `_usd_invested_by_date`, `_index_cum_returns`, `_index_day_moves`,
  `compute_index_vs_account(tx, dom_asset_hist, index_hist, initial, fee_rate_krw, fee_rate_usd,
  kospi_weight)`. 반환 dict 구조는 new1 §6-17과 동일. meritz엔 pytest가 없어 new1 테스트로
  로직 검증 후 이식함.

### 6-5. 2026-09-04 — new1 오늘 변경분 대량 이식 (new1 §6-18/§6-19 등)
방어 성적이 의도대로 나온 걸 확인하고 사용자가 "외국인 배지만 빼고 다 넣자"고 해서 이식:
- **SamHynix extracted 패널**(new1 §6-19): "Account : Index" 밑 expander. 혼합지수의
  코스피 다리를 "코스피 ex-삼성전자·삼성전자우·SK하이닉스"로 갈아끼운 버전. 국내 벤치에
  적용(meritz는 원래 국내주식만 계산이므로 코스피 다리만 교체하면 됨).
  - `portfolio_core`: `load/save/snapshot_bigcap_history`, `fetch_bigcap_quotes`,
    `synthetic_kospi_ex_bigcap`, 상수 `BIGCAP_CODES`/`_BIGCAP_SHARES`/`_KOSPI_MKTCAP_ANCHOR`.
    `synthetic_kospi_ex_bigcap(index_hist, bigcap_hist)`가 index_hist의 KOSPI 열을 합성
    레벨로 바꾼 사본을 돌려주고, 그걸 `compute_index_vs_account`에 그대로 넘기면 끝.
    meritz엔 `resolve_trading_date`가 없어 `snapshot_bigcap_history`는 `today_kst_str()` 사용.
  - `bigcap_history.csv`(날짜,삼성전자,삼성전자우,SK하이닉스 종가), 백필 `python
    backfill_bigcap_history.py`(재실행 가능), 일별 갱신은 새로고침 핸들러의
    `snapshot_bigcap_history(fetch_bigcap_quotes())`.
  - 비중 상수는 2026-09-04 스냅샷(삼성 ~28%+삼성우 ~3%+하이닉스 ~22%≈52%). 분기 갱신 권장.
- **"KOSPI 2-Track Trend" 라인차트**: "Account : Index" 패널 바로 밑. 일반 코스피(빨강) vs
  삼성·하이닉스 제외(파랑), **y축은 실제 지수 포인트**, hover엔 전일 대비 등락률%.
- **표에 "5일" 컬럼**: 누적 / 5일 / 당일. "5일" = 시계열 5행 전 대비(코스피·코스닥=5거래일,
  벤치·내 주식·내 계좌=스냅샷 5구간).
- **렌더러 추출**: 지수 대비 계좌 렌더링을 `_render_iva_panel(iva, idx_hist_local, kospi_label,
  carousel_id)` 로컬 함수로 빼서 메인/SamHynix 두 패널이 공유. 캐러셀 id `cwrap`/`cwrap_ex`
  분리 + 점 클릭/좌우 화살표 키로도 전환(PC).
- **섹션 타이틀 영어화**: 종목별 보유현황→`Holdings`, 실현손익 그래프→`Realized P&L`,
  지수 대비 계좌→`Account : Index`, 섹터 비중 보기→`Sectors`, 거래 내역→`History Calendar`,
  탭 포트폴리오/거래 기록→`Portfolio`/`Analysis`. (영어 라벨 첫 글자 항상 대문자.)
- **자잘한 디자인**: 섹터 범례↔막대 간격(`.legend-wrap` margin-bottom 20px), WATERING을
  텍스트 칩→점(회색/누르면 녹색), Holdings 정렬 토글 점을 업데이트 날짜 옆에 나란히,
  **물타기 회복 종목 카드 옅은 녹색**(`.stock-card.watered-ok` — 현재 사이클 매수 2회+ &
  현재가 ≥ 최초진입가).
- **미이식**: 외국인 보유율 배지(new1 §4). 사용자가 "외국인 제외" 명시.

### 6-6. 2026-09-08 — 레드와이어(USD) 배제 + new1 최근 변경 대량 이식
사용자: "국내주식만 new1처럼. 레드와이어는 잊자(묵혀둘 거)."
- **§0 레드와이어 제거**: `transactions.csv`에서 레드와이어 8행 → `redwire_archive.csv`(앱 안 읽음).
  **최초자본 10,000,000 → 8,000,000** (저번에 200만원을 달러로 환전 → RDW 위성계좌). 이제 전
  거래 통화="원". 체크포인트 삭제 후 전체 재생. 통화/환율/`fee_rate_usd`/`fetch_usd_quotes`/
  `apply_transaction` 통화분기/D0(RDW 순투입) = **죽은 코드로 남김**(USD 거래 0건이라 안 돎).
- **§1 소규모**: 요약카드 "최초자본 대비" → **"어제 대비 ±N원"**(+빨강/−파랑). 단, asset_history
  히스토리엔 RDW 섞인 값이라 `dom_asset_history(국내평가) + _cash_by_date(그날 예수금)`로
  "국내 총자산"을 재구성해 비교. Holdings 타이틀 `(이익 N / 손실 M)`. 물타기 그래프 x축
  날짜 눈금(dtick 며칠). `synthetic_kospi_ex_bigcap` 기간매칭 수정(bigcap 중간날 누락 시 폭주 방지)
  + `ingest_daily.py`에 bigcap lock-step 스냅샷. `resolve_trading_date()` 신설 + 스냅샷 5함수 통일.
- **§2 DC/UC/even 캡처 재설계**(new1 §6-17 2026-09-07): **CR·국면막대·RP 전부 폐기.**
  하락/상승/even 3버킷, DC/UC=Σ내당일/Σ벤치당일, even=e평균, ERA/PCT/evr 승률.
  `compute_index_vs_account` 반환 = `cap{acct,stock}` / `n{down,up,even}` / `even_anomalies`.
  `_render_iva_panel` = 캐러셀 1장 [5줄 표 + 선그래프], 2장 [캡처 표 3개(_cap_tbl) + 일별 캡처 막대].
- **Realized P&L 미실현손실 선**: `asset_history.csv`를 국내 전용으로 재생성(각 날짜까지 재생 +
  국내 종목 히스토리 종가). 1회성 데이터 정정.
- **index_history.csv 정정**: 9/4~9/7이 앱 새로고침 stale 값으로 오염(9/7 = 9/4 복제)돼
  new1과 어긋나 있던 것 → `backfill_index_dom_history.py`로 공식 종가 재소급.
- **index/bigcap_history 재오염 + 근본 원인 수정 (2026-09-10, new1 CLAUDE.md §6-2 참고)**:
  `ingest_daily.py`가 `index_history`/`bigcap_history`를 **실시간 시세**로 `on_date=trade_date`에
  찍고 있어서, **과거 날짜 매매일지를 장중에 반영하면 그 과거 날짜 행이 '오늘 장중값'으로 덮였다**
  — 909.csv(9/9)를 9/10 장중에 반영하다 `index_history[9/9]`가 9/10 장중 KOSPI(7002)로 덮여
  new1(7051.64)과 어긋났고 → 혼합지수·`SamHynix extracted`·`VIP vs Orchestra/Orchestration`
  패널이 통째로 오염. bigcap도 9/4·9/9·9/10이 갈림. **수정**: `ingest_daily.py`에 `_close_on()`
  헬퍼 — `fetch_daily_price_history`로 trade_date **확정 종가 먼저** 조회, 없을 때만 실시간
  폴백. `index_history.csv`/`bigcap_history.csv`/`fund_nav_history.csv`(9/10 행 누락분)를
  new1과 **동일 파일**로 맞춤. 당일 값은 장중이라 잠정 — 다음날 ingest가 확정 종가로 자동 정정.
- **§3 VIP vs Orchestra vs Orchestration**(new1 §6-21, 2026-09-08 3-way로 확장): SamHynix extracted 밑
  `st.expander("VIP vs Orchestra vs Orchestration")`. 표 3행(VIP / Orchestra=new1 계좌 / Orchestration=
  meritz 계좌) × 누적/당일, **값 검정**, 점 색만 VIP 파랑 / Orchestra 빨강 / Orchestration 녹색.
  그래프 3선 동색, 범례 없음, 셋 다 8/14=0. `fund_nav_history.csv`(펀드 기준가, new1과 공유) +
  **`both_accounts.csv`(날짜, orchestra, orchestration)** — new1의 `sync_both_accounts.py`가 두 레포에
  똑같이 써준다. 어느 앱이든 ingest 후 세션이 `python sync_both_accounts.py`(new1 폴더) → 두 레포
  각각 `both_accounts.csv` commit. `load_both_accounts()` + `compute_vip_vs_orchestra(iva,
  both_accounts, self_key="orchestration")`. 기준가는 자동 조회 없이 세션이 채팅으로 받아 CSV append.
  - **(2026-09-10 개정)** `self_key="orchestration"` → **Orchestration(meritz 자기 계좌)은 라이브
    `me["계좌수익"]` 재기준화값을 씀** (Account:Index '내 계좌'와 같은 데이터). Orchestra(new1)는
    선그래프 히스토리는 `both_accounts.csv`, **표 누적/당일 + 선 마지막 점은 `peer_latest`**.
  - **Supabase 런타임 채널 `account_snapshot` (2026-09-10 신설, new1 §6-21 참고)**: `both_accounts.csv`가
    세션 sync 시점에 얼어서(장중 sync면 그 시각값 고정) 상대 앱 라이브값을 못 따라가는 문제 해결.
    양쪽 앱이 **시세 새로고침마다** 자기 계좌 라이브 상태를 `account_snapshot`에 upsert
    (`write_account_snapshot("orchestration", ...)`), meritz VIP 패널은 새로고침 때 Orchestra(new1)
    최신값을 `fetch_peer_account_snapshot("orchestra", ...)`로 읽어 `st.session_state["peer_orchestra"]`에
    캐싱 → `compute_vip_vs_orchestra(..., peer_latest=...)`. **graceful degradation**: 시크릿 없음/
    네트워크/테이블 없음 → 조용히 `both_accounts.csv` 폴백, 앱 불변.
    - 스키마: `account_snapshot(id, app, trade_date, cum, day, total_asset, updated_at)`,
      `unique(app, trade_date)`.
    - **셋업(사용자)**: ① Supabase에 `account_snapshot` 테이블 생성(new1 CLAUDE.md §6-21에 SQL).
      ② **meritz Streamlit Cloud secrets + 로컬 `.streamlit/secrets.toml`에 `[supabase]`**
      (new1과 같은 URL/anon_key). 없어도 앱은 폴백으로 정상.
- **§4 수수료 모델**(new1 §6-4): `apply_transaction` — 매수 수수료 0, 매도 시 매도금액 × fee_rate 를
  예수금과 그 건 realized 양쪽에서 차감. `account_state.수수료율_원화` 0.000579 → **0.002**
  (수수료율_달러는 휴면). 전체 재생 → 매도 14건 실현손익 재기록.
- **§5 P&L Actions**(new1 §6-20): Realized P&L 밑 `st.expander("P&L Actions")`.
  `_all_cycles`/`_cycle_bucket`/`compute_pnl_actions` — 사이클(진입~전량청산) 단위로 FA(1매수 전량)/
  MO(부분매도 있음)/MA(물타기 전량) 3버킷. 표(이름/실현/비중/손익률) + 도넛(FA 빨강/MO 녹색/MA 파랑,
  글씨 하양) + 상태표(Numbers/Ratio) + Watering 상세(흡수율·시드 배수). USD 없어 new1 그대로 이식.
- **결과**: meritz Analysis 탭이 new1과 사실상 동일한 포맷. 포트폴리오 탭은 관심종목 스크리너
  4개(Fishing/Volume/Foreigner/포프)만 빠짐 — Supabase 파이프라인에 묶인 거라 이식 안 함(사용자 결정).
- **Today's Take**(new1 §4, 2026-09-08): Portfolio 요약카드 "어제 대비" 자리 → 3줄.
  ① 내 주식 어제 대비 ±원 + ▲▼ 내 주식 당일%  ② 혼합지수 당일% · W/O SH(반도체 제외) 당일%
  ③ DC/UC(오늘 하락일 c=DC / 상승일 c=UC / even·무데이터 —) · W/O SH 동일.
  Portfolio 탭에서 `compute_index_vs_account` 2번 호출(기본/반도체제외).
- **DC/UC 색 스왑**(2026-09-08): DC(하락일 방어)=파랑 / UC(상승일 참여)=빨강. 캡처 표·일별 막대·
  Today's Take 전부. 일일거래 매수/매도 = 한 줄 평문(회색 chip 제거).
- **WATERING 상세 "현재가" 선 실데이터화**(2026-09-11, new1 §6-10 갱신 포팅): 예전엔 최초매입일
  →오늘 두 점 직선이라 "그 사이 등락 없이 꾸준히 내려온 것처럼" 보이는 문제. meritz엔 new1의
  Supabase price_history가 없어서, **KRW 종목은 `fetch_daily_price_history`(네이버 일별시세,
  종목당 API 호출 1번으로 구간 전체)**로 실제 일별 종가를 그리고, **USD(나스닥) 종목은 이 API가
  국내 전용이라 지원 밖 — 두 점 직선 폴백** 그대로. 첫/끝 점은 실제 체결가·실시간가로 고정.
  세션당 종목코드 1회만 조회(`st.session_state["holding_price_hist_cache"]`).

### 6-7. 2026-09-16 — 새로고침 캐시(§6-31)·FA 승률(§6-30)·섹터 미분류 정리 (new1 부분 이식)
사용자: "메리츠에 모든 기능을 이식 시킬 필요는 없고" — new1의 최신 변경 중 이 세 가지만
선택적으로 포팅. Fishing/Volume/Foreigner/Link류(관심종목 스크리너)는 여전히 미이식 상태
그대로(§6-6 결과 문단 참고, meritz엔 Supabase watchlist 파이프라인 자체가 없음).
- **새로고침 결과 로컬 캐시 (new1 §6-31)**: meritz엔 Up/Down 하나만 수동 새로고침 버튼으로
  session_state가 채워지는 패널이라(다른 새로고침류는 전부 세션당 1회 자동 실행,
  `auto_refreshed` 패턴) 이식 범위도 Up/Down 하나로 충분함. `portfolio_core.py`에
  `save_ui_cache_json`/`load_ui_cache_json` + `UI_CACHE_DIR = HERE / "ui_cache"`(`.gitignore`)
  포팅 — DataFrame용(`save_ui_cache_df`/`load_ui_cache_df`)은 meritz에 캐싱 대상 DataFrame이
  없어서 이식 안 함. `app.py`의 Up/Down 새로고침 버튼 핸들러에서 저장, 세션이 새로 열려
  `updown_results`가 없으면 렌더 직전에 로컬 캐시부터 채움.
- **FA 승률 (new1 §6-30)**: `_all_cycles()`에 `first_buy_date`/`close_date` 필드 추가(원래
  meritz의 `_all_cycles`엔 §6-6에서 포팅해온 P&L Actions용 필드만 있었음) + `compute_fa_win_rate(tx)`
  신설(new1과 완전히 동일한 정의·반환값). `app.py` daily-trade-box(일일거래 총 ~회) 맨 밑에
  `Total N/M(%)` + `FA N(%) · MA N(%) · MO N(%)` 두 줄 — new1과 동일 포맷(2026-09-16 당일
  new1에서 MA/MO에도 % 추가된 최종형까지 한 번에 이식). 평균 보유일수는 new1과 마찬가지로
  화면엔 표시 안 함(함수 반환값엔 `avg_days` 남아있음).
- **섹터 "미분류" 12종목 정리**: `portfolio_data.csv`에 남아있던 미분류 12종목(씨앤씨인터내셔널·
  대신증권·풀무원·앱클론·바텍·씨티케이·파라다이스·카페24·인바디·파마리서치·엘앤씨바이오·
  OCI홀딩스) 전부 **new1의 `stock_sector_cache.csv`(§6-24, 27개 수정섹터+기타2 체계)에서
  이미 값이 있는 걸 확인**하고 그대로 가져와 채움 — meritz 자체의 27개 카테고시 전면 개편(§6-24)은
  **안 함**(요청 범위 밖, meritz는 여전히 구 세분류 섹터 체계 그대로). 즉 이 12종목만
  "기타2"(new1의 153개 밖 분류)나 27개 카테고리 값(화장품·의류·바이오 등)을 갖게 돼서
  **meritz 안에 신구 섹터 체계가 일부 섞여 있음** — 의도된 상태(§6-3에 이미 적혀있던
  "미분류 종목은 new1 캐시에서 찾아본다"는 절차를 그대로 실행한 것). `update_sector_cache()`로
  `stock_sector_cache.csv`에도 반영해둬서, 이 12종목이 전량매도 후 재진입해도 자동으로
  같은 섹터가 다시 배정됨. **주의**: meritz의 `apply_transaction`은 신규 보유 종목 생성
  시점에만 캐시에서 섹터를 읽어오고(§6-3), 이미 "미분류"로 박제된 기존 행은 캐시를 갱신해도
  자동으로 안 고쳐진다 — 그래서 `portfolio_data.csv`의 섹터 셀도 직접 같이 패치함(new1
  `fix_sector.py`와 같은 원칙, meritz엔 전용 스크립트가 없어 이번엔 인라인으로 처리).

### 6-8. ingest_daily.py가 매일 라이브 시세도 무조건 새로고침 (2026-09-17, new1 §6-2 6번째 재발 포팅)
- **동기**: 예전엔 "코드 미확인 종목이 있을 때만" 세션이 수동으로 `refresh_all_prices()`를
  돌리는 구조였는데, 코드가 이미 다 있는 평범한 날엔 이 스텝 자체가 통째로 스킵됐다. 그러면
  `portfolio_data.csv`에 커밋되는 현재가/등락률은 "마지막으로 라이브 새로고침이 실제로
  성공했던 시점"에 그대로 멈춘 채 커밋되고, 그 이후 며칠이고 아무도 안 건드린다. 실제로
  겪음: 대부분 종목이 **9/15 17:22** 시점 값으로 이틀 넘게 멈춰있었고, 사용자가 "메리츠는
  어제 대비 자산이 올랐는데 왜 -4,050원으로 나오니?"라고 지적해서 발견 — app.py의
  day_change가 (오늘 live total_assets, stale 가격 기반) − (dom_asset_history의 어제 스냅샷,
  그것도 마찬가지로 그 전날 stale 가격으로 계산된 값)을 빼다 보니 실제 시장 움직임과
  무관한 값이 나왔다.
- **new1과 다른 점 — meritz는 확정 종가 장치(compute_metrics_at_close, new1 §6-2 5번째
  재발)가 아직 없다**: new1은 이 라이브 새로고침을 "표시용 현재가"에만 영향 주고 그날의
  asset_history 스냅샷 자체는 확정 종가로 별도 계산해서 안전한데, meritz는 스냅샷도
  `compute_metrics(holdings2, ...)`가 그 시점 holdings2의 현재가를 그대로 쓴다 — 즉 라이브
  새로고침을 **스냅샷 계산 앞**(코드 보충 직후, `save_transactions`/`save_holdings` 전)에
  넣어서, 최소한 "며칠 전 가격"이 아니라 "지금 라이브 가격"으로는 그날 스냅샷이 찍히게 했다.
  완벽한 확정종가 방식은 아직 아니라서(장중에 ingest를 돌리면 그 순간의 라이브가가 스냅샷에
  들어감), **meritz에 compute_metrics_at_close/resolve_trading_date를 포팅하는 건 여전히
  별개의 남은 과제**(§6-4에 이미 있던 "meritz는 아직 resolve_trading_date 없음" 메모와 같은
  갈래) — 이번 수정은 "멀티데이 staleness"만 없앤 것이지 "장중 반영 시 스냅샷 오염" 문제
  전체를 해결한 건 아니다. **→ 바로 다음(§6-9)에서 이 남은 과제도 포팅함.**
- **수정 직후 조치**: 세션이 직접 `refresh_all_prices()`를 한 번 더 돌려 오늘자 라이브
  가격으로 `portfolio_data.csv`를 갱신·커밋(43종목 갱신, 실패 없음) — 다음 ingest부터는
  자동으로 이 스텝을 타므로 재발 안 함.

### 6-9. compute_metrics_at_close 포팅 — 스냅샷도 확정 종가 기준으로 (2026-09-17, new1 §6-2 5번째 재발 포팅)
- **동기**: §6-8을 고치고도 "메리츠 어제보다 2~3만원 올랐는데 여전히 -5,990원으로 나온다"는
  지적이 이어짐 — §6-8은 "표시용 현재가/스냅샷 계산에 쓰는 현재가"가 매일 안 갱신되는
  문제만 없앴을 뿐, **스냅샷 자체가 확정 종가가 아니라 그 순간의 라이브가를 쓴다는 더 근본
  문제**는 그대로 남아있었다. 실측으로 확인: 9/16 `dom_asset_history` 값(5,080,500원)이
  실제로는 9/16 당일 확정 종가가 아니라 그 전날(9/15) 무렵 가격 그대로 찍혀있었음 —
  confirmed close로 다시 계산하니 **5,049,095원**이 나왔고(−31,405원 차이), 이 stale
  베이스라인 때문에 "오늘 대비"가 계속 잘못된 부호로 나왔다(실측: 틀린 베이스라인으로
  day_change = −3,415원, 정정된 베이스라인으로 day_change = **+27,990원** — 사용자가
  체감한 "2~3만원 올랐다"와 정확히 일치).
- **수정**: new1의 `compute_metrics_at_close(df, cash, trade_date)`(§6-2 5번째 재발)를
  meritz에 포팅 — `portfolio_core.compute_metrics_at_close(df, cash, trade_date,
  fx_rate=1.0)`. 종목코드별로 `fetch_daily_price_history`(KRX 전용)로 그 trade_date의
  확정 종가를 조회해 평가하고, 없으면(당일 장중 반영 등) 실시간 시세로, 그마저 없으면
  기존 현재가로 폴백한다. **레드와이어(RDW) 등 통화="USD" 종목은 이 함수가 확정 종가를
  못 구해와 기존 현재가 그대로 쓰는데, `dom_asset_history`(§6-4)가 애초에 USD 종목을
  제외하므로 이 함수의 목적(국내 스냅샷 정확도)엔 영향 없다.** `ingest_daily.py`가
  `compute_metrics(holdings2, cash, fx_rate)`로 스냅샷용 `df`/`stock_val`/`total_assets`를
  계산하던 걸 `compute_metrics_at_close(holdings2, cash, trade_date, fx_rate)`로 교체 —
  이 값들은 `snapshot_history`/`snapshot_sector_history`/`snapshot_dom_asset_history`뿐
  아니라 반영 후 콘솔 요약 출력에도 그대로 쓰여 new1과 동일한 패턴.
- **기존 오염된 9/16 값도 정정**: 9/16 이후 거래가 없어(현재 보유 구성 = 9/16 당시 구성과
  동일) 현재 holdings로 confirmed-close 재계산이 안전했음 — `snapshot_dom_asset_history
  (5049095.0, "2026-09-16")`로 그 자리에서 덮어씀. **주의**: 이 방식(현재 holdings로
  과거 날짜를 재계산)은 그 날짜 이후 거래가 없었을 때만 안전 — 거래가 있었다면 그 날짜
  시점의 holdings 구성 자체가 지금과 달라서 이 방법을 쓸 수 없다(체크포인트나 재생이
  필요해짐, meritz는 체크포인트 자체가 없음 — new1과 다른 점).
- **여전히 남은 차이(수용)**: new1은 `resolve_trading_date()`로 장 시작 전/주말 새로고침이면
  직전 거래일로 자동 보정하는데, meritz는 아직 이 함수 자체가 없다(§6-4에 이미 있던 메모) —
  `compute_metrics_at_close`는 trade_date를 받은 그대로 신뢰하므로, ingest를 실행하는 날짜
  인자가 정확해야 한다(지금까지 실제로 문제 된 적은 없음, 매매일지 반영일을 사람이 직접
  넘기므로).
- **new1 쪽 원본**: new1 `claude.md` §6-2 "6번째 재발" 참고, GS리테일 실측 사례(등락률
  -5.79% stale → 실제 -0.21%)로 처음 발견됨.

### 6-10. 확정 종가 로직을 portfolio_core.confirmed_close_or_live로 통합 (2026-09-17, new1 §6-2 7번째 재발 포팅)
- **동기**: `ingest_daily.py`의 "확정 종가 우선, 없으면 실시간 폴백"(`_close_on`) 로직이
  처음부터 new1·meritz 각자 **로컬 클로저로 복제**돼 있었다 — "같은 함수인데 왜 파일이
  두 개냐"는 사용자 지적(2026-09-17)으로 드러남. 실제로 이 복제 때문에 이 레포의
  `index_history[9/16]`이 확정 종가(6,717.97·815.98)가 아니라 그날 장중 어느 시점
  스냅(6,653.21·805.7, 65p·10p 차이)으로 커밋된 채 방치돼, 그 이후 "당일" 코스피/코스닥/
  혼합지수 계산이 전부 실제보다 크게 부풀려지는 사고로 이어짐(사용자가 "코스피 0.75%인데
  왜 혼합지수가 1.90%냐"고 지적해서 발견). `bigcap_history[9/14~9/16]`도 new1과 함께
  확정 종가와 최대 33,000원(SK하이닉스 9/16) 어긋나 있었음 — SamHynix extracted가
  대형주 비중을 `1/(1−W)`로 증폭하는 구조라 이 오차가 화면에서는 훨씬 크게 보였음.
- **수정**: `portfolio_core.confirmed_close_or_live(code, trade_date, fallback)` 신설 —
  new1의 동명 함수와 **완전히 동일한 구현**(둘 중 하나만 고치는 일이 없도록 두 docstring
  서로가 서로를 참조하게 해둠). `ingest_daily.py`는 이제 `_close_on = core.
  confirmed_close_or_live`로 별칭만 두고 직접 호출 — 로컬 클로저 삭제. 오염됐던
  `index_history[9/16]`/`bigcap_history[9/14~16]`는 `fetch_daily_price_history`로
  재조회한 확정 종가로 두 레포 모두 덮어씀.
- **교훈**: 로직이 여러 파일(레포)에 복제돼 있으면 "지금은 똑같아 보여도" 실행 시점에
  따라 각 파일이 서로 다른 값을 커밋하게 될 잠재 위험이 항상 있다 — new1/meritz처럼
  물리적으로 분리된 두 레포 사이에서도 "같은 로직"은 최대한 문자 그대로 동일한 함수로
  유지하고, 앞으로 이런 헬퍼를 새로 만들 때는 처음부터 양쪽에 똑같이 추가할 것.
