from manage import derive_id, infer_type_from_path


class TestDeriveId:
    def test_basic(self):
        assert derive_id("cycles/cycle-1/unit-1-test/thinker/round-1/result.md") == "c1-u1-thinker-r1-result"

    def test_with_sub_unit(self):
        path = "cycles/cycle-1/unit-1-test/sub-1a-detail/thinker/round-1/result.md"
        assert derive_id(path) == "c1-u1-s1a-thinker-r1-result"

    def test_drops_prompts_dir(self):
        assert derive_id("cycles/cycle-1/unit-1-test/coder/prompts/test.md") == "c1-u1-coder-test"

    def test_drops_results_dir(self):
        assert derive_id("cycles/cycle-1/unit-1-test/coder/results/output.md") == "c1-u1-coder-output"

    def test_context_path(self):
        assert derive_id("context/assumptions/homogeneity.md") == "assumptions-homogeneity"

    def test_strips_md(self):
        result = derive_id("cycles/cycle-1/unit-1-test/frontier.md")
        assert not result.endswith(".md")

    def test_named_cycle(self):
        """Regression: cycle-N-name should abbreviate to cN."""
        assert derive_id("cycles/cycle-1-enrichment/frontier.md") == "c1-frontier"

    def test_named_cycle_with_unit(self):
        assert derive_id("cycles/cycle-1-enrichment/unit-1-bottleneck/frontier.md") == "c1-u1-frontier"

    def test_deep_thinker(self):
        assert derive_id("cycles/cycle-1/deep-thinker/result.md") == "c1-deep-thinker-result"

    # --- Flat claims/ hierarchy (principia) ---

    def test_flat_claim(self):
        assert derive_id("claims/claim-1-enrichment/claim.md") == "h1-claim"

    def test_flat_claim_with_role(self):
        path = "claims/claim-2-topology/architect/round-1/result.md"
        assert derive_id(path) == "h2-architect-r1-result"

    def test_flat_claim_experimenter(self):
        path = "claims/claim-1-enrichment/experimenter/results/output.md"
        assert derive_id(path) == "h1-experimenter-output"

    def test_flat_claim_arbiter(self):
        path = "claims/claim-3-stability/arbiter/results/verdict.md"
        assert derive_id(path) == "h3-arbiter-verdict"


class TestInferType:
    def test_thinker_result(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/thinker/round-1/result.md") == "claim"

    def test_thinker_prompt(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/thinker/round-1/prompt.md") == "question"

    def test_refutor_result(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/refutor/round-1/result.md") == "claim"

    def test_refutor_prompt(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/refutor/round-1/prompt.md") == "question"

    def test_coder(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/coder/results/output.md") == "evidence"

    def test_judge(self):
        assert infer_type_from_path("cycles/cycle-1/unit-1/judge/results/verdict.md") == "verdict"

    def test_researcher(self):
        assert infer_type_from_path("cycles/cycle-1/researcher/results/result.md") == "reference"

    def test_assumption(self):
        assert infer_type_from_path("context/assumptions/homogeneity.md") == "assumption"

    def test_frontier(self):
        assert infer_type_from_path("cycles/cycle-1/frontier.md") == "verdict"

    def test_deep_thinker_result(self):
        assert infer_type_from_path("cycles/cycle-1/deep-thinker/result.md") == "claim"

    def test_deep_thinker_prompt(self):
        assert infer_type_from_path("cycles/cycle-1/deep-thinker/prompt.md") == "question"

    def test_fallback(self):
        assert infer_type_from_path("cycles/cycle-1/unknown/file.md") == "reference"
