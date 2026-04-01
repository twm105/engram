"""Tests for engram.cli — click CLI commands."""

import json
import os

import pytest
from click.testing import CliRunner

from engram.cli import cli


@pytest.fixture
def runner(tmp_db_path, monkeypatch):
    """CLI runner with temp database."""
    monkeypatch.setenv("ENGRAM_DB", tmp_db_path)
    monkeypatch.setenv("ENGRAM_PROJECT", "test")
    return CliRunner()


class TestAdd:
    def test_add_semantic(self, runner):
        result = runner.invoke(cli, ["add", "semantic", "User prefers dark mode"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "id" in data
        assert data["type"] == "semantic"
        assert data["project"] == "test"

    def test_add_with_title(self, runner):
        result = runner.invoke(cli, [
            "add", "episodic", "Fixed the pagination bug",
            "--title", "Pagination fix",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "episodic"

    def test_add_with_importance(self, runner):
        result = runner.invoke(cli, [
            "add", "semantic", "Critical fact",
            "--importance", "0.9",
        ])
        assert result.exit_code == 0

    def test_add_with_project_override(self, runner):
        result = runner.invoke(cli, [
            "add", "semantic", "something",
            "--project", "other",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["project"] == "other"

    def test_add_invalid_type(self, runner):
        result = runner.invoke(cli, ["add", "invalid", "content"])
        assert result.exit_code != 0

    def test_add_procedural(self, runner):
        result = runner.invoke(cli, [
            "add", "procedural", "Run make deploy then check logs",
            "--title", "Deploy steps",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "procedural"


class TestQuery:
    def test_query_finds_match(self, runner):
        runner.invoke(cli, ["add", "semantic", "User prefers dark mode"])
        result = runner.invoke(cli, ["query", "dark mode"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data
        assert len(data["results"]) >= 1
        assert "dark mode" in data["results"][0]["content"]

    def test_query_no_results(self, runner):
        runner.invoke(cli, ["add", "semantic", "hello world"])
        result = runner.invoke(cli, ["query", "quantum physics"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["results"] == []

    def test_query_with_types_filter(self, runner):
        runner.invoke(cli, ["add", "semantic", "dark mode setting"])
        runner.invoke(cli, ["add", "episodic", "enabled dark mode yesterday"])
        result = runner.invoke(cli, ["query", "dark mode", "--types", "episodic"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all(r["type"] == "episodic" for r in data["results"])

    def test_query_with_top_k(self, runner):
        for i in range(5):
            runner.invoke(cli, ["add", "semantic", f"test fact {i}"])
        result = runner.invoke(cli, ["query", "test fact", "--top-k", "2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["results"]) <= 2


class TestList:
    def test_list_all(self, runner):
        runner.invoke(cli, ["add", "semantic", "one"])
        runner.invoke(cli, ["add", "episodic", "two"])
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["memories"]) == 2

    def test_list_by_type(self, runner):
        runner.invoke(cli, ["add", "semantic", "one"])
        runner.invoke(cli, ["add", "episodic", "two"])
        result = runner.invoke(cli, ["list", "--type", "semantic"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["memories"]) == 1
        assert data["memories"][0]["type"] == "semantic"

    def test_list_with_limit(self, runner):
        for i in range(5):
            runner.invoke(cli, ["add", "semantic", f"fact {i}"])
        result = runner.invoke(cli, ["list", "--limit", "2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["memories"]) == 2

    def test_list_empty(self, runner):
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["memories"] == []


class TestGet:
    def test_get_existing(self, runner):
        add_result = runner.invoke(cli, ["add", "semantic", "a fact"])
        id_ = json.loads(add_result.output)["id"]
        result = runner.invoke(cli, ["get", id_])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == id_
        assert data["content"] == "a fact"

    def test_get_nonexistent(self, runner):
        result = runner.invoke(cli, ["get", "nonexistent"])
        assert result.exit_code != 0


class TestDelete:
    def test_delete_existing(self, runner):
        add_result = runner.invoke(cli, ["add", "semantic", "to delete"])
        id_ = json.loads(add_result.output)["id"]
        result = runner.invoke(cli, ["delete", id_])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is True

    def test_delete_nonexistent(self, runner):
        result = runner.invoke(cli, ["delete", "nope"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] is False


class TestStats:
    def test_stats(self, runner):
        runner.invoke(cli, ["add", "semantic", "one"])
        runner.invoke(cli, ["add", "semantic", "two"])
        runner.invoke(cli, ["add", "episodic", "three"])
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 3
        assert data["by_type"]["semantic"] == 2

    def test_stats_empty(self, runner):
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 0
