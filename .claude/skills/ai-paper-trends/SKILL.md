---
name: ai-paper-trends
description: >-
  HuggingFace 주간 트렌딩 AI 논문 상위 6편을 수집·분석·요약하고, 누적 데이터로
  최근 AI 시장 동향 인사이트를 도출해 예쁜 한국어 HTML 리포트로 정리한다.
  "이번 주 논문 정리", "AI 논문 트렌드", "주간 논문", "월간 종합 트렌드",
  "이번 주 트렌딩 논문 분석해줘" 같은 요청에 사용. 개인 학습용.
---

# AI 논문 트렌드 분석 (ai-paper-trends)

매주 HuggingFace 트렌딩 논문 상위 6편을 수집→분석→요약하고, 누적 데이터로 AI 동향
인사이트를 도출해 한국어 HTML 리포트로 만든다. **결정론적 작업은 스크립트, 판단·서술은
너(Claude)** 가 맡는다.

## 핵심 경로

- **프로젝트 루트(ROOT)** = 이 스킬이 속한 작업 폴더. 보통 현재 작업 디렉터리이며,
  기본값은 `C:\Users\juse9\OneDrive\Desktop\지성\논문정리`.
- 스크립트: `<ROOT>\.claude\skills\ai-paper-trends\scripts\` 의 `fetch_papers.py`,
  `merge_analysis.py`, `rollup.py`, `render.py`.
- 데이터: `<ROOT>\_data\` (weeks/, analysis/, months/, taxonomy.json, index.json).
- 산출물: `<ROOT>\<YYYY.MM>\<week>_주간리포트.html`, 각 월 `index.html`, 루트 `index.html`.
- 명세: 같은 폴더의 `schema.json`(논문 객체), `<ROOT>\_data\taxonomy.json`(분류 체계).

> Windows/PowerShell. 경로에 한글·공백이 있으니 **항상 따옴표 + 절대경로**. Python은 `py` 로 실행.

---

## 주간 워크플로우 (사용자가 스킬 호출 시)

### ① 수집 (스크립트)
```
py "<ROOT>\.claude\skills\ai-paper-trends\scripts\fetch_papers.py" --root "<ROOT>" --week auto
```
- stdout의 간결 요약(번호·제목·▲업보트·arxiv id·GitHub)만 읽는다. 거대 JSON은 읽지 말 것.
- `STATUS=exists`가 나오면 이번 주는 이미 수집됨 → 재수집이 필요하면 `--force` 추가.
- `FETCH_ERROR`면 네트워크 문제 → 사용자에게 알리고 잠시 후 재시도. **부분 산출물 만들지 말 것.**
- 응답이 6편 미만이면 받은 만큼만 진행하고 리포트에 그 사실을 명시.

### ② 1차 분석 (너가 수행 — 6편 전부, 초록 기반)
`<ROOT>\_data\weeks\<week>.json`을 읽어 각 논문의 `raw.summary` + `raw.ai_summary` +
`raw.ai_keywords`만으로 분석한다. **이 단계에서 arxiv 원문은 읽지 않는다(토큰 절약).**

각 논문에 대해 `schema.json`의 형식대로 채운다:
- `classify`: `taxonomy.json`의 **폐쇄형 10개 카테고리**에서 고른다. `categories`는 ≤2개,
  `primary_category` 정확히 1개. `topic_tags`는 `ai_keywords`를 `keyword_aliases`로
  정규화한 표준형(소문자-하이픈). `method_tags`·`modality`·`confidence`도 채운다.
- `tier1`: `one_liner`(40~70자), `problem`(2~3문장), `approach`(3~4문장, 기법명 원어 병기),
  `contributions`(불릿 2~4, 가능하면 수치), `why_now`(트렌드 관점 2~3문장 — 이 시스템의 정체성),
  `difficulty`(입문/중급/고급), `recommended_reader`, `field_tags`(3~5 한국어), `interest`(raw 그대로).
- `learning`: `key_terms`(핵심 용어 3개 + 한 줄 뜻), `recall_quiz`(회상 문제 1개 Q/A), `spaced_review`.

분석을 **패치 JSON** 으로 작성한다 → `<ROOT>\_data\analysis\<week>.patch.json`
(형식은 `merge_analysis.py` 상단 주석 참고: `{week_id, papers:{<id>:{classify,tier1,learning}}, week_summary}`).
거대한 weeks JSON을 직접 수기 편집하지 말 것. 그다음:
```
py "<ROOT>\.claude\skills\ai-paper-trends\scripts\merge_analysis.py" --root "<ROOT>" --patch "<ROOT>\_data\analysis\<week>.patch.json"
```

### ③ 관심 논문 심층 분석 (대화형 — 하이브리드의 '깊은' 층)
1차 6편의 카드 요약(한 줄 핵심 + 업보트 + 분야)을 **대화창에 먼저 제시**하고 묻는다:
> "더 깊게 볼 논문이 있으면 번호로 알려주세요 (예: `1,4` / 없으면 `없음`). 선택한 논문만 arxiv 원문을 심층 분석합니다."

- 사용자가 고른 논문만 `WebFetch`로 `https://arxiv.org/abs/<id>`(가벼움) 호출, 필요 시 `pdf`.
- `tier2` 채우기: `method_detail, experiment_setup, datasets, limitations{by_authors,by_claude},
  reproducibility{code,weights,data,license,note}, my_learning_points, related_work, claude_note`.
