#!/usr/bin/env python3
"""
Domain instantiation script for ArborGraph-Intent.

Automates complete workflow for a new domain:
1. Build KG from domain documents
2. Load or auto-generate taxonomy tree
3. Run ArborGraph-Intent pipeline
4. Generate metrics report
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from arborgraph.intent_pipeline import IntentPipeline
from arborgraph.arborgraph import ArborGraph
from arborgraph.models.taxonomy.taxonomy_tree import TaxonomyTree
from arborgraph.models.taxonomy.auto_taxonomy import AutoTaxonomy
from arborgraph.models.storage.networkx_storage import NetworkXStorage
from arborgraph.utils.intent_metrics import IntentMetrics

logger = logging.getLogger(__name__)


async def run_domain(
    domain_dir: str,
    output_dir: Optional[str] = None,
    kg_path: Optional[str] = None,
    generate_taxonomy: bool = False,
    source_document: Optional[str] = None,
):
    """
    Run ArborGraph-Intent pipeline for a domain.

    :param domain_dir: Directory containing domain config
    :param output_dir: Output directory for results
    :param kg_path: Path to existing KG (skip build if provided)
    :param generate_taxonomy: Whether to auto-generate taxonomy from source document
    :param source_document: Path to domain document for auto-taxonomy generation
    """
    domain_dir = Path(domain_dir)
    config_path = domain_dir / "intent_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"intent_config.yaml not found in {domain_dir}")

    # Load config
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    intent_config = config_data.get("intent", config_data)

    # Setup output directory
    output_dir = Path(output_dir or domain_dir / "output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup LLM client (simplified - assumes OpenAI compatible)
    # For proper implementation, use the same LLM setup as arborgraph_cli.py
    from dotenv import load_dotenv
    load_dotenv()

    # Simple LLM client setup for demonstration
    # In production, integrate with proper arborgraph_cli.py LLM client
    api_key = os.environ.get("SYNTHESIZER_API_KEY", "")
    api_base = os.environ.get("SYNTHESIZER_BASE_URL", "")
    api_model = os.environ.get("SYNTHESIZER_MODEL", "")
    rpm = int(os.environ.get("RPM", "1000"))
    tpm = int(os.environ.get("TPM", "50000"))

    if not api_key:
        logger.error("API Key not found. Set SYNTHESIZER_API_KEY environment variable.")
        return None

    # Create a simple async LLM client interface
    class SimpleLLMClient:
        def __init__(self, api_key, api_base, api_model, rpm, tpm):
            self.api_key = api_key
            self.api_base = api_base
            self.api_model = api_model
            self.rpm = rpm
            self.tpm = tpm

        async def query(self, prompt: str) -> str:
            """Simple async query method - should use actual OpenAI client in production"""
            # This is a placeholder - use proper OpenAI client in production
            import httpx
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base if self.api_base else None,
            max_retries=2,
                timeout=60.0,
            http_client=httpx.AsyncClient(timeout=120.0),
            )

            response = await client.chat.completions.create(
                model=self.api_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.7,
            )

            return response.choices[0].message.content if response.choices else ""

    llm_client = SimpleLLMClient(api_key, api_base, api_model, rpm, tpm)

    # Step 1: Build or load KG
    graph_storage = None
    if kg_path:
        logger.info(f"Loading existing KG from {kg_path}")
        graph_storage = NetworkXStorage()
        try:
            graph_storage.load(kg_path)
            logger.info("KG loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load KG, will build new one: {e}")
            graph_storage = None

    # Step 2: Load or generate taxonomy
    taxonomy_config = intent_config.get("taxonomy", {})
    taxonomy_path = taxonomy_config.get("path")

    if generate_taxonomy and source_document:
        logger.info(f"Auto-generating taxonomy from {source_document}")
        with open(source_document, "r", encoding="utf-8") as f:
            doc_text = f.read()

        domain_name = intent_config.get("taxonomy", {}).get("domain", "general")

        # Note: AutoTaxonomy needs to be implemented or use different approach
        logger.warning("Auto-taxonomy generation requires AutoTaxonomy implementation")
        # Fallback to loading taxonomy from file
        if taxonomy_path and os.path.exists(taxonomy_path):
            tree = TaxonomyTree.load(taxonomy_path)
        else:
            logger.error(f"Taxonomy file not found: {taxonomy_path}")
            return None
    elif taxonomy_path and os.path.exists(taxonomy_path):
        logger.info(f"Loading taxonomy from {taxonomy_path}")
        tree = TaxonomyTree.load(taxonomy_path)
    else:
        logger.error("No taxonomy available. Provide --generate-taxonomy with --source-document")
        return None

    logger.info(f"Taxonomy loaded: {tree.name} ({tree.size} nodes)")

    # If no graph storage, we can't run the pipeline
    if not graph_storage:
        logger.error("No knowledge graph available. Provide --kg-path or --generate-taxonomy is not available")
        return None

    # Step 3: Run ArborGraph-Intent pipeline
    try:
        logger.info("Initializing ArborGraph-Intent pipeline...")
        pipeline = IntentPipeline.from_config(str(config_path), llm_client, graph_storage)

        target_count = intent_config.get("generation", {}).get("target_qa_pairs", 100)
        batch_size = intent_config.get("generation", {}).get("batch_size", 10)

        logger.info(f"Generating {target_count} QA pairs (batch_size: {batch_size})")

        results = await pipeline.run(target_count=target_count, batch_size=batch_size)

        # Step 4: Save results
        results_file = output_dir / "qa_pairs.json"
        logger.info(f"Saving results to {results_file}")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Step 5: Generate metrics report
        metrics = IntentMetrics(tree)
        report = metrics.calculate_coverage(results)
        report["distribution"] = metrics.calculate_distribution(results)

        metrics_file = output_dir / "metrics_report.json"
        logger.info(f"Saving metrics to {metrics_file}")
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("Domain instantiation complete!")
        logger.info(f"Generated {len(results)} QA pairs")
        logger.info(f"Taxonomy coverage: {report['coverage']['overall_ratio']:.1%}")

        return str(results_file), str(metrics_file)

    except Exception as e:
        logger.error(f"Error running ArborGraph-Intent pipeline: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Run ArborGraph-Intent pipeline for a specific domain"
    )
    parser.add_argument(
        "--domain", "-d", required=True,
        help="Directory containing domain config (e.g., arborgraph/configs/intent/finance)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory for results (default: domain/output)"
    )
    parser.add_argument(
        "--kg", "-k",
        help="Path to existing knowledge graph (skip KG build)"
    )
    parser.add_argument(
        "--generate-taxonomy", "-g", action="store_true",
        help="Auto-generate taxonomy from source document"
    )
    parser.add_argument(
        "--source-document", "-s",
        help="Source document for taxonomy auto-generation"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    results = asyncio.run(run_domain(
        domain_dir=args.domain,
        output_dir=args.output,
        kg_path=args.kg,
        generate_taxonomy=args.generate_taxonomy,
        source_document=args.source_document,
    ))

    if results:
        print("✅ ArborGraph-Intent pipeline completed successfully!")
        print(f"📊 Results: {results[0]}")
        print(f"📊 Metrics: {results[1]}")
    else:
        print("❌ ArborGraph-Intent pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
