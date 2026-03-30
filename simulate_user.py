"""
Integration Test: Simulate Developer Workflow

This script tests the production-ready Flowstate daemon with:
- Knowledge graph persistence
- Semantic queries
- Process correlation
- Import inference
"""

import os
import shutil
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flowstate import FlowstateDaemon, KnowledgeGraph, ContextNode, ContextQueryResult


def test_knowledge_graph():
    """Test that the knowledge graph works correctly."""
    
    print("🧪 Testing knowledge graph...")
    
    # Create a test database
    test_db = Path("/tmp/flowstate_test_db.db")
    if test_db.exists():
        test_db.unlink()
    
    graph = KnowledgeGraph(db_path=str(test_db))
    
    # Test 1: Add nodes
    print("   Adding nodes...")
    node1 = ContextNode(
        id="file:/tmp/test/main.py",
        kind="file",
        path="/tmp/test/main.py",
        content="from database import connect",
        metadata={"size": 100}
    )
    graph.add_node(node1)
    
    node2 = ContextNode(
        id="file:/tmp/test/database.py",
        kind="file",
        path="/tmp/test/database.py",
        content="def connect(): return {}"
    )
    graph.add_node(node2)
    
    assert len(graph.nodes) == 2, f"Expected 2 nodes, got {len(graph.nodes)}"
    print(f"   ✓ Added 2 nodes")
    
    # Test 2: Add edges
    print("   Adding edges...")
    from flowstate import ContextEdge
    edge = ContextEdge(
        source="file:/tmp/test/main.py",
        target="file:/tmp/test/database.py",
        relationship="imports",
        strength=1.0
    )
    graph.add_edge(edge)
    
    neighbors = graph.get_neighbors("file:/tmp/test/main.py")
    assert len(neighbors) == 1, f"Expected 1 neighbor, got {len(neighbors)}"
    print(f"   ✓ Added 1 edge, verified neighbors")
    
    # Test 3: Query
    print("   Testing queries...")
    result = graph.query("database")
    assert len(result.results) >= 1, "Query should return results"
    print(f"   ✓ Query returned {len(result.results)} results")
    
    # Test 4: Persistence
    print("   Testing persistence...")
    del graph  # Clear from memory
    graph2 = KnowledgeGraph(db_path=str(test_db))
    assert len(graph2.nodes) == 2, "Graph should persist"
    print(f"   ✓ Graph persisted correctly")
    
    # Cleanup
    test_db.unlink()
    
    return True


def test_file_monitoring():
    """Test that file monitoring works correctly."""
    
    print("\n🧪 Testing file monitoring...")
    
    test_dir = Path("/tmp/flowstate_file_test_" + str(int(time.time())))
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create test files
        main_py = test_dir / "main.py"
        main_py.write_text("from database import connect\n\ndef main():\n    pass\n")
        
        database_py = test_dir / "database.py"
        database_py.write_text("def connect():\n    return {}\n")
        
        # Create daemon with fresh database (outside watched directory)
        test_db = Path("/tmp/flowstate_test_db.db")
        if test_db.exists():
            test_db.unlink()
        daemon = FlowstateDaemon(watch_paths=[str(test_dir)], db_path=str(test_db))
        
        # Start monitoring
        daemon.start()
        time.sleep(2)
        
        # Verify files were indexed (filter to test_dir only)
        file_nodes = [n for n in daemon.graph.nodes.values() if n.kind == "file" and str(test_dir) in (n.path or "")]
        assert len(file_nodes) == 2, f"Expected 2 files, got {len(file_nodes)}"
        print(f"   ✓ Indexed {len(file_nodes)} files")
        
        # Verify import inference
        main_node = next((n for n in file_nodes if "main.py" in n.path), None)
        assert main_node is not None, "Could not find main.py"
        
        neighbors = daemon.graph.get_neighbors(main_node.id)
        neighbor_paths = [n.path for n in neighbors if n.path]
        assert any("database.py" in p for p in neighbor_paths), "Should know about database.py import"
        print(f"   ✓ Inferred import relationship")
        
        # Test query
        result = daemon.query("connect")
        assert len(result.results) >= 1, "Query should find 'connect'"
        print(f"   ✓ Query found {len(result.results)} results for 'connect'")
        
        # Stop daemon
        daemon.stop()
        
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_process_monitoring():
    """Test that process monitoring works correctly."""
    
    print("\n🧪 Testing process monitoring...")
    
    test_dir = Path("/tmp/flowstate_process_test_" + str(int(time.time())))
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create a test file
        test_file = test_dir / "test.py"
        test_file.write_text("# test file")
        
        # Create daemon
        daemon = FlowstateDaemon(watch_paths=[str(test_dir)])
        daemon.start()
        time.sleep(2)
        
        # Trigger process scan
        daemon.process_monitor.scan()
        time.sleep(1)
        
        # Check that processes were indexed
        process_nodes = [n for n in daemon.graph.nodes.values() if n.kind == "process"]
        # We should have at least some processes (python, bash, etc.)
        assert len(process_nodes) > 0, "Should have indexed some processes"
        print(f"   ✓ Indexed {len(process_nodes)} processes")
        
        daemon.stop()
        
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_query_system():
    """Test the natural language query system."""
    
    print("\n🧪 Testing query system...")
    
    graph = KnowledgeGraph()
    
    # Add test data
    test_cases = [
        ("file:/test/main.py", "file", "from database import connect\ndef main(): pass"),
        ("file:/test/database.py", "file", "def connect(): return {}"),
        ("file:/test/utils.py", "file", "def format_output(row): return str(row)"),
    ]
    
    for node_id, kind, content in test_cases:
        node = ContextNode(id=node_id, kind=kind, path=node_id.split(":")[1], content=content)
        graph.add_node(node)
    
    # Test queries
    queries = [
        ("database", 1),  # Should find database.py
        ("connect", 2),   # Should find main.py and database.py
        ("format", 1),    # Should find utils.py
    ]
    
    for query_text, expected_min in queries:
        result = graph.query(query_text)
        assert len(result.results) >= expected_min, f"Query '{query_text}' should return at least {expected_min} results"
        print(f"   ✓ Query '{query_text}' returned {len(result.results)} results")
    
    return True


