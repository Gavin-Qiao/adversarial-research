from manage import _parse_yaml_value, extract_title, get_body, parse_frontmatter


class TestParseYamlValue:
    def test_null_values(self):
        assert _parse_yaml_value("null") is None
        assert _parse_yaml_value("~") is None
        assert _parse_yaml_value("") is None

    def test_inline_list(self):
        assert _parse_yaml_value("[a, b, c]") == ["a", "b", "c"]

    def test_empty_list(self):
        assert _parse_yaml_value("[]") == []

    def test_quoted_string_double(self):
        assert _parse_yaml_value('"hello world"') == "hello world"

    def test_quoted_string_single(self):
        assert _parse_yaml_value("'hello world'") == "hello world"

    def test_plain_string(self):
        assert _parse_yaml_value("hello") == "hello"

    def test_strips_whitespace(self):
        assert _parse_yaml_value("  hello  ") == "hello"

    def test_list_with_quoted_items(self):
        assert _parse_yaml_value("['a', \"b\"]") == ["a", "b"]


class TestParseFrontmatter:
    def test_simple(self):
        text = "---\nid: test\ntype: claim\nstatus: pending\n---\nBody text"
        meta = parse_frontmatter(text)
        assert meta["id"] == "test"
        assert meta["type"] == "claim"
        assert meta["status"] == "pending"

    def test_empty_frontmatter(self):
        text = "---\n---\nBody"
        assert parse_frontmatter(text) == {}

    def test_no_frontmatter(self):
        text = "Just a regular markdown file"
        assert parse_frontmatter(text) == {}

    def test_unclosed_frontmatter(self):
        text = "---\nid: test\nno closing"
        assert parse_frontmatter(text) == {}

    def test_list_value(self):
        text = "---\ndepends_on: [a, b]\n---\n"
        meta = parse_frontmatter(text)
        assert meta["depends_on"] == ["a", "b"]

    def test_null_value(self):
        text = "---\nattack_type: null\n---\n"
        meta = parse_frontmatter(text)
        assert meta["attack_type"] is None

    def test_value_with_colon(self):
        text = '---\ncounterfactual: "This would break: everything"\n---\n'
        meta = parse_frontmatter(text)
        assert meta["counterfactual"] == "This would break: everything"

    def test_skips_comments(self):
        text = "---\n# comment\nid: test\n---\n"
        meta = parse_frontmatter(text)
        assert "# comment" not in meta
        assert meta["id"] == "test"


class TestGetBody:
    def test_with_frontmatter(self):
        text = "---\nid: test\n---\nBody text here"
        assert get_body(text) == "Body text here"

    def test_without_frontmatter(self):
        text = "Just body text"
        assert get_body(text) == "Just body text"


class TestExtractTitle:
    def test_h1(self):
        assert extract_title("# My Title\nSome content") == "My Title"

    def test_no_heading(self):
        assert extract_title("No heading here") is None

    def test_h2_ignored(self):
        assert extract_title("## H2 heading") is None

    def test_h1_with_leading_blank(self):
        assert extract_title("\n# Title") == "Title"
