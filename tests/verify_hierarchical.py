#!/usr/bin/env python
"""
Comprehensive verification script for hierarchical SFT generation implementation.

Run this script to verify all components are properly integrated.
"""

import sys
import asyncio


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def print_section(title):
    """Print formatted section."""
    print(f"\n{title}")
    print("-" * 70)


def check_syntax():
    """Check Python syntax of all new files."""
    print_section("1. Syntax Verification")

    files = [
        "arborgraph/models/partitioner/hierarchical_partitioner.py",
        "arborgraph/models/generator/tree_generator.py",
        "arborgraph/templates/generation/hierarchical_generation.py",
    ]

    import py_compile
    for filepath in files:
        try:
            py_compile.compile(filepath, doraise=True)
            print(f"✓ {filepath}")
        except py_compile.PyCompileError as e:
            print(f"✗ {filepath}: {e}")
            return False

    print("\n✅ All syntax checks passed")
    return True


def check_imports():
    """Check that all modules can be imported."""
    print_section("2. Import Verification")

    try:
        from arborgraph.models import HierarchicalPartitioner, TreeStructureGenerator
        print("✓ HierarchicalPartitioner imported")
        print("✓ TreeStructureGenerator imported")

        from arborgraph.templates import HIERARCHICAL_GENERATION_PROMPT
        print("✓ HIERARCHICAL_GENERATION_PROMPT imported")

        # Check template structure
        assert "en" in HIERARCHICAL_GENERATION_PROMPT, "Missing English templates"
        assert "zh" in HIERARCHICAL_GENERATION_PROMPT, "Missing Chinese templates"

        patterns = ["sibling", "inheritance", "abstraction", "multilevel"]
        for lang in ["en", "zh"]:
            for pattern in patterns:
                assert pattern in HIERARCHICAL_GENERATION_PROMPT[lang], \
                    f"Missing {pattern} pattern in {lang}"

        print(f"✓ Template structure valid (2 languages, 4 patterns each)")

        print("\n✅ All imports successful")
        return True

    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def check_registration():
    """Check that partitioner and generator are registered."""
    print_section("3. Registration Verification")

    try:
        # Check partitioner registration
        with open("arborgraph/operators/partition/partition_kg.py", "r") as f:
            content = f.read()
            assert "hierarchical" in content.lower(), "Partitioner not registered"
            assert "HierarchicalPartitioner" in content, "Class not imported"
        print("✓ Partitioner registered in partition_kg.py")

        # Check generator registration
        with open("arborgraph/operators/generate/generate_qas.py", "r") as f:
            content = f.read()
            assert "hierarchical" in content.lower(), "Generator not registered"
            assert "TreeStructureGenerator" in content, "Class not imported"
        print("✓ Generator registered in generate_qas.py")

        # Check config
        with open("backend/schemas.py", "r") as f:
            content = f.read()
            assert "hierarchical_relations" in content, "Config field missing"
            assert "structure_format" in content, "Config field missing"
        print("✓ Config fields added to TaskConfig")

        print("\n✅ All registrations verified")
        return True

    except Exception as e:
        print(f"✗ Registration check failed: {e}")
        return False


async def test_partitioner():
    """Test HierarchicalPartitioner functionality."""
    print_section("4. Partitioner Functionality Test")

    from arborgraph.models import HierarchicalPartitioner

    class MockGraph:
        async def get_all_nodes(self):
            return [
                ("A", {"description": "Node A"}),
                ("B", {"description": "Node B"}),
                ("C", {"description": "Node C"}),
            ]

        async def get_all_edges(self):
            return [
                ("B", "A", {"relation_type": "is_a"}),
                ("C", "A", {"relation_type": "is_a"}),
            ]

    try:
        partitioner = HierarchicalPartitioner(hierarchical_relations=["is_a"])
        communities = await partitioner.partition(MockGraph())

        assert len(communities) > 0, "No communities created"
        print(f"✓ Created {len(communities)} community(ies)")

        # Check metadata
        for comm in communities:
            assert "type" in comm.metadata, "Missing community type metadata"
        print(f"✓ All communities have metadata")

        print("\n✅ Partitioner test passed")
        return True

    except Exception as e:
        print(f"✗ Partitioner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generator():
    """Test TreeStructureGenerator functionality."""
    print_section("5. Generator Functionality Test")

    from arborgraph.models import TreeStructureGenerator

    try:
        # Test serialization
        batch = (
            [("Root", {"description": "Root node"}), ("Child", {"description": "Child node"})],
            [("Child", "Root", {"relation_type": "is_a", "description": "Child is a Root"})]
        )

        for fmt in ["markdown", "json", "outline"]:
            gen = TreeStructureGenerator(
                llm_client=None,
                structure_format=fmt,
                hierarchical_relations=["is_a"]
            )
            output = gen._serialize_to_format(batch)
            assert len(output) > 0, f"{fmt} serialization failed"
        print(f"✓ All serialization formats work (markdown, json, outline)")

        # Test parsing
        test_response = """Question: Test question?
Answer: Test answer.
Hierarchical Reasoning: Test reasoning."""

        parsed = TreeStructureGenerator.parse_response(test_response)
        assert len(parsed) > 0, "Parsing failed"
        qa = list(parsed.values())[0]
        assert "question" in qa and "answer" in qa, "Missing required fields"
        print(f"✓ Response parsing works")

        print("\n✅ Generator test passed")
        return True

    except Exception as e:
        print(f"✗ Generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print_header("HIERARCHICAL SFT GENERATION - VERIFICATION SCRIPT")

    results = []

    # Run tests
    results.append(("Syntax", check_syntax()))
    results.append(("Imports", check_imports()))
    results.append(("Registration", check_registration()))
    results.append(("Partitioner", asyncio.run(test_partitioner())))
    results.append(("Generator", test_generator()))

    # Summary
    print_header("VERIFICATION SUMMARY")

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "✗ FAIL"
        print(f"{name:20} {status}")
        all_passed = all_passed and passed

    print("\n" + "=" * 70)

    if all_passed:
        print("🎉 ALL VERIFICATION TESTS PASSED!".center(70))
        print("=" * 70)
        print("\nThe hierarchical SFT generation system is ready to use!")
        print("\nQuick start:")
        print("  1. Set partition_method='hierarchical' in config")
        print("  2. Set mode='hierarchical' or mode='all' in config")
        print("  3. Run your SFT generation pipeline")
        print("\nFor more details, see HIERARCHICAL_IMPLEMENTATION.md")
        return 0
    else:
        print("❌ SOME TESTS FAILED".center(70))
        print("=" * 70)
        print("\nPlease review the errors above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
