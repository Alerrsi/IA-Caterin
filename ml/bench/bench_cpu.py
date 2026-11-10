#!/usr/bin/env python3
"""Benchmark en CPU para los modelos candidatos de Cáterin (AGENTS.md sección 3.1).

Mide en TU equipo, sin GPU:
  llm       Latencia y tokens/s por Ollama, RAM usada, tool calling y extracción de pedidos
  embed     Latencia de embeddings y reranker + humo de recuperación (corpus mínimo sintético)
  detector  Latencia de un detector exportado a ONNX (p. ej. RF-DETR Nano) en CPU

Uso rápido:
  1) LLM (Ollama corriendo; antes: ollama pull qwen3:4b qwen3:8b)
       python bench_cpu.py llm --models qwen3:4b qwen3:8b --repeats 3
  2) Embeddings y reranker (pip install sentence-transformers)
       python bench_cpu.py embed --embed-models BAAI/bge-m3 Qwen/Qwen3-Embedding-0.6B \
              --reranker BAAI/bge-reranker-v2-m3
  3) Detector (pip install onnxruntime numpy; el .onnx sale de `model.export()` de rfdetr)
       python bench_cpu.py detector --onnx output/inference_model.onnx --imgsz 384

Cada comando agrega sus resultados a bench_results.json (--out para cambiar el nombre).

Versión 2.0 (T10, 9-nov-2026), correcciones del ADR-003:
  - RAM por nombre EXACTO del modelo en /api/ps (antes coincidía por prefijo: qwen3:4b y qwen3:8b se mezclaban).
  - Tokens generados (eval_count) de cada respuesta, p50 y el detalle por pregunta.
  - Extracción: qué campo falló en cada caso.
  - Redacción en texto libre: marca respuestas con razonamiento filtrado ("Okay, let's…", <think>, inglés),
    y mide también la variante JSON {"respuesta": "..."} que usa la app (apps/api/app/core/llm.py).
  - Versión del script, carga del sistema (/proc/loadavg) antes y después de cada modelo.
Cierra otros programas pesados mientras mides y conecta el cargador del notebook.

LIMITES (importante para el ADR-003):
  - El corpus de `embed` es un test de humo de 12 pasajes sintéticos. NO reemplaza la evaluación
    de T10 con documentos reales de una pyme.
  - `detector` mide latencia con una imagen aleatoria; no mide precisión. La precisión sale del
    entrenamiento con fotos reales de productos.
  - Las pruebas de tool calling y extracción son pocos casos: sirven para descartar modelos
    malos, no para fijar porcentajes de confiabilidad.
"""
import argparse
import json
import os
import platform
import sys
import time
import unicodedata
import urllib.error
import urllib.request

SCRIPT_VERSION = "2.0.0"

# --------------------------------------------------------------------------- utilidades


def pct(values, p):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def norm(text):
    return unicodedata.normalize("NFD", str(text).lower()).encode("ascii", "ignore").decode()


def sysinfo():
    cpu = platform.processor()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    info = {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
    }
    try:
        import psutil  # opcional

        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        pass
    return info


def loadavg():
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            return [float(x) for x in fh.read().split()[:3]]
    except OSError:
        return None


ENGLISH = {"the", "user", "is", "asking", "let", "me", "okay", "so", "need", "check", "wait", "data", "should", "answer"}


def leaks_reasoning(text):
    """True si la respuesta trae razonamiento en vez de (o antes de) la respuesta: <think>, "Okay, let's…",
    o mucho vocabulario inglés. Heurística: sirve para detectar el problema, no para medir calidad."""
    t = str(text).strip()
    if "<think>" in t or t.lower().startswith(("okay", "let me", "alright", "hmm", "first,")):
        return True
    words = [w for w in norm(t).replace(",", " ").replace(".", " ").split() if w.isalpha()]
    return bool(words) and sum(w in ENGLISH for w in words) / len(words) > 0.12


def save(out, key, data):
    results = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            results = json.load(fh)
    results["system"] = sysinfo()
    results["script_version"] = SCRIPT_VERSION
    results.setdefault(key, {}).update(data)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {out}")


def rank_metrics(sim, gold):
    """sim: matriz consultas x pasajes (lista de listas o ndarray). gold: índice correcto por consulta."""
    hits1 = hits3 = 0
    rr = 0.0
    for row, g in zip(sim, gold):
        order = sorted(range(len(row)), key=lambda i: -float(row[i]))
        pos = order.index(g) + 1
        hits1 += pos == 1
        hits3 += pos <= 3
        rr += 1.0 / pos
    n = len(gold)
    return {"recall@1": round(hits1 / n, 3), "recall@3": round(hits3 / n, 3), "mrr": round(rr / n, 3)}


