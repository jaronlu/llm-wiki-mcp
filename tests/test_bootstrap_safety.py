from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.bootstrap import init_wiki, inspect_wiki
from llm_wiki_mcp.config import load_config


def test_init_wiki_creates_minimal_structure_without_overwriting(
    tmp_path: Path,
) -> None:
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


def test_inspect_wiki_reports_missing_and_detected_counts(
    tmp_path: Path, sample_wiki: Path
) -> None:
    missing_result = inspect_wiki(tmp_path / "not-yet")
    assert missing_result["is_wiki"] is False
    assert "SCHEMA.md" in missing_result["missing"]
    assert missing_result["next_action"] == "run init_wiki"

    complete_result = inspect_wiki(sample_wiki)
    assert (
        complete_result["is_wiki"] is False
    )  # fixture intentionally lacks SCHEMA/AGENTS
    assert complete_result["detected"]["formal_pages"] == 1
    assert complete_result["detected"]["raw_sources"] == 1
    assert complete_result["detected"]["markdown_files"] >= 4


def test_default_config_uses_home_relative_wiki_root(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("LLM_WIKI_MCP_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.wiki_root == Path.home() / "llm-wiki"
    assert config.init_wiki_root is None
    assert config.allow_write_raw is False


def test_default_config_reads_local_config_yaml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LLM_WIKI_MCP_CONFIG", raising=False)
    wiki_root = tmp_path / "wiki"
    init_root = tmp_path / "init-wiki"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "\n".join([
            f"wiki_root: {wiki_root}",
            f"init_wiki_root: {init_root}",
            "allow_write_raw: true",
            "",
        ])
    )

    monkeypatch.chdir(tmp_path)
    config = load_config()

    assert config.wiki_root == wiki_root
    assert config.init_wiki_root == init_root
    assert config.allow_write_raw is True


def test_config_file_and_env_root_override(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "llm-wiki-mcp.yaml"
    configured_root = tmp_path / "configured-wiki"
    override_root = tmp_path / "override-wiki"
    config_path.write_text(
        "\n".join([
            f"wiki_root: {configured_root}",
            f"init_wiki_root: {tmp_path / 'init-target'}",
            "allow_write_raw: false",
            "formal_dirs: [domains, entities, projects]",
            "",
        ])
    )

    config = load_config(config_path)
    assert config.wiki_root == configured_root
    assert config.init_wiki_root == tmp_path / "init-target"
    assert config.allow_write_raw is False
    assert config.formal_dirs == ("domains", "entities", "projects")

    monkeypatch.setenv("LLM_WIKI_ROOT", str(override_root))
    monkeypatch.setenv("LLM_WIKI_INIT_ROOT", str(tmp_path / "init-override"))
    override = load_config(config_path)
    assert override.wiki_root == override_root
    assert override.init_wiki_root == tmp_path / "init-override"
    assert override.allow_write_raw is False


def test_config_rejects_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("wiki_root: ~/wiki\nunknown_field: true\n")

    with pytest.raises(ValueError, match="Unknown config field"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("formal_dirs", "[domains/nested]"),
        ("raw_dirs", "[]"),
        ("non_formal_dirs", "[drafts, 123]"),
    ],
)
def test_config_rejects_invalid_directory_fields(
    tmp_path: Path, field: str, value: str
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"{field}: {value}\n")

    with pytest.raises(ValueError, match=field):
        load_config(config_path)


@pytest.mark.parametrize("value", ["0", "-1", "false", "not-a-number", "1.5"])
def test_config_rejects_invalid_log_retention(tmp_path: Path, value: str) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"log_retention_entries: {value}\n")

    with pytest.raises(ValueError, match="log_retention_entries"):
        load_config(config_path)


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
        if any(
            part in {".git", ".venv", "__pycache__", ".pytest_cache"}
            for part in path.parts
        ):
            continue
        if path.suffix not in scanned_suffixes or not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(project_root)}: {marker}")

    assert offenders == []
