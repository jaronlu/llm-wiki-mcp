from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp import config as config_module
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


def test_bootstrap_uses_configured_wiki_directories(tmp_path: Path) -> None:
    root = tmp_path / "custom-wiki"

    init_result = init_wiki(
        root,
        formal_dirs=("knowledge",),
        raw_dirs=("sources",),
        non_formal_dirs=("drafts", "inbox"),
    )
    (root / "knowledge/custom.md").write_text("# Custom\n")
    (root / "sources/source.md").write_text("# Source\n")

    inspect_result = inspect_wiki(
        root,
        formal_dirs=("knowledge",),
        raw_dirs=("sources",),
        non_formal_dirs=("drafts", "inbox"),
    )

    assert "knowledge" in init_result["created"]
    assert "sources" in init_result["created"]
    assert "inbox" in init_result["created"]
    schema = (root / "SCHEMA.md").read_text()
    assert "`knowledge/`" in schema
    assert "`sources/`" in schema
    assert "`inbox/`" in schema
    assert inspect_result["detected"]["formal_pages"] == 1
    assert inspect_result["detected"]["raw_sources"] == 1


def test_default_config_uses_home_relative_wiki_root(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.chdir(Path("/"))
    config = load_config()
    assert config.wiki_root == Path.home() / "llm-wiki"
    assert config.allow_write_raw is False


def test_default_config_reads_project_config_yaml(tmp_path: Path, monkeypatch) -> None:
    wiki_root = tmp_path / "wiki"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "\n".join([
            f"wiki_root: {wiki_root}",
            "allow_write_raw: true",
            "",
        ])
    )

    monkeypatch.chdir(Path("/"))
    monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", config_dir / "config.yaml")
    config = load_config()

    assert config.wiki_root == wiki_root
    assert config.allow_write_raw is True


def test_config_reads_project_config_not_cwd_config(
    tmp_path: Path, monkeypatch
) -> None:
    project_config = tmp_path / "project" / "config" / "config.yaml"
    cwd_config = tmp_path / "cwd" / "config" / "config.yaml"
    project_config.parent.mkdir(parents=True)
    cwd_config.parent.mkdir(parents=True)
    configured_root = tmp_path / "configured-wiki"
    cwd_root = tmp_path / "cwd-wiki"
    project_config.write_text(
        "\n".join(
            [
                f"wiki_root: {configured_root}",
                "allow_write_raw: false",
                "formal_dirs: [domains, entities, projects]",
                "",
            ]
        )
    )
    cwd_config.write_text(
        "\n".join(
            [
                f"wiki_root: {cwd_root}",
                "allow_write_raw: true",
                "",
            ]
        )
    )

    monkeypatch.chdir(cwd_config.parents[1])
    monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", project_config)

    config = load_config()

    assert config.wiki_root == configured_root
    assert config.allow_write_raw is False
    assert config.formal_dirs == ("domains", "entities", "projects")


def test_config_rejects_unknown_fields(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("wiki_root: ~/wiki\nunknown_field: true\n")

    with pytest.raises(ValueError, match="Unknown config field"):
        monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", config_path)
        load_config()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("formal_dirs", "[domains/nested]"),
        ("raw_dirs", "[]"),
        ("non_formal_dirs", "[drafts, 123]"),
    ],
)
def test_config_rejects_invalid_directory_fields(
    tmp_path: Path, monkeypatch, field: str, value: str
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"{field}: {value}\n")

    with pytest.raises(ValueError, match=field):
        monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", config_path)
        load_config()


@pytest.mark.parametrize("value", ["0", "-1", "false", "not-a-number", "1.5"])
def test_config_rejects_invalid_log_retention(tmp_path: Path, monkeypatch, value: str) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"log_retention_entries: {value}\n")

    with pytest.raises(ValueError, match="log_retention_entries"):
        monkeypatch.setattr(config_module, "PROJECT_CONFIG_PATH", config_path)
        load_config()


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
