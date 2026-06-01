from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .common import (
    ensure_dir,
    load_json,
    markdown_table,
    normalize_list,
    safe_float,
    safe_int,
    write_json,
    write_text,
)


NO_TASTE_MAX_RAW_SCORE = 104
TASTE_MAX_RAW_SCORE = 114
USER_PREFERENCE_MAX_SCORE = 10

EXPLICIT_PREFER_KEYS = ("prefer_tags", "preferred_tags", "preference_tags", "taste_tags")
EXPLICIT_AVOID_KEYS = ("avoid_tags", "negative_tags", "mismatch_tags")


def parse_candidates(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value]
    if isinstance(value, dict) and isinstance(value.get("candidates"), list):
        return [dict(item) for item in value["candidates"]]
    raise ValueError("candidates JSON must be a list or an object with a 'candidates' list")


def parse_commit_date(raw: Any) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def _clamped_explicit_score(
    candidate: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> tuple[int, str | None]:
    for key in keys:
        if key in candidate and candidate[key] not in (None, ""):
            value = int(round(safe_float(candidate[key], default)))
            value = max(minimum, min(maximum, value))
            return value, key
    return default, None


def license_score(candidate: dict[str, Any]) -> tuple[int, str]:
    points, source = _clamped_explicit_score(
        candidate,
        ("license_score", "license_points"),
        default=2 if candidate.get("license") else 0,
        minimum=0,
        maximum=4,
    )
    if source:
        return points, f"license score from {source}"
    if candidate.get("license"):
        return points, "license present; set license_score for precise scoring"
    return points, "license missing; set license_score after review"


def runnable_score(candidate: dict[str, Any]) -> tuple[int, str]:
    points, source = _clamped_explicit_score(
        candidate,
        ("runnable_score", "runnable_points"),
        default=5,
        minimum=-5,
        maximum=20,
    )
    if source:
        return points, f"runnable score from {source}"
    raw = candidate.get("runnable")
    if isinstance(raw, bool):
        return (20, "runnable") if raw else (-5, "not verified runnable")
    return points, "runnable not scored explicitly"


def compute_score(candidate: dict[str, Any]) -> tuple[int, str]:
    points, source = _clamped_explicit_score(
        candidate,
        ("resource_fit_score", "resource_score", "compute_score", "compute_points"),
        default=5,
        minimum=0,
        maximum=10,
    )
    if source:
        return points, f"resource fit score from {source}"
    return points, "run resources not scored explicitly"


def activity_score(raw: Any, today: date) -> tuple[int, str]:
    commit_date = parse_commit_date(raw)
    if commit_date is None:
        return 0, "last_commit missing or unparsable"
    days = max((today - commit_date).days, 0)
    if days <= 180:
        return 10, "active within 180 days"
    if days <= 365:
        return 7, "active within 1 year"
    if days <= 730:
        return 4, "active within 2 years"
    return 1, "inactive for more than 2 years"


def stars_score(raw: Any) -> tuple[int, str]:
    stars = safe_int(raw)
    if stars >= 1000:
        return 10, "strong community signal"
    if stars >= 200:
        return 8, "good community signal"
    if stars >= 50:
        return 6, "some community signal"
    if stars > 0:
        return 3, "small community signal"
    return 0, "no star signal"


def keyword_score(candidate: dict[str, Any]) -> tuple[int, list[str], str]:
    agent_matches = normalize_list(candidate.get("matched_jd_terms"))
    matched = list(dict.fromkeys(agent_matches))
    explicit_score, source = _clamped_explicit_score(
        candidate,
        ("jd_match_score", "jd_score", "jd_match_points"),
        default=min(30, len(matched) * 5),
        minimum=0,
        maximum=30,
    )
    score = explicit_score
    reason = f"JD match score from {source}" if source else f"{len(matched)} agent-supplied JD matches"
    return score, matched, reason


def _tag_slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", "-").replace("+", "-")
    text = re.sub(r"[\s/]+", "-", text)
    text = re.sub(r"[^a-z0-9.#\-一-鿿]+", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def canonicalize_tags(values: Any) -> set[str]:
    return {tag for value in normalize_list(values) if (tag := _tag_slug(value))}


def _collect_taste_tags(data: dict[str, Any], keys: tuple[str, ...]) -> set[str]:
    tags: set[str] = set()
    for key in keys:
        tags.update(canonicalize_tags(data.get(key)))
    return tags


def _parse_json_taste(text: str) -> tuple[set[str], set[str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set(), set()
    if not isinstance(data, dict):
        return set(), set()
    prefer = _collect_taste_tags(data, EXPLICIT_PREFER_KEYS)
    avoid = _collect_taste_tags(data, EXPLICIT_AVOID_KEYS)
    return prefer, avoid


def _parse_explicit_tag_lines(text: str) -> tuple[set[str], set[str]]:
    prefer: set[str] = set()
    avoid: set[str] = set()
    consumed_patterns = [*EXPLICIT_PREFER_KEYS, *EXPLICIT_AVOID_KEYS]
    line_pattern = re.compile(
        rf"(?im)^\s*({'|'.join(re.escape(key) for key in consumed_patterns)})\s*[:=]\s*(.+)$"
    )
    for match in line_pattern.finditer(text):
        key = match.group(1).lower()
        raw_values = match.group(2).strip().strip("[]{}()")
        values = normalize_list(raw_values.replace('"', "").replace("'", ""))
        if key in EXPLICIT_AVOID_KEYS:
            avoid.update(canonicalize_tags(values))
        else:
            prefer.update(canonicalize_tags(values))
    return prefer, avoid


def parse_user_taste(taste_text: str | None) -> tuple[set[str], set[str]]:
    """Read structured user preference tags from JSON or key-value text.

    The agent must do natural-language interpretation before calling this script.
    This helper only slugs explicit prefer_tags / avoid_tags and never applies a
    built-in domain vocabulary.
    """
    if taste_text is None or not taste_text.strip():
        return set(), set()

    prefer, avoid = _parse_json_taste(taste_text)
    explicit_prefer, explicit_avoid = _parse_explicit_tag_lines(taste_text)
    prefer.update(explicit_prefer)
    avoid.update(explicit_avoid)

    prefer.difference_update(avoid)
    return prefer, avoid


def has_effective_taste(taste_text: str | None) -> bool:
    prefer, avoid = parse_user_taste(taste_text)
    return bool(prefer or avoid)


def _ordered_intersection(items: Iterable[str], wanted: set[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item in wanted and item not in result:
            result.append(item)
    return result


def taste_score(candidate: dict[str, Any], taste_text: str | None) -> tuple[int, list[str], list[str], list[str]]:
    prefer_tags, user_avoid_tags = parse_user_taste(taste_text)
    if not (prefer_tags or user_avoid_tags):
        return 0, [], [], []

    positive_tags = canonicalize_tags([
        *normalize_list(candidate.get("taste_tags")),
        *normalize_list(candidate.get("tags")),
    ])
    project_avoid_tags = canonicalize_tags([
        *normalize_list(candidate.get("avoid_tags")),
        *positive_tags,
    ])

    matches = _ordered_intersection(sorted(positive_tags - user_avoid_tags), prefer_tags)
    mismatches = _ordered_intersection(sorted(project_avoid_tags), user_avoid_tags)

    points = min(USER_PREFERENCE_MAX_SCORE, len(matches) * 2) - min(4, len(mismatches) * 2)

    notes: list[str] = []
    if matches:
        notes.append("匹配用户偏好：" + ", ".join(matches[:8]))
    else:
        notes.append("未命中显式用户偏好标签")
    if mismatches:
        notes.append("命中用户避雷项：" + ", ".join(mismatches[:8]))
    notes.append(f"user_preference={points}/{USER_PREFERENCE_MAX_SCORE}")
    return points, matches, mismatches, notes


def normalize_score(raw_score: float, max_raw_score: float) -> float:
    if max_raw_score <= 0:
        return 0.0
    x = max(0.0, min(float(raw_score), float(max_raw_score)))
    return round(x * 100 / float(max_raw_score), 2)


def score_candidate(
    candidate: dict[str, Any],
    jd_text: str,
    today: date | None = None,
    taste_text: str | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    prefer_tags, avoid_tags = parse_user_taste(taste_text)
    effective_taste = bool(prefer_tags or avoid_tags)
    max_raw_score = TASTE_MAX_RAW_SCORE if prefer_tags else NO_TASTE_MAX_RAW_SCORE

    keyword_points, matched_keywords, keyword_reason = keyword_score(candidate)
    license_points, license_reason = license_score(candidate)
    runnable_points, runnable_reason = runnable_score(candidate)
    compute_points, compute_reason = compute_score(candidate)
    activity_points, activity_reason = activity_score(candidate.get("last_commit"), today)
    stars_points, stars_reason = stars_score(candidate.get("stars"))
    user_preference_points, taste_matches, taste_mismatches, preference_notes = taste_score(candidate, taste_text)

    mod_ideas = normalize_list(candidate.get("mod_ideas"))
    mod_points = min(20, len(mod_ideas) * 5)
    risk_notes = normalize_list(candidate.get("risk_notes"))
    risk_penalty_points = min(20, len(risk_notes) * 3)

    raw_score = (
        keyword_points
        + license_points
        + runnable_points
        + compute_points
        + activity_points
        + stars_points
        + mod_points
        + user_preference_points
        - risk_penalty_points
    )
    score = normalize_score(raw_score, max_raw_score)

    score_reasons = [
        keyword_reason,
        license_reason,
        runnable_reason,
        compute_reason,
        activity_reason,
        stars_reason,
        f"{len(mod_ideas)} modification ideas",
        f"{len(risk_notes)} risk notes",
    ]
    if effective_taste:
        score_reasons.append(
            f"user preference {user_preference_points}/{USER_PREFERENCE_MAX_SCORE}: "
            f"{len(taste_matches)} matches, {len(taste_mismatches)} avoid matches"
        )

    result: dict[str, Any] = {
        **candidate,
        "score": score,
        "raw_score": raw_score,
        "max_raw_score": max_raw_score,
        "score_breakdown": {
            "jd_match": keyword_points,
            "license": license_points,
            "runnable": runnable_points,
            "resource_fit": compute_points,
            "activity": activity_points,
            "stars": stars_points,
            "modification_space": mod_points,
            "user_preference": user_preference_points,
            "risk_penalty": -risk_penalty_points,
        },
        "matched_keywords": matched_keywords,
        "score_reasons": score_reasons,
    }
    if effective_taste:
        result.update(
            {
                "taste_matches": taste_matches,
                "taste_mismatches": taste_mismatches,
                "user_preference_notes": preference_notes,
            }
        )
    return result


def rank_candidates(
    jd_text: str,
    candidates: list[dict[str, Any]],
    today: date | None = None,
    taste_text: str | None = None,
) -> list[dict[str, Any]]:
    scored = [
        score_candidate(candidate, jd_text, today=today, taste_text=taste_text)
        for candidate in candidates
    ]
    return sorted(
        scored,
        key=lambda item: (-safe_float(item.get("score")), str(item.get("name", "")).lower()),
    )


def _format_score(value: Any) -> str:
    return f"{safe_float(value):.2f}"


def _should_include_taste_column(ranked: list[dict[str, Any]], include_taste: bool | None) -> bool:
    if include_taste is not None:
        return include_taste
    return any(
        safe_int(item.get("max_raw_score")) == TASTE_MAX_RAW_SCORE
        or "taste_matches" in item
        or "taste_mismatches" in item
        for item in ranked
    )


def _format_taste_fit(item: dict[str, Any]) -> str:
    preference = item.get("score_breakdown", {}).get("user_preference", 0)
    matches = normalize_list(item.get("taste_matches"))
    mismatches = normalize_list(item.get("taste_mismatches"))
    parts = [f"{preference}/{USER_PREFERENCE_MAX_SCORE}"]
    if matches:
        parts.append("match: " + ", ".join(matches[:4]))
    if mismatches:
        parts.append("avoid: " + ", ".join(mismatches[:3]))
    return "; ".join(parts)


def render_markdown(ranked: list[dict[str, Any]], jd_path: str | None = None, include_taste: bool | None = None) -> str:
    show_taste = _should_include_taste_column(ranked, include_taste)
    rows = []
    for index, item in enumerate(ranked, start=1):
        row = [
            index,
            item.get("name", "unnamed"),
            _format_score(item.get("score", 0)),
            item.get("raw_score", ""),
            item.get("max_raw_score", ""),
            item.get("license", ""),
            item.get("stars", ""),
            item.get("last_commit", ""),
            item.get("runnable", ""),
            item.get("compute", item.get("resources", "")),
            ", ".join(normalize_list(item.get("matched_keywords"))[:6]),
        ]
        if show_taste:
            row.append(_format_taste_fit(item))
        row.append("; ".join(normalize_list(item.get("risk_notes"))[:3]) or "无")
        rows.append(row)

    best = ranked[0] if ranked else None
    backup = ranked[1] if len(ranked) > 1 else None
    headers = [
        "Rank",
        "Name",
        "Score",
        "Raw",
        "Max Raw",
        "License",
        "Stars",
        "Last Commit",
        "Runnable",
        "Resources",
        "Matched",
    ]
    if show_taste:
        headers.append("Taste Fit")
    headers.append("Risks")

    parts = [
        "# 候选项目排序",
        "",
        f"- JD 来源：`{jd_path}`" if jd_path else "- JD 来源：未记录",
        f"- 主项目推荐：`{best.get('name')}`，score={_format_score(best.get('score'))}" if best else "- 主项目推荐：TODO",
        f"- 备选项目：`{backup.get('name')}`，score={_format_score(backup.get('score'))}" if backup else "- 备选项目：TODO",
        "- 分数说明：先计算 raw_score，再按 max_raw_score 归一化到 0-100。",
    ]
    if show_taste:
        parts.append("- 用户偏好：已启用 Taste Fit 小权重；它只用于近分排序辅助，不覆盖 JD 匹配、可运行性和风险。")
    parts.extend(
        [
            "",
            markdown_table(headers, rows),
            "",
            "## 使用说明",
            "",
            "- 这个脚本只根据显式字段打分；语义判断、JD 命中度和最终选择仍需 AI 助手/人工审阅。",
            "- 不可运行、资源要求过高、风险说明过多的项目，除非非常贴 JD，否则不建议作为主项目。",
            "- 推荐项目应尽快进入最小路径摸底、简历 4-5 行版本和面试 Q&A，而不是卡在完美复现。",
        ]
    )
    return "\n".join(parts)


def write_ranking_outputs(
    ranked: list[dict[str, Any]],
    out_dir: str | Path,
    jd_path: str | None = None,
    include_taste: bool | None = None,
) -> dict[str, str]:
    out = ensure_dir(out_dir)
    paths = {
        "candidate_score_json": str(write_json(out / "candidate_score.json", {"candidates": ranked})),
        "candidate_score_md": str(
            write_text(
                out / "candidate_score.md",
                render_markdown(ranked, jd_path=jd_path, include_taste=include_taste),
            )
        ),
    }
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank GitHub project candidates for a computer-industry internship JD.")
    parser.add_argument("--jd", required=True, help="Path to a text file containing the target job description.")
    parser.add_argument("--candidates", required=True, help="Path to candidate JSON.")
    parser.add_argument("--taste", help="Optional path to structured user taste JSON or tag lines.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)

    jd_path = Path(args.jd)
    jd_text = jd_path.read_text(encoding="utf-8", errors="replace")
    candidates = parse_candidates(load_json(args.candidates))
    taste_text = None
    if args.taste:
        taste_text = Path(args.taste).read_text(encoding="utf-8", errors="replace")
    effective_taste = has_effective_taste(taste_text)
    ranked = rank_candidates(jd_text, candidates, taste_text=taste_text)
    paths = write_ranking_outputs(
        ranked,
        args.out,
        jd_path=str(jd_path),
        include_taste=effective_taste,
    )
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
