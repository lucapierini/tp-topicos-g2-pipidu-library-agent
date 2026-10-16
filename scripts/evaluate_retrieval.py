"""Evalúa búsqueda híbrida y re-ranking contra el set de calibración, sin tocar el RAG de producción (R-4.10, D98).

El umbral de similitud de coseno deja pasar consultas del dominio que no tienen respuesta («¿me puedo conectar al
wifi de la biblioteca con mi legajo?» puntúa 0.70 contra el reglamento). El puntaje es el problema, no el valor
del corte, así que acá se comparan puntajes alternativos con las mismas 126 consultas y las mismas métricas
(AUC, F1, recall y falsos positivos) que `scripts/calibrate_threshold.py`:

- **denso** (el actual): similitud de coseno del mejor fragmento.
- **léxico**: cobertura de la consulta por palabras exactas. Es la fracción del peso (IDF) de los términos de la
  consulta que aparece en el fragmento; un término que no existe en ningún documento («wifi») pesa lo máximo y
  baja la cobertura. No necesita modelo ni red.
- **híbrido**: combinación lineal de ambos, `alpha * denso_normalizado + (1 - alpha) * léxico`, sobre todos los
  fragmentos (no solo el top-5 denso).
- **re-ranking**: un modelo puntúa de 0 a 3 si cada uno de los 5 fragmentos candidatos *contiene la respuesta* a la
  pregunta (no si habla del mismo tema). Cuesta una llamada al modelo por consulta.
- **híbrido + re-ranking** y **re-ranking + denso** (el re-ranking desempata con la similitud).

Uso (requiere la base con los documentos indexados y GEMINI_API_KEY; el re-ranking cuesta ~250 llamadas, que se
guardan en `--cache` para no repetirlas):

    python scripts/evaluate_retrieval.py [--out TP/evidencia/busqueda_hibrida_rerank.json] [--no-rerank]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.calibrate_threshold import auc, build_cases, pick_thresholds, sweep  # noqa: E402

def build_validation_cases():
    """Las consultas del set de validación, con el mismo formato que `build_cases()`."""
    from scripts.calibrate_threshold import Case
    from tests.validation_set import VALIDATION_SET

    return [Case(c.id, c.question, c.covered, c.group, c.document) for c in VALIDATION_SET]


TOP_K = 5
ALPHAS = (0.5, 0.6, 0.7, 0.8, 0.9)
DENSE_LOW, DENSE_HIGH = 0.50, 0.85   # rango observado de la similitud de coseno: se lleva a [0, 1]
RERANK_MAX = 3                       # escala del re-ranking: 0 = no se relaciona … 3 = contesta directo
PREFIX = 6                           # raíz tosca: "préstamo" y "préstamos" comparten "presta"

_STOPWORDS = frozenset("""
a al algo ante con contra cual cuales cuando cuanto cuantos cuanta cuantas como de del desde donde el ella ellas
ellos en entre es esta estan este esto estos fue ha han hay la las le les lo los me mi mis mas mucho muy ni no
nos o os otra otro para pero por porque que quien quienes se si sin sobre su sus te tiene tienen tu tus un una uno
unas unos y ya yo puedo puede pueden puedes soy son ser sido hace hacer hago
a an and are as at be been but by can do does for from has have how i if in is it its me my of on or our so than
that the their them there these they this to was we were what when where which who whom why will with you your
""".split())


# --------------------------------------------------------------------------- léxico (puro)


def tokenize(text: str) -> list[str]:
    """Minúsculas, sin acentos, sin palabras vacías y con raíz tosca (primeros `PREFIX` caracteres)."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9$]+", folded)
    return [w[:PREFIX] for w in words if w not in _STOPWORDS and len(w) > 1]


def build_idf(chunk_tokens: list[set[str]]) -> dict[str, float]:
    """IDF de BM25 por término. Un término ausente del corpus recibe el valor máximo (`unknown_idf`)."""
    n = len(chunk_tokens)
    df: dict[str, int] = {}
    for tokens in chunk_tokens:
        for t in tokens:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}


def unknown_idf(n_chunks: int) -> float:
    return math.log(1 + (n_chunks + 0.5) / 0.5)