# --------------------------------------------------------------------------- LLM (Ollama)

SYSTEM = "Eres el asistente de una pyme de catering en Chile. Responde en español de Chile, breve y claro."
CONTEXT = (
    "Datos de la pyme (hoy):\n"
    "- Stock: harina 18 kg; carne molida 6 kg; salmón ahumado 2,5 kg; crema 3 L; huevos 90 unidades.\n"
    "- Receta empanadas de pino (docena): harina 600 g, carne 400 g, cebolla 300 g, 2 huevos.\n"
    "- Pedidos próximos: sábado 22, cóctel 50 personas (80 empanadas, 60 canapés); "
    "viernes 28, matrimonio 120 personas.\n"
    "- Proveedor Molino Sur: harina saco 25 kg a $21.000; Distribuidora Araucanía: despacho martes y jueves.\n"
)
LAT_QUESTIONS = [
    "¿Me alcanza la harina para las empanadas del pedido del sábado?",
    "¿Qué pedidos tengo próximamente y para cuántas personas?",
    "Redáctame un mensaje corto de WhatsApp confirmando el anticipo del 50% a una clienta.",
    "¿Qué proveedor despacha los martes y jueves?",
]

TOOLS = [
    {"type": "function", "function": {
        "name": "get_stock", "description": "Stock actual de un insumo",
        "parameters": {"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]}}},
    {"type": "function", "function": {
        "name": "get_recipe_cost", "description": "Costo de producir una receta",
        "parameters": {"type": "object", "properties": {"recipe": {"type": "string"}}, "required": ["recipe"]}}},
    {"type": "function", "function": {
        "name": "list_upcoming_orders", "description": "Pedidos de los próximos días",
        "parameters": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]}}},
]
TOOL_CASES = [
    ("¿Cuánta harina me queda en bodega?", "get_stock", "item", "harina"),
    ("¿Cuánto cuesta producir la receta de empanadas de pino?", "get_recipe_cost", "recipe", "empanada"),
    ("¿Qué pedidos tengo esta semana?", "list_upcoming_orders", None, None),
    ("Cuéntame un chiste corto.", None, None, None),  # no debe llamar herramientas
]

ANSWER_SCHEMA = {"type": "object", "properties": {"respuesta": {"type": "string"}}, "required": ["respuesta"]}
ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "guests": {"type": ["integer", "null"]},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": ["string", "null"]}},
            "required": ["name", "quantity"]}},
    },
    "required": ["items"],
}
# (texto, invitados, [(palabra clave, cantidades aceptadas)])
EXTRACT_CASES = [
    ("Necesito 80 empanadas de pino y 60 canapés de salmón para el sábado 22, somos como 50 personas.",
     50, [("empanada", {80}), ("canape", {60})]),
    ("Cotízame un cóctel para 120 personas: 240 brochetas de pollo, 120 mini quiches y 5 kilos de ensalada.",
     120, [("brocheta", {240}), ("quiche", {120}), ("ensalada", {5})]),
    ("Quiero 3 docenas de sopaipillas para mañana.",
     None, [("sopaipilla", {3, 36})]),
]


