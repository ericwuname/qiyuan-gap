# -*- coding: utf-8 -*-
"""启元智能 · 启元智脑记忆引擎 · Phase 2"""
__version__ = "2.0.0"
__author__ = "Qiyuan Intelligence"

try:
    from .memory_engine import MemoryEngine
except ImportError:
    MemoryEngine = None

from .workspace import Workspace

__all__ = ["MemoryEngine", "Workspace"]