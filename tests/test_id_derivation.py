from manage import derive_id, infer_type_from_path


class TestDeriveId:
    # --- claims/ hierarchy ---

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

    # --- context/ ---

    def test_context_path(self):
        assert derive_id("context/assumptions/homogeneity.md") == "assumptions-homogeneity"

    # --- prompts/results stripping with claims paths ---

    def test_drops_prompts_dir(self):
        assert derive_id("claims/claim-1-test/architect/prompts/test.md") == "h1-architect-test"

    def test_drops_results_dir(self):
        assert derive_id("claims/claim-1-test/experimenter/results/output.md") == "h1-experimenter-output"


class TestInferType:
    def test_architect_result(self):
        assert infer_type_from_path("claims/claim-1-test/architect/round-1/result.md") == "claim"

    def test_architect_prompt(self):
        assert infer_type_from_path("claims/claim-1-test/architect/round-1/prompt.md") == "question"

    def test_adversary_result(self):
        assert infer_type_from_path("claims/claim-1-test/adversary/round-1/result.md") == "claim"

    def test_adversary_prompt(self):
        assert infer_type_from_path("claims/claim-1-test/adversary/round-1/prompt.md") == "question"

    def test_experimenter(self):
        assert infer_type_from_path("claims/claim-1-test/experimenter/results/output.md") == "evidence"

    def test_arbiter(self):
        assert infer_type_from_path("claims/claim-1-test/arbiter/results/verdict.md") == "verdict"

    def test_scout(self):
        assert infer_type_from_path("claims/claim-1-test/scout/results/result.md") == "reference"

    def test_claim_md(self):
        assert infer_type_from_path("claims/claim-1-test/claim.md") == "claim"

    def test_assumption(self):
        assert infer_type_from_path("context/assumptions/homogeneity.md") == "assumption"

    def test_fallback(self):
        assert infer_type_from_path("claims/claim-1-test/unknown/file.md") == "reference"