def post(host, path, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(host.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def chat(host, model, messages, tools=None, fmt=None, num_predict=160, num_ctx=4096):
    payload = {
        "model": model, "messages": messages, "stream": False, "think": False, "keep_alive": "15m",
        "options": {"temperature": 0.1, "num_ctx": num_ctx, "num_predict": num_predict},
    }
    if tools:
        payload["tools"] = tools
    if fmt:
        payload["format"] = fmt
    try:
        return post(host, "/api/chat", payload)
    except urllib.error.HTTPError as err:
        if err.code == 400 and "think" in payload:  # modelo sin soporte de thinking
            payload.pop("think")
            return post(host, "/api/chat", payload)
        raise


def tok_per_s(resp):
    dur = resp.get("eval_duration") or 0
    return resp["eval_count"] / (dur / 1e9) if dur and resp.get("eval_count") else None


def args_of(call):
    a = call.get("function", {}).get("arguments", {})
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            a = {}
    return a if isinstance(a, dict) else {}


def exact_name(model):
    return model if ":" in model else model + ":latest"


def ram_of(host, model):
    """Memoria del modelo cargado, por nombre EXACTO (corrige la coincidencia por prefijo de la v1)."""
    want = exact_name(model)
    for m in post(host, "/api/ps").get("models", []):
        if want in (m.get("name"), m.get("model")):
            return {"ram_gb": round(m.get("size", 0) / 1e9, 2), "vram_gb": round(m.get("size_vram", 0) / 1e9, 2)}
    return {"ram_gb": None, "note": f"{want} no aparece en /api/ps"}


def bench_llm_model(host, model, repeats, num_ctx):
    out = {"script_version": SCRIPT_VERSION, "loadavg_before": loadavg()}
    warm = chat(host, model, [{"role": "user", "content": "Hola"}], num_predict=8, num_ctx=num_ctx)
    out["load_s"] = round((warm.get("load_duration") or 0) / 1e9, 2)

    totals, tps, prefill, tokens, leaks, detail = [], [], [], [], 0, []
    for rep_i in range(repeats):
        for q in LAT_QUESTIONS:
            t0 = time.perf_counter()
            r = chat(host, model, [{"role": "system", "content": SYSTEM + "\n" + CONTEXT},
                                   {"role": "user", "content": q}], num_ctx=num_ctx)
            totals.append(time.perf_counter() - t0)
            if tok_per_s(r):
                tps.append(tok_per_s(r))
            prefill.append((r.get("prompt_eval_duration") or 0) / 1e9)
            tokens.append(r.get("eval_count") or 0)
            text = r.get("message", {}).get("content", "")
            leak = leaks_reasoning(text)
            leaks += leak
            if rep_i == 0:
                detail.append({"pregunta": q, "tokens": r.get("eval_count"), "razonamiento_filtrado": leak,
                               "inicio": text[:160]})
    out["latency_s"] = {"p50": round(pct(totals, 50), 1), "p95": round(pct(totals, 95), 1), "n": len(totals)}
    out["tokens_per_s_p50"] = round(pct(tps, 50), 1) if tps else None
    out["prompt_eval_s_p50"] = round(pct(prefill, 50), 2)
    out["tokens_out"] = {"p50": pct(tokens, 50), "max": max(tokens) if tokens else None}
    out["texto_libre"] = {"respuestas_con_razonamiento": leaks, "total": len(totals), "detalle": detail}

    # Variante que usa la app: salida JSON {"respuesta": "..."} (impide que se cuele el razonamiento).
    jtot, jtok, jleaks, jdetail = [], [], 0, []
    for q in LAT_QUESTIONS:
        t0 = time.perf_counter()
        r = chat(host, model, [{"role": "system", "content": SYSTEM + " Responde en 2 o 3 frases.\n" + CONTEXT},
                               {"role": "user", "content": q}], fmt=ANSWER_SCHEMA, num_predict=120, num_ctx=num_ctx)
        jtot.append(time.perf_counter() - t0)
        jtok.append(r.get("eval_count") or 0)
        try:
            answer = json.loads(r["message"]["content"]).get("respuesta", "")
        except (ValueError, KeyError, AttributeError):
            answer = ""
        leak = leaks_reasoning(answer) or not answer
        jleaks += leak
        jdetail.append({"pregunta": q, "tokens": r.get("eval_count"), "razonamiento_o_vacia": leak,
                        "respuesta": answer[:200]})
    out["respuesta_json"] = {"latency_s_p50": round(pct(jtot, 50), 1), "tokens_p50": pct(jtok, 50),
                             "razonamiento_o_vacia": jleaks, "total": len(jtot), "detalle": jdetail}

    try:
        out.update(ram_of(host, model))
    except Exception as exc:  # noqa: BLE001
        out["ram_gb"] = None
        out["ram_error"] = str(exc)[:120]

    tool_ok, tool_detail = 0, []
    for text, want, key, kw in TOOL_CASES:
        try:
            r = chat(host, model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
                     tools=TOOLS, num_ctx=num_ctx)
            calls = r.get("message", {}).get("tool_calls") or []
            if want is None:
                ok = not calls
            else:
                ok = bool(calls) and calls[0].get("function", {}).get("name") == want
                if ok and key:
                    ok = kw in norm(args_of(calls[0]).get(key, ""))
            tool_detail.append({"caso": text, "ok": bool(ok)})
            tool_ok += bool(ok)
        except Exception as exc:  # noqa: BLE001
            tool_detail.append({"caso": text, "ok": False, "error": str(exc)[:120]})
    out["tool_calling"] = {"ok": tool_ok, "total": len(TOOL_CASES), "detalle": tool_detail}

    got = total = 0
    fallos = []
    for text, guests, items in EXTRACT_CASES:
        try:
            r = chat(host, model, [
                {"role": "system", "content": "Extrae el pedido de catering. Responde solo JSON según el esquema."},
                {"role": "user", "content": text}], fmt=ORDER_SCHEMA, num_predict=300, num_ctx=num_ctx)
            data = json.loads(r["message"]["content"])
        except Exception:  # noqa: BLE001
            data = {}
        if guests is not None:
            total += 1
            if data.get("guests") == guests:
                got += 1
            else:
                fallos.append({"caso": text[:50], "campo": "guests", "esperado": guests, "obtenido": data.get("guests")})
        for kw, qtys in items:
            total += 1
            hit = None
            for it in data.get("items", []) or []:
                try:
                    if kw in norm(it.get("name", "")) and float(it.get("quantity", -1)) in qtys:
                        hit = it
                        break
                except (TypeError, ValueError):
                    pass
            if hit:
                got += 1
            else:
                same = [it for it in data.get("items", []) or [] if kw in norm(it.get("name", ""))]
                fallos.append({"caso": text[:50], "campo": f"item:{kw}", "esperado": sorted(qtys),
                               "obtenido": same or "producto ausente"})
    out["extraccion"] = {"campos_ok": got, "campos_total": total, "fallos": fallos}
    out["loadavg_after"] = loadavg()
    return out


def unload(host, model):
    """Saca el modelo de la memoria (keep_alive 0) para medir el siguiente sin competir por RAM."""
    try:
        post(host, "/api/generate", {"model": model, "keep_alive": 0})
    except Exception:  # noqa: BLE001
        pass


def cmd_llm(args):
    results = {}
    for model in args.models:
        print(f"\n== {model} ==", flush=True)
        try:
            results[model] = bench_llm_model(args.host, model, args.repeats, args.num_ctx)
            print(json.dumps(results[model], ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            results[model] = {"error": str(exc)[:200]}
            print("Falló:", exc)
        unload(args.host, model)
    save(args.out, "llm", results)


# --------------------------------------------------------------------------- embeddings y reranker

CORPUS = [
    "La harina de trigo se compra en sacos de 25 kg al proveedor Molino Sur; el precio cambia cada mes.",
    "Receta empanadas de pino: por docena se usan 600 g de harina, 400 g de carne molida, 300 g de cebolla, huevo duro y aceitunas.",
    "Los canapés de salmón requieren 15 g de salmón ahumado por unidad y se preparan el mismo día del evento.",
    "El cliente debe pagar un 50% de anticipo para reservar la fecha del evento.",
    "El inventario de lácteos se revisa los lunes; la crema y el queso fresco duran cinco días refrigerados.",
    "Proveedor Distribuidora Araucanía: despacho en Temuco los martes y jueves, pedido mínimo de 80 mil pesos.",
    "La merma estimada de verduras frescas es del 12% por limpieza y corte.",
    "Para eventos de más de 100 personas se agregan dos personas de servicio por cada 40 invitados.",
    "Las brochetas de pollo se marinan por 4 horas y se cocinan en horno a 200 grados por 18 minutos.",
    "Los pagos a proveedores se concentran los días 5 y 20 de cada mes mediante transferencia.",
    "El salmón ahumado se cotiza con una pescadería del sur; el precio por kilo varía según la temporada.",
    "Las cotizaciones tienen una validez de 7 días corridos desde la fecha de emisión.",
]
QUERIES = [
    ("¿Cuánta harina lleva una docena de empanadas?", 1),
    ("¿Cuándo reparte el proveedor en Temuco?", 5),
    ("¿Cuánto anticipo se cobra al cliente?", 3),
    ("¿Cuánto dura la crema en el refrigerador?", 4),
    ("¿Cuántos meseros necesito para 150 invitados?", 7),
    ("¿A qué temperatura y por cuánto tiempo van las brochetas?", 8),
    ("¿Cuántos días vale una cotización?", 11),
    ("¿Qué porcentaje de pérdida tienen las verduras?", 6),
]


def cmd_embed(args):
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    gold = [g for _, g in QUERIES]
    questions = [q for q, _ in QUERIES]
    results, first_sim = {}, None
    for name in args.embed_models:
        print(f"\n== {name} ==", flush=True)
        t0 = time.perf_counter()
        model = SentenceTransformer(name, device="cpu")
        load_s = time.perf_counter() - t0
        kw = {"prompt_name": "query"} if "Qwen3-Embedding" in name else {}
        t0 = time.perf_counter()
        docs = model.encode(CORPUS, normalize_embeddings=True, batch_size=8)
        corpus_s = time.perf_counter() - t0
        lat = []
        qv = []
        for q in questions:
            t0 = time.perf_counter()
            qv.append(model.encode([q], normalize_embeddings=True, **kw)[0])
            lat.append(time.perf_counter() - t0)
        sim = np.array(qv) @ np.array(docs).T
        if first_sim is None:
            first_sim = sim
        results[name] = {
            "load_s": round(load_s, 1), "dim": int(docs.shape[1]),
            "corpus_12_pasajes_s": round(corpus_s, 2),
            "consulta_ms_p50": round(pct(lat, 50) * 1000), "consulta_ms_p95": round(pct(lat, 95) * 1000),
            **rank_metrics(sim, gold),
        }
        print(json.dumps(results[name], indent=2))
        del model

    if args.reranker and first_sim is not None:
        print(f"\n== reranker {args.reranker} ==", flush=True)
        t0 = time.perf_counter()
        ce = CrossEncoder(args.reranker, device="cpu", max_length=512)
        load_s = time.perf_counter() - t0
        lat5, lat20, new_sim = [], [], []
        for qi, q in enumerate(questions):
            cand = list(np.argsort(-first_sim[qi])[:5])
            t0 = time.perf_counter()
            sc = ce.predict([(q, CORPUS[i]) for i in cand])
            lat5.append(time.perf_counter() - t0)
            row = [-1e9] * len(CORPUS)
            for i, s in zip(cand, sc):
                row[i] = float(s)
            new_sim.append(row)
            pairs20 = [(q, CORPUS[i % len(CORPUS)]) for i in range(20)]
            t0 = time.perf_counter()
            ce.predict(pairs20)
            lat20.append(time.perf_counter() - t0)
        results["reranker:" + args.reranker] = {
            "load_s": round(load_s, 1),
            "rerank_5_candidatos_ms_p50": round(pct(lat5, 50) * 1000),
            "rerank_20_candidatos_ms_p50": round(pct(lat20, 50) * 1000),
            "tras_rerank_top5_del_primer_modelo": rank_metrics(new_sim, gold),
        }
        print(json.dumps(results["reranker:" + args.reranker], indent=2))
    save(args.out, "embed", results)


# --------------------------------------------------------------------------- detector ONNX


def cmd_detector(args):
    import numpy as np
    import onnxruntime as ort

    opts = ort.SessionOptions()
    if args.threads:
        opts.intra_op_num_threads = args.threads
    t0 = time.perf_counter()
    sess = ort.InferenceSession(args.onnx, opts, providers=["CPUExecutionProvider"])
    load_s = time.perf_counter() - t0
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) and d > 0 else (1 if i == 0 else args.imgsz) for i, d in enumerate(inp.shape)]
    dtype = np.float16 if "float16" in inp.type else np.float32
    x = np.random.rand(*shape).astype(dtype)
    for _ in range(args.warmup):
        sess.run(None, {inp.name: x})
    times = []
    for _ in range(args.runs):
        t0 = time.perf_counter()
        sess.run(None, {inp.name: x})
        times.append((time.perf_counter() - t0) * 1000)
    res = {
        "onnx": os.path.basename(args.onnx), "input_shape": shape, "threads": args.threads or "auto",
        "load_s": round(load_s, 2), "ms_p50": round(pct(times, 50), 1), "ms_p95": round(pct(times, 95), 1),
        "fps_p50": round(1000 / pct(times, 50), 2),
        "nota": "latencia con imagen aleatoria; no mide precisión",
    }
    print(json.dumps(res, indent=2))
    save(args.out, "detector", {os.path.basename(args.onnx): res})


# --------------------------------------------------------------------------- CLI


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="bench_results.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("llm")
    p.add_argument("--models", nargs="+", default=["qwen3:4b", "qwen3:8b"])
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--num-ctx", type=int, default=4096)
    p.set_defaults(fn=cmd_llm)

    p = sub.add_parser("embed")
    p.add_argument("--embed-models", nargs="+", default=["BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"])
    p.add_argument("--reranker", default="BAAI/bge-reranker-v2-m3")
    p.set_defaults(fn=cmd_embed)

    p = sub.add_parser("detector")
    p.add_argument("--onnx", required=True)
    p.add_argument("--imgsz", type=int, default=384)
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--threads", type=int, default=0)
    p.set_defaults(fn=cmd_detector)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
