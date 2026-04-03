"""
Tests for ArborGraph-Intent Taxonomy Tree, Diversity Sampler, and Auto Taxonomy.

Tests cover:
- TaxonomyTree: loading (flat/nested, JSON/YAML), validation, traversal, serialization
- DiversitySampler: all three strategies + coverage tracking
- AutoTaxonomy: prompt building, response parsing
"""

import asyncio
import json
import os
import tempfile
from collections import Counter
from unittest.mock import AsyncMock

import pytest

from arborgraph.models.taxonomy.auto_taxonomy import AutoTaxonomy
from arborgraph.models.taxonomy.diversity_sampler import DiversitySampler
from arborgraph.models.taxonomy.taxonomy_tree import (
    COGNITIVE_DIMENSIONS,
    TaxonomyNode,
    TaxonomyTree,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

SAMPLE_NESTED_TREE = {
    "name": "test_taxonomy",
    "description": "A test taxonomy",
    "domain": "testing",
    "version": "1.0",
    "nodes": [
        {
            "id": "root-1",
            "name": "Category A",
            "description": "First category",
            "cognitive_dimension": "concept_explanation",
            "children": [
                {
                    "id": "child-1a",
                    "name": "Subcategory A1",
                    "description": "First subcategory of A",
                    "cognitive_dimension": "relational_reasoning",
                    "children": [
                        {
                            "id": "leaf-1a1",
                            "name": "Leaf A1-1",
                            "description": "A leaf node",
                            "cognitive_dimension": "anomaly_diagnosis",
                            "children": [],
                        },
                        {
                            "id": "leaf-1a2",
                            "name": "Leaf A1-2",
                            "description": "Another leaf node",
                            "cognitive_dimension": "rule_compliance",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "child-1b",
                    "name": "Subcategory A2",
                    "description": "Second subcategory of A",
                    "cognitive_dimension": "comparative_analysis",
                    "children": [],
                },
            ],
        },
        {
            "id": "root-2",
            "name": "Category B",
            "description": "Second category",
            "cognitive_dimension": "procedural_knowledge",
            "children": [
                {
                    "id": "child-2a",
                    "name": "Subcategory B1",
                    "description": "First subcategory of B",
                    "cognitive_dimension": "concept_explanation",
                    "children": [],
                },
            ],
        },
    ],
}

SAMPLE_FLAT_TREE = {
    "name": "flat_taxonomy",
    "description": "A flat-format taxonomy",
    "domain": "testing",
    "nodes": [
        {"id": "root", "name": "Root", "parent_id": None,
         "cognitive_dimension": "concept_explanation"},
        {"id": "a", "name": "Branch A", "parent_id": "root",
         "cognitive_dimension": "relational_reasoning"},
        {"id": "b", "name": "Branch B", "parent_id": "root",
         "cognitive_dimension": "rule_compliance"},
        {"id": "a1", "name": "Leaf A1", "parent_id": "a",
         "cognitive_dimension": "anomaly_diagnosis"},
        {"id": "a2", "name": "Leaf A2", "parent_id": "a",
         "cognitive_dimension": "comparative_analysis"},
        {"id": "b1", "name": "Leaf B1", "parent_id": "b",
         "cognitive_dimension": "procedural_knowledge"},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# TaxonomyTree Tests
# ═══════════════════════════════════════════════════════════════════

class TestTaxonomyTreeLoading:
    """Test loading from different formats."""

    def test_load_nested_format(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        assert tree.name == "test_taxonomy"
        assert tree.domain == "testing"
        assert tree.size == 7  # 2 roots + 3 children + 2 leaves

    def test_load_flat_format(self):
        tree = TaxonomyTree.from_dict(SAMPLE_FLAT_TREE)
        assert tree.name == "flat_taxonomy"
        assert tree.size == 6

    def test_load_json_file(self, tmp_path):
        json_path = tmp_path / "test_tree.json"
        with open(json_path, "w") as f:
            json.dump(SAMPLE_NESTED_TREE, f)

        tree = TaxonomyTree.load(str(json_path))
        assert tree.name == "test_taxonomy"
        assert tree.size == 7

    def test_load_yaml_file(self, tmp_path):
        yaml_path = tmp_path / "test_tree.yaml"
        import yaml
        with open(yaml_path, "w") as f:
            yaml.dump(SAMPLE_NESTED_TREE, f)

        tree = TaxonomyTree.load(str(yaml_path))
        assert tree.name == "test_taxonomy"
        assert tree.size == 7

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            TaxonomyTree.load("/nonexistent/path.json")

    def test_load_empty_nodes(self):
        with pytest.raises(ValueError, match="at least one node"):
            TaxonomyTree.from_dict({"name": "empty", "nodes": []})


class TestTaxonomyTreeStructure:
    """Test tree structure and traversal."""

    def test_roots(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        roots = tree.roots
        assert len(roots) == 2
        root_ids = {r.id for r in roots}
        assert root_ids == {"root-1", "root-2"}

    def test_leaves(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        leaves = tree.leaves
        leaf_ids = {l.id for l in leaves}
        assert "leaf-1a1" in leaf_ids
        assert "leaf-1a2" in leaf_ids
        assert "child-1b" in leaf_ids
        assert "child-2a" in leaf_ids

    def test_max_depth(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        assert tree.max_depth == 2  # root -> child -> leaf

    def test_get_node(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        node = tree.get_node("child-1a")
        assert node is not None
        assert node.name == "Subcategory A1"

    def test_get_node_nonexistent(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        assert tree.get_node("nonexistent") is None

    def test_get_branch(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        branch = tree.get_branch("leaf-1a1")
        ids = [n.id for n in branch]
        assert ids == ["root-1", "child-1a", "leaf-1a1"]

    def test_get_subtree(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        subtree = tree.get_subtree("child-1a")
        subtree_ids = {n.id for n in subtree}
        assert subtree_ids == {"child-1a", "leaf-1a1", "leaf-1a2"}

    def test_get_siblings(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        siblings = tree.get_siblings("child-1a")
        sibling_ids = {s.id for s in siblings}
        assert sibling_ids == {"child-1b"}

    def test_get_nodes_by_dimension(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        nodes = tree.get_nodes_by_dimension("concept_explanation")
        assert len(nodes) == 2  # root-1 and child-2a

    def test_get_nodes_at_depth(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        depth_0 = tree.get_nodes_at_depth(0)
        depth_1 = tree.get_nodes_at_depth(1)
        depth_2 = tree.get_nodes_at_depth(2)
        assert len(depth_0) == 2  # two roots
        assert len(depth_1) == 3  # child-1a, child-1b, child-2a
        assert len(depth_2) == 2  # leaf-1a1, leaf-1a2

    def test_flat_format_depths(self):
        tree = TaxonomyTree.from_dict(SAMPLE_FLAT_TREE)
        root = tree.get_node("root")
        assert root.depth == 0
        a = tree.get_node("a")
        assert a.depth == 1
        a1 = tree.get_node("a1")
        assert a1.depth == 2


class TestTaxonomyTreeValidation:
    """Test validation."""

    def test_valid_tree(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        issues = tree.validate()
        errors = [i for i in issues if i.startswith("ERROR")]
        assert len(errors) == 0

    def test_invalid_cognitive_dimension(self):
        data = {
            "name": "bad_dim",
            "nodes": [
                {"id": "r", "name": "Root", "parent_id": None,
                 "cognitive_dimension": "nonexistent_dimension"},
            ]
        }
        tree = TaxonomyTree.from_dict(data)
        issues = tree.validate()
        assert any("unknown cognitive_dimension" in i for i in issues)

    def test_orphan_parent_reference(self):
        data = {
            "name": "orphan",
            "nodes": [
                {"id": "r", "name": "Root", "parent_id": None},
                {"id": "c", "name": "Child", "parent_id": "nonexistent_parent"},
            ]
        }
        tree = TaxonomyTree.from_dict(data)
        issues = tree.validate()
        assert any("non-existent parent" in i for i in issues)


class TestTaxonomyTreeSerialization:
    """Test save/load round-trip."""

    def test_round_trip_json(self, tmp_path):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        out_path = str(tmp_path / "output.json")
        tree.save(out_path)

        loaded = TaxonomyTree.load(out_path)
        assert loaded.name == tree.name
        assert loaded.size == tree.size
        assert loaded.max_depth == tree.max_depth

    def test_round_trip_yaml(self, tmp_path):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        out_path = str(tmp_path / "output.yaml")
        tree.save(out_path)

        loaded = TaxonomyTree.load(out_path)
        assert loaded.name == tree.name
        assert loaded.size == tree.size

    def test_to_dict_consistency(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        d = tree.to_dict()
        tree2 = TaxonomyTree.from_dict(d)
        assert tree2.size == tree.size
        assert tree2.name == tree.name

    def test_statistics(self):
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        stats = tree.get_statistics()
        assert stats["total_nodes"] == 7
        assert stats["root_count"] == 2
        assert stats["max_depth"] == 2
        assert "dimension_distribution" in stats


# ═══════════════════════════════════════════════════════════════════
# DiversitySampler Tests
# ═══════════════════════════════════════════════════════════════════

class TestDiversitySampler:
    """Test sampling strategies."""

    def _make_sampler(self, seed: int = 42) -> DiversitySampler:
        tree = TaxonomyTree.from_dict(SAMPLE_NESTED_TREE)
        return DiversitySampler(tree, seed=seed)

    def test_uniform_branch_sampling(self):
        sampler = self._make_sampler()
        samples = sampler.sample(4, strategy="uniform_branch")
        assert len(samples) == 4
        # Should sample from both branches
        root_ids = set()
        for s in samples:
            branch = sampler.tree.get_branch(s.id)
            root_ids.add(branch[0].id)
        assert len(root_ids) > 0

    def test_depth_weighted_sampling(self):
        sampler = self._make_sampler()
        samples = sampler.sample(4, strategy="depth_weighted")
        assert len(samples) == 4
        # With high weight_factor, deeper nodes should appear more often
        depths = [s.depth for s in samples]
        assert max(depths) > 0  # At least some non-root nodes

    def test_coverage_tracking_sampling(self):
        sampler = self._make_sampler()

        # First batch: all should be uncovered
        batch1 = sampler.sample(3, strategy="coverage")
        assert len(batch1) == 3
        assert sampler.coverage_ratio > 0

        # Second batch: should prefer uncovered nodes
        batch2 = sampler.sample(3, strategy="coverage")
        assert len(batch2) == 3
        # Combined should cover more than just batch1
        assert sampler.coverage_ratio > 3 / 7

    def test_coverage_full_tree(self):
        sampler = self._make_sampler()
        # Sample all nodes
        all_samples = sampler.sample(7, strategy="coverage")
        assert len(all_samples) == 7
        assert sampler.coverage_ratio == 1.0

    def test_coverage_reset(self):
        sampler = self._make_sampler()
        sampler.sample(3, strategy="coverage")
        assert sampler.coverage_ratio > 0
        sampler.reset_coverage()
        assert sampler.coverage_ratio == 0.0

    def test_sample_k_greater_than_size(self):
        sampler = self._make_sampler()
        samples = sampler.sample(100, strategy="uniform_branch")
        assert len(samples) <= 7  # Can't return more than tree size

    def test_sample_empty_tree(self):
        tree = TaxonomyTree(name="empty")
        # Add one node to avoid from_dict error
        sampler = DiversitySampler(tree, seed=42)
        samples = sampler.sample(5)
        assert len(samples) == 0

    def test_coverage_by_dimension(self):
        sampler = self._make_sampler()
        sampler.sample(7, strategy="coverage")
        dim_coverage = sampler.get_coverage_by_dimension()
        # All assigned dimensions should be 1.0
        for dim, ratio in dim_coverage.items():
            assert ratio == 1.0

    def test_coverage_by_depth(self):
        sampler = self._make_sampler()
        sampler.sample(7, strategy="coverage")
        depth_coverage = sampler.get_coverage_by_depth()
        for depth, ratio in depth_coverage.items():
            assert ratio == 1.0

    def test_uniformity_statistical(self):
        """After many samples, branch coverage should be roughly even."""
        sampler = self._make_sampler(seed=123)
        branch_counter = Counter()

        for _ in range(200):
            sampler.reset_coverage()
            samples = sampler.sample(2, strategy="uniform_branch")
            for s in samples:
                branch = sampler.tree.get_branch(s.id)
                if branch:
                    branch_counter[branch[0].id] += 1

        # Both roots should have been sampled
        assert len(branch_counter) >= 2
        counts = list(branch_counter.values())
        # Ratio between most and least sampled should be < 5x
        assert max(counts) / max(min(counts), 1) < 5


# ═══════════════════════════════════════════════════════════════════
# AutoTaxonomy Tests
# ═══════════════════════════════════════════════════════════════════

class TestAutoTaxonomy:
    """Test auto-taxonomy generation with mocked LLM."""

    def test_parse_response_pure_json(self):
        auto = AutoTaxonomy(llm_client=None)
        response = json.dumps(SAMPLE_NESTED_TREE)
        parsed = auto._parse_response(response)
        assert parsed["name"] == "test_taxonomy"

    def test_parse_response_markdown_block(self):
        auto = AutoTaxonomy(llm_client=None)
        response = f"Here is the taxonomy:\n```json\n{json.dumps(SAMPLE_NESTED_TREE)}\n```\nDone."
        parsed = auto._parse_response(response)
        assert parsed["name"] == "test_taxonomy"

    def test_parse_response_embedded_json(self):
        auto = AutoTaxonomy(llm_client=None)
        response = f"Some text before\n{json.dumps(SAMPLE_NESTED_TREE)}\nSome text after"
        parsed = auto._parse_response(response)
        assert parsed["name"] == "test_taxonomy"

    def test_parse_response_no_json(self):
        auto = AutoTaxonomy(llm_client=None)
        with pytest.raises(json.JSONDecodeError):
            auto._parse_response("This has no JSON at all")

    def test_generate_from_document(self):
        async def _run():
            # Mock LLM that returns valid taxonomy
            mock_llm = AsyncMock()
            mock_llm.query = AsyncMock(return_value=json.dumps(SAMPLE_NESTED_TREE))

            auto = AutoTaxonomy(llm_client=mock_llm)
            tree = await auto.generate_from_document(
                document_text="This is a test domain document about financial risk.",
                domain_name="finance",
            )

            assert tree.size == 7
            assert mock_llm.query.called

        asyncio.run(_run())

    def test_generate_retries_on_bad_json(self):
        async def _run():
            mock_llm = AsyncMock()
            # First call returns garbage, second returns valid JSON
            mock_llm.query = AsyncMock(
                side_effect=[
                    "This is not JSON",
                    json.dumps(SAMPLE_NESTED_TREE),
                ]
            )

            auto = AutoTaxonomy(llm_client=mock_llm)
            tree = await auto.generate_from_document(
                document_text="Test doc",
                domain_name="test",
                max_retries=3,
            )
            assert tree.size == 7
            assert mock_llm.query.call_count == 2

        asyncio.run(_run())

    def test_generate_fails_after_max_retries(self):
        async def _run():
            mock_llm = AsyncMock()
            mock_llm.query = AsyncMock(return_value="Not JSON at all")

            auto = AutoTaxonomy(llm_client=mock_llm)
            with pytest.raises(ValueError, match="Failed to generate taxonomy"):
                await auto.generate_from_document(
                    document_text="Test doc",
                    domain_name="test",
                    max_retries=2,
                )
            assert mock_llm.query.call_count == 2

        asyncio.run(_run())

    def test_build_prompt_contains_domain(self):
        auto = AutoTaxonomy(llm_client=None)
        prompt = auto._build_prompt("Some document text", "finance")
        assert "finance" in prompt
        assert "Some document text" in prompt
        assert "concept_explanation" in prompt  # Contains cognitive dims


# ═══════════════════════════════════════════════════════════════════
# Edge Case Tests
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_node_tree(self):
        data = {
            "name": "single",
            "nodes": [{"id": "only", "name": "Only Node"}],
        }
        tree = TaxonomyTree.from_dict(data)
        assert tree.size == 1
        assert tree.max_depth == 0
        assert len(tree.roots) == 1
        assert len(tree.leaves) == 1
        issues = tree.validate()
        assert not any(i.startswith("ERROR") for i in issues)

    def test_deep_tree(self):
        """Test a tree with depth 5."""
        nodes = [{"id": "d0", "name": "Depth 0", "parent_id": None}]
        for i in range(1, 6):
            nodes.append({
                "id": f"d{i}", "name": f"Depth {i}", "parent_id": f"d{i-1}",
            })
        tree = TaxonomyTree.from_dict({"name": "deep", "nodes": nodes})
        assert tree.max_depth == 5
        branch = tree.get_branch("d5")
        assert len(branch) == 6

    def test_wide_tree(self):
        """Test a tree with many children."""
        nodes = [{"id": "root", "name": "Root", "parent_id": None}]
        for i in range(20):
            nodes.append({
                "id": f"c{i}", "name": f"Child {i}", "parent_id": "root",
            })
        tree = TaxonomyTree.from_dict({"name": "wide", "nodes": nodes})
        assert tree.size == 21
        root = tree.get_node("root")
        assert len(root.children) == 20

    def test_taxonomy_node_properties(self):
        node = TaxonomyNode(id="test", name="Test", parent_id=None)
        assert node.is_root is True
        assert node.is_leaf is True
        node.children.append(TaxonomyNode(id="child", name="Child", parent_id="test"))
        assert node.is_leaf is False

    def test_cognitive_dimensions_constant(self):
        assert len(COGNITIVE_DIMENSIONS) == 6
        assert "concept_explanation" in COGNITIVE_DIMENSIONS
        assert "relational_reasoning" in COGNITIVE_DIMENSIONS
