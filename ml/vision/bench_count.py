"""Latencia de punta a punta de `POST /vision/count` contra la API corriendo (T06).

Genera fotos sintéticas del tamaño de un celular (por defecto 4000×3000 = 12 MP, JPEG calidad 90),
las sube N veces y reporta p50/p95 del lado del cliente y los tiempos que informa el servidor.

    env/bin/python ml/vision/bench_count.py --email duena.aromos@demo.local --password caterin-demo-2026

Solo usa la biblioteca estándar y Pillow. Las fotos son sintéticas: miden latencia, no precisión.
"""

import argparse
import io
import json
import random
import statistics
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def synthetic_photo(width: int, height: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", (width, height), (rnd.randint(150, 200), rnd.randint(140, 180), rnd.randint(110, 150)))
    draw = ImageDraw.Draw(img)
    for _ in range(40):  # "empanadas" sobre una bandeja, para que el JPEG pese como una foto real
        x, y = rnd.randint(0, width - 400), rnd.randint(0, height - 300)
        draw.ellipse((x, y, x + rnd.randint(250, 400), y + rnd.randint(150, 300)), fill=(205, 150, 80))
    noisy = Image.effect_noise((width, height), 24).convert("RGB")
    img = Image.blend(img, noisy, 0.15).filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def request(url: str, data: bytes, headers: dict[str, str]) -> dict:  # type: ignore[type-arg]
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")  # noqa: S310 - URL local
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return json.loads(resp.read())


def multipart(field: str, filename: str, payload: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    return head + payload + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p * (len(ordered) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000/api/v1")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--width", type=int, default=4000)
    ap.add_argument("--height", type=int, default=3000)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("runs") / "bench_count.json")
    args = ap.parse_args()

    login = request(
        f"{args.api}/auth/login",
        json.dumps({"email": args.email, "password": args.password}).encode(),
        {"Content-Type": "application/json"},
    )
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    photos = [synthetic_photo(args.width, args.height, s) for s in range(3)]
    client_ms: list[float] = []
    server_ms: list[float] = []
    model = ""
    for i in range(args.runs + 1):
        body, ctype = multipart("image", "bandeja.jpg", photos[i % len(photos)])
        start = time.perf_counter()
        res = request(f"{args.api}/vision/count", body, {**auth, "Content-Type": ctype})
        elapsed = (time.perf_counter() - start) * 1000
        if i == 0:
            continue  # calentamiento
        client_ms.append(elapsed)
        server_ms.append(res["elapsed_ms"])
        model = res["model_version"]

    def summary(values: list[float]) -> dict[str, float]:
        return {"p50": round(statistics.median(values)), "p95": round(pct(values, 0.95)), "max": round(max(values))}

    result = {
        "model_version": model,
        "image": f"{args.width}x{args.height} JPEG q90 (sintética), {round(statistics.mean(len(p) for p in photos) / 1e6, 2)} MB",
        "runs": args.runs,
        "client_total_ms": summary(client_ms),
        "server_elapsed_ms": summary(server_ms),
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
