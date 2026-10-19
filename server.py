#!/usr/bin/env python3
"""NALAR single-origin PWA + Python forecasting API (standard library only)."""
from __future__ import annotations

import json
import math
import mimetypes
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
MAX_BODY = 1_000_000
METHODS = ("Naive", "Mean", "Moving average", "Weighted moving average", "Linear trend", "Exponential smoothing")


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def linear_fit(xs: list[float], ys: list[float]):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = average(xs), average(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator < 1e-10:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator
    return {"intercept": my - slope * mx, "slope": slope, "mean_x": mx, "mean_y": my}


def linear_predict(fit, x: float) -> float:
    return fit["mean_y"] + fit["slope"] * (x - fit["mean_x"])


def model_forecast(method: str, values: list[float], steps: int = 1) -> float:
    n, last = len(values), values[-1]
    if method == "Naive":
        return last
    if method == "Mean":
        return average(values)
    if method == "Moving average":
        return average(values[-min(3, n):])
    if method == "Weighted moving average":
        recent = values[-min(4, n):]
        weights = list(range(1, len(recent) + 1))
        return sum(v * w for v, w in zip(recent, weights)) / sum(weights)
    if method == "Linear trend":
        fit = linear_fit(list(map(float, range(n))), values)
        return linear_predict(fit, n - 1 + steps) if fit else last
    if method == "Exponential smoothing":
        alpha, level = 0.35, values[0]
        for value in values[1:]:
            level = alpha * value + (1 - alpha) * level
        return level
    return last


def walk_forward_error(method: str, values: list[float]):
    errors = []
    for index in range(4, len(values)):
        predicted = model_forecast(method, values[:index], 1)
        errors.append(abs(values[index] - predicted))
    return average(errors) if errors else None


def variable_candidate(rows: list[dict], variable_id: str):
    pairs = []
    for row in rows:
        raw = (row.get("variableValues") or {}).get(variable_id)
        try:
            x, y = float(raw), float(row["count"])
        except (TypeError, ValueError, KeyError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            pairs.append((x, y))
    if len(pairs) < 6:
        return None
    errors = []
    for index in range(4, len(pairs)):
        fit = linear_fit([p[0] for p in pairs[:index]], [p[1] for p in pairs[:index]])
        if fit:
            errors.append(abs(pairs[index][1] - linear_predict(fit, pairs[index][0])))
    fit = linear_fit([p[0] for p in pairs], [p[1] for p in pairs])
    if not errors or not fit:
        return None
    return {"fit": fit, "mae": average(errors), "n": len(pairs)}


def forecast(payload: dict) -> dict:
    rows = payload.get("observations")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("Masukkan setidaknya 3 observasi.")
    horizon = max(1, min(12, int(payload.get("horizon", 1))))
    clean_rows = []
    for row in rows[:10000]:
        try:
            count = float(row["count"])
        except (TypeError, ValueError, KeyError):
            continue
        if not math.isfinite(count) or count < 0:
            continue
        clean_rows.append({"date": str(row.get("date", "")), "count": count, "variableValues": row.get("variableValues") or {}})
    clean_rows.sort(key=lambda row: row["date"])
    if len(clean_rows) < 3:
        raise ValueError("Data hitungan valid belum cukup.")
    values = [row["count"] for row in clean_rows]
    candidates = []
    for method in METHODS:
        error = walk_forward_error(method, values)
        if error is not None:
            candidates.append({"name": method, "mae": error, "prediction": model_forecast(method, values, horizon)})
    selected_variable_used = False
    variable_id = payload.get("variableId")
    future_value = payload.get("futureVariableValue")
    if variable_id and future_value is not None:
        try:
            future_x = float(future_value)
        except (TypeError, ValueError):
            future_x = float("nan")
        var_model = variable_candidate(clean_rows, str(variable_id))
        if var_model and math.isfinite(future_x):
            candidates.append({"name": "Regresi variabel tunggal", "mae": var_model["mae"], "prediction": linear_predict(var_model["fit"], future_x)})
    if not candidates:
        estimate = model_forecast("Weighted moving average", values, horizon)
        best = {"name": "Weighted moving average", "mae": None, "prediction": estimate}
        quality = "Estimasi awal · belum cukup uji balik"
    else:
        candidates.sort(key=lambda item: item["mae"])
        best = candidates[0]
        quality = "Evaluasi historis tersedia"
        selected_variable_used = best["name"] == "Regresi variabel tunggal"
    prediction = max(0.0, best["prediction"])
    mae = best["mae"]
    spread = max(0.0, mae * 1.28) if mae is not None else None
    lower = max(0.0, prediction - spread) if spread is not None else None
    upper = prediction + spread if spread is not None else None
    return {
        "ok": True,
        "bestMethod": "Regresi variabel tunggal" if selected_variable_used else best["name"],
        "prediction": prediction,
        "mae": mae,
        "range": spread,
        "lower": lower,
        "upper": upper,
        "n": len(values),
        "horizon": horizon,
        "quality": quality,
        "selectedVariableUsed": selected_variable_used,
        "comparison": [{"name": item["name"], "mae": item["mae"]} for item in candidates],
    }


class NalarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            body = json.dumps({"ok": True, "service": "nalar-python-forecast", "version": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/forecast":
            self.send_error(404, "Endpoint tidak ditemukan")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                raise ValueError("Ukuran permintaan tidak valid.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = forecast(payload)
            status = 200
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            result = {"ok": False, "error": str(error)}
            status = 400
        body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Avoid printing request bodies or user-entered observation values.
        super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), NalarHandler)
    print(f"NALAR server ready on port {port}")
    server.serve_forever()