def test_integration():
    """Test a complete workflow."""
    
    print("\n🧪 Testing complete workflow...")
    
    test_dir = Path("/tmp/flowstate_integration_" + str(int(time.time())))
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create a small project
        src_dir = test_dir / "src"
        src_dir.mkdir()
        
        (src_dir / "main.py").write_text("""
from database import connect
from utils import format_output

def main():
    db = connect()
    print(format_output(db))
""")
        
        (src_dir / "database.py").write_text("""
def connect():
    return {"users": ["alice", "bob"]}
""")
        
        (src_dir / "utils.py").write_text("""
def format_output(data):
    return str(data)
""")
        
        # Create daemon with fresh database (outside watched directory)
        test_db = Path("/tmp/flowstate_integration_db.db")
        if test_db.exists():
            test_db.unlink()
        daemon = FlowstateDaemon(watch_paths=[str(src_dir)], db_path=str(test_db))
        daemon.start()
        time.sleep(2)
        
        # Test 1: Files indexed
        file_nodes = [n for n in daemon.graph.nodes.values() if n.kind == "file" and str(src_dir) in (n.path or "")]
        assert len(file_nodes) == 3, f"Expected 3 files, got {len(file_nodes)}"
        print(f"   ✓ Indexed 3 files")
        
        # Test 2: Import inference
        main_node = next(n for n in file_nodes if "main.py" in n.path)
        neighbors = daemon.graph.get_neighbors(main_node.id)
        neighbor_names = [os.path.basename(n.path or "") for n in neighbors if n.path]
        assert "database.py" in neighbor_names, "Should know about database import"
        assert "utils.py" in neighbor_names, "Should know about utils import"
        print(f"   ✓ Inferred imports: {', '.join(neighbor_names)}")
        
        # Test 3: Query
        result = daemon.query("connect")
        assert len(result.results) >= 2, "Should find files with 'connect'"
        print(f"   ✓ Query 'connect' found {len(result.results)} files")
        
        # Test 4: Path finding
        database_node = next(n for n in file_nodes if "database.py" in n.path)
        path = daemon.graph.find_path(main_node.id, database_node.id)
        assert len(path) == 2, "Should find direct path"
        print(f"   ✓ Found path: main.py → database.py")
        
        # Test 5: Persistence
        daemon.stop()
        time.sleep(0.5)
        
        # Reload graph
        graph2 = KnowledgeGraph(db_path=daemon.graph.db_path)
        assert len(graph2.nodes) > 0, "Graph should persist"
        print(f"   ✓ Graph persisted ({len(graph2.nodes)} nodes)")
        
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("FLOWSTATE INTEGRATION TEST SUITE (Production Ready)")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Knowledge Graph", test_knowledge_graph()))
    results.append(("File Monitoring", test_file_monitoring()))
    results.append(("Process Monitoring", test_process_monitoring()))
    results.append(("Query System", test_query_system()))
    results.append(("Integration", test_integration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Flowstate is production-ready.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        sys.exit(1)
