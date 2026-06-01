import json
from datetime import date

from shushu_internship_tool.candidate_score import (
    has_effective_taste,
    normalize_score,
    parse_user_taste,
    rank_candidates,
    render_markdown,
    taste_score,
)


def test_candidate_score_ranks_matchable_runnable_project_first() -> None:
    jd = "Backend Engineer Intern with FastAPI, PostgreSQL, Docker, API design, testing, and deployment experience."
    candidates = [
        {
            "name": "broken-huge-project",
            "repo_url": "https://github.com/example/broken",
            "license": "unknown",
            "stars": 3,
            "last_commit": "2021-01-01",
            "tags": ["research"],
            "matched_jd_terms": ["api"],
            "license_score": 0,
            "runnable": False,
            "compute": "large cluster",
            "resource_fit_score": 3,
            "mod_ideas": [],
            "risk_notes": ["no license", "requires private dataset"],
        },
        {
            "name": "tiny-backend-project",
            "repo_url": "https://github.com/example/tiny",
            "license": "Apache-2.0",
            "stars": 350,
            "last_commit": "2026-05-01",
            "tags": ["fastapi", "postgresql", "docker", "deployment"],
            "matched_jd_terms": ["backend", "api design", "testing", "docker"],
            "license_score": 4,
            "runnable": True,
            "compute": "local Docker smoke-test",
            "resource_fit_score": 10,
            "mod_ideas": ["add JWT auth", "add Redis cache", "add integration tests"],
            "risk_notes": ["database migration needs setup"],
        },
        {
            "name": "okay-project",
            "repo_url": "https://github.com/example/okay",
            "license": "MIT",
            "stars": 80,
            "last_commit": "2025-08-01",
            "tags": ["sqlite"],
            "matched_jd_terms": ["database"],
            "license_score": 4,
            "runnable": "partial",
            "runnable_score": 10,
            "compute": "cpu",
            "resource_fit_score": 8,
            "mod_ideas": ["add tests"],
            "risk_notes": [],
        },
    ]

    ranked = rank_candidates(jd, candidates, today=date(2026, 5, 17))

    assert ranked[0]["name"] == "tiny-backend-project"
    assert ranked[0]["score"] > ranked[1]["score"]
    assert ranked[-1]["name"] == "broken-huge-project"

    markdown = render_markdown(ranked, jd_path="jd.txt")
    assert "主项目推荐" in markdown
    assert "tiny-backend-project" in markdown
    assert "requires private dataset" in markdown


def test_candidate_score_uses_agent_supplied_jd_matches_without_role_aliases() -> None:
    jd = "推荐算法工程师，负责视频推荐、搜索分发、大语言模型、深度学习和海量用户行为数据挖掘。"
    candidates = [
        {
            "name": "agent-selected-domain-project",
            "repo_url": "https://github.com/example/domain-project",
            "license": "MIT",
            "stars": 4500,
            "last_commit": "2026-04-01",
            "tags": ["recommendation", "pytorch", "ranking"],
            "matched_jd_terms": ["推荐算法", "搜索分发", "大语言模型", "用户行为数据"],
            "license_score": 4,
            "runnable": True,
            "compute": "local or single GPU",
            "resource_fit_score": 8,
            "mod_ideas": ["video proxy dataset", "ranking metrics dashboard"],
            "risk_notes": [],
        },
        {
            "name": "generic-web-admin",
            "repo_url": "https://github.com/example/admin",
            "license": "MIT",
            "stars": 300,
            "last_commit": "2026-04-01",
            "tags": ["react", "dashboard"],
            "matched_jd_terms": [],
            "license_score": 4,
            "runnable": True,
            "compute": "local Docker smoke-test",
            "resource_fit_score": 10,
            "mod_ideas": ["add page"],
            "risk_notes": [],
        },
    ]

    ranked = rank_candidates(jd, candidates, today=date(2026, 5, 17))

    assert ranked[0]["name"] == "agent-selected-domain-project"
    assert {"推荐算法", "搜索分发", "大语言模型", "用户行为数据"} & set(ranked[0]["matched_keywords"])


def _max_score_candidate(**overrides):
    candidate = {
        "name": "max-project",
        "repo_url": "https://github.com/example/max",
        "license": "MIT",
        "license_score": 4,
        "stars": 1000,
        "last_commit": "2026-05-17",
        "tags": ["fastapi", "postgresql", "docker", "testing", "deployment", "api"],
        "matched_jd_terms": ["fastapi", "postgresql", "docker", "testing", "deployment", "api"],
        "runnable": True,
        "runnable_score": 20,
        "compute": "local Docker smoke-test",
        "resource_fit_score": 10,
        "mod_ideas": ["add auth", "add cache", "add tests", "add deploy"],
        "risk_notes": [],
    }
    candidate.update(overrides)
    return candidate