def coverage(query_tokens: list[str], chunk_tokens: set[str], idf: dict[str, float], unknown: float) -> float:
    """Fracción del peso IDF de los términos de la consulta que aparece en el fragmento. 0 si no hay términos."""
    terms = set(query_tokens)
    total = sum(idf.get(t, unknown) for t in terms)
    if not total:
        return 0.0
    return sum(idf[t] for t in terms if t in chunk_tokens and t in idf) / total


# --------------------------------------------------------------------------- puntajes (puros)


def normalize_dense(similarity: float) -> float:
    return min(1.0, max(0.0, (similarity - DENSE_LOW) / (DENSE_HIGH - DENSE_LOW)))


def hybrid(dense: float, lexical: float, alpha: float) -> float:
    return alpha * normalize_dense(dense) + (1 - alpha) * lexical


def best_chunk(chunks: list[dict], key: Callable[[dict], float]) -> dict:
    return max(chunks, key=key)


def rerank_prompt(question: str, chunks: list[dict]) -> str:
    body = "\n\n".join(f"[{i}] ({c['document']}, {c['location']})\n{c['text']}" for i, c in enumerate(chunks))
    return f"Pregunta: {question}\n\nFragmentos:\n\n{body}"


RERANK_SYSTEM = """Sos un evaluador de relevancia para un buscador de documentos de una biblioteca universitaria.
Dada una pregunta y unos fragmentos numerados, puntuá cada fragmento de 0 a 3 según si CONTIENE la información que
la pregunta pide:

0 = no tiene relación con la pregunta.
1 = es del mismo tema general, pero no contiene lo que se pregunta.
2 = contiene parte de la respuesta.
3 = contesta la pregunta de forma directa.

Compartir el tema o el vocabulario (biblioteca, salas, libros, préstamos) NO alcanza para más de 1: hay que
encontrar el dato pedido. No inventes ni supongas lo que no está escrito. Devolvé solo JSON:
{"scores": [<un entero por fragmento, en el mismo orden>]}"""


def parse_relevance(raw: str | None, n: int) -> list[int]:
    """Valida la salida del re-ranking: `n` enteros en 0..RERANK_MAX; cualquier otra cosa es un error."""
    try:
        data = json.loads(raw or "")
        scores = [int(round(float(s))) for s in data["scores"]]
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"salida de re-ranking inválida: {exc}") from exc
    if len(scores) != n:
        raise ValueError(f"se esperaban {n} puntajes y llegaron {len(scores)}")
    return [min(RERANK_MAX, max(0, s)) for s in scores]


def rerank_score(relevances: list[int]) -> float:
    return max(relevances) / RERANK_MAX if relevances else 0.0


def rerank_plus_dense(relevance: float, dense: float, weight: float = 0.7) -> float:
    """El re-ranking manda; la similitud desempata entre fragmentos con el mismo puntaje."""
    return weight * relevance + (1 - weight) * normalize_dense(dense)


# --------------------------------------------------------------------------- resumen (puro)


def summarize(name: str, rows: list[dict], score_key: str, doc_key: str | None = None,
              model_calls: int = 0) -> dict:
    """AUC, mejor F1 y costo en falsos positivos de un puntaje sobre las consultas cubiertas y no cubiertas."""
    pos = [r[score_key] for r in rows if r["covered"]]
    neg = [r[score_key] for r in rows if not r["covered"]]
    table = sweep(pos, neg, low=0.0, high=1.0, step=0.005)
    picks = pick_thresholds(table, 0.95)
    out = {
        "strategy": name, "score_key": score_key, "auc": auc(pos, neg),
        "best_f1": picks.get("best_f1"), "min_recall_95": picks.get("min_recall"),
        "no_false_positive": picks.get("no_false_positive"),
        "model_calls_per_query": model_calls,  # llamadas al modelo de generación, además de la del embedding
    }
    if doc_key:
        pairs = [r for r in rows if r["covered"] and r.get("expected_document")]
        hits = [r[doc_key].startswith(r["expected_document"]) for r in pairs]
        out["top1_document_accuracy"] = round(sum(hits) / len(hits), 3) if hits else None
    return out


def frozen_thresholds(summary: list[dict]) -> dict[str, dict]:
    """Por estrategia: clave del puntaje y los dos umbrales elegidos sobre la calibración (mejor F1 y recall ≥ 95 %)."""
    out = {}
    for s_ in summary:
        out[s_["strategy"]] = {
            "score_key": s_["score_key"],
            "best_f1": s_["best_f1"]["threshold"],
            "min_recall_95": (s_["min_recall_95"] or {}).get("threshold"),
        }
    return out


