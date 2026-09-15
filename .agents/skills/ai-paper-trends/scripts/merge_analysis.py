#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_analysis.py — Claude가 작성한 분석 패치를 주차 기록에 병합

Claude는 거대한 weeks/*.json을 직접 수기 편집하지 않는다(오류·토큰 낭비).
대신 분석 결과만 담은 작은 패치 JSON을 작성하고, 이 스크립트가 raw를 보존한 채
classify/tier1/tier2/learning/week_summary 만 안전하게 합친다(멱등, 부분 갱신 가능).

패치 형식:
{
  "week_id": "2026-W25",
  "papers": {
    "<arxiv_id>": { "classify": {...}, "tier1": {...}, "tier2": {...}, "learning": {...} },
    ...
  },
  "week_summary": { ... }
}
(papers의 각 키는 일부만 있어도 됨 — 있는 키만 갱신. tier2는 심층 분석한 논문에만.)

사용: py merge_analysis.py --root "C:\\...\\논문정리" --patch "C:\\...\\patch.json"
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MERGE_KEYS = ("classify", "tier1", "tier2", "learning", "title_ko")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--patch", required=True)
    args = ap.parse_args()

    with open(args.patch, encoding="utf-8") as f:
        patch = json.load(f)

    week_id = patch.get("week_id")
    if not week_id:
        print("ERROR: patch에 week_id 없음", file=sys.stderr)
        sys.exit(1)

    week_path = os.path.join(args.root, "_data", "weeks", f"{week_id}.json")
    if not os.path.exists(week_path):
        print(f"ERROR: {week_path} 없음. 먼저 fetch_papers.py 실행", file=sys.stderr)
        sys.exit(1)

    with open(week_path, encoding="utf-8") as f:
        week = json.load(f)

    patch_papers = patch.get("papers") or {}
    by_id = {p.get("id"): p for p in week.get("papers", [])}
    updated = 0
    unknown = []
    for pid, fields in patch_papers.items():
        target = by_id.get(pid)
        if not target:
            unknown.append(pid)
            continue
        for k in MERGE_KEYS:
            if k in fields:
                target[k] = fields[k]
        updated += 1

    if "week_summary" in patch:
        week["week_summary"] = patch["week_summary"]

    with open(week_path, "w", encoding="utf-8") as f:
        json.dump(week, f, ensure_ascii=False, indent=2)

    print(f"STATUS=ok week={week_id} updated_papers={updated}")
    if unknown:
        print(f"WARN: weeks 파일에 없는 id(무시됨): {', '.join(unknown)}", file=sys.stderr)
    if "week_summary" in patch:
        print("week_summary 갱신됨")


if __name__ == "__main__":
    main()
