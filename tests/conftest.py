"""Configuración compartida de la suite.

Los tests offline no escriben en `agent_runs`: sin esto, cada `LibraryAgent` construido sin
recorder usaría el backend por defecto (`pg`) e intentaría conectarse a una base que no existe en una
máquina limpia (Art. 6). Los tests de integración pasan su recorder explícito.
"""
from __future__ import annotations

import os

os.environ.setdefault("AGENT_RUNS_BACKEND", "memory")