def validate(frozen: dict[str, dict], rows: list[dict]) -> list[dict]:
    """Aplica los umbrales congelados a filas que NO se usaron para elegirlos: la medición fuera de muestra."""
    from scripts.calibrate_threshold import confusion

    out = []
    for name, f in frozen.items():
        key = f["score_key"]
        if not rows or key not in rows[0]:
            continue
        pos = [r[key] for r in rows if r["covered"]]
        neg = [r[key] for r in rows if not r["covered"]]
        entry = {"strategy": name, "auc": auc(pos, neg)}
        for label in ("best_f1", "min_recall_95"):
            if f[label] is not None:
                entry[label] = confusion(pos, neg, f[label])
        out.append(entry)
    return out


def group_means(rows: list[dict], score_key: str) -> dict:
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r[score_key])
    return {g: {"n": len(v), "min": round(min(v), 3), "mean": round(sum(v) / len(v), 3), "max": round(max(v), 3)}
            for g, v in sorted(groups.items())}


# --------------------------------------------------------------------------- caché de embeddings


class CachedEmbedder:
    """Guarda el vector de cada consulta en disco: repetir la evaluación no vuelve a gastar la cuota de embeddings.

    La cuota gratuita (1.000 pedidos por día) se agotó con corridas repetidas de ~190 consultas cada una. La clave
    incluye el modelo y la dimensión, así que un cambio de embeddings no reutiliza vectores viejos.
    """

    def __init__(self, inner, cache_path: Path | None, model: str = "", dim: int = 0) -> None:
        self.inner, self.cache_path, self.prefix = inner, cache_path, f"{model}|{dim}|"
        self.cache: dict[str, list[float]] = {}
        self.hits = self.misses = 0
        if cache_path and cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))

    def embed_query(self, text: str) -> list[float]:
        key = self.prefix + text
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        vector = self.inner.embed_query(text)
        self.misses += 1
        self.cache[key] = vector
        if self.cache_path:  # se persiste en cada consulta: si la cuota se corta, lo hecho no se pierde
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")
        return vector


# --------------------------------------------------------------------------- re-ranking con el modelo


class GeminiReranker:
    """Una llamada por consulta con sus fragmentos candidatos. Los resultados se guardan en un caché JSON."""

    def __init__(self, config, cache_path: Path | None = None, client=None) -> None:
        self.cfg = config
        self._client = client
        self.cache_path = cache_path
        self.cache: dict[str, list[int]] = {}
        self.calls = 0
        if cache_path and cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise SystemExit("Falta GEMINI_API_KEY (Art. 9: se lee del entorno)")
            self._client = genai.Client(
                api_key=key, http_options=types.HttpOptions(timeout=self.cfg.api_timeout_s * 1000)
            )
        return self._client

    TRANSIENT_ATTEMPTS = 8

    def _generate_with_backoff(self, client, prompt, config, call_with_retry):
        """`call_with_retry` cubre la cuota (429); acá se suman los 5xx transitorios (503 por alta demanda)."""
        import time

        for attempt in range(self.TRANSIENT_ATTEMPTS):
            try:
                return call_with_retry(
                    lambda: client.models.generate_content(model=self.cfg.model, contents=prompt, config=config),
                    retries=self.cfg.api_max_retries,
                )
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if not (isinstance(code, int) and 500 <= code < 600) or attempt == self.TRANSIENT_ATTEMPTS - 1:
                    raise
                time.sleep(min(60, 5 * 2 ** attempt))

    def relevances(self, question: str, chunks: list[dict]) -> list[int]:
        key = question + "|" + ",".join(str(c["id"]) for c in chunks)
        if key in self.cache:
            return self.cache[key]
        from google.genai import types

        from agent.retry import call_with_retry

        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=RERANK_SYSTEM, temperature=0, response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={"scores": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.INTEGER))},
                required=["scores"],
            ),
        )
        prompt = rerank_prompt(question, chunks)
        response = self._generate_with_backoff(client, prompt, config, call_with_retry)
        self.calls += 1
        scores = parse_relevance(response.text, len(chunks))
        self.cache[key] = scores
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        return scores


