"""Prueba de carga ligera de la API (T10). Simula a varias usuarias de la pyme de demo trabajando a la vez.

Mezcla (pesos): preguntas frecuentes al asistente (nivel 0 si ASSISTANT_USE_LLM=false), lecturas de inventario,
recetas y pedidos, una cotización de un pedido existente y el conteo por foto. Con `LOAD_PROFILE=llm` solo hace
preguntas que el nivel 1 redacta con el LLM (para ver cómo se comporta la cola de Ollama).

Corre dentro de la red del contenedor de la API (llega a :8000 y a una instancia extra en :8001):

    docker run --rm --network container:caterin-api-1 -v "$PWD":/load:z -w /load caterin-api \
        .venv/bin/locust -f locustfile.py --headless -u 5 -r 1 -t 5m --host http://127.0.0.1:8000 \
        --csv results/mix --only-summary

OJO: cada cotización crea una versión nueva en la base de desarrollo (`quote`), y cada pregunta una fila en
`assistant_interaction`. Son datos de demo, pero quedan.
"""

import base64
import os
import random
from pathlib import Path

from locust import HttpUser, between, task

EMAIL = os.environ.get("LOAD_EMAIL", "duena.aromos@demo.local")
PASSWORD = os.environ.get("LOAD_PASSWORD", "caterin-demo-2026")
PROFILE = os.environ.get("LOAD_PROFILE", "mix")

LEVEL0 = [
    "¿Cuánta harina me queda?",
    "¿Qué me falta comprar?",
    "¿Qué pedidos tengo esta semana?",
    "¿Dónde está más barata la harina?",
    "¿Qué días despacha Harinas Cautín?",
    "¿Qué lleva el pedido del matrimonio?",
    "¿Me alcanza para el pedido del matrimonio?",
    "¿Cuánto produje hoy?",
]
LEVEL1 = [  # intenciones con allow_level1: con ASSISTANT_USE_LLM=true las redacta el LLM
    "¿Cuánto me sale la docena de empanadas de queso?",
    "¿Cuánto me cuestan 50 canapés de salmón?",
    "¿Dónde está más barata la mantequilla?",
]
# Foto JPEG del split de test sintético de visión (ml/vision/data, no se commitea). Si no está, un PNG de 1x1,
# que la API procesa en pocos ms: en ese caso la latencia de vision/count NO representa una foto real.
# Se copia junto al locustfile porque el contenedor solo monta esta carpeta: cp <foto>.jpg bandeja.jpg
PHOTO = Path(__file__).with_name("bandeja.jpg")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
IMAGE = ("bandeja.jpg", PHOTO.read_bytes(), "image/jpeg") if PHOTO.exists() else ("bandeja.png", PNG, "image/png")


class Duena(HttpUser):
    wait_time = between(1, 3)  # una persona no hace clic sin parar

    def on_start(self) -> None:
        r = self.client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}, name="auth/login")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        orders = self.client.get("/api/v1/orders", name="orders").json()
        self.order_ids = [o["id"] for o in orders if o["status"] in ("draft", "confirmed")]

    def _ask(self, question: str, name: str) -> None:
        self.client.post("/api/v1/assistant/ask", json={"question": question}, name=name)

    @task(4)
    def ask_level0(self) -> None:
        if PROFILE == "llm":
            self._ask(random.choice(LEVEL1), "assistant/ask (nivel 1, LLM)")  # noqa: S311
        else:
            self._ask(random.choice(LEVEL0), "assistant/ask (nivel 0)")  # noqa: S311

    @task(3)
    def inventory(self) -> None:
        if PROFILE != "llm":
            self.client.get("/api/v1/ingredients?limit=100", name="ingredients")

    @task(2)
    def recipes(self) -> None:
        if PROFILE != "llm":
            self.client.get("/api/v1/recipes", name="recipes")

    @task(2)
    def orders(self) -> None:
        if PROFILE != "llm":
            self.client.get("/api/v1/orders?upcoming_days=7", name="orders?upcoming_days=7")

    @task(1)
    def quote(self) -> None:
        if PROFILE != "llm" and self.order_ids:
            oid = random.choice(self.order_ids)  # noqa: S311
            self.client.post(f"/api/v1/orders/{oid}/quotes", json={}, name="orders/{id}/quotes")

    @task(1)
    def vision(self) -> None:
        if PROFILE == "llm":
            return
        with self.client.post(
            "/api/v1/vision/count",
            files={"image": IMAGE},
            name="vision/count",
            catch_response=True,
        ) as r:
            if r.status_code == 503:  # sin modelo en desarrollo: esperado, no es una falla de la API
                r.success()
