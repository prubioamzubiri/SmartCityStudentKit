"""Servidor HTTP de prueba que imita la API de SmartCity y registra las peticiones recibidas."""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "secreto"

STATE = {
    "scale": 52.1, "simSeconds": 30600, "simTime": "2026-01-05T08:30:00", "caughtUp": True, "cars": 812,
    "params": {"maxCars": 1500, "maxPedestrians": 12000, "scenario": "auto"},
    "traffic": {"stopped": 120, "avgKmh": 23.4}, "signalPlan": {"default": {}, "signals": {}},
    "sensors": [{"id": "S1", "name": "Avenida", "x": 10.0, "z": -5.0, "total": 400, "current": 3}],
    "pedestrianSensors": [{"id": "P1", "name": "Boulevard", "x": 0.0, "z": 0.0, "total": 90, "current": 7}],
    "parkings": [{"id": "U-1", "name": "Centro", "capacity": 300, "occupancy": 0.5, "tracked": False}],
    "restrictions": [], "writeProtected": True, "paramsLocked": False,
}
BUSES = {"lines": [
    {"id": "L1", "fleet": 6, "minFleet": 1, "maxFleet": 30, "capacity": 80, "active": 4, "passengers": 160,
     "full": 0, "waiting": 12, "suspended": False, "tracked": False},
    {"id": "L2", "fleet": 3, "minFleet": 1, "maxFleet": 30, "capacity": 80, "active": 0, "passengers": 0,
     "full": 0, "waiting": 0, "suspended": True, "tracked": False},
]}
TRAFFIC_CSV = ("timestamp,weekday,sensor_id,sensor_name,x,z,count,count_fwd,count_bwd,avg_speed_kmh\n"
               "2026-01-05T08:00:00,1,S1,Avenida,10,-5,42,20,22,31.5\n"
               "2026-01-05T08:05:00,1,S1,Avenida,10,-5,40,19,21,\n")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self):
        url = urllib.parse.urlsplit(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else None
        self.server.calls.append({"method": self.command, "path": url.path, "query": query, "body": body,
                                  "auth": self.headers.get("Authorization")})
        method, path = self.command, url.path

        if method != "GET" and self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(401, {"error": "Token no válido"})
        if method == "GET" and path == "/api/health":
            return self._send(200, {"ok": True})
        if method == "GET" and path == "/api/state":
            return self._send(200, STATE)
        if method == "GET" and path == "/api/docs.md":
            return self._send(200, "# API", "text/markdown")
        if method == "GET" and path == "/api/point":
            if not ({"x", "z"} <= query.keys() or {"lat", "lon"} <= query.keys()):
                return self._send(400, {"error": "Indica el punto con x y z (metros) o con lat y lon"})
            return self._send(200, {"cars": {"count": 30, "stopped": 15, "avgKmh": 8}, "pedestrians": {"count": 50},
                                    "radius": float(query.get("radius", 50)), "signals": []})
        if method == "GET" and path == "/api/roads":
            return self._send(200, {"roads": [{"way": 2325, "class": "primary", "distance": 4.2}]})
        if method == "GET" and path == "/api/roads/2325":
            return self._send(200, {"way": 2325, "class": "primary"})
        if method == "GET" and path == "/api/buses":
            return self._send(200, BUSES)
        if method == "PATCH" and path.startswith("/api/buses/"):
            if path != "/api/buses/L1":
                return self._send(404, {"error": "Línea no encontrada"})
            return self._send(200, {"id": "L1", "fleet": body["fleet"]})
        if method == "PUT" and path.endswith("/tracked"):
            return self._send(200, {"tracked": body["ids"]})
        if method == "GET" and path == "/api/bikes":
            return self._send(200, {"inUse": 5, "stations": [{"id": "municipal/0", "available": 4, "capacity": 10}]})
        if method == "PUT" and path == "/api/bikes/capacity":
            return self._send(200, {"inUse": 5, "stations": []})
        if method == "GET" and path == "/api/signals":
            return self._send(200, {"signals": [{"id": 13965274528, "mode": "normal"}]})
        if path.startswith("/api/signals/") and path != "/api/signals/plan":
            return self._send(200, {"id": int(path.rsplit("/", 1)[1]), "override": body})
        if method == "PUT" and path == "/api/signals/plan":
            return self._send(200, body["plan"])
        if method == "GET" and path == "/api/restrictions":
            return self._send(200, {"restrictions": [{"id": "R1"}, {"id": "R2"}]})
        if method == "POST" and path == "/api/restrictions":
            return self._send(201, {"id": "R3", **body})
        if path.startswith("/api/restrictions/"):
            return self._send(200, {"ok": True} if method == "DELETE" else {"id": path.rsplit("/", 1)[1]})
        if method == "POST" and path in ("/api/sensors", "/api/pedestrian-sensors"):
            return self._send(201, {"id": "S2" if path == "/api/sensors" else "P2", "name": body.get("name", "")})
        if path.startswith(("/api/sensors/", "/api/pedestrian-sensors/")):
            return self._send(200, {"ok": True})
        if method == "PUT" and path == "/api/params":
            return self._send(403, {"error": "Los parámetros de demanda están bloqueados en este servidor"})
        if method == "GET" and path.endswith(".csv"):
            return self._send(200, TRAFFIC_CSV, "text/csv; charset=utf-8")
        if method == "GET" and path == "/api/events":
            return self._send(200, {"events": [{"id": "E1"}]})
        if method == "GET" and path == "/api/holidays":
            return self._send(200, {"holidays": [{"date": "2026-01-20", "name": "San Sebastián"}]})
        if method == "GET" and path == "/api/weather":
            return self._send(200, {"current": {"condition": "rain"}, "forecast": []})
        return self._send(404, {"error": "No encontrado"})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle


class FakeServer:
    def __enter__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.calls = []
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        return self

    @property
    def calls(self):
        return self.httpd.calls

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