def _taste(prefer_tags=None, avoid_tags=None) -> str:
    return json.dumps(
        {
            "prefer_tags": prefer_tags or [],
            "avoid_tags": avoid_tags or [],
        }
    )


def test_no_effective_taste_uses_104_denominator_and_no_taste_column() -> None:
    jd = "FastAPI PostgreSQL Docker testing deployment API"
    ranked = rank_candidates(
        jd,
        [
            _max_score_candidate(name="base-better-project"),
            _max_score_candidate(
                name="taste-tagged-lower-project",
                stars=50,
                taste_tags=["backend", "ai-app", "local-docker", "interview-friendly"],
            ),
        ],
        today=date(2026, 5, 17),
        taste_text="无，按 JD 推荐",
    )

    assert ranked[0]["name"] == "base-better-project"
    assert ranked[0]["raw_score"] == 104
    assert ranked[1]["score_breakdown"]["user_preference"] == 0
    assert ranked[0]["max_raw_score"] == 104
    assert ranked[0]["score"] == 100.0
    assert ranked[0]["score_breakdown"]["user_preference"] == 0
    assert "taste_matches" not in ranked[0]

    markdown = render_markdown(ranked, jd_path="jd.txt")
    assert "Taste Fit" not in markdown


def test_empty_and_unstructured_taste_texts_are_not_effective() -> None:
    assert not has_effective_taste(None)
    assert not has_effective_taste("   \n\t")
    assert not has_effective_taste("无")
    assert not has_effective_taste("都可以")
    assert not has_effective_taste("跳过")
    assert not has_effective_taste("none")
    assert not has_effective_taste("no preference")
    assert not has_effective_taste("无 / 都可以")
    assert not has_effective_taste("项目偏好 / taste：无，按 JD 推荐")
    assert not has_effective_taste("无，但其实更偏后端")
    assert not has_effective_taste("更想做后端，本地 Docker 跑通，适合面试讲")

    assert has_effective_taste(_taste(prefer_tags=["backend"]))
    assert has_effective_taste("prefer_tags: backend, local_docker\navoid_tags: pure_frontend")


def test_effective_taste_uses_114_denominator_and_can_reach_100() -> None:
    jd = "FastAPI PostgreSQL Docker testing deployment API"
    taste_text = _taste(
        prefer_tags=["backend", "ai-app", "local-docker", "interview-friendly", "api", "database"]
    )
    candidate = _max_score_candidate(
        tags=["fastapi", "postgresql", "docker", "rag", "testing", "deployment"],
        taste_tags=["backend", "ai-app", "local-docker", "interview-friendly", "api", "database"],
    )

    ranked = rank_candidates(jd, [candidate], today=date(2026, 5, 17), taste_text=taste_text)

    assert ranked[0]["raw_score"] == 114
    assert ranked[0]["max_raw_score"] == 114
    assert ranked[0]["score"] == 100.0
    assert ranked[0]["score_breakdown"]["user_preference"] == 10
    assert {"backend", "ai-app", "local-docker", "interview-friendly"} <= set(ranked[0]["taste_matches"])

    markdown = render_markdown(ranked, jd_path="jd.txt")
    assert "Taste Fit" in markdown
    assert "user_preference" not in markdown  # keep table human-readable rather than dumping JSON keys


def test_negative_raw_score_clamps_to_zero_after_normalization() -> None:
    assert normalize_score(-8, 104) == 0.0

    jd = "Backend API"
    candidate = {
        "name": "bad-project",
        "repo_url": "https://github.com/example/bad",
        "license": "unknown",
        "stars": 0,
        "last_commit": "2019-01-01",
        "tags": [],
        "matched_jd_terms": [],
        "license_score": 0,
        "runnable": False,
        "compute": "expensive distributed cluster",
        "resource_fit_score": 0,
        "mod_ideas": [],
        "risk_notes": ["risk"] * 20,
    }

    ranked = rank_candidates(jd, [candidate], today=date(2026, 5, 17))

    assert ranked[0]["raw_score"] < 0
    assert ranked[0]["score"] == 0.0


