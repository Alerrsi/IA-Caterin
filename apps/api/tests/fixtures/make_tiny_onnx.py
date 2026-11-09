"""Genera tiny_detector.onnx: mismo contrato de salida que RF-DETR (`dets` y `labels`), con valores fijos.

No es un modelo: siempre "detecta" 2 empanadas y 1 canapé. Sirve para probar OnnxDetector y el endpoint.
Uso (necesita `onnx`, que no es dependencia de la API):  python make_tiny_onnx.py
"""

import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

HERE = Path(__file__).parent
N, C = 4, 2  # 4 consultas; 2 clases + 1 ranura "sin objeto" al final, como RF-DETR
boxes = np.array(
    [[[0.25, 0.25, 0.2, 0.2], [0.75, 0.25, 0.2, 0.2], [0.5, 0.75, 0.2, 0.2], [0.5, 0.5, 0.1, 0.1]]], np.float32
)
logits = np.full((1, N, C + 1), -9.0, np.float32)
logits[0, 0, 0] = logits[0, 1, 0] = 6.0  # empanada
logits[0, 2, 1] = 6.0  # canape
logits[0, 3, 2] = 9.0  # ranura extra: debe ignorarse

graph = helper.make_graph(
    [
        helper.make_node("Constant", [], ["dets"], value=numpy_helper.from_array(boxes)),
        helper.make_node("Constant", [], ["labels"], value=numpy_helper.from_array(logits)),
    ],
    "tiny",
    [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 32, 32])],
    [
        helper.make_tensor_value_info("dets", TensorProto.FLOAT, [1, N, 4]),
        helper.make_tensor_value_info("labels", TensorProto.FLOAT, [1, N, C + 1]),
    ],
)
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
onnx.checker.check_model(model)
onnx.save(model, HERE / "tiny_detector.onnx")
(HERE / "tiny_detector.json").write_text(
    json.dumps({"version": "tiny-test", "classes": ["empanada", "canape"], "input_size": 32})
)
