from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.bootstrap import init_wiki, inspect_wiki
from llm_wiki_mcp.config import load_config


def test_init_wiki_creates_minimal_structure_without_overwriting(tmp_path: Path) -> None:
    root = tmp_path / "new-wiki"
    root.mkdir()
    (root / "index.md").write_text("# Existing Index\n")

    result = init_wiki(root, profile="personal", language="zh")

    assert result["initialized"] is True
    assert "SCHEMA.md" in result["created"]
    assert "AGENTS.md" in result["created"]
    assert "index.md" in result["skipped"]
    assert (root / "SCHEMA.md").is_file()
    assert (root / "AGENTS.md").is_file()
    assert (root / "log.md").is_file()
    assert (root / "_meta/topic-map.md").is_file()
    assert (root / "scripts/wiki_lint.py").is_file()
    assert (root / "domains").is_dir()
    assert (root / "entities").is_dir()
    assert (root / "raw").is_dir()
    assert (root / "drafts").is_dir()
    assert (root / "reading").is_dir()
    assert (root / "index.md").read_text() == "# Existing Index\n"


def test_inspect_wiki_reports_missing_and_detected_counts(tmp_path: Path, sample_wiki: Path) -> None:
    missing_result = inspect_wiki(tmp_path / "not-yet")
    assert missing_result["is_wiki"] is False
    assert "SCHEMA.md" in missing_result["missing"]
    assert missing_result["next_action"] == "run init_wiki"

    complete_result = inspect_wiki(sample_wiki)
    assert complete_result["is_wiki"] is False  # fixture intentionally lacks SCHEMA/AGENTS
    assert complete_result["detected"]["formal_pages"] == 1
    assert complete_result["detected"]["raw_sources"] == 1
    assert complete_result["detected"]["markdown_files"] >= 4


def test_default_config_uses_home_relative_wiki_root() -> None:
    config = load_config()
    assert config.wiki_root == Path.home() / "llm-wiki"


def test_open_source_files_do_not_contain_local_private_markers() -> None:
    project_root = Path(__file__).resolve().parents[1]
    scanned_suffixes = {".py", ".md", ".toml", ".yaml", ".yml"}
    forbidden = [
        "/Users/" + "ryan",
        "jr.lu" + ".jobs",
        "Jaron" + "'s",
        "ryan" + "@",
    ]
    offenders: list[str] = []

    for path in project_root.rglob("*"):
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix not in scanned_suffixes or not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(project_root)}: {marker}")

    assert offenders == []
