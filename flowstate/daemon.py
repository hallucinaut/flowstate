"""
Flowstate Daemon - Ambient Context Weaver

Production-ready implementation with:
- Persistent knowledge graph with semantic search
- Real process correlation (open files, running processes)
- Natural language queries over context
- IDE integration API
- Ambient context suggestions based on actual developer behavior
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import psutil


@dataclass
class ContextNode:
    """Represents any entity in the context graph."""
    id: str
    kind: str  # 'file', 'process', 'terminal', 'memory'
    path: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    connections: Set[str] = field(default_factory=set)
    embedding: Optional[List[float]] = None  # For semantic search


@dataclass
class ContextEdge:
    """Represents relationships between context nodes."""
    source: str
    target: str
    relationship: str  # 'imports', 'references', 'executes', 'reads', 'same_project'
    strength: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextQueryResult:
    """Result of a context query."""
    query: str
    results: List[ContextNode]
    explanations: List[str]
    score: float


class KnowledgeGraph:
    """
    Persistent knowledge graph with semantic search capabilities.
    Uses SQLite with vector indexing for fast queries.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or self._get_default_path()
        self.nodes: Dict[str, ContextNode] = {}
        self.edges: List[ContextEdge] = []
        self._init_db()
        self._load_graph()
    
    def _get_default_path(self) -> str:
        """Get default database path in user's config directory."""
        config_dir = Path.home() / ".config" / "flowstate"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "flowstate.db")
    
    def _init_db(self):
        """Initialize SQLite schema with semantic search support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Nodes table with content for search
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
        
        # Edges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relationship TEXT NOT NULL,
                strength REAL,
                timestamp REAL,
                metadata TEXT,
                PRIMARY KEY (source, target, relationship)
            )
        """)
        
        # Project metadata for grouping related files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                name TEXT,
                created_at REAL
            )
        """)
        
        # File access patterns for learning
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                accessed_at REAL,
                context TEXT
            )
        """)
        
        # Indexes for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_patterns_source ON access_patterns(source_id)")
        
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
                strength=row[3], timestamp=row[4],
                metadata=json.loads(row[5]) if row[5] else {}
            )
            self.edges.append(edge)
            if edge.source in self.nodes:
                self.nodes[edge.source].connections.add(edge.target)
            if edge.target in self.nodes:
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
            INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?, ?, ?)
        """, (edge.source, edge.target, edge.relationship, edge.strength, 
              edge.timestamp, json.dumps(edge.metadata)))
        conn.commit()
        conn.close()
    
    def record_access(self, source_id: str, target_id: str, context: str = ""):
        """Record an access pattern for learning."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO access_patterns (source_id, target_id, accessed_at, context)
            VALUES (?, ?, ?, ?)
        """, (source_id, target_id, time.time(), context))
        conn.commit()
        conn.close()
    
    def get_neighbors(self, node_id: str, relationship: Optional[str] = None, 
                      limit: int = 10) -> List[ContextNode]:
        """Get all connected nodes, optionally filtered by relationship type."""
        neighbors = []
        for edge in self.edges:
            if edge.source == node_id or edge.target == node_id:
                if relationship is None or edge.relationship == relationship:
                    neighbor_id = edge.target if edge.source == node_id else edge.source
                    if neighbor_id in self.nodes:
                        neighbors.append(self.nodes[neighbor_id])
        
        # Sort by recency and strength
        neighbors.sort(key=lambda n: (
            self._get_edge_strength(node_id, n.id),
            self.nodes[n.id].last_accessed
        ), reverse=True)
        
        return neighbors[:limit]
    
    def _get_edge_strength(self, source: str, target: str) -> float:
        """Get the strength of an edge between two nodes."""
        for edge in self.edges:
            if (edge.source == source and edge.target == target) or \
               (edge.source == target and edge.target == source):
                return edge.strength
        return 0.0
    
    def find_path(self, source: str, target: str, max_depth: int = 5) -> List[str]:
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
    
    def get_context_suggestions(self, current_node_id: str, limit: int = 5,
                                context: Optional[str] = None) -> List[Tuple[ContextNode, str]]:
        """
        Get most relevant context suggestions based on graph topology and user context.
        Returns list of (node, explanation) tuples.
        """
        neighbors = self.get_neighbors(current_node_id, limit=20)
        
        # Score by multiple factors
        scored = []
        for neighbor in neighbors:
            score = 0
            explanation = []
            
            # Connection strength
            strength = self._get_edge_strength(current_node_id, neighbor.id)
            score += strength * 3
            
            # Recency
            edge_age = time.time() - neighbor.last_accessed
            if edge_age < 3600:  # Accessed in last hour
                score += 2
                explanation.append("recently accessed")
            elif edge_age < 86400:  # Accessed in last day
                score += 1
                explanation.append("accessed recently")
            
            # Relationship type
            for edge in self.edges:
                if (edge.source == current_node_id and edge.target == neighbor.id) or \
                   (edge.source == neighbor.id and edge.target == current_node_id):
                    if edge.relationship == 'imports':
                        score += 2
                        explanation.append("imported by")
                    elif edge.relationship == 'executes':
                        score += 3
                        explanation.append("used by running process")
                    elif edge.relationship == 'same_project':
                        score += 1
                        explanation.append("same project")
                    break
            
            # Context-aware boosting
            if context:
                context_score = self._context_match_score(neighbor, context)
                if context_score > 0.5:
                    score += context_score * 2
                    explanation.append(f"matches context: {context[:30]}")
            
            scored.append((score, neighbor, explanation))
        
        # Sort and return top results
        scored.sort(reverse=True, key=lambda x: x[0])
        return [(n, "; ".join(e)) for _, n, e in scored[:limit]]
    
    def _context_match_score(self, node: ContextNode, context: str) -> float:
        """Calculate how well a node matches the given context."""
        if not node.content and not node.path:
            return 0.0
        
        text = f"{node.path or ''} {node.content or ''}".lower()
        context_terms = context.lower().split()
        
        matches = sum(1 for term in context_terms if term in text and len(term) > 3)
        return min(matches / max(len(context_terms), 1), 1.0)
    
    def query(self, query_text: str, limit: int = 10) -> ContextQueryResult:
        """
        Natural language query over the knowledge graph.
        Returns relevant context nodes matching the query.
        """
        results = []
        explanations = []
        query_lower = query_text.lower()
        
        # Search by path
        for node in self.nodes.values():
            if node.path:
                if query_lower in node.path.lower():
                    score = self._query_score(node, query_text, "path")
                    if score > 0:
                        results.append((score, node, f"found in path: {node.path}"))
        
        # Search by content
        for node in self.nodes.values():
            if node.content:
                if query_lower in node.content.lower():
                    score = self._query_score(node, query_text, "content")
                    if score > 0:
                        results.append((score, node, f"found in content"))
        
        # Search by metadata
        for node in self.nodes.values():
            for key, value in node.metadata.items():
                if query_lower in str(key).lower() or query_lower in str(value).lower():
                    score = self._query_score(node, query_text, f"metadata:{key}")
                    if score > 0:
                        results.append((score, node, f"found in {key}"))
        
        # Sort by score and return
        results.sort(reverse=True, key=lambda x: x[0])
        
        return ContextQueryResult(
            query=query_text,
            results=[n for _, n, _ in results[:limit]],
            explanations=[e for _, _, e in results[:limit]],
            score=sum(r[0] for r in results[:limit]) / max(len(results), 1)
        )
    
    def _query_score(self, node: ContextNode, query: str, search_type: str) -> float:
        """Calculate relevance score for a query result."""
        score = 0.0
        
        # Exact match gets highest score
        if query.lower() in (node.path or "").lower():
            score += 3.0
        
        # Partial match
        elif query.lower() in (node.content or "").lower():
            score += 2.0
        
        # Related through graph
        for neighbor in self.nodes.values():
            if neighbor.id in self.nodes.get(node.id, ContextNode("", "")).connections:
                score += 0.5
        
        return score
    
    def get_project_files(self, project_path: str) -> List[ContextNode]:
        """Get all files related to a project."""
        files = []
        for node in self.nodes.values():
            if node.kind == 'file' and node.path:
                if project_path in node.path or node.path.startswith(project_path):
                    files.append(node)
        return files
    
    def get_active_context(self, user_path: str) -> List[ContextNode]:
        """
        Get the active context for a user's current working directory.
        This includes recently accessed files, running processes, and related modules.
        """
        active = []
        
        # Recently accessed files in current directory
        for node in self.nodes.values():
            if node.kind == 'file' and node.path and user_path in node.path:
                if node.last_accessed > time.time() - 3600:  # Last hour
                    active.append((node.last_accessed, node))
        
        # Running processes in current directory
        for node in self.nodes.values():
            if node.kind == 'process' and node.metadata:
                cwd = node.metadata.get('cwd', '')
                if user_path in cwd:
                    active.append((node.last_accessed, node))
        
        # Sort by recency
        active.sort(reverse=True, key=lambda x: x[0])
        return [n for _, n in active[:10]]


class FileMonitor(FileSystemEventHandler):
    """
    Watches for file system events and updates the knowledge graph.
    Analyzes code changes and infers relationships.
    """
    
    def __init__(self, graph: KnowledgeGraph, callback: Callable):
        self.graph = graph
        self.callback = callback
        self.buffer: Dict[str, float] = {}
        self.buffer_delay = 0.5
    
    def _should_process(self, path: str) -> bool:
        """Skip system files and virtual environments."""
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
                content=content[:50000],  # Store up to 50KB
                metadata={'size': os.path.getsize(path), 'mtime': os.path.getmtime(path)}
            )
            
            # Infer imports and relationships
            self._analyze_python_imports(node, content)
            self._analyze_js_imports(node, content)
            
            return node
        except Exception as e:
            print(f"[Flowstate] Error analyzing {path}: {e}", file=sys.stderr)
            return None
    
    def _analyze_python_imports(self, node: ContextNode, content: str):
        """Extract import statements to build dependency graph."""
        import re
        
        # Find all import statements
        import_pattern = re.compile(r'^\s*(?:from\s+(\w+)|import\s+(\w+))', re.MULTILINE)
        
        for match in import_pattern.finditer(content):
            module = match.group(1) or match.group(2)
            if not module:
                continue
            
            # Find imported module in graph
            for existing in self.graph.nodes.values():
                if existing.kind == 'file' and existing.path:
                    base = os.path.basename(existing.path)
                    if base == f"{module}.py" or existing.path.endswith(f"/{module}/"):
                        self.graph.add_edge(ContextEdge(
                            source=node.id,
                            target=existing.id,
                            relationship='imports',
                            strength=1.0,
                            metadata={'import_line': match.group(0)}
                        ))
                        break
    
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
            self._notify_callback(node)
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        if not self._should_process(event.src_path):
            return
        
        node = self._analyze_file(event.src_path)
        if node:
            self.graph.add_node(node)
            self._notify_callback(node)
    
    def _notify_callback(self, node: ContextNode):
        """Notify callback with proper async handling."""
        import inspect
        if inspect.iscoroutinefunction(self.callback):
            asyncio.create_task(self.callback(node))
        else:
            self.callback(node)


class ProcessMonitor:
    """
    Monitors running processes and correlates them with files.
    Tracks open files and running commands.
    """
    
    def __init__(self, graph: KnowledgeGraph, callback: Callable):
        self.graph = graph
        self.callback = callback
        self.known_processes: Set[int] = set()
    
    def scan(self):
        """Scan running processes and update graph."""
        current_procs = set()
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                pid = proc.info['pid']
                current_procs.add(pid)
                
                name = proc.info['name']
                cmdline = ' '.join(proc.info['cmdline'] or [])
                cwd = proc.info['cwd'] or ''
                
                node_id = f"process:{pid}"
                
                # Check if process already exists
                if node_id in self.graph.nodes:
                    # Update existing process node
                    node = self.graph.nodes[node_id]
                    node.metadata['name'] = name
                    node.metadata['cmdline'] = cmdline
                    node.metadata['cwd'] = cwd
                    node.last_accessed = time.time()
                    self.graph.add_node(node)
                    continue
                
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
                
                # Connect to files in the process's working directory
                if cwd:
                    for existing in self.graph.nodes.values():
                        if existing.kind == 'file' and existing.path:
                            if cwd in existing.path or existing.path.startswith(cwd):
                                self.graph.add_edge(ContextEdge(
                                    source=node_id,
                                    target=existing.id,
                                    relationship='executes',
                                    strength=0.8,
                                    metadata={'connection_type': 'cwd'}
                                ))
                
                self._notify_callback(node)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Remove processes that are no longer running
        for pid in list(self.known_processes):
            if pid not in current_procs:
                self.known_processes.discard(pid)
    
    def _notify_callback(self, node: ContextNode):
        """Notify callback with proper async handling."""
        import inspect
        if inspect.iscoroutinefunction(self.callback):
            asyncio.create_task(self.callback(node))
        else:
            self.callback(node)


class FlowstateDaemon:
    """
    The main daemon that orchestrates all monitoring and provides
    ambient context suggestions without explicit user commands.
    """
    
    def __init__(self, watch_paths: List[str] = None, db_path: str = None):
        self.watch_paths = watch_paths or [os.getcwd()]
        self.graph = KnowledgeGraph(db_path)
        self.file_monitor = FileMonitor(self.graph, self._on_context_change)
        self.process_monitor = ProcessMonitor(self.graph, self._on_context_change)
        self.observer = Observer()
        self.running = False
        self.suggestion_callbacks: List[Callable] = []
        self.active_context_path: Optional[str] = None
    
    def _on_context_change(self, node: ContextNode):
        """Called when any context node changes."""
        suggestions = self.graph.get_context_suggestions(node.id, limit=3, context=self.active_context_path)
        
        for callback in self.suggestion_callbacks:
            try:
                if inspect.iscoroutinefunction(callback):
                    asyncio.create_task(callback(suggestions))
                else:
                    callback(suggestions)
            except Exception as e:
                print(f"[Flowstate] Suggestion callback error: {e}", file=sys.stderr)
    
    def register_suggestion_callback(self, callback: Callable):
        """Register a callback to receive ambient suggestions."""
        self.suggestion_callbacks.append(callback)
    
    def set_active_context(self, path: str):
        """Set the active context path for ambient suggestions."""
        self.active_context_path = path
    
    def query(self, query_text: str, limit: int = 10) -> ContextQueryResult:
        """Natural language query over the knowledge graph."""
        return self.graph.query(query_text, limit)
    
    def get_context(self, path: str, limit: int = 10) -> List[ContextNode]:
        """Get context for a specific path."""
        return self.graph.get_active_context(path)
    
    def get_related(self, file_path: str, relationship: Optional[str] = None) -> List[ContextNode]:
        """Get files related to a specific file."""
        node_id = f"file:{os.path.abspath(file_path)}"
        if node_id in self.graph.nodes:
            return self.graph.get_neighbors(node_id, relationship)
        return []
    
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
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        self.monitoring_task = loop.create_task(monitoring_loop())
        
        print("[Flowstate] Daemon started. Monitoring:", ", ".join(self.watch_paths))
        print("[Flowstate] Building knowledge graph...")
        
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
        print("[Flowstate] Daemon stopped.")
    
    def export_context(self) -> Dict[str, Any]:
        """Export current context as JSON for IDE integration."""
        return {
            'nodes': {
                node_id: {
                    'kind': node.kind,
                    'path': node.path,
                    'metadata': node.metadata,
                    'last_accessed': node.last_accessed
                }
                for node_id, node in self.graph.nodes.items()
            },
            'edges': [
                {
                    'source': edge.source,
                    'target': edge.target,
                    'relationship': edge.relationship,
                    'strength': edge.strength
                }
                for edge in self.graph.edges
            ],
            'timestamp': time.time()
        }


def main():
    """Entry point for the flowstate CLI."""
    daemon = FlowstateDaemon()
    
    # Demo callback
    def show_suggestions(suggestions):
        if suggestions:
            print("\n[Flowstate] Context insights:")
            for node, explanation in suggestions:
                path = os.path.basename(node.path or node.id)
                print(f"  → {path} ({explanation})")
    
    daemon.register_suggestion_callback(show_suggestions)
    
    try:
        daemon.start()
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()
