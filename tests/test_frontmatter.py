"""Direct tests for the frontmatter module (not via manage.py re-exports)."""

from frontmatter import (
    _parse_yaml_value,
    _yaml_val,
    extract_title,
    get_body,
    parse_frontmatter,
    readable_id,
    serialise_frontmatter,
)


class TestReadableId:
    def test_hyphens_to_spaces(self):
        assert readable_id("c1-u1-thinker") == "C1 U1 Thinker"

    def test_underscores_to_spaces(self):
        assert readable_id("some_node_id") == "Some Node Id"

    def test_mixed(self):
        assert readable_id("c1-u1_test-node") == "C1 U1 Test Node"

    def test_empty(self):
        assert readable_id("") == ""

    def test_single_word(self):
        assert readable_id("enrichment") == "Enrichment"


class TestParseYamlValueDirect:
    def test_null(self):
        assert _parse_yaml_value("null") is None
        assert _parse_yaml_value("~") is None
        assert _parse_yaml_value("") is None

    def test_inline_list(self):
        assert _parse_yaml_value("[a, b, c]") == ["a", "b", "c"]

    def test_empty_list(self):
        assert _parse_yaml_value("[]") == []

    def test_quoted_double(self):
        assert _parse_yaml_value('"hello"') == "hello"

    def test_quoted_single(self):
        assert _parse_yaml_value("'hello'") == "hello"

    def test_plain(self):
        assert _parse_yaml_value("plain-value") == "plain-value"

    def test_whitespace_stripped(self):
        assert _parse_yaml_value("  spaced  ") == "spaced"

    def test_list_with_empty_items(self):
        assert _parse_yaml_value("[a, , b]") == ["a", "b"]


class TestParseFrontmatterDirect:
    def test_basic(self):
        text = "---\nid: test\ntype: claim\n---\nBody"
        meta = parse_frontmatter(text)
        assert meta["id"] == "test"
        assert meta["type"] == "claim"

    def test_no_frontmatter(self):
        assert parse_frontmatter("Just text") == {}

    def test_filepath_in_warning(self, capsys):
        text = "---\ndepends_on:\n  - item\nid: x\n---\n"
        parse_frontmatter(text, filepath="my/file.md")
        err = capsys.readouterr().err
        assert "my/file.md" in err

    def test_comment_lines_skipped(self):
        text = "---\n# this is a comment\nid: test\n---\n"
        meta = parse_frontmatter(text)
        assert meta["id"] == "test"
        assert len(meta) == 1

    def test_line_without_colon_skipped(self):
        text = "---\nid: test\norphan line\nstatus: ok\n---\n"
        meta = parse_frontmatter(text)
        assert meta["id"] == "test"
        assert meta["status"] == "ok"
        assert len(meta) == 2


class TestYamlValDirect:
    def test_none(self):
        assert _yaml_val(None) == "null"

    def test_empty_list(self):
        assert _yaml_val([]) == "[]"

    def test_list(self):
        assert _yaml_val(["a", "b"]) == "[a, b]"

    def test_special_quoted(self):
        assert _yaml_val("true") == '"true"'
        assert _yaml_val("null") == '"null"'

    def test_numeric_quoted(self):
        assert _yaml_val("42") == '"42"'

    def test_colon_quoted(self):
        assert _yaml_val("key: val") == '"key: val"'

    def test_normal_string(self):
        assert _yaml_val("hello") == "hello"


class TestSerialiseFrontmatterDirect:
    def test_roundtrip(self):
        meta = {"id": "test", "type": "claim", "status": "pending", "date": "2026-01-01"}
        text = serialise_frontmatter(meta) + "\n"
        parsed = parse_frontmatter(text)
        assert parsed == meta

    def test_canonical_order(self):
        meta = {"status": "active", "id": "x", "type": "claim"}
        result = serialise_frontmatter(meta)
        lines = result.split("\n")[1:-1]  # strip --- delimiters
        keys = [line.split(":")[0] for line in lines]
        assert keys == ["id", "type", "status"]


class TestGetBodyDirect:
    def test_with_frontmatter(self):
        assert get_body("---\nid: x\n---\nBody") == "Body"

    def test_without_frontmatter(self):
        assert get_body("No frontmatter") == "No frontmatter"

    def test_empty_body(self):
        assert get_body("---\nid: x\n---\n") == ""


class TestExtractTitleDirect:
    def test_h1(self):
        assert extract_title("# Title") == "Title"

    def test_no_heading(self):
        assert extract_title("No heading") is None

    def test_h2_not_matched(self):
        assert extract_title("## H2") is None

    def test_multiple_h1_returns_first(self):
        assert extract_title("# First\n# Second") == "First"
