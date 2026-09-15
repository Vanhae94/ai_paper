#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rollup.py — 전 주차 정량 롤업 (_data/index.json 재생성)

모든 _data/weeks/*.json 을 읽어 결정론적으로 집계한다. LLM 없이 만들 수 있는
정량 신호의 단일 출처(single source of truth)이며, 차트와 '최근 동향' 추론의 근거가 된다.
매주 실행하며 항상 전체 재생성(멱등).

사용: py rollup.py --root "C:\\...\\논문정리"
"""
import argparse
import datetime
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_taxonomy(root):
    path = os.path.join(root, "_data", "taxonomy.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_alias_map(taxonomy):
    """variant(소문자) -> canonical 표준형"""
    rev = {}
    for canon, variants in (taxonomy.get("keyword_aliases") or {}).items():
        rev[canon.lower()] = canon
        for v in variants:
            rev[v.lower()] = canon
    return rev


def normalize_kw(kw, alias_map):
    k = (kw or "").strip().lower()
    if not k:
        return None
    if k in alias_map:
        return alias_map[k]
    return k.replace(" ", "-")


def paper_tags(paper, alias_map):
    """분석된 topic_tags 우선, 없으면 raw.ai_keywords를 별칭 정규화."""
    cls = paper.get("classify")
    if cls and cls.get("topic_tags"):
        tags = cls["topic_tags"]
    else:
        tags = [normalize_kw(k, alias_map) for k in (paper.get("raw", {}).get("ai_keywords") or [])]
    out = []
    seen = set()
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def primary_category(paper):
    cls = paper.get("classify")
    if cls and cls.get("primary_category"):
        return cls["primary_category"]
    return "(미분류)"


def load_weeks(root):
    weeks = []
    for p in sorted(glob.glob(os.path.join(root, "_data", "weeks", "*.json"))):
        if p.endswith(".raw.json"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                weeks.append(json.load(f))
        except Exception as e:  # noqa: BLE001
            print(f"WARN: {p} 읽기 실패: {e}", file=sys.stderr)
    weeks.sort(key=lambda w: w.get("week_id", ""))
    return weeks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    root = args.root

    taxonomy = load_taxonomy(root)
    alias_map = build_alias_map(taxonomy)
    weeks = load_weeks(root)

    category_timeseries = {}     # cat -> {week: count}
    category_upvote = {}         # cat -> {week: upvote_sum}
    keyword_freq = {}            # tag -> {weeks:set, count:int, first_seen:str}
    paper_week_map = {}          # arxiv_id -> first week seen
    paper_weeks = {}             # arxiv_id -> [등장한 모든 주차] (연속 등장/streak 계산용)
    per_week = {}                # week -> rollup
    total_papers = 0

    for w in weeks:
        wid = w.get("week_id", "?")
        papers = w.get("papers") or []
        wk_upvotes = 0
        wk_tag_count = {}
        for p in papers:
            total_papers += 1
            pid = p.get("id")
            if pid and pid not in paper_week_map:
                paper_week_map[pid] = wid
            if pid:
                paper_weeks.setdefault(pid, []).append(wid)

            cat = primary_category(p)
            category_timeseries.setdefault(cat, {})
            category_timeseries[cat][wid] = category_timeseries[cat].get(wid, 0) + 1

            up = int(p.get("raw", {}).get("upvotes") or 0)
            wk_upvotes += up
            category_upvote.setdefault(cat, {})
            category_upvote[cat][wid] = category_upvote[cat].get(wid, 0) + up

            for t in paper_tags(p, alias_map):
                rec = keyword_freq.setdefault(t, {"weeks": set(), "count": 0, "first_seen": wid})
                rec["count"] += 1
                rec["weeks"].add(wid)
                if wid < rec["first_seen"]:
                    rec["first_seen"] = wid
                wk_tag_count[t] = wk_tag_count.get(t, 0) + 1

        top_tags = sorted(wk_tag_count.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        ws = w.get("week_summary") or {}
        per_week[wid] = {
            "month_folder": w.get("month_folder"),
            "date_range_ko": w.get("date_range_ko"),
            "paper_count": len(papers),
            "total_upvotes": wk_upvotes,
            "top_tags": [t for t, _ in top_tags],
            "headline_ko": ws.get("headline_ko") or "",
            "analyzed": bool(ws),
        }

    # set -> 정렬 리스트
    keyword_freq_out = {}
    for t, rec in keyword_freq.items():
        keyword_freq_out[t] = {
            "count": rec["count"],
            "weeks": sorted(rec["weeks"]),
            "first_seen": rec["first_seen"],
        }

    index = {
        "schema_version": 1,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "weeks_covered": [w.get("week_id") for w in weeks],
        "category_timeseries": category_timeseries,
        "category_upvote_weighted": category_upvote,
        "keyword_freq": keyword_freq_out,
        "paper_week_map": paper_week_map,
        "paper_weeks": paper_weeks,
        "per_week": per_week,
        "totals": {"papers": total_papers, "weeks": len(weeks)},
    }

    out_path = os.path.join(root, "_data", "index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"STATUS=ok weeks={len(weeks)} papers={total_papers} keywords={len(keyword_freq_out)}")
    print(f"path={out_path}")
    # 최근 동향 추론을 돕는 간결 신호 (Claude가 이 stdout만 읽어도 됨)
    if keyword_freq_out:
        top = sorted(keyword_freq_out.items(), key=lambda kv: (-kv[1]["count"], kv[0]))[:8]
        print("상위 키워드(누적):")
        for t, r in top:
            print(f"  - {t}: {r['count']}회, {len(r['weeks'])}주 등장, 최초 {r['first_seen']}")


if __name__ == "__main__":
    main()
