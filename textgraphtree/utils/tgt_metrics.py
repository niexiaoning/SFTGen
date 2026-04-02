"""
Evaluation metrics for TGT framework.

Calculates:
- Taxonomy Node Coverage
- Cognitive Dimension Distribution
- Quality scores (if critic metadata available)
"""

import json
import logging
import os
from collections import Counter
from typing import Any, Dict, List

from textgraphtree.models.taxonomy.taxonomy_tree import TaxonomyTree

logger = logging.getLogger(__name__)


class TGMetrics:
    def __init__(self, taxonomy_tree: TaxonomyTree):
        self.tree = taxonomy_tree

    def calculate_coverage(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate intent coverage from generated results.

        :param results: List of generated QA pairs with metadata
        :return: Coverage statistics
        """
        covered_ids = set()
        for item in results:
            intent_id = item.get("metadata", {}).get("intent_id")
            if intent_id:
                covered_ids.add(intent_id)

        all_node_ids = {n.id for n in self.tree.get_all_nodes()}
        all_leaf_ids = {n.id for n in self.tree.leaves}

        coverage_stats = {
            "overall_count": len(all_node_ids),
            "overall_covered": len(covered_ids & all_node_ids),
            "overall_ratio": len(covered_ids & all_node_ids) / len(all_node_ids) if all_node_ids else 0,
            "leaf_count": len(all_leaf_ids),
            "leaf_covered": len(covered_ids & all_leaf_ids),
            "leaf_ratio": len(covered_ids & all_leaf_ids) / len(all_leaf_ids) if all_leaf_ids else 0,
        }

        # Per-dimension coverage
        dimension_stats = {}
        for dim in self.tree._get_all_dimensions():
            dim_nodes = {n.id for n in self.tree.get_nodes_by_dimension(dim)}
            if not dim_nodes:
                continue
            dim_covered = len(covered_ids & dim_nodes)
            dimension_stats[dim] = {
                "count": len(dim_nodes),
                "covered": dim_covered,
                "ratio": dim_covered / len(dim_nodes),
            }
        
        coverage_stats["by_dimension"] = dimension_stats
        return coverage_stats

    def calculate_distribution(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate distribution of cognitive dimensions in the generated data."""
        dimensions = []
        for item in results:
            dim = item.get("metadata", {}).get("cognitive_dimension")
            if dim:
                dimensions.append(dim)
        
        counts = Counter(dimensions)
        total = len(dimensions)
        
        return {
            "counts": dict(counts),
            "ratios": {k: v / total for k, v in counts.items()} if total > 0 else {},
            "total": total
        }

    def generate_report(self, results_path: str, output_path: str = None) -> Dict[str, Any]:
        """Generate a full metrics report from a results file."""
        if not os.path.exists(results_path):
            raise FileNotFoundError(f"Results file not found: {results_path}")

        with open(results_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        coverage = self.calculate_coverage(results)
        distribution = self.calculate_distribution(results)

        report = {
            "taxonomy_name": self.tree.name,
            "domain": self.tree.domain,
            "sample_size": len(results),
            "coverage": coverage,
            "distribution": distribution,
        }

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Metrics report saved to %s", output_path)

        return report
