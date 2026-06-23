#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_papers.py — HuggingFace 주간 트렌딩 논문 수집기 (멱등)

HF 공식 JSON API에서 트렌딩 상위 N편을 가져와 평탄화하고,
주차별 불변 기록(_data/weeks/YYYY-Wnn.json)으로 저장한다.
분석 필드(classify/tier1/tier2/learning/week_summary)는 골격(null)만 만들고,
Claude가 이후 채운다.

설계 원칙: 네트워크 I/O·정규화·멱등성은 스크립트가 담당(결정론적, 토큰 0).
표준 라이브러리만 사용(urllib + json) — pip 설치 불필요.

사용:
  py fetch_papers.py --root "C:\\...\\논문정리" [--week auto|2026-W24] [--limit 6] [--force]
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.request
import urllib.error

# Windows 콘솔에서 한글 제목 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API_URL = "https://huggingface.co/api/daily_papers?sort=trending&limit={limit}"


def iso_week_id(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def parse_week_id(week_id: str):
    """'2026-W24' -> (2026, 24)"""
    y, w = week_id.split("-W")
    return int(y), int(w)


def monday_of_week(week_id: str) -> datetime.date:
    y, w = parse_week_id(week_id)
    return datetime.date.fromisocalendar(y, w, 1)


def month_folder_for_week(week_id: str) -> str:
    """그 주 월요일이 속한 월을 'YYYY.MM' 형식으로."""
    mon = monday_of_week(week_id)
    return f"{mon.year}.{mon.month:02d}"


def date_range_ko(week_id: str) -> str:
    mon = monday_of_week(week_id)
    sun = mon + datetime.timedelta(days=6)
    if mon.month == sun.month:
        return f"{mon.year}-{mon.month:02d}-{mon.day:02d} ~ {sun.month:02d}-{sun.day:02d}"
    return f"{mon.year}-{mon.month:02d}-{mon.day:02d} ~ {sun.year}-{sun.month:02d}-{sun.day:02d}"


def fetch_json(url: str, retries: int = 2, timeout: int = 20):
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ai-paper-trends/1.0 (personal study)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)  # 지수 백오프: 1s, 2s
    print(f"FETCH_ERROR {type(last_err).__name__}: {last_err}", file=sys.stderr)
    sys.exit(2)


def short(n) -> str:
    """업보트/스타 한국식 축약: 1234 -> '1.2k'"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1000:
        return f"{n/1000:.1f}k".replace(".0k", "k")
    return str(n)


def build_links(pid, github_repo, project_page):
    links = [
        {"rank": 1, "label": "HF 토론·요약", "url": f"https://huggingface.co/papers/{pid}"},
        {"rank": 2, "label": "arXiv 초록", "url": f"https://arxiv.org/abs/{pid}"},
        {"rank": 3, "label": "PDF 원문", "url": f"https://arxiv.org/pdf/{pid}"},
    ]
    if github_repo:
        # githubRepo는 "owner/name" 또는 전체 URL일 수 있음
        gh = github_repo
        if not str(gh).startswith("http"):
            gh = f"https://github.com/{gh}"
        links.append({"rank": 4, "label": "코드(GitHub)", "url": gh})
    if project_page:
        links.append({"rank": 5, "label": "프로젝트 페이지", "url": project_page})
    return links


def flatten(entry: dict, rank: int) -> dict:
    """HF API entry -> schema.json 논문 객체 (raw + links + 분석 골격)."""
    p = entry.get("paper") or {}
    pid = p.get("id") or ""
    github_repo = p.get("githubRepo") or entry.get("githubRepo")
    project_page = entry.get("projectPage") or p.get("projectPage")  # 보통 null
    authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]

    raw = {
        "summary": p.get("summary") or entry.get("summary") or "",
        "ai_summary": p.get("ai_summary") or "",
        "ai_keywords": p.get("ai_keywords") or [],
        "upvotes": p.get("upvotes") or 0,
        "num_comments": entry.get("numComments") or 0,   # 최상위!
        "github_repo": github_repo,
        "github_stars": p.get("githubStars") or 0,
        "project_page": project_page,
    }

    return {
        "id": pid,
        "title": p.get("title") or entry.get("title") or "",
        "title_ko": None,
        "authors": authors,
        "published_at": entry.get("submittedOnDailyAt") or entry.get("publishedAt") or p.get("publishedAt"),
        "rank": rank,
        "raw": raw,
        "links": build_links(pid, github_repo, project_page),
        # --- 아래는 Claude가 채움 ---
        "classify": None,
        "tier1": None,
        "tier2": None,
        "learning": None,
    }


def main():
    ap = argparse.ArgumentParser(description="HF 트렌딩 논문 수집 (멱등)")
    ap.add_argument("--root", required=True, help="프로젝트 루트 (논문정리 폴더 절대경로)")
    ap.add_argument("--week", default="auto", help="auto 또는 YYYY-Wnn")
    ap.add_argument("--date", default=None, help="기준 날짜 YYYY-MM-DD (week=auto일 때 사용)")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="기존 주차 파일이 있어도 재수집")
    args = ap.parse_args()

    if args.week == "auto":
        if args.date:
            base = datetime.date.fromisoformat(args.date)
        else:
            base = datetime.date.today()
        week_id = iso_week_id(base)
    else:
        week_id = args.week

    root = args.root
    data_dir = os.path.join(root, "_data", "weeks")
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, f"{week_id}.json")
    raw_path = os.path.join(data_dir, f"{week_id}.raw.json")

    # 멱등: 이미 처리한 주차는 스킵 (--force 시에만 재수집)
    if os.path.exists(out_path) and not args.force:
        print(f"STATUS=exists week={week_id} path={out_path}")
        print("이미 수집된 주차입니다. 재수집하려면 --force 를 사용하세요.")
        return

    api_data = fetch_json(API_URL.format(limit=args.limit))
    if not isinstance(api_data, list):
        print("FETCH_ERROR: 예상치 못한 응답 형식(배열 아님)", file=sys.stderr)
        sys.exit(2)

    # 전체 원본 박제(감사·재현용, 불변)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(api_data, f, ensure_ascii=False, indent=2)

    papers = [flatten(entry, i + 1) for i, entry in enumerate(api_data)]

    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    record = {
        "schema_version": 1,
        "week_id": week_id,
        "date_range_ko": date_range_ko(week_id),
        "month_folder": month_folder_for_week(week_id),
        "collected_at": now,
        "source": "huggingface daily_papers?sort=trending&limit=" + str(args.limit),
        "paper_count": len(papers),
        "papers": papers,
        "week_summary": None,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # 간결 요약만 stdout으로 (Claude가 거대 JSON 통독하지 않도록)
    print(f"STATUS=ok week={week_id} count={len(papers)} month={record['month_folder']}")
    print(f"path={out_path}")
    print(f"기간: {record['date_range_ko']}")
    for p in papers:
        gh = f" [GH★{short(p['raw']['github_stars'])}]" if p["raw"]["github_repo"] else ""
        kws = ", ".join(p["raw"]["ai_keywords"][:4])
        print(f"  {p['rank']}. {p['title']}")
        print(f"     ▲{short(p['raw']['upvotes'])} 💬{p['raw']['num_comments']}  arxiv:{p['id']}{gh}")
        if kws:
            print(f"     키워드: {kws}")


if __name__ == "__main__":
    main()
