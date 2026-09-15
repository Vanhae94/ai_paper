import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDER_PATH = ROOT / ".claude" / "skills" / "ai-paper-trends" / "scripts" / "render.py"
SPEC = importlib.util.spec_from_file_location("paper_trends_render", RENDER_PATH)
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


class StreakRenderingTests(unittest.TestCase):
    def test_missing_iso_week_breaks_streak_badge(self):
        week = {
            "week_id": "2026-W38",
            "month_folder": "2026.09",
            "date_range_ko": "2026-09-14 ~ 09-20",
            "papers": [
                {
                    "id": "paper-1",
                    "title": "Example Paper",
                    "rank": 1,
                    "authors": [],
                    "published_at": None,
                    "raw": {"upvotes": 1, "num_comments": 0, "github_stars": 0},
                    "links": [
                        {
                            "rank": 1,
                            "label": "HuggingFace",
                            "url": "https://huggingface.co/papers/paper-1",
                        }
                    ],
                    "classify": None,
                    "tier1": None,
                    "tier2": None,
                    "learning": None,
                }
            ],
            "week_summary": {},
        }
        index_data = {
            "weeks_covered": ["2026-W36", "2026-W38"],
            "paper_weeks": {"paper-1": ["2026-W36", "2026-W38"]},
            "per_week": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            week_dir = root / "_data" / "weeks"
            week_dir.mkdir(parents=True)
            (week_dir / "2026-W38.json").write_text(
                json.dumps(week), encoding="utf-8"
            )

            report_path = render.render_week(str(root), "2026-W38", {}, index_data)
            report = Path(report_path).read_text(encoding="utf-8")

        self.assertNotIn("badge--streak", report)


class LinkRenderingTests(unittest.TestCase):
    def test_github_stars_are_hidden_without_a_github_link(self):
        paper = {
            "id": "paper-1",
            "title": "Example Paper",
            "rank": 1,
            "authors": [],
            "published_at": None,
            "raw": {"upvotes": 1, "num_comments": 0, "github_stars": 24014},
            "links": [
                {
                    "rank": 1,
                    "label": "HuggingFace",
                    "url": "https://huggingface.co/papers/paper-1",
                }
            ],
            "classify": None,
            "tier1": None,
            "tier2": None,
            "learning": None,
        }

        card = render.build_card(paper, 1, {})

        self.assertNotIn("badge--star", card)


if __name__ == "__main__":
    unittest.main()
