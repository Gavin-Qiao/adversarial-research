from frontmatter import _yaml_val, parse_frontmatter, serialise_frontmatter


class TestYamlVal:
    def test_none(self):
        assert _yaml_val(None) == "null"

    def test_empty_list(self):
        assert _yaml_val([]) == "[]"

    def test_list_with_items(self):
        assert _yaml_val(["a", "b"]) == "[a, b]"

    def test_list_with_yaml_specials(self):
        result = _yaml_val(["true", "false", "null"])
        assert '"true"' in result
        assert '"false"' in result
        assert '"null"' in result

    def test_normal_string(self):
        assert _yaml_val("hello") == "hello"

    def test_yaml_special_string(self):
        assert _yaml_val("true") == '"true"'
        assert _yaml_val("false") == '"false"'
        assert _yaml_val("null") == '"null"'
        assert _yaml_val("yes") == '"yes"'
        assert _yaml_val("no") == '"no"'

    def test_numeric_string(self):
        assert _yaml_val("42") == '"42"'
        assert _yaml_val("3.14") == '"3.14"'

    def test_string_with_colon(self):
        assert _yaml_val("key: value") == '"key: value"'

    def test_normal_id(self):
        assert _yaml_val("c1-u1-thinker-r1-result") == "c1-u1-thinker-r1-result"


class TestSerialiseFrontmatter:
    def test_key_order(self):
        meta = {
            "counterfactual": None,
            "id": "test",
            "status": "pending",
            "type": "claim",
            "date": "2026-01-01",
        }
        result = serialise_frontmatter(meta)
        lines = result.split("\n")
        # Skip --- delimiters, check canonical order
        keys = [line.split(":")[0] for line in lines[1:-1]]
        assert keys.index("id") < keys.index("type")
        assert keys.index("type") < keys.index("status")
        assert keys.index("status") < keys.index("date")

    def test_contains_delimiters(self):
        meta = {"id": "test", "type": "claim", "status": "pending"}
        result = serialise_frontmatter(meta)
        assert result.startswith("---\n")
        assert result.endswith("\n---")


class TestRoundTrip:
    def test_simple_roundtrip(self):
        meta = {
            "id": "c1-u1-thinker-r1-result",
            "type": "claim",
            "status": "pending",
            "date": "2026-01-01",
            "depends_on": [],
            "assumes": [],
            "attack_type": None,
            "falsified_by": None,
            "counterfactual": None,
        }
        serialized = serialise_frontmatter(meta)
        parsed = parse_frontmatter(serialized + "\n")
        assert parsed["id"] == meta["id"]
        assert parsed["type"] == meta["type"]
        assert parsed["status"] == meta["status"]
        assert parsed["depends_on"] == meta["depends_on"]
        assert parsed["attack_type"] is None

    def test_roundtrip_with_lists(self):
        meta = {
            "id": "test",
            "type": "claim",
            "status": "pending",
            "date": "2026-01-01",
            "depends_on": ["a", "b", "c"],
            "assumes": ["x"],
        }
        serialized = serialise_frontmatter(meta)
        parsed = parse_frontmatter(serialized + "\n")
        assert parsed["depends_on"] == ["a", "b", "c"]
        assert parsed["assumes"] == ["x"]

    def test_roundtrip_yaml_special_in_list(self):
        """Regression: list items matching YAML specials must survive round-trip."""
        meta = {
            "id": "test",
            "type": "claim",
            "status": "pending",
            "date": "2026-01-01",
            "depends_on": ["true", "false"],
            "assumes": [],
        }
        serialized = serialise_frontmatter(meta)
        parsed = parse_frontmatter(serialized + "\n")
        assert parsed["depends_on"] == ["true", "false"]
