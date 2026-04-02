"""
Tests for ArborGraph-Intent Phase 6: Evaluation Metrics.
"""

import pytest
from arborgraph.models.taxonomy.taxonomy_tree import TaxonomyTree
from arborgraph.utils.intent_metrics import IntentMetrics

SAMPLE_TREE = {
    "name": "Test Tree",
    "domain": "test",
    "nodes": [
        {
            "id": "root",
            "name": "Root",
            "cognitive_dimension": "concept_explanation",
            "children": [
                {"id": "leaf1", "name": "L1", "cognitive_dimension": "relational_reasoning"},
                {"id": "leaf2", "name": "L2", "cognitive_dimension": "rule_compliance"}
            ]
        }
    ]
}

def test_coverage_calculation():
    tree = TaxonomyTree.from_dict(SAMPLE_TREE)
    metrics = IntentMetrics(tree)
    
    # Results cover root and leaf1
    results = [
        {"metadata": {"intent_id": "root", "cognitive_dimension": "concept_explanation"}},
        {"metadata": {"intent_id": "leaf1", "cognitive_dimension": "relational_reasoning"}}
    ]
    
    coverage = metrics.calculate_coverage(results)
    
    assert coverage["overall_count"] == 3
    assert coverage["overall_covered"] == 2
    assert coverage["leaf_count"] == 2
    assert coverage["leaf_covered"] == 1
    
    assert coverage["by_dimension"]["concept_explanation"]["ratio"] == 1.0
    assert coverage["by_dimension"]["relational_reasoning"]["ratio"] == 1.0
    assert coverage["by_dimension"]["rule_compliance"]["ratio"] == 0.0

def test_distribution_calculation():
    tree = TaxonomyTree.from_dict(SAMPLE_TREE)
    metrics = IntentMetrics(tree)
    
    results = [
        {"metadata": {"cognitive_dimension": "A"}},
        {"metadata": {"cognitive_dimension": "A"}},
        {"metadata": {"cognitive_dimension": "B"}}
    ]
    
    dist = metrics.calculate_distribution(results)
    assert dist["counts"]["A"] == 2
    assert dist["counts"]["B"] == 1
    assert dist["ratios"]["A"] == pytest.approx(0.666, 0.01)