- tier2를 패치에 추가해 다시 `merge_analysis.py` 실행. **0편이면 이 단계를 건너뛴다.**

### ④ 트렌드 인사이트 (너 + 누적 데이터)
```
py "<ROOT>\.claude\skills\ai-paper-trends\scripts\rollup.py" --root "<ROOT>"
```
- `rollup.py` stdout(누적 상위 키워드)과 `<ROOT>\_data\index.json`의 `category_timeseries` /
  `keyword_freq` / `totals.weeks` 를 근거로 `week_summary`를 작성(②의 패치에 포함하거나 추가 머지).
- `headline_ko`(히어로 한 줄), `clusters`(primary_category로 묶고 ≥2편이면 클러스터),
  `narrative_ko`(3~5문장, **반드시 정량 근거 인용**), `recent_trend_ko`, `caveats_ko`.
- **콜드스타트 분기** (`totals.weeks` 기준):
  - 1주차: `recent_trend_ko` = "기준선 수립 중 — 비교 데이터 없음". 신규/부상 강조 끔(`emerging_keywords` 비움).
  - 2주차: 직전 주 대비 단순 등장/소멸만. "부상/지속" 단어 금지.
  - 3주차+: 지속(최근 3~4주 중 3주+) / 부상(서로 다른 2주+ 등장, 1주 단발은 "단발 등장") / 식어감(3주+ 데이터 시) 판정.
- **과적합 방지**: 정성 문장은 index.json 숫자에 근거. 업보트는 "관심도"(중요도 아님). 표본 6편 한계 caveat 상시.

### ⑤ HTML 렌더 + 인덱스 갱신 (스크립트)
```
py "<ROOT>\.claude\skills\ai-paper-trends\scripts\render.py" --root "<ROOT>" --week <week>
```
- 주간 리포트 + 월간 index + 마스터 index를 멱등 재생성(중복 링크 없음).
- 연속 등장 논문은 카드에 "🔁 N주 연속" 배지가 **자동 표시**된다(rollup의 `paper_weeks` 기반으로 render가 계산 — Claude 작업 불필요).
- 끝나면 산출물 경로(`<ROOT>\<YYYY.MM>\<week>_주간리포트.html`)를 사용자에게 알리고,
  관심 논문 링크(HF/arxiv/GitHub)를 대화에도 함께 남긴다.

---

## 월간 종합 트렌드 (월말 또는 "월간 종합" 요청 시)

이번 주가 그 달의 마지막 주(다음 주가 다음 달)인지 ISO 주차로 판단해 사용자에게 제안하거나,
명시 요청 시 생성한다.

1. `index.json`의 `per_week`/`category_timeseries`에서 해당 월(`month_folder` 일치) 주차를 모은다.
2. 그 달을 관통하는 **3대 흐름**을 도출 — 각 흐름에 대표 논문 2~3편 인용 + 개인 학습자 관점 시사점.
3. `<ROOT>\_data\months\<YYYY.MM>.json` 작성:
   ```json
   { "month":"2026.06", "headline_ko":"...",
     "synthesis":[ {"title":"...","tag":"persist|emerging|cooling","body":"..."}, ... ] }
   ```
4. `render.py`를 (`--week` 없이 또는 최신 주차로) 실행 → 월간 `index.html`에 종합 섹션이 임베드된다.

---

## 견고성 체크리스트
- fetch 실패 시 파이프라인 중단(부분 산출물 금지), 사용자에게 재시도 안내.
- 같은 주 재실행은 안전(merge/rollup/render 모두 멱등). 분석을 고치려면 패치만 수정 후 재머지·재렌더.
- arxiv는 `abs` 우선(토큰 절약), 더 필요할 때만 `pdf`. WebFetch는 공개 URL만 가능.
- 분류가 애매하면 `confidence:"low"`로 표시(정량 집계엔 들어가되 트렌드 단정 근거로는 약하게).