def test_decimal_scores_are_sorted_without_truncating_fractional_part() -> None:
    jd = "Backend API Docker database testing deployment"
    taste_text = _taste(prefer_tags=["backend", "ai-app", "local-docker", "interview-friendly"])
    high = {
        "name": "z-higher-fractional-score",
        "repo_url": "https://github.com/example/high",
        "license": "MIT",
        "license_score": 4,
        "stars": 200,
        "last_commit": "2026-05-17",
        "tags": ["fastapi", "docker"],
        "matched_jd_terms": ["backend", "api", "docker", "database", "testing", "deployment"],
        "runnable": True,
        "runnable_score": 20,
        "compute": "local Docker smoke-test",
        "resource_fit_score": 10,
        "mod_ideas": [],
        "risk_notes": [],
        "taste_tags": ["backend", "ai-app", "local-docker", "interview-friendly"],
    }
    low = {
        **high,
        "name": "a-lower-fractional-score",
        "repo_url": "https://github.com/example/low",
        "stars": 50,
        "mod_ideas": ["add tests"],
        "taste_tags": ["backend"],
    }

    ranked = rank_candidates(jd, [low, high], today=date(2026, 5, 17), taste_text=taste_text)

    assert ranked[0]["name"] == "z-higher-fractional-score"
    assert ranked[0]["raw_score"] == 90
    assert ranked[1]["raw_score"] == 87
    assert ranked[0]["score"] == 78.95
    assert ranked[1]["score"] == 76.32


def test_taste_matching_can_break_close_ties_but_not_override_major_quality_gap() -> None:
    jd = "Backend API Docker database testing deployment"
    taste_text = _taste(prefer_tags=["backend", "ai-app", "local-docker", "interview-friendly", "api"])
    taste_match = _max_score_candidate(
        name="taste-match-close-project",
        stars=200,
        mod_ideas=["add tests"],
        taste_tags=["backend", "ai-app", "local-docker", "interview-friendly", "api"],
    )
    close_default = _max_score_candidate(
        name="close-default-project",
        stars=200,
        mod_ideas=[],
        taste_tags=[],
    )

    ranked = rank_candidates(jd, [close_default, taste_match], today=date(2026, 5, 17), taste_text=taste_text)

    assert ranked[0]["name"] == "taste-match-close-project"
    assert ranked[0]["score_breakdown"]["user_preference"] == 10

    high_quality = _max_score_candidate(name="high-quality-project", taste_tags=[])
    risky_but_tasty = _max_score_candidate(
        name="risky-but-tasty-project",
        license="unknown",
        license_score=0,
        stars=3,
        runnable=False,
        runnable_score=-5,
        compute="expensive distributed cluster",
        resource_fit_score=0,
        mod_ideas=[],
        risk_notes=["no license", "private data", "heavy cluster", "old deps", "unclear run", "closed service", "large dataset"],
        taste_tags=["backend", "ai-app", "local-docker", "interview-friendly", "api"],
    )

    ranked_quality_gap = rank_candidates(
        jd,
        [risky_but_tasty, high_quality],
        today=date(2026, 5, 17),
        taste_text=taste_text,
    )

    assert ranked_quality_gap[0]["name"] == "high-quality-project"
    assert ranked_quality_gap[1]["score_breakdown"]["user_preference"] == 10


def test_structured_taste_lines_and_avoid_tags_are_handled() -> None:
    taste_text = "prefer_tags: backend, local_docker, interview-friendly\navoid_tags: pure_frontend, multi-gpu"
    prefer_tags, avoid_tags = parse_user_taste(taste_text)

    assert {"backend", "local-docker", "interview-friendly"} <= prefer_tags
    assert "pure-frontend" in avoid_tags
    assert "multi-gpu" in avoid_tags
    assert "pure-frontend" not in prefer_tags

    backend_candidate = {"taste_tags": ["backend", "local-docker", "interview-friendly"], "tags": ["fastapi", "docker"], "avoid_tags": []}
    frontend_candidate = {"taste_tags": ["pure-frontend"], "tags": ["react"], "avoid_tags": ["pure-frontend"]}

    backend_score, backend_matches, backend_mismatches, _ = taste_score(backend_candidate, taste_text)
    frontend_score, frontend_matches, frontend_mismatches, _ = taste_score(frontend_candidate, taste_text)

    assert backend_score > frontend_score
    assert {"backend", "local-docker", "interview-friendly"} <= set(backend_matches)
    assert "pure-frontend" not in frontend_matches
    assert "pure-frontend" in frontend_mismatches
    assert frontend_score < 0
