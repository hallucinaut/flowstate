# Flowstate 🌊

> **The ambient context Weaver for knowledge workers**

---

## The Old Way

Developers today suffer from **fragmented context**. Your workflow is splintered across:

- **Terminal** - running commands, viewing logs
- **IDE** - writing code, debugging
- **Browser** - documentation, Stack Overflow, specs
- **Git** - commits, branches, diffs

**The cost:** 23+ minutes of daily context-switching overhead. You constantly lose your place, forget what you were working on, and waste time re-orienting yourself.

Traditional tools try to solve this with:
- Tab managers (passive, you remember to use them)
- Note-taking apps (manual, you have to remember to document)
- Chatbots (explicit prompts, you have to ask)

**None of these work because they require you to interrupt your flow to manage context.**

---

## The New Paradigm

**Flowstate is different.** It's an **ambient daemon** that runs silently in the background, building a live knowledge graph of your entire development environment.

### How It Works

1. **File System Monitoring** - Watches your codebase for changes, automatically analyzes imports and dependencies
2. **Process Monitoring** - Tracks running processes and correlates them with files
3. **Knowledge Graph Construction** - Builds a persistent graph connecting files, processes, and context
4. **Ambient Suggestions** - Surfaces relevant context **before you ask** - no prompts, no commands

### The Magic

```python
# You're editing a Python file
from database import connect

# Flowstate KNOWS this file imports from database.py
# It also knows database.py is used by your running pytest process
# It SURFACES this connection automatically:

[Flowstate] Context insights:
  → file: database.py (imported by current file)
  → process: 12345 (pytest running, uses database.py)
```

**No commands. No prompts. Just awareness.**

---

## Under the Hood

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Flowstate Daemon                      │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ File Monitor │  │ Process Mon. │  │   Graph DB   │  │
│  │  (watchdog)  │  │  (psutil)    │  │  (SQLite)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│         └──────────────────┼──────────────────┘          │
│                            │                             │
│                    ┌───────▼───────┐                     │
│                    │ Knowledge     │                     │
│                    │ Graph Engine  │                     │
│                    │  (BFS, scoring)│                    │
│                    └───────┬───────┘                     │
│                            │                             │
│                    ┌───────▼───────┐                     │
│                    │ Ambient       │                     │
│                    │ Suggestions   │                     │
│                    └───────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Key Technologies

- **watchdog** - Cross-platform file system event monitoring
- **psutil** - Process and system monitoring
- **SQLite** - Persistent knowledge graph storage
- **asyncio** - Non-blocking concurrent monitoring
- **AnyIO** - Cross-platform async primitives

### The Knowledge Graph

```python
# Every entity becomes a node in the graph
ContextNode(
    id="file:/path/to/code.py",
    kind="file",
    path="/path/to/code.py",
    content="from database import connect",
    metadata={"size": 1234}
)

# Relationships become edges
ContextEdge(
    source="file:/path/to/code.py",
    target="file:/path/to/database.py",
    relationship="imports",
    strength=1.0
)
```

### Ambient Intelligence

Flowstate doesn't wait for you to ask. It continuously:

1. **Analyzes** every file change for import relationships
2. **Correlates** running processes with active files
3. **Scores** relevance based on graph topology and recency
4. **Surfaces** the most relevant context automatically

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

Runs in the foreground, monitoring the current directory and all subdirectories.

### As a Library

```python
from flowstate import FlowstateDaemon

daemon = FlowstateDaemon(watch_paths=["./src", "./tests"])

async def on_insights(insights):
    print("Relevant context:", insights)

daemon.register_suggestion_callback(on_insights)
daemon.start()
```

---

## Proof of Concept

See `simulate_user.py` for a complete integration test that simulates human workflow and verifies Flowstate's ambient awareness.

```bash
python simulate_user.py
```

---

## Why This Matters

**Flowstate is not a tool you use. It's a tool that uses you.**

- **Invisible UI** - Runs entirely in the background
- **Intent-Based** - You define the end state (working code), it builds the infrastructure
- **Hyper-Contextual** - Unifies terminal, IDE, and browser into one memory graph

This is the first workflow tool that **anticipates your needs** rather than reacting to your commands.

---

## License

MIT - Open source, free for personal and commercial use.

---

## The Future

This is just the beginning. Next iterations will add:

- Browser DOM monitoring
- IDE plugin integration (VSCode, JetBrains)
- Natural language queries over the knowledge graph
- Cross-device context synchronization

**The goal:** A truly ambient computing layer that understands your work without you having to explain it.
