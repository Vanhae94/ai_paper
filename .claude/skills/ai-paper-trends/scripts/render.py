#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — 분석 JSON → 예쁜 HTML 리포트 (템플릿 주입)

주차별 weeks/*.json(Claude가 분석 채움) + index.json(정량 롤업)을 읽어
report.html / monthly.html / master_index.html / paper_card.html 템플릿에 주입한다.
조건부 렌더(빈 링크·미수행 심층 생략), 순수 CSS/SVG 시각화, 인덱스 멱등 재생성.

사용:
  py render.py --root "C:\\...\\논문정리" --week 2026-W25   # 주간 렌더 + 인덱스 재생성
  py render.py --root "C:\\...\\논문정리"                    # 인덱스만 재생성
"""
import argparse
import datetime
import glob
import html
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(SKILL_DIR, "templates")
LEFTOVER = re.compile(r"\{\{[A-Z_]+\}\}")


# ----------------------------- 유틸 -----------------------------
def esc(s):
    return html.escape(str(s if s is not None else ""))


def short(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1000:
        return f"{n/1000:.1f}k".replace(".0k", "k")
    return str(n)


def load_tpl(name):
    with open(os.path.join(TPL_DIR, name), encoding="utf-8") as f:
        return f.read()


def fill(tpl, mapping):
    for k, v in mapping.items():
        tpl = tpl.replace("{{" + k + "}}", v if v is not None else "")
    return LEFTOVER.sub("", tpl)  # 미사용 토큰 제거


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_weeks(root):
    weeks = []
    for p in sorted(glob.glob(os.path.join(root, "_data", "weeks", "*.json"))):
        if p.endswith(".raw.json"):
            continue
        weeks.append(load_json(p))
    weeks.sort(key=lambda w: w.get("week_id", ""))
    return weeks


def cat_label_map(taxonomy):
    m = {}
    for c in (taxonomy.get("primary_categories") or []):
        m[c["key"]] = c.get("label_ko", c["key"])
    return m


def now_str():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def first_sentence(text):
    t = (text or "").replace("\n", " ").strip()
    if not t:
        return ""
    for sep in ["다. ", ". ", "다.", "."]:
        idx = t.find(sep)
        if 0 < idx < 160:
            return t[:idx + (1 if sep.strip() == "." else 2)].strip()
    return t[:140].strip()


def paper_tags(paper):
    cls = paper.get("classify") or {}
    if cls.get("topic_tags"):
        return cls["topic_tags"]
    return [k.strip().lower().replace(" ", "-") for k in (paper.get("raw", {}).get("ai_keywords") or [])]


# ----------------------------- 카드 -----------------------------
def build_card(paper, idx, cat_labels, streak=1):
    raw = paper.get("raw", {})
    t1 = paper.get("tier1") or {}
    t2 = paper.get("tier2")
    learn = paper.get("learning") or {}
    cls = paper.get("classify") or {}

    pid = paper.get("id", "")
    hf_url = next((l["url"] for l in paper.get("links", []) if l.get("rank") == 1),
                  f"https://huggingface.co/papers/{pid}")

    # 카테고리 라벨
    cat = ""
    if cls.get("primary_category") and cls["primary_category"] != "(미분류)":
        cat = cat_labels.get(cls["primary_category"], cls["primary_category"])

    # 저자
    authors = paper.get("authors") or []
    if authors:
        head = ", ".join(authors[:3])
        authors_str = head + (f" 외 {len(authors)-3}명" if len(authors) > 3 else "")
    else:
        authors_str = "저자 정보 없음"
    if paper.get("published_at"):
        pub = str(paper["published_at"])[:10]
    else:
        pub = ""

    # 배지
    badges = [f'<span class="badge badge--up">▲ {short(raw.get("upvotes"))}</span>',
              f'<span class="badge badge--cm">💬 {raw.get("num_comments", 0)}</span>']
    if raw.get("github_stars"):
        badges.append(f'<span class="badge badge--star">★ {short(raw["github_stars"])}</span>')
    if streak and streak >= 2:
        badges.insert(0, f'<span class="badge badge--streak">🔁 {streak}주 연속</span>')
    badges_html = "".join(badges)

    # 키워드 칩
    chips = paper_tags(paper)[:6]
    chips_html = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)

    # 한 줄 요약
    one = t1.get("one_liner") or first_sentence(raw.get("ai_summary") or raw.get("summary")) or esc(paper.get("title"))
    oneliner = esc(one)

    # 본문
    if t1.get("problem") or t1.get("approach"):
        body_parts = []
        if t1.get("problem"):
            body_parts.append(f'<p>{esc(t1["problem"])}</p>')
        if t1.get("approach"):
            body_parts.append(f'<p>{esc(t1["approach"])}</p>')
        body_html = "".join(body_parts)
    else:
        fallback = raw.get("ai_summary") or (raw.get("summary") or "")[:400]
        body_html = f'<p>{esc(first_sentence_or_full(fallback))}</p>'

    # 기여
    contrib_html = ""
    if t1.get("contributions"):
        lis = "".join(f"<li>{esc(c)}</li>" for c in t1["contributions"])
        contrib_html = f'<ul class="pc-contrib">{lis}</ul>'

    # 메타
    meta_bits = []
    if t1.get("difficulty"):
        meta_bits.append(f'<span class="pc-diff">{esc(t1["difficulty"])}</span>')
    if t1.get("recommended_reader"):
        meta_bits.append(f'<span>{esc(t1["recommended_reader"])}</span>')
    if pub:
        meta_bits.append(f'<span>📅 {esc(pub)}</span>')
    if pid:
        meta_bits.append(f'<span>arXiv:{esc(pid)}</span>')
    meta_html = " · ".join(meta_bits)

    # 핵심 용어
    terms_html = ""
    if learn.get("key_terms"):
        terms_html = "".join(
            f'<span class="term"><b>{esc(kt.get("term"))}</b> {esc(kt.get("gloss"))}</span>'
            for kt in learn["key_terms"]
        )

    # 링크 버튼 (null은 fetch가 이미 제외)
    btns = []
    for l in sorted(paper.get("links", []), key=lambda x: x.get("rank", 99)):
        cls_b = "btn"
        if l.get("rank") == 1:
            cls_b = "btn btn--primary"
        elif "코드" in l.get("label", "") or "GitHub" in l.get("label", ""):
            cls_b = "btn btn--code"
        btns.append(f'<a class="{cls_b}" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])}</a>')
    links_html = "".join(btns)

    # 회상 퀴즈
    quiz_html = ""
    rq = learn.get("recall_quiz") or {}
    if rq.get("question"):
        quiz_html = (
            '<div class="quiz">'
            f'<p class="quiz__q"><b>RECALL ↺</b> {esc(rq["question"])}</p>'
            f'<details><summary>정답 보기</summary><p class="quiz__a">{esc(rq.get("answer"))}</p></details>'
            '</div>'
        )

    # 심층 분석 (tier2 있을 때만)
    deep_html = ""
    deepbadge = ""
    if t2:
        deepbadge = '<span class="deep-badge">🔬 심층</span>'
        deep_html = build_deep(t2)

    return fill(load_tpl("paper_card.html"), {
        "STAGGER": str(idx),
        "TAGS": esc(" ".join((t1.get("field_tags") or []) + chips)).lower(),
        "RANK": str(paper.get("rank", idx)),
        "CAT": esc(cat),
        "URL_HF": esc(hf_url),
        "TITLE": esc(paper.get("title")),
        "DEEPBADGE": deepbadge,
        "AUTHORS": esc(authors_str),
        "BADGES": badges_html,
        "CHIPS": chips_html,
        "ONELINER": oneliner,
        "BODY": body_html,
        "CONTRIB": contrib_html,
        "META": meta_html,
        "TERMS": terms_html,
        "LINKS": links_html,
        "QUIZ": quiz_html,
        "DEEP": deep_html,
    })


def first_sentence_or_full(text):
    t = (text or "").replace("\n", " ").strip()
    return t


def build_deep(t2):
    parts = ['<details class="deep"><summary><span class="caret">▸</span> 🔬 심층 분석 보기</summary><div class="deep__body">']
    if t2.get("method_detail"):
        parts.append(f'<h4>방법 상세</h4><p>{esc(t2["method_detail"])}</p>')
    if t2.get("experiment_setup"):
        lis = "".join(f"<li>{esc(x)}</li>" for x in t2["experiment_setup"])
        parts.append(f'<h4>실험 셋업</h4><ul>{lis}</ul>')
    if t2.get("datasets"):
        ds = "".join(
            f'<li>{esc(d.get("name",""))}'
            + (f' — {esc(d.get("scale",""))}' if d.get("scale") else "")
            + (f' ({esc(d.get("domain",""))})' if d.get("domain") else "")
            + "</li>"
            for d in t2["datasets"]
        )
        parts.append(f'<h4>데이터셋</h4><ul>{ds}</ul>')
    lim = t2.get("limitations") or {}
    if lim.get("by_authors") or lim.get("by_claude"):
        lis = ""
        for x in (lim.get("by_authors") or []):
            lis += f"<li>{esc(x)} <small>(저자 인정)</small></li>"
        for x in (lim.get("by_claude") or []):
            lis += f"<li>{esc(x)} <small>(추가 의문)</small></li>"
        parts.append(f'<h4>한계 · 비판</h4><ul>{lis}</ul>')
    rp = t2.get("reproducibility") or {}
    if rp:
        cells = []
        for label, key in [("코드", "code"), ("가중치", "weights"), ("데이터", "data"), ("라이선스", "license")]:
            if rp.get(key):
                cells.append(f'<span>{label} <b>{esc(rp[key])}</b></span>')
        note = f'<p>{esc(rp["note"])}</p>' if rp.get("note") else ""
        if cells:
            parts.append(f'<h4>재현 가능성</h4><div class="repro">{"".join(cells)}</div>{note}')
    if t2.get("my_learning_points"):
        lis = "".join(f"<li>{esc(x)}</li>" for x in t2["my_learning_points"])
        parts.append(f'<h4>📌 내 학습 포인트</h4><ul>{lis}</ul>')
    rw = t2.get("related_work") or {}
    if rw.get("prior") or rw.get("followup"):
        lis = ""
        for x in (rw.get("prior") or []):
            lis += f'<li>← {esc(x.get("name",""))}: {esc(x.get("relation",""))}</li>'
        for x in (rw.get("followup") or []):
            lis += f'<li>→ {esc(x.get("name",""))}: {esc(x.get("relation",""))}</li>'
        parts.append(f'<h4>연결 연구</h4><ul>{lis}</ul>')
    if t2.get("claude_note"):
        parts.append(f'<h4>Claude 종합 코멘트</h4><p>{esc(t2["claude_note"])}</p>')
    parts.append("</div></details>")
    return "".join(parts)


# ----------------------------- 시각화 -----------------------------
def build_kwbar(tag_counts, title="이번 주 키워드 빈도"):
    if not tag_counts:
        return ""
    rows = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    vmax = max(v for _, v in rows) or 1
    out = [f'<h4>{esc(title)}</h4>']
    for i, (t, v) in enumerate(rows):
        pct = round(v / vmax * 100)
        out.append(
            f'<div class="kwbar__row"><span title="{esc(t)}">{esc(t)}</span>'
            f'<div class="kwbar__track"><i style="--v:{pct}%;--d:{0.15+i*0.08:.2f}s"></i></div>'
            f'<b>{v}</b></div>'
        )
    return "".join(out)


def build_sparkline(points, label="주차별 관심도(업보트) 추이"):
    """points: [(wid, value), ...] 오름차순"""
    if len(points) < 2:
        return ('<h4 style="margin-top:1.4rem">' + esc(label) + '</h4>'
                '<p style="font-size:.75rem;color:var(--text-faint);font-family:var(--font-mono)">'
                '데이터 축적 중 — 2주 이상부터 추이가 표시됩니다.</p>')
    W, H, px, py = 300, 90, 14, 14
    vals = [v for _, v in points]
    vmax, vmin = max(vals), min(vals)
    span = (vmax - vmin) or 1
    n = len(points)
    coords = []
    for i, (_, v) in enumerate(points):
        x = px + i * (W - 2 * px) / (n - 1)
        y = (H - py) - (v - vmin) / span * (H - 2 * py)
        coords.append((x, y))
    line_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f'M {coords[0][0]:.1f},{H-py} ' + " ".join(f"L {x:.1f},{y:.1f}" for x, y in coords) + f' L {coords[-1][0]:.1f},{H-py} Z'
    dots = "".join(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="2.6"/>' for x, y in coords)
    labels = ""
    for i, (wid, _) in enumerate(points):
        wk = wid.split("-W")[-1] if "-W" in wid else wid
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        labels += f'<text x="{coords[i][0]:.1f}" y="{H-2}" text-anchor="{anchor}">W{esc(wk)}</text>'
    return (
        f'<h4 style="margin-top:1.4rem">{esc(label)}</h4>'
        f'<svg class="trend-svg" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">'
        '<defs>'
        '<linearGradient id="auroraStroke" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#3DDC97"/><stop offset="1" stop-color="#2BB6C9"/></linearGradient>'
        '<linearGradient id="auroraFill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#3DDC97"/><stop offset="1" stop-color="#3DDC97" stop-opacity="0"/></linearGradient>'
        '</defs>'
        f'<path class="area" d="{area}"/><polyline class="line" points="{line_pts}"/>{dots}{labels}'
        '</svg>'
    )


def build_insight(week, index_data):
    ws = week.get("week_summary") or {}
    # 좌: 서술형 인사이트
    notes = []
    if ws.get("narrative_ko"):
        notes.append(f'<div class="insight__note"><h3>📋 이번 주 요약</h3><p>{esc(ws["narrative_ko"])}</p></div>')
    if ws.get("recent_trend_ko"):
        notes.append(f'<div class="insight__note"><h3>🌊 최근 동향</h3><p>{esc(ws["recent_trend_ko"])}</p></div>')
    if ws.get("emerging_keywords"):
        chips = "".join(f'<span class="chip">{esc(k)}</span>' for k in ws["emerging_keywords"])
        notes.append(f'<div class="insight__note"><h3>✨ 새로 부상 <span class="tag tag--emerging">EMERGING</span></h3><div class="chip-row" style="margin-top:.5rem">{chips}</div></div>')
    if not notes:
        notes.append('<div class="insight__note"><p style="color:var(--text-faint)">동향 분석이 아직 작성되지 않았습니다.</p></div>')

    # 우: 이번 주 키워드 빈도 + 누적 업보트 추이
    tag_counts = {}
    for p in (week.get("papers") or []):
        for t in set(paper_tags(p)):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    kwbar = build_kwbar(tag_counts)

    spark = ""
    per_week = (index_data or {}).get("per_week") or {}
    if per_week:
        pts = [(w, per_week[w].get("total_upvotes", 0)) for w in sorted(per_week)]
        spark = build_sparkline(pts)

    return (
        '<div class="insight"><div class="insight__grid">'
        f'<div>{"".join(notes)}</div>'
        f'<aside class="kwbar">{kwbar}{spark}</aside>'
        '</div></div>'
    )


def stat_block(num, label):
    return f'<div class="stat"><span class="stat__num">{num}</span><span class="stat__label">{esc(label)}</span></div>'


# ----------------------------- 주간 리포트 -----------------------------
def render_week(root, week_id, taxonomy, index_data):
    week = load_json(os.path.join(root, "_data", "weeks", f"{week_id}.json"))
    if not week:
        print(f"ERROR: {week_id}.json 없음", file=sys.stderr)
        sys.exit(1)
    cat_labels = cat_label_map(taxonomy)
    papers = week.get("papers") or []
    ws = week.get("week_summary") or {}

    # 연속 등장(streak): 이번 주에서 거슬러 올라가며 연속으로 트렌딩한 주차 수
    weeks_covered = (index_data or {}).get("weeks_covered") or []
    paper_weeks = (index_data or {}).get("paper_weeks") or {}

    def streak_for(pid):
        appears = set(paper_weeks.get(pid, []))
        appears.add(week_id)  # 이번 주는 당연히 포함
        if week_id not in weeks_covered:
            return 1
        i = weeks_covered.index(week_id)
        s = 0
        while i >= 0 and weeks_covered[i] in appears:
            s += 1
            i -= 1
        return s

    cards = "\n".join(build_card(p, i + 1, cat_labels, streak_for(p.get("id"))) for i, p in enumerate(papers))

    total_up = sum(int(p.get("raw", {}).get("upvotes") or 0) for p in papers)
    distinct_tags = len({t for p in papers for t in paper_tags(p)})
    stats = stat_block(len(papers), "논문") + stat_block(short(total_up), "총 업보트") + stat_block(distinct_tags, "키워드")

    headline = ws.get("headline_ko") or "이번 주 트렌딩 논문을 수집·분석했습니다."
    lede = f'이번 주 한 줄 트렌드: <b>{esc(headline)}</b>' if ws.get("headline_ko") else esc(headline)
    caveat = ws.get("caveats_ko") or "주 6편 트렌딩 표본 기준이며 HuggingFace 커뮤니티 인기 편향이 있습니다. 업보트는 중요도가 아닌 ‘관심도’ 지표입니다."

    out = fill(load_tpl("report.html"), {
        "TITLE": f"{week_id} 주간 AI 논문 리포트",
        "ASSETS": "../_assets",
        "ROOT": "..",
        "MONTH_LABEL": esc(week.get("month_folder", "")),
        "EYEBROW": esc(f'{week_id} · {week.get("date_range_ko","")}'),
        "HERO_TITLE": f'이번 주 가장 주목받은 <em>AI 논문 {len(papers)}편</em>',
        "LEDE": lede,
        "STATS": stats,
        "COUNT": str(len(papers)),
        "CARDS": cards,
        "INSIGHT": build_insight(week, index_data),
        "CAVEAT": esc(caveat),
        "GENERATED": now_str(),
    })

    month_dir = os.path.join(root, week.get("month_folder", "misc"))
    os.makedirs(month_dir, exist_ok=True)
    out_path = os.path.join(month_dir, f"{week_id}_주간리포트.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"WROTE {out_path}")
    return out_path


# ----------------------------- 주차 카드 -----------------------------
def week_card(week, href):
    papers = week.get("papers") or []
    ws = week.get("week_summary") or {}
    total_up = sum(int(p.get("raw", {}).get("upvotes") or 0) for p in papers)
    tag_counts = {}
    for p in papers:
        for t in set(paper_tags(p)):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top = [t for t, _ in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
    chips = "".join(f'<span class="chip">{esc(t)}</span>' for t in top)
    title = ws.get("headline_ko") or "주간 트렌딩 리포트"
    return (
        f'<a class="week-card" href="{esc(href)}" data-tags="{esc(" ".join(top)).lower()}">'
        f'<span class="week-card__wk">{esc(week.get("week_id"))} · {esc(week.get("date_range_ko",""))}</span>'
        f'<div class="week-card__title">{esc(title)}</div>'
        f'<div class="week-card__meta"><span>📄 {len(papers)}편</span><span>▲ {short(total_up)}</span></div>'
        f'<div class="chip-row">{chips}</div>'
        '</a>'
    )


# ----------------------------- 인덱스 재생성 -----------------------------
def render_indexes(root, taxonomy, index_data):
    weeks = load_all_weeks(root)
    by_month = {}
    for w in weeks:
        by_month.setdefault(w.get("month_folder", "misc"), []).append(w)

    # 월간 인덱스
    for month, mweeks in by_month.items():
        mweeks_sorted = sorted(mweeks, key=lambda w: w.get("week_id", ""), reverse=True)
        cards = "\n".join(week_card(w, f'{w.get("week_id")}_주간리포트.html') for w in mweeks_sorted)
        m_papers = sum(len(w.get("papers") or []) for w in mweeks)
        m_up = sum(int(p.get("raw", {}).get("upvotes") or 0) for w in mweeks for p in (w.get("papers") or []))
        stats = stat_block(len(mweeks), "주차") + stat_block(m_papers, "논문") + stat_block(short(m_up), "총 업보트")
        y, mm = month.split(".") if "." in month else (month, "")
        synthesis = build_monthly_synthesis(root, month, mweeks, index_data)
        out = fill(load_tpl("monthly.html"), {
            "TITLE": f"{month} 월간 AI 논문",
            "ASSETS": "../_assets",
            "ROOT": "..",
            "EYEBROW": esc(f"{month} · 월간 관측 일지"),
            "HERO_TITLE": f"{esc(y)}년 {esc(mm)}월 <em>AI 논문 흐름</em>",
            "LEDE": f"이 달 {len(mweeks)}개 주차, 총 {m_papers}편의 트렌딩 논문을 정리했습니다.",
            "STATS": stats,
            "SYNTHESIS": synthesis,
            "WEEK_CARDS": cards,
            "GENERATED": now_str(),
        })
        mdir = os.path.join(root, month)
        os.makedirs(mdir, exist_ok=True)
        with open(os.path.join(mdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(out)
        print(f"WROTE {os.path.join(mdir, 'index.html')}")

    # 마스터 인덱스
    total_papers = sum(len(w.get("papers") or []) for w in weeks)
    distinct_kw = len((index_data or {}).get("keyword_freq") or {})
    stats = stat_block(len(weeks), "주차") + stat_block(total_papers, "논문") + stat_block(distinct_kw or "—", "누적 키워드")

    # 누적 상위 키워드 패널
    top_kw_html = ""
    kf = (index_data or {}).get("keyword_freq") or {}
    if kf:
        counts = {t: r["count"] for t, r in kf.items()}
        bar = build_kwbar(counts, title="누적 상위 키워드")
        top_kw_html = f'<section class="section"><h2 class="section-title"><span class="ix">★</span> 누적 트렌드 신호</h2><div class="insight"><aside class="kwbar">{bar}</aside></div></section>'

    # 월별 섹션
    sections = []
    for month in sorted(by_month, reverse=True):
        mweeks_sorted = sorted(by_month[month], key=lambda w: w.get("week_id", ""), reverse=True)
        cards = "\n".join(week_card(w, f'{month}/{w.get("week_id")}_주간리포트.html') for w in mweeks_sorted)
        sections.append(
            f'<div class="month-band"><h2>{esc(month)}</h2><div class="rule"></div>'
            f'<a href="{esc(month)}/index.html">월간 상세 →</a></div>'
            f'<div class="card-grid">{cards}</div>'
        )
    if not sections:
        sections.append('<div class="empty-state"><div class="big">아직 리포트가 없습니다</div>'
                        '<p>스킬을 실행해 첫 주간 리포트를 생성하세요.</p></div>')

    out = fill(load_tpl("master_index.html"), {
        "STATS": stats,
        "TOP_KEYWORDS": top_kw_html,
        "MONTH_SECTIONS": "\n".join(sections),
        "GENERATED": now_str(),
    })
    with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print(f"WROTE {os.path.join(root, 'index.html')}")


def build_monthly_synthesis(root, month, mweeks, index_data):
    """_data/months/{month}.json 이 있으면 월간 종합 섹션을 임베드. 없으면 안내."""
    data = load_json(os.path.join(root, "_data", "months", f"{month}.json"))
    if not data:
        return ('<div class="caveat"><span>🗓️</span><p>월간 종합 트렌드는 <b>월말</b>에 생성됩니다. '
                '현재는 주차별 리포트를 누적 중입니다.</p></div>')
    notes = []
    for blk in (data.get("synthesis") or []):
        tagcls = {"persist": "tag--persist", "emerging": "tag--emerging", "cooling": "tag--cooling"}.get(blk.get("tag"), "tag--persist")
        tagtxt = {"persist": "지속", "emerging": "부상", "cooling": "식어감"}.get(blk.get("tag"), "")
        tag_html = f'<span class="tag {tagcls}">{tagtxt}</span>' if tagtxt else ""
        notes.append(f'<div class="insight__note"><h3>{esc(blk.get("title"))} {tag_html}</h3><p>{esc(blk.get("body"))}</p></div>')
    # 월간 추이 (이 달 주차별 업보트)
    pts = [(w.get("week_id"), sum(int(p.get("raw", {}).get("upvotes") or 0) for p in (w.get("papers") or [])))
           for w in sorted(mweeks, key=lambda x: x.get("week_id", ""))]
    spark = build_sparkline(pts, label="이 달 주차별 관심도 추이")
    headline = data.get("headline_ko") or "이 달의 AI 연구 흐름"
    return (
        '<section class="section"><h2 class="section-title"><span class="ix">∑</span> 월간 종합 트렌드</h2>'
        f'<p class="hero__lede" style="margin-bottom:1.3rem">{esc(headline)}</p>'
        '<div class="insight"><div class="insight__grid">'
        f'<div>{"".join(notes)}</div><aside class="kwbar">{spark}</aside>'
        '</div></div></section>'
    )


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--week", default=None, help="YYYY-Wnn (지정 시 주간 렌더)")
    args = ap.parse_args()
    root = args.root

    taxonomy = load_json(os.path.join(root, "_data", "taxonomy.json"), {})
    index_data = load_json(os.path.join(root, "_data", "index.json"), {})

    if args.week:
        render_week(root, args.week, taxonomy, index_data)
    render_indexes(root, taxonomy, index_data)
    print("STATUS=ok")


if __name__ == "__main__":
    main()
