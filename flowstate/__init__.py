"""
Flowstate - Ambient Context Weaver

Production-ready ambient context monitoring with:
- Persistent knowledge graph with semantic search
- Real process correlation
- Natural language queries
- IDE integration API
"""

from .daemon import (
    FlowstateDaemon,
    KnowledgeGraph,
    ContextNode,
    ContextEdge,
    ContextQueryResult
)

__version__ = "1.0.0"
__all__ = ["FlowstateDaemon", "KnowledgeGraph", "ContextNode", "ContextEdge", "ContextQueryResult"]