# --------------------------------------------------------------------------- ejecución


def choose_alpha(rows: list[dict]) -> float:
    """El α de mayor AUC sobre estas filas. Solo se elige con el set de calibración; la validación lo recibe fijo."""
    return max(ALPHAS, key=lambda a: auc([r[f"hibrido_{a}"] for r in rows if r["covered"]],
                                         [r[f"hibrido_{a}"] for r in rows if not r["covered"]]) or 0)


def evaluate(cases, embedder, store, reranker, cfg, alpha: float | None = None) -> tuple[list[dict], list[dict]]:
    """Calcula los puntajes de cada estrategia para cada consulta. Devuelve (filas, resumen).

    `alpha` fija el peso del híbrido que se combina con el re-ranking; sin él se elige el mejor sobre estas filas.
    """
    prepared = []
    chunk_tokens: list[set[str]] | None = None
    for case in cases:
        vector = embedder.embed_query(case.question)
        chunks = [
            {"id": c.id, "document": c.document, "location": c.location, "text": c.text, "dense": c.similarity}
            for c in store.search(vector, 1000)  # todos los fragmentos: el corpus es chico
        ]
        if chunk_tokens is None:
            chunk_tokens = [set(tokenize(c["text"])) for c in chunks]
            order = [c["id"] for c in chunks]
        prepared.append((case, chunks))
    assert chunk_tokens is not None
    token_by_id = dict(zip(order, chunk_tokens, strict=True))
    idf = build_idf(chunk_tokens)
    unknown = unknown_idf(len(chunk_tokens))

    rows = []
    for case, chunks in prepared:
        q_tokens = tokenize(case.question)
        for c in chunks:
            c["lexical"] = coverage(q_tokens, token_by_id[c["id"]], idf, unknown)
        dense_top = sorted(chunks, key=lambda c: c["dense"], reverse=True)[:TOP_K]
        row = {
            "id": case.id, "query": case.question, "covered": case.covered, "group": case.group,
            "expected_document": case.document,
            "denso": dense_top[0]["dense"], "denso_doc": dense_top[0]["document"],
            "lexico": max(c["lexical"] for c in chunks),
        }
        row["lexico_doc"] = best_chunk(chunks, lambda c: c["lexical"])["document"]
        best_alpha_chunks = {}
        for alpha in ALPHAS:
            ranked = sorted(chunks, key=lambda c, a=alpha: hybrid(c["dense"], c["lexical"], a), reverse=True)
            best_alpha_chunks[alpha] = ranked
            row[f"hibrido_{alpha}"] = hybrid(ranked[0]["dense"], ranked[0]["lexical"], alpha)
            row[f"hibrido_{alpha}_doc"] = ranked[0]["document"]
        row["_dense_top"], row["_hybrid_ranked"] = dense_top, best_alpha_chunks
        rows.append(row)

    summary = [
        summarize("denso (actual)", rows, "denso", "denso_doc"),
        summarize("léxico", rows, "lexico", "lexico_doc"),
        *(summarize(f"híbrido α={a}", rows, f"hibrido_{a}", f"hibrido_{a}_doc") for a in ALPHAS),
    ]
    if reranker is not None:
        best_alpha = alpha if alpha is not None else choose_alpha(rows)
        for r in rows:
            top = r["_dense_top"]
            rel = reranker.relevances(r["query"], top)
            r["rerank"] = rerank_score(rel)
            r["rerank_doc"] = top[max(range(len(top)), key=lambda i: (rel[i], top[i]["dense"]))]["document"]
            r["rerank_denso"] = rerank_plus_dense(r["rerank"], top[0]["dense"])
            hyb = r["_hybrid_ranked"][best_alpha][:TOP_K]
            rel_h = reranker.relevances(r["query"], hyb)
            r["hibrido_rerank"] = rerank_score(rel_h)
            r["hibrido_rerank_doc"] = hyb[max(range(len(hyb)), key=lambda i: (rel_h[i], hyb[i]["dense"]))]["document"]
            r["hibrido_rerank_denso"] = rerank_plus_dense(r["hibrido_rerank"], hyb[0]["dense"])
        summary += [
            summarize("re-ranking (top-5 denso)", rows, "rerank", "rerank_doc", model_calls=1),
            summarize("re-ranking + denso", rows, "rerank_denso", model_calls=1),
            summarize(f"híbrido α={best_alpha} + re-ranking", rows, "hibrido_rerank", "hibrido_rerank_doc", model_calls=1),
            summarize(f"híbrido α={best_alpha} + re-ranking + denso", rows, "hibrido_rerank_denso", model_calls=1),
        ]
    for r in rows:
        r.pop("_dense_top", None)
        r.pop("_hybrid_ranked", None)
    return rows, summary


