from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / "skills" / "shushu-internship-tool" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "shushu-internship-tool" / "agents" / "openai.yaml"
CANDIDATE_SCORE = (
    ROOT
    / "skills"
    / "shushu-internship-tool"
    / "scripts"
    / "shushu_internship_tool"
    / "candidate_score.py"
)


def test_taste_gate_requires_structured_choice_controls() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")
    combined = skill + "\n" + openai_yaml

    assert "request_user_input" in combined
    assert "必须先弹出 yes/no gate" in skill
    assert "必须进入第二阶段偏好选择" in skill
    assert "提供 3 个" in skill
    assert "客户端会自动附加 Other" in skill
    assert "不允许把 yes/no 或 A/B/C/D" in skill
    assert "不要用普通回复模拟控件" in skill
    assert "退化为一句简短追问" not in combined


def test_taste_options_are_open_source_repo_preferences() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")
    combined = skill + "\n" + openai_yaml

    assert "无论用户怎么选，后续 workflow 都必须继续找 2-3 个候选 GitHub 开源项目" in skill
    assert "这 3 个建议选项必须全部是“开源项目筛选 / 改造偏好”" in skill
    assert "开源项目改造是整个 skill 的固定前提" in skill
    assert "不能把“开源项目改造”做成单独选项" in openai_yaml
    assert "从零自建项目" in combined


def test_effective_taste_flows_into_candidate_scoring() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")

    assert "必须先把最终 taste 写入 `taste.json`" in skill
    assert "忘记传 `--taste` 属于 workflow 错误" in skill
    assert "score_breakdown.user_preference" in skill
    assert "`max_raw_score` 应为 114" in skill
    assert "Taste Fit" in skill
    assert "最终推荐理由必须引用脚本输出的 Taste Fit / `user_preference`" in skill


def test_no_preference_path_preserves_legacy_workflow() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")

    assert "无偏好线路验收" in skill
    assert "不要弹出第二阶段偏好选择" in skill
    assert "不要创建 `taste.json`" in skill
    assert "排序命令不得包含 `--taste`" in skill
    assert "输出报告不得显示 Taste Fit 列" in skill
    assert "不得输出 `taste_matches`" in skill


def test_candidate_score_uses_explicit_fields_instead_of_hardcoded_vocab() -> None:
    source = CANDIDATE_SCORE.read_text(encoding="utf-8")

    assert "matched_jd_terms" in source
    assert "license_score" in source
    assert "runnable_score" in source
    assert "resource_fit_score" in source
    assert "PERMISSIVE_LICENSE_HINTS" not in source
    assert "jd_keywords" not in source
    assert "tokenize(" not in source
    assert "any(key in text" not in source
    assert "local_docker" not in source
    assert "multi_gpu" not in source
