"""Chequeos estáticos del Dockerfile (T9.2): lo que se puede afirmar sin construir la imagen.

La construcción real necesita el daemon de Docker y se verifica aparte (`docker build`). Acá se
atrapan los errores que rompen un build en limpio: rutas copiadas que no existen en el repo, secretos
horneados en la imagen, el contenedor corriendo como root y un contexto que arrastra el `.env`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "docker" / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


def _instructions() -> list[str]:
    """Instrucciones del Dockerfile con las continuaciones de línea unidas y sin comentarios."""
    joined = re.sub(r"\\\s*\n", " ", DOCKERFILE.read_text(encoding="utf-8"))
    return [ln.strip() for ln in joined.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def test_every_copied_source_exists_in_the_repo() -> None:
    # Un `ui/` vacío no existe en un clon limpio (git no versiona directorios vacíos): COPY fallaría.
    missing = []
    for line in _instructions():
        if not line.upper().startswith("COPY "):
            continue
        parts = [p for p in line.split()[1:] if not p.startswith("--")]
        for source in parts[:-1]:
            if not (ROOT / source).exists():
                missing.append(source)
    assert not missing, f"COPY de rutas que no existen en el repo: {missing}"


def test_the_image_does_not_bake_secrets() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(ENV|ARG)\s+\w*(KEY|PASSWORD|SECRET|TOKEN)\w*\s*=?\s*\S+", text, re.M)
    assert not re.search(r"AIza[0-9A-Za-z_-]{20,}", text)


def test_the_container_does_not_run_as_root() -> None:
    users = [ln.split(maxsplit=1)[1] for ln in _instructions() if ln.upper().startswith("USER ")]
    assert users and users[-1].strip() not in {"root", "0"}


def test_dependencies_come_from_the_pinned_runtime_file() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "requirements.txt" in text
    assert "requirements-dev.txt" not in text, "pytest/faker no van a la imagen de producción (Art. 8)"


def test_the_build_context_excludes_the_env_file_and_the_git_history() -> None:
    patterns = {ln.strip() for ln in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()}
    assert {".env", ".git", ".venv"} <= patterns


def test_the_production_stage_does_not_ship_the_tests() -> None:
    # `measure` lleva tests/ porque `measure_golden.py` importa los dobles y el golden set; `runtime`, no.
    stages = re.split(r"(?im)^FROM\s+", DOCKERFILE.read_text(encoding="utf-8"))[1:]
    runtime = next(s for s in stages if re.search(r"\bAS\s+runtime\b", s.splitlines()[0], re.I))
    assert not re.search(r"^COPY\s+.*\btests/?\b", runtime, re.M)