def _fmt(point: dict | None) -> str:
    if not point:
        return "—"
    return f"u={point['threshold']:.3f} recall={point.get('recall', 0):.2f} fp={point.get('fp', point.get('fn', '?'))}"


def _print_table(title: str, summary: list[dict], n_pos: int, n_neg: int) -> None:
    print(f"\n{title}: {n_pos} cubiertas · {n_neg} sin cobertura\n")
    print(f"{'estrategia':<38}{'AUC':>7}  {'doc 1º':>6}   mejor F1 / recall ≥ 95 %")
    for s_ in summary:
        doc = s_.get("top1_document_accuracy")
        print(f"{s_['strategy']:<38}{s_['auc']:>7.3f}  {('' if doc is None else f'{doc:.2f}'):>6}   "
              f"F1={s_['best_f1']['f1']:.3f} {_fmt(s_['best_f1'])}  |  {_fmt(s_['min_recall_95'])}")


def _print_validation(validation: list[dict], n_pos: int, n_neg: int) -> None:
    print(f"\nVALIDACIÓN fuera de muestra (umbrales congelados): {n_pos} cubiertas · {n_neg} sin cobertura\n")
    print(f"{'estrategia':<38}{'AUC':>7}   al umbral de mejor F1            | al umbral de recall ≥ 95 %")
    for v in validation:
        def cell(c):
            if not c:
                return "—".ljust(32)
            return f"u={c['threshold']:.3f} recall={c['recall']:.2f} fp={c['fp']:>2}/{n_neg} F1={c['f1']:.2f}"
        print(f"{v['strategy']:<38}{v['auc']:>7.3f}   {cell(v.get('best_f1')):<32} | {cell(v.get('min_recall_95'))}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="TP/evidencia/busqueda_hibrida_rerank.json")
    parser.add_argument("--cache", default="TP/evidencia/rerank_scores.json")
    parser.add_argument("--embeddings-cache", default=".cache/query_embeddings.json",
                        help="caché local (fuera de git) de los vectores de las consultas")
    parser.add_argument("--no-rerank", action="store_true", help="solo denso, léxico e híbrido (sin llamadas al modelo)")
    parser.add_argument("--no-validation", action="store_true", help="omite el set de validación")
    args = parser.parse_args()

    from agent.config import load_config
    from agent.tools.rag_tool import GeminiEmbedder, PgVectorStore

    cfg = load_config()
    store = PgVectorStore(cfg)
    embedder = CachedEmbedder(GeminiEmbedder(cfg), Path(args.embeddings_cache), cfg.embedding_model, cfg.embedding_dim)
    reranker = None if args.no_rerank else GeminiReranker(cfg, Path(args.cache))
    validation_rows: list[dict] = []
    validation: list[dict] = []
    try:
        rows, summary = evaluate(build_cases(), embedder, store, reranker, cfg)
        alpha = choose_alpha(rows)
        if not args.no_validation:
            validation_rows, _ = evaluate(build_validation_cases(), embedder, store, reranker, cfg, alpha=alpha)
            validation = validate(frozen_thresholds(summary), validation_rows)
    finally:
        store.close()

    n_pos = sum(r["covered"] for r in rows)
    _print_table("CALIBRACIÓN (con estos datos se eligieron α, el rango y los umbrales)", summary, n_pos, len(rows) - n_pos)
    if validation:
        v_pos = sum(r["covered"] for r in validation_rows)
        _print_validation(validation, v_pos, len(validation_rows) - v_pos)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "embedding_model": cfg.embedding_model, "model": cfg.model, "alphas": list(ALPHAS), "alpha_chosen": alpha,
        "dense_range": [DENSE_LOW, DENSE_HIGH], "summary": summary, "cases": rows,
        "frozen_thresholds": frozen_thresholds(summary), "validation": validation, "validation_cases": validation_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
