# 📄 AI Papers Weekly — AI 논문 트렌드 관측 일지

매주 [HuggingFace 트렌딩 논문](https://huggingface.co/papers/trending) 상위 6편을 자동 수집하고,
Claude가 한국어로 분석·요약하며, 누적 데이터로 AI 시장 동향 인사이트를 도출해
**예쁜 HTML 리포트**로 정리하는 개인 학습용 시스템.

> **핵심 철학:** 결정론적 작업(수집·집계·렌더)은 Python 스크립트가, 판단·서술(분석·인사이트)은 Claude가 맡는다.
> Python 표준 라이브러리만 사용 — **추가 설치(pip) 없음**.

---

## ⚡ 매주 사용법 (TL;DR)

Claude Code에서 이 폴더를 열고:

```
이번 주 논문 정리해줘
```
또는 슬래시 커맨드 `/ai-paper-trends` 입력.

그러면 Claude가 자동으로:
1. **수집** — HF 트렌딩 상위 6편을 가져옴
2. **1차 분석** — 6편 전부 초록 기반 한국어 요약·분류
3. **심층 분석(선택)** — "더 깊게 볼 논문 번호?"를 물어봄 → 고른 논문만 arXiv 원문까지 심층 분석
4. **트렌드 인사이트** — 누적 데이터로 "최근 동향" 도출
5. **HTML 생성** — 주간 리포트 + 월간/마스터 인덱스 갱신

결과물: [`index.html`](index.html)(전체 대시보드)와 `2026.06/2026-Wxx_주간리포트.html`.

---

## 🧭 동작 원리 (파이프라인)

```
사용자: "이번 주 논문 정리해줘"  ─▶  Claude가 SKILL.md 절차를 오케스트레이션
  │
  ├─ ① fetch_papers.py   HF API 호출 → 평탄화 → _data/weeks/<주차>.json 저장 (멱등)
  ├─ ② [Claude]          6편 초록 분석 → 패치 JSON 작성 → merge_analysis.py로 병합
  ├─ ③ [Claude+사용자]   관심 논문만 WebFetch(arXiv) 심층 분석 → tier2 병합
  ├─ ④ rollup.py         전 주차 집계 → _data/index.json (정량 신호 단일 출처)
  │     [Claude]          누적 신호 근거로 week_summary(동향) 작성
  └─ ⑤ render.py         분석 JSON → 템플릿 주입 → HTML + 인덱스 멱등 재생성
                         (연속 등장 논문엔 "🔁 N주 연속" 배지 자동 부착)
```

**데이터 출처:** `https://huggingface.co/api/daily_papers?sort=trending&limit=6` (공식 JSON API, HTML 파싱 불필요).
각 논문에서 제목·초록·HF AI요약·키워드·업보트·댓글·저자·GitHub·링크를 가져온다.

---

## 📁 폴더 구조

```
논문정리/                                  ← 프로젝트 루트 (이 폴더 전체가 자기완결형)
├─ README.md                             ← 이 문서
├─ index.html                            ← 마스터 대시보드 (전체 주차/월)
├─ 2026.06/                              ← 월별 폴더 (점 구분)
│  ├─ index.html                         ← 월간 인덱스 (+ 월말 종합 임베드)
│  └─ 2026-W25_주간리포트.html            ← 주간 리포트
├─ _assets/
│  ├─ style.css                          ← 단일 공통 디자인 시스템 "Aurora Ink"
│  └─ app.js                             ← 테마 토글 등 (외부 라이브러리 0)
├─ _data/                                ← 모든 데이터 (재생성·트렌드 분석 소스)
│  ├─ taxonomy.json                      ← 폐쇄형 카테고리 10개 + 키워드 별칭 사전
│  ├─ index.json                         ← 전 주차 정량 롤업 (rollup.py가 매주 재생성)
│  ├─ weeks/<주차>.json                  ← 주차별 원본+분석 기록 (불변)
│  ├─ weeks/<주차>.raw.json              ← API 원본 응답 박제 (감사용)
│  ├─ analysis/<주차>.patch.json         ← Claude가 작성하는 분석 패치
│  └─ months/<YYYY.MM>.json              ← 월간 종합 트렌드 (월말 생성)
└─ .claude/
   ├─ launch.json                        ← 미리보기용 정적 서버 설정 (선택)
   └─ skills/ai-paper-trends/
      ├─ SKILL.md                        ← 주간 워크플로우 절차 (Claude의 지침)
      ├─ schema.json                     ← 논문 객체 데이터 명세
      ├─ scripts/                        ← fetch / merge / rollup / render
      └─ templates/                      ← report / monthly / master_index / paper_card
```

---

## 🔧 구성요소 (스크립트)

모든 스크립트는 `py <스크립트> --root "<프로젝트 루트 절대경로>"` 형식. 위치:
`.claude/skills/ai-paper-trends/scripts/`

| 스크립트 | 역할 | 주요 인자 |
|---|---|---|
| `fetch_papers.py` | HF API 수집·평탄화·멱등 저장 | `--root` `--week auto\|YYYY-Wnn` `--limit 6` `--force` `--date YYYY-MM-DD` |
| `merge_analysis.py` | Claude의 분석 패치를 주차 기록에 병합(`raw` 보존) | `--root` `--patch <경로>` |
| `rollup.py` | 전 주차 정량 롤업(`index.json`) 재생성 | `--root` |
| `render.py` | 분석 JSON → HTML 렌더 + 인덱스 재생성 | `--root` `--week YYYY-Wnn`(생략 시 인덱스만) |

**멱등성:** 같은 주차 재수집은 `--force` 없으면 스킵. merge/rollup/render는 항상 안전하게 재실행 가능(중복 링크 없음).

---

## 🗃️ 데이터 모델 (3층)

1. **`weeks/<주차>.json`** — 불변 기록. `raw`(API 원본 평탄화) + Claude가 채우는 `classify`/`tier1`/`tier2`/`learning` + 주차 `week_summary`.
   - `tier1` = 1차(초록 기반, 6편 전부) · `tier2` = 심층(arXiv 원문, 관심 논문만, 없으면 `null`).
   - 정확한 필드는 [`schema.json`](.claude/skills/ai-paper-trends/schema.json) 참조.
2. **`index.json`** — `rollup.py`가 weeks 전체를 읽어 결정론적으로 만드는 **정량 신호 단일 출처**
   (카테고리/키워드 추이, `paper_weeks`=논문별 등장 주차 이력, 논문-주차 매핑, 누적 합계).
   차트·동향 추론·연속 등장(streak) 계산의 근거.
3. **`taxonomy.json`** — 폐쇄형 1차 카테고리 10개(주차 간 비교용) + `keyword_aliases`(동의어 통합 사전).

> Claude는 거대한 weeks JSON을 직접 편집하지 않고, 작은 **패치 JSON**(`analysis/<주차>.patch.json`)을 작성해
> `merge_analysis.py`로 병합한다 → 안전·재현 가능. 분석을 고치려면 패치만 수정 후 재병합·재렌더.
> 1차 분석과 심층(tier2)은 패치를 나눠도 된다(예: `<주차>.patch.json` + `<주차>.deep.patch.json`).
> `merge_analysis.py`는 **있는 키만 갱신**하므로 여러 번 부분 병합해도 안전하다.

---

## 📈 트렌드 분석 방법론 (과적합 방지가 핵심)

표본이 주 6편으로 작기 때문에 **정량(스크립트 집계)과 정성(Claude 서술)을 분리**하고, 정성 문장은 반드시 정량 근거를 인용한다.

- **콜드스타트 분기**(`index.json`의 `totals.weeks` 기준):
  - 1주차 → "기준선 수립 중"(비교 데이터 없음)
  - 2주차 → 직전 주 대비 단순 등장/소멸만 (성급한 "부상/지속" 단정 금지)
  - 3주차+ → 지속(최근 3~4주 중 3주+) / 부상(서로 다른 2주+ 등장) / 식어감(3주+ 데이터 시) 판정
- **상시 경고:** "주 6편 표본·HF 인기 편향" caveat 고정. 업보트는 중요도가 아닌 **관심도** 지표.
- **시각화:** 외부 차트 라이브러리 0 — 키워드 빈도는 CSS 막대, 주차 추이는 인라인 SVG로 그린다.

---

## 🔁 연속 등장(streak) 추적

같은 논문이 여러 주 연속 트렌딩에 오르면 카드에 **"🔁 N주 연속"** 배지가 자동으로 붙는다.

- `rollup.py`가 논문별 등장 주차를 `index.json`의 `paper_weeks`에 기록한다.
- `render.py`가 렌더 대상 주차에서 거슬러 올라가며 **연속 등장 주차 수(as-of-주차)** 를 계산한다.
  예: W26 리포트의 어떤 논문이 W25·W26에 있었다면 그 시점 기준 "2주 연속"으로 표시(W27까지 보지 않음).
- 2주 이상일 때만 배지를 단다. 신규 논문은 배지 없음.
- **완전 자동** — Claude 작업 불필요. 과거 주차를 다시 렌더하면 그 시점 기준으로 소급 표시된다.

> 배지 스타일은 `_assets/style.css`의 `.badge--streak`(오로라 제이드). 임계값(2주 이상)은 `render.py`의 `build_card`에서 조정.

---

## 🎨 디자인 시스템 — "Aurora Ink"

- 컨셉: 잉크빛 심우주 위 오로라 — 개인 연구 관측 일지. **다크 기본 + 라이트 토글**(localStorage 기억).
- 폰트: Pretendard(본문) · Fraunces(헤드라인) · Space Mono(수치·ID) — CDN, 차단 시 시스템 폰트로 폴백.
- 단일 [`_assets/style.css`](_assets/style.css) 하나로 모든 페이지 일관. 빌드 단계 없이 브라우저에서 바로 열림.
- 색감·무드를 바꾸려면 `style.css` 상단의 CSS 변수(`:root`)만 수정하면 전체가 일관되게 바뀐다.

---

## 🚀 새 환경에서 셋업 (포터빌리티)

**이 폴더 전체를 복사**하면 그대로 동작한다. 시스템이 자기완결형이기 때문:

1. **필요 조건**
   - Python **3.8+ 필요**(`datetime.date.fromisocalendar` 사용, 권장 3.10+). 추가 패키지 **없음**.
   - 인터넷 (HF API 수집 + 폰트 CDN + arXiv 심층 조회).
   - 분석·인사이트 단계는 **Claude Code** 가 수행(스킬 자동 인식). → 아래 "수동 실행"으로 LLM 없이도 부분 운용 가능.
2. **경로**: 스크립트는 `--root`로 루트를 받으므로 폴더 위치가 어디든 OK. 한글·공백 경로는 항상 따옴표.
3. **OS 차이**: Windows는 `py`, macOS/Linux는 `python3`. 경로 구분자만 주의(스크립트는 `os.path`로 OS 무관).
4. **스킬 인식**: Claude Code에서 이 폴더를 작업 디렉터리로 열면 `.claude/skills/ai-paper-trends`가 자동 등록된다.
   전역으로 쓰려면 `.claude/skills/ai-paper-trends` 폴더를 `~/.claude/skills/`로 복사.
5. **확인**: `py ".claude/skills/ai-paper-trends/scripts/fetch_papers.py" --root "<루트>" --week auto` 가
   `STATUS=ok ...`를 출력하면 정상.

---

## 🛠️ 스킬 없이 수동 실행 (LLM 없는 환경 폴백)

결정론적 단계(수집·집계·렌더)는 Claude 없이도 돈다. 분석(②③④의 서술)만 사람이 패치 JSON으로 채우면 된다.

```bash
ROOT="<프로젝트 루트>"
S="$ROOT/.claude/skills/ai-paper-trends/scripts"

# ① 수집
py "$S/fetch_papers.py" --root "$ROOT" --week auto

# ② 분석: _data/analysis/<주차>.patch.json 을 직접 작성
#    (형식은 merge_analysis.py 상단 주석 / schema.json 참고)
py "$S/merge_analysis.py" --root "$ROOT" --patch "$ROOT/_data/analysis/<주차>.patch.json"

# ④ 집계
py "$S/rollup.py" --root "$ROOT"

# ⑤ 렌더
py "$S/render.py" --root "$ROOT" --week <주차>
```

분석을 비워두고 `fetch → render`만 돌려도 초록·HF AI요약 기반의 폴백 카드가 렌더된다.

---

## 🗓️ 월간 종합 트렌드

월말(또는 "월간 종합" 요청) 시, 그 달을 관통하는 3~4개 흐름을 도출해 `_data/months/<YYYY.MM>.json`에 저장하고
`render.py`를 (week 지정 없이 또는 최신 주차로) 다시 돌리면, 해당 월 `index.html` 상단에 종합 섹션
(서술 + 주차별 관심도 추이 SVG)이 자동 임베드된다. 파일이 없으면 "월말에 생성됩니다" 안내만 표시.

형식:

```json
{
  "month": "2026.06",
  "headline_ko": "그 달을 한 줄로 요약",
  "synthesis": [
    { "title": "흐름 제목", "tag": "persist | emerging | cooling",
      "body": "정량 신호를 인용한 근거 + 개인 학습자 관점 시사점" }
  ]
}
```

`tag`는 리포트에서 **지속 / 부상 / 식어감** 색상 배지로 렌더된다.

---

## 🧯 트러블슈팅

| 증상 | 원인·해결 |
|---|---|
| `FETCH_ERROR` | 네트워크/HF API 일시 오류 → 잠시 후 재시도. 부분 산출물은 만들지 않음. |
| `STATUS=exists` | 이번 주는 이미 수집됨. 다시 받으려면 `--force` 추가. |
| HTML 글꼴이 밋밋 | 폰트 CDN 차단/오프라인 → 시스템 폰트로 폴백(정상). |
| 디자인 변경이 안 보임 | 브라우저 CSS 캐시 → 새로고침(Ctrl+F5). |
| 한글 깨짐 | 모든 파일 I/O는 UTF-8. 새 스크립트 추가 시 `encoding="utf-8"` 유지. |
| `py`를 못 찾음 | macOS/Linux면 `python3`로 교체. |

---

## 📌 자주 쓰는 명령 요약

```bash
# 이번 주 수집
py ".claude/skills/ai-paper-trends/scripts/fetch_papers.py" --root "." --week auto
# 분석 병합
py ".claude/skills/ai-paper-trends/scripts/merge_analysis.py" --root "." --patch "_data/analysis/2026-W26.patch.json"
# 정량 롤업
py ".claude/skills/ai-paper-trends/scripts/rollup.py" --root "."
# 주간 렌더(+인덱스)
py ".claude/skills/ai-paper-trends/scripts/render.py" --root "." --week 2026-W26
# 인덱스만 재생성
py ".claude/skills/ai-paper-trends/scripts/render.py" --root "."
```

> 자세한 주간 절차는 [`SKILL.md`](.claude/skills/ai-paper-trends/SKILL.md), 데이터 명세는 [`schema.json`](.claude/skills/ai-paper-trends/schema.json) 참조.
