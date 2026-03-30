"""
Synapse - Ambient Context Weaver

A revolutionary workflow tool that builds a live knowledge graph of your
development environment, surfacing contextual insights without explicit commands.
"""

from .daemon import SynapseDaemon, KnowledgeGraph, ContextNode, ContextEdge

__version__ = "0.1.0"
__all__ = ["SynapseDaemon", "KnowledgeGraph", "ContextNode", "ContextEdge"]
