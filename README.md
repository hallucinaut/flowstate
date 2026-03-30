# Flowstate 🌊

> **Ambient context monitoring for developers**

---

## What This Is

Flowstate is a **background daemon** that monitors your development environment and builds a knowledge graph of your codebase. It tracks:

- **File changes** - Watches for code modifications and analyzes imports
- **Running processes** - Correlates processes with their working directories
- **Access patterns** - Learns which files you work with together

---

## What This Is NOT

- ❌ **Not an IDE plugin** - No VSCode or JetBrains integration
- ❌ **Not a browser monitor** - Doesn't track your web activity
- ❌ **Not AI-powered** - No machine learning, just graph queries
- ❌ **Not magic** - You still need to understand your code

---

## Installation

```bash
pip install flowstate
```

### Development Setup

```bash
git clone https://github.com/hallucinaut/flowstate
cd flowstate
pip install -e ".[dev]"
```

---

## Usage

### As a Daemon

```bash
flowstate
```

Monitors the current directory and prints context insights when files change.

### As a Library

```python
from flowstate import FlowstateDaemon, KnowledgeGraph

# Create a knowledge graph (persists to ~/.config/flowstate/flowstate.db)
graph = KnowledgeGraph()

# Query the graph
result = graph.query("database connection")
for node in result.results:
    print(f"{node.path}: {node.content[:100]}")

# Get related files
related = graph.get_neighbors("file:/path/to/main.py")
for file in related:
    print(f"Related: {file.path}")
```

---

## API Reference

### KnowledgeGraph

```python
from flowstate import KnowledgeGraph

graph = KnowledgeGraph()

# Add a node
from flowstate import ContextNode
node = ContextNode(
    id="file:/path/to/code.py",
    kind="file",
    path="/path/to/code.py",
    content="print('hello')"
)
graph.add_node(node)

# Add an edge
from flowstate import ContextEdge
edge = ContextEdge(
    source="file:/path/to/a.py",
    target="file:/path/to/b.py",
    relationship="imports",
    strength=1.0
)
graph.add_edge(edge)

# Query the graph
result = graph.query("database")
print(result.results)  # List of ContextNode
print(result.explanations)  # List of why each matched

# Get neighbors
neighbors = graph.get_neighbors("file:/path/to/main.py")

# Find path between nodes
path = graph.find_path("file:/path/to/a.py", "file:/path/to/b.py")
```

### FlowstateDaemon

```python
from flowstate import FlowstateDaemon

daemon = FlowstateDaemon(watch_paths=["./src", "./tests"])

def on_insights(suggestions):
    """Callback for ambient suggestions."""
    for node, explanation in suggestions:
        print(f"{node.path}: {explanation}")

daemon.register_suggestion_callback(on_insights)
daemon.start()

# Query while running
result = daemon.query("user authentication")
print(result.results)

# Get context for a path
context = daemon.get_context("/path/to/project")
print(context)

# Stop the daemon
daemon.stop()
```

---

## How It Works

### Knowledge Graph

The core is a SQLite database with two main tables:

1. **nodes** - Files, processes, and other entities
2. **edges** - Relationships between nodes (imports, executes, etc.)

### File Monitoring

Uses `watchdog` to detect file changes:
- On creation/modification, reads file content
- Parses import statements (Python and JavaScript)
- Creates edges between files

### Process Monitoring

Uses `psutil` to scan running processes:
- Tracks PID, name, command line, working directory
- Creates edges between processes and files in their cwd

### Query System

Natural language queries work by:
1. Searching file paths for matching terms
2. Searching file content for matching terms
3. Searching metadata fields
4. Boosting results based on graph connectivity

---

## Limitations

### What Works Well

- ✅ File import tracking (Python, JavaScript)
- ✅ Process correlation with working directories
- ✅ Fast graph traversal and path finding
- ✅ Persistent storage between sessions
- ✅ Basic natural language queries

### What Doesn't Work

- ❌ **No real "ambient suggestions"** - The daemon monitors files but doesn't proactively push insights
- ❌ **No browser integration** - Doesn't track your web activity
- ❌ **No IDE plugin** - No VSCode, JetBrains, or other editor integration
- ❌ **No semantic understanding** - Queries are text-based, not AI-powered
- ❌ **No actual context awareness** - Doesn't know what you're "thinking about"

---

## Proof of Concept

Run the integration test:

```bash
python simulate_user.py
```

This simulates a developer workflow and verifies:
- Files are indexed correctly
- Import relationships are inferred
- Queries return relevant results
- The graph persists between sessions

---

## License

MIT - Open source, free for personal and commercial use.

---

## Future Possibilities

If you want to extend this:

1. **Add IDE integration** - Create a VSCode extension that uses the daemon API
2. **Add semantic search** - Integrate with an embedding model for better queries
3. **Add more file types** - Support Go, Rust, TypeScript, etc.
4. **Add user feedback** - Learn which suggestions are useful
5. **Add project detection** - Auto-detect project boundaries

---

## Honesty Check

This tool is **functional but limited**. It does what it says:

- It monitors files ✅
- It builds a graph ✅
- It can query the graph ✅

But it's **not** the "ambient intelligence" the original README claimed. The suggestions are just connected files, not actual insights. The process correlation is basic (just working directory matching).

If you want a true ambient context tool, you'd need:
- IDE plugin (to know what you're editing)
- Browser integration (to know what docs you're reading)
- AI/ML (to understand your intent)
- Real-time analysis (not just file watching)

This is a **foundation** for such a tool, not the finished product.
