"""
Synapse Daemon - Ambient Context Weaver

The revolutionary core: A background daemon that continuously monitors
your development environment and builds a live knowledge graph, surfacing
contextual insights without explicit commands.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
import psutil


@dataclass
class ContextNode:
    """Represents any entity in the context graph: file, process, terminal output."""
    id: str
    kind: str  # 'file', 'process', 'terminal', 'browser', 'memory'
    path: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    connections: Set[str] = field(default_factory=set)


@dataclass
class ContextEdge:
    """Represents relationships between context nodes."""
    source: str
    target: str
    relationship: str  # 'imports', 'references', 'executes', 'reads'
    strength: float = 1.0
    timestamp: float = field(default_factory=time.time)


class KnowledgeGraph:
    """
    Persistent knowledge graph stored in SQLite with in-memory indexing
    for O(1) node lookups and relationship queries.
    """
    
    def __init__(self, db_path: str = "synapse_graph.db"):
        self.db_path = db_path
        self.nodes: Dict[str, ContextNode] = {}
        self.edges: List[ContextEdge] = []
        self._init_db()
        self._load_graph()
    
    def _init_db(self):
        """Initialize SQLite schema for persistent storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                path TEXT,
                content TEXT,
                metadata TEXT,
                created_at REAL,
                last_accessed REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relationship TEXT NOT NULL,
                strength REAL,
                timestamp REAL,
                PRIMARY KEY (source, target, relationship)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)
        """)
        
        conn.commit()
        conn.close()
    
    def _load_graph(self):
        """Load graph from persistent storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM nodes")
        for row in cursor.fetchall():
            node = ContextNode(
                id=row[0], kind=row[1], path=row[2], content=row[3],
                metadata=json.loads(row[4]) if row[4] else {},
                created_at=row[5], last_accessed=row[6]
            )
            self.nodes[node.id] = node
        
        cursor.execute("SELECT * FROM edges")
        for row in cursor.fetchall():
            edge = ContextEdge(
                source=row[0], target=row[1], relationship=row[2],
                strength=row[3], timestamp=row[4]
            )
            self.edges.append(edge)
            self.nodes[edge.source].connections.add(edge.target)
            self.nodes[edge.target].connections.add(edge.source)
        
        conn.close()
    
    def add_node(self, node: ContextNode):
        """Add or update a node in the graph."""
        self.nodes[node.id] = node
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (node.id, node.kind, node.path, node.content,
              json.dumps(node.metadata), node.created_at, node.last_accessed))
        conn.commit()
        conn.close()
    
    def add_edge(self, edge: ContextEdge):
        """Add a relationship edge between nodes."""
        self.edges.append(edge)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?, ?)
        """, (edge.source, edge.target, edge.relationship, edge.strength, edge.timestamp))
        conn.commit()
        conn.close()
    
    def get_neighbors(self, node_id: str, relationship: Optional[str] = None) -> List[ContextNode]:
        """Get all connected nodes, optionally filtered by relationship type."""
        neighbors = []
        for edge in self.edges:
            if edge.source == node_id or edge.target == node_id:
                if relationship is None or edge.relationship == relationship:
                    neighbor_id = edge.target if edge.source == node_id else edge.source
                    if neighbor_id in self.nodes:
                        neighbors.append(self.nodes[neighbor_id])
        return neighbors
    
    def find_path(self, source: str, target: str, max_depth: int = 3) -> List[str]:
        """Find shortest path between two nodes using BFS."""
        if source == target:
            return [source]
        
        visited = {source}
        queue = [(source, [source])]
        
        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue
            
            for neighbor in self.get_neighbors(current):
                if neighbor.id == target:
                    return path + [neighbor.id]
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append((neighbor.id, path + [neighbor.id]))
        
        return []
    
    def get_context_suggestions(self, current_node_id: str, limit: int = 5) -> List[ContextNode]:
        """Get most relevant context suggestions based on graph topology."""
        neighbors = self.get_neighbors(current_node_id)
        
        # Score by connection strength and recency
        scored = []
        for neighbor in neighbors:
            score = 0
            for edge in self.edges:
                if edge.source == current_node_id and edge.target == neighbor.id:
                    score += edge.strength * (1 + (time.time() - edge.timestamp) / 3600)
            scored.append((score, neighbor))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [n for _, n in scored[:limit]]


class FileMonitor(FileSystemEventHandler):
    """
    Watches for file system events and updates the knowledge graph.
    Automatically analyzes code changes and infers relationships.
    """
    
    def __init__(self, graph: KnowledgeGraph, callback: Callable):
        self.graph = graph
        self.callback = callback
        self.buffer: Dict[str, float] = {}
        self.buffer_delay = 0.5  # Debounce events
    
    def _should_process(self, path: str) -> bool:
        """Skip system files, virtual environments, etc."""
        skip_patterns = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.tox'}
        path_lower = path.lower()
        return not any(pattern in path_lower for pattern in skip_patterns)
    
    def _analyze_file(self, path: str) -> Optional[ContextNode]:
        """Analyze file content and infer relationships."""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            node_id = f"file:{os.path.abspath(path)}"
            node = ContextNode(
                id=node_id,
                kind='file',
                path=path,
                content=content[:10000],  # Store first 10KB for analysis
                metadata={'size': os.path.getsize(path)}
            )
            
            # Infer imports and relationships
            if path.endswith('.py'):
                self._analyze_python_imports(node, content)
            elif path.endswith('.js') or path.endswith('.ts'):
                self._analyze_js_imports(node, content)
            
            return node
        except Exception as e:
            print(f"[Synapse] Error analyzing {path}: {e}", file=sys.stderr)
            return None
    
    def _analyze_python_imports(self, node: ContextNode, content: str):
        """Extract import statements to build dependency graph."""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                try:
                    # Parse import (simplified)
                    if line.startswith('from '):
                        module = line.split(' ')[1].split(' ')[0].split('.')[0]
                    else:
                        module = line.split(' ')[1].split('.')[0]
                    
                    # Find imported module
                    for existing in self.graph.nodes.values():
                        if existing.kind == 'file' and existing.path:
                            base = os.path.basename(existing.path)
                            if base == f"{module}.py" or existing.path.endswith(f"/{module}/"):
                                self.graph.add_edge(ContextEdge(
                                    source=node.id,
                                    target=existing.id,
                                    relationship='imports',
                                    strength=1.0
                                ))
                                break
                except:
                    pass
    
    def _analyze_js_imports(self, node: ContextNode, content: str):
        """Extract import/require statements for JS/TS files."""
        import re
        patterns = [
            r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                for existing in self.graph.nodes.values():
                    if existing.kind == 'file' and existing.path:
                        if match in existing.path or existing.path.endswith(match):
                            self.graph.add_edge(ContextEdge(
                                source=node.id,
                                target=existing.id,
                                relationship='imports',
                                strength=1.0
                            ))
                            break
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        if not self._should_process(event.src_path):
            return
        
        # Debounce rapid changes
        now = time.time()
        if event.src_path in self.buffer:
            if now - self.buffer[event.src_path] < self.buffer_delay:
                return
        self.buffer[event.src_path] = now
        
        node = self._analyze_file(event.src_path)
        if node:
            node.last_accessed = now
            self.graph.add_node(node)
            asyncio.create_task(self.callback(node))
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        if not self._should_process(event.src_path):
            return
        
        node = self._analyze_file(event.src_path)
        if node:
            self.graph.add_node(node)
            asyncio.create_task(self.callback(node))


class ProcessMonitor:
    """
    Monitors running processes and correlates them with files.
    Creates process nodes in the knowledge graph.
    """
    
    def __init__(self, graph: KnowledgeGraph, callback: Callable):
        self.graph = graph
        self.callback = callback
        self.known_processes: Set[int] = set()
    
    def scan(self):
        """Scan running processes and update graph."""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                pid = proc.info['pid']
                name = proc.info['name']
                cmdline = ' '.join(proc.info['cmdline'] or [])
                cwd = proc.info['cwd'] or ''
                
                if pid in self.known_processes:
                    continue
                
                self.known_processes.add(pid)
                
                node_id = f"process:{pid}"
                node = ContextNode(
                    id=node_id,
                    kind='process',
                    path=cmdline,
                    metadata={
                        'name': name,
                        'cwd': cwd,
                        'cmdline': cmdline
                    }
                )
                self.graph.add_node(node)
                
                # Connect to current working directory
                if cwd:
                    for existing in self.graph.nodes.values():
                        if existing.kind == 'file' and existing.path and cwd in existing.path:
                            self.graph.add_edge(ContextEdge(
                                source=node_id,
                                target=existing.id,
                                relationship='executes',
                                strength=0.8
                            ))
                            break
                
                asyncio.create_task(self.callback(node))
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass


class SynapseDaemon:
    """
    The main daemon that orchestrates all monitoring and provides
    ambient context suggestions without explicit user commands.
    """
    
    def __init__(self, watch_paths: List[str] = None):
        self.watch_paths = watch_paths or [os.getcwd()]
        self.graph = KnowledgeGraph()
        self.file_monitor = FileMonitor(self.graph, self._on_context_change)
        self.process_monitor = ProcessMonitor(self.graph, self._on_context_change)
        self.observer = Observer()
        self.running = False
        self.suggestion_callbacks: List[Callable] = []
    
    def _on_context_change(self, node: ContextNode):
        """Called when any context node changes."""
        # Generate ambient suggestions
        suggestions = self.graph.get_context_suggestions(node.id, limit=3)
        
        for callback in self.suggestion_callbacks:
            try:
                asyncio.create_task(callback(suggestions))
            except Exception as e:
                print(f"[Synapse] Suggestion callback error: {e}", file=sys.stderr)
    
    def register_suggestion_callback(self, callback: Callable):
        """Register a callback to receive ambient suggestions."""
        self.suggestion_callbacks.append(callback)
    
    def get_suggestions(self, context_id: str) -> List[ContextNode]:
        """Get suggestions for a specific context node."""
        return self.graph.get_context_suggestions(context_id)
    
    def find_context_path(self, source: str, target: str) -> List[str]:
        """Find how two context nodes are connected."""
        return self.graph.find_path(source, target)
    
    def start(self):
        """Start the daemon and begin monitoring."""
        self.running = True
        
        # Start file monitoring
        for path in self.watch_paths:
            if os.path.exists(path):
                self.observer.schedule(self.file_monitor, path, recursive=True)
        
        self.observer.start()
        
        # Start process monitoring loop
        async def monitoring_loop():
            while self.running:
                self.process_monitor.scan()
                await asyncio.sleep(2)
        
        self.monitoring_task = asyncio.create_task(monitoring_loop())
        
        print("[Synapse] Daemon started. Monitoring:", ", ".join(self.watch_paths))
        print("[Synapse] Building initial knowledge graph...")
        
        # Index current files
        self._index_current_files()
    
    def _index_current_files(self):
        """Index all files in watch paths on startup."""
        for path in self.watch_paths:
            if os.path.exists(path):
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        node = self.file_monitor._analyze_file(file_path)
                        if node:
                            self.graph.add_node(node)
    
    def stop(self):
        """Stop the daemon."""
        self.running = False
        self.observer.stop()
        self.observer.join()
        if hasattr(self, 'monitoring_task'):
            self.monitoring_task.cancel()
        print("[Synapse] Daemon stopped.")
    
    def query(self, query_text: str) -> List[ContextNode]:
        """
        Natural language query over the knowledge graph.
        Returns relevant context nodes matching the query.
        """
        results = []
        query_lower = query_text.lower()
        
        for node in self.graph.nodes.values():
            score = 0
            
            # Search in path
            if node.path and query_lower in node.path.lower():
                score += 2
            
            # Search in content
            if node.content and query_lower in node.content.lower():
                score += 1
            
            # Search in metadata
            for key, value in node.metadata.items():
                if query_lower in str(key).lower() or query_lower in str(value).lower():
                    score += 1
            
            if score > 0:
                results.append((score, node))
        
        results.sort(reverse=True, key=lambda x: x[0])
        return [n for _, n in results[:10]]


def main():
    """Entry point for the synapse CLI."""
    daemon = SynapseDaemon()
    
    # Demo callback
    async def show_suggestions(suggestions):
        if suggestions:
            print("\n[Synapse] Context insights:")
            for s in suggestions:
                print(f"  → {s.kind}: {s.path or s.id}")
    
    daemon.register_suggestion_callback(show_suggestions)
    
    try:
        daemon.start()
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()
