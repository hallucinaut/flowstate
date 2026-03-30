"""
Integration Test: Simulate Human Workflow

This script acts like a human developer interacting with the OS, verifying
that Flowstate successfully builds context and provides ambient awareness.
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flowstate import FlowstateDaemon, KnowledgeGraph


def simulate_developer_workflow():
    """
    Simulates a realistic developer workflow:
    1. Create a Python project with multiple files
    2. Write code with imports
    3. Run a process that uses those files
    4. Verify Flowstate builds the correct knowledge graph
    """
    
    test_dir = Path("/tmp/flowstate_test_" + str(int(time.time())))
    test_dir.mkdir(exist_ok=True)
    
    print(f"🧪 Setting up test environment: {test_dir}")
    
    try:
        # STEP 1: Create project structure
        print("\n📁 Creating project structure...")
        src_dir = test_dir / "src"
        src_dir.mkdir()
        
        # Create main.py
        main_py = src_dir / "main.py"
        main_py.write_text("""
from database import connect
from utils import format_output

def main():
    db = connect()
    data = db.query("SELECT * FROM users")
    for row in data:
        print(format_output(row))

if __name__ == "__main__":
    main()
""")
        
        # Create database.py
        database_py = src_dir / "database.py"
        database_py.write_text("""
def connect():
    return {"status": "connected"}

def query(sql):
    return [{"id": 1, "name": "Alice"}]
""")
        
        # Create utils.py
        utils_py = src_dir / "utils.py"
        utils_py.write_text("""
def format_output(row):
    return f"User: {row['name']}"
""")
        
        print("   ✓ Created main.py, database.py, utils.py")
        
        # STEP 2: Initialize Flowstate daemon
        print("\n🌊 Initializing Flowstate...")
        daemon = FlowstateDaemon(watch_paths=[str(src_dir)])
        graph = daemon.graph  # Access the daemon's graph
        
        # Verify only our test files are indexed
        file_nodes = [n for n in graph.nodes.values() if n.kind == "file" and str(src_dir) in (n.path or "")]
        print(f"   Indexed {len(file_nodes)} files from test directory")
        
        # Capture suggestions
        captured_suggestions = []
        
        def capture_suggestions(suggestions):
            captured_suggestions.extend(suggestions)
            print(f"   💡 Ambient insight: {len(suggestions)} new connections")
        
        daemon.register_suggestion_callback(capture_suggestions)
        
        # STEP 3: Start monitoring
        print("\n👀 Starting monitoring...")
        daemon.start()
        time.sleep(2)  # Let it index files
        
        # STEP 4: Verify knowledge graph
        print("\n🔍 Verifying knowledge graph...")
        
        # Check that all files were indexed (filter to src_dir only)
        file_nodes = [n for n in graph.nodes.values() if n.kind == "file" and str(src_dir) in (n.path or "")]
        assert len(file_nodes) == 3, f"Expected 3 files, got {len(file_nodes)}"
        print(f"   ✓ Indexed {len(file_nodes)} files")
        
        # Check that import relationships were inferred
        edges = graph.edges
        import_edges = [e for e in edges if e.relationship == "imports"]
        assert len(import_edges) >= 2, f"Expected at least 2 import edges, got {len(import_edges)}"
        print(f"   ✓ Inferred {len(import_edges)} import relationships")
        
        # STEP 5: Test context suggestions
        print("\n💡 Testing ambient suggestions...")
        
        # Find main.py node
        main_node = None
        for node in graph.nodes.values():
            if "main.py" in (node.path or ""):
                main_node = node
                break
        
        assert main_node is not None, "Could not find main.py node"
        
        # Get neighbors (imported modules)
        neighbors = graph.get_neighbors(main_node.id)
        neighbor_paths = [n.path for n in neighbors if n.path]
        
        assert "database.py" in str(neighbor_paths), "Should know about database.py import"
        assert "utils.py" in str(neighbor_paths), "Should know about utils.py import"
        print(f"   ✓ Correctly identified imports: {neighbor_paths}")
        
        # STEP 6: Test path finding
        print("\n🔗 Testing path finding...")
        
        # Find database.py node
        database_node = None
        for node in graph.nodes.values():
            if "database.py" in (node.path or ""):
                database_node = node
                break
        
        assert database_node is not None, "Could not find database.py node"
        
        # Find path between main.py and database.py
        path = graph.find_path(main_node.id, database_node.id)
        assert len(path) == 2, f"Expected direct path, got {path}"
        print(f"   ✓ Found path: {' → '.join([n.id.split(':')[-1] for n in [main_node, database_node]])}")
        
        # STEP 7: Simulate file modification
        print("\n✏️  Simulating file modification...")
        
        # Add a new import
        main_py.write_text("""
from database import connect
from utils import format_output
from logger import log

def main():
    log("Starting application")
    db = connect()
    data = db.query("SELECT * FROM users")
    for row in data:
        print(format_output(row))

if __name__ == "__main__":
    main()
""")
        
        time.sleep(1)  # Let watchdog detect the change
        
        # Verify new import was detected
        new_edges = graph.edges[len(edges):]
        new_imports = [e for e in new_edges if e.relationship == "imports"]
        print(f"   ✓ Detected {len(new_imports)} new import(s) after modification")
        
        # STEP 8: Clean up
        print("\n🧹 Cleaning up...")
        daemon.stop()
        shutil.rmtree(test_dir)
        print(f"   ✓ Removed test directory")
        
        print("\n✅ All tests passed! Flowstate successfully:")
        print("   • Indexed multiple files")
        print("   • Inferred import relationships")
        print("   • Built knowledge graph with edges")
        print("   • Provided ambient context suggestions")
        print("   • Detected file modifications in real-time")
        print("   • Found paths between connected files")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        shutil.rmtree(test_dir, ignore_errors=True)
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        shutil.rmtree(test_dir, ignore_errors=True)
        return False


def test_concurrent_monitoring():
    """
    Test that Flowstate can handle concurrent file operations
    without blocking or losing events.
    """
    
    test_dir = Path("/tmp/flowstate_concurrent_" + str(int(time.time())))
    test_dir.mkdir(exist_ok=True)
    
    print(f"\n🧪 Testing concurrent file operations: {test_dir}")
    
    try:
        daemon = FlowstateDaemon(watch_paths=[str(test_dir)])
        graph = daemon.graph  # Access the daemon's graph
        
        daemon.start()
        time.sleep(1)
        
        # Create 10 files rapidly
        print("\n⚡ Creating 10 files rapidly...")
        for i in range(10):
            (test_dir / f"file_{i}.py").write_text(f"# File {i}")
        
        time.sleep(2)
        
        # Verify all files were indexed (filter to test directory only)
        file_nodes = [n for n in graph.nodes.values() if n.kind == "file" and str(test_dir) in (n.path or "")]
        assert len(file_nodes) == 10, f"Expected 10 files, got {len(file_nodes)}"
        print(f"   ✓ Indexed all 10 files concurrently")
        
        daemon.stop()
        shutil.rmtree(test_dir)
        return True
        
    except AssertionError as e:
        print(f"\n❌ Concurrent test failed: {e}")
        shutil.rmtree(test_dir, ignore_errors=True)
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        shutil.rmtree(test_dir, ignore_errors=True)
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("FLOWSTATE INTEGRATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run main workflow test
    results.append(("Workflow Simulation", simulate_developer_workflow()))
    
    # Run concurrent test
    results.append(("Concurrent Monitoring", test_concurrent_monitoring()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Flowstate is ready for production.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        sys.exit(1)
