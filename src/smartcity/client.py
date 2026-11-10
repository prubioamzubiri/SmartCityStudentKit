"""Cliente de la API REST de SmartCity.

Uso básico::

    from smartcity import SmartCity

    city = SmartCity("http://localhost:8080", token="...")   # o variables SMARTCITY_URL / SMARTCITY_TOKEN
    state = city.state()
    print(state["simTime"], state["cars"], state["traffic"]["avgKmh"])

    near = city.point(lat=43.3166, lon=-1.98, radius=200)
    city.restrictions.create("entry_limit", lat=43.3166, lon=-1.98, radius=300, limit=10)
    city.buses.set_fleet("L1", 12)
    rows = city.history.traffic(start="2026-01-05", end="2026-01-06")

Todas las respuestas JSON se devuelven tal cual como ``dict`` / ``list`` (los campos están descritos en
``docs/API.md`` del simulador, también en ``city.docs()``). Los errores lanzan :class:`SmartCityError` o una subclase.
"""
import csv
import datetime as _dt
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .constants import DEFAULT_SCALE, HISTORIES, RestrictionMode
from .errors import SmartCityConnectionError, SmartCityError, error_for_status

__all__ = ["SmartCity"]

_UNSET = object()


# --------------------------------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------------------------------

def _point(x=None, z=None, lat=None, lon=None):
    """Parámetros de un punto: ``x`` y ``z`` (metros) o ``lat`` y ``lon``."""
    if x is not None and z is not None:
        return {"x": x, "z": z}
    if lat is not None and lon is not None:
        return {"lat": lat, "lon": lon}
    raise ValueError("Indica el punto con x y z (metros) o con lat y lon")


def _time(value):
    """Fecha simulada para ``from`` / ``to``: acepta ``str`` ISO, ``datetime`` o ``date``."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, _dt.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(value, _dt.date):
        return value.strftime("%Y-%m-%d")
    raise TypeError("Las fechas deben ser str (AAAA-MM-DD[THH:MM[:SS]]), datetime o date")


def _number(text):
    """Convierte las celdas numéricas de un CSV; deja el resto como texto (vacío -> None)."""
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_csv(text, convert=True):
    """Convierte un CSV de la API en una lista de ``dict`` (con números si ``convert``)."""
    reader = csv.DictReader(io.StringIO(text))
    if not convert:
        return list(reader)
    return [{k: _number(v) for k, v in row.items()} for row in reader]


def parse_sim_time(value):
    """``"2026-01-05T08:30:00"`` -> ``datetime`` (sin zona horaria: es la hora simulada)."""
    return _dt.datetime.fromisoformat(value)


# --------------------------------------------------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------------------------------------------------

class SmartCity:
    """Conexión con un servidor SmartCity.

    :param url: URL base (por defecto ``$SMARTCITY_URL`` o ``http://localhost:8080``).
    :param token: token de escritura (por defecto ``$SMARTCITY_TOKEN``). Las lecturas no lo necesitan.
    :param timeout: segundos máximos por petición.
    """

    def __init__(self, url=None, token=None, timeout=30.0):
        self.url = (url or os.environ.get("SMARTCITY_URL") or "http://localhost:8080").rstrip("/")
        self.token = os.environ.get("SMARTCITY_TOKEN", "") if token is None else token
        self.timeout = timeout

        self.sensors = Sensors(self, "/api/sensors", "traffic")
        self.pedestrian_sensors = Sensors(self, "/api/pedestrian-sensors", "pedestrians")
        self.parkings = Parkings(self)
        self.buses = Buses(self)
        self.bikes = Bikes(self)
        self.signals = Signals(self)
        self.restrictions = Restrictions(self)
        self.history = History(self)

    def __repr__(self):
        return f"SmartCity({self.url!r}, token={'***' if self.token else None})"

    # -- transporte ---------------------------------------------------------------------------------------------------

    def request(self, method, path, params=None, body=None, raw=False):
        """Petición genérica. Devuelve el JSON decodificado (o el texto si ``raw``).

        ``params`` se añade a la URL (se ignoran los ``None``); ``body`` se envía como JSON.
        """
        query = {k: v for k, v in (params or {}).items() if v is not None}
        url = self.url + path + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = {"Accept": "text/csv, application/json" if raw else "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            text = err.read().decode("utf-8", "replace")
            try:
                message = json.loads(text).get("error", text)
            except (ValueError, AttributeError):
                message = text or err.reason
            raise error_for_status(err.code, message, method, path) from None
        except (urllib.error.URLError, OSError) as err:
            reason = getattr(err, "reason", err)
            raise SmartCityConnectionError(f"No se puede conectar con {self.url}: {reason}", method=method, path=path) from None
        if raw:
            return payload
        return json.loads(payload) if payload else None

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def _write(self, method, path, body=None):
        return self.request(method, path, body={} if body is None and method != "DELETE" else body)

    # -- estado y reloj -----------------------------------------------------------------------------------------------

    def health(self):
        """``True`` si el servidor responde."""
        try:
            return bool(self.get("/api/health").get("ok"))
        except SmartCityError:
            return False

    def state(self):
        """Resumen de toda la ciudad (``GET /api/state``)."""
        return self.get("/api/state")

    def sim_time(self):
        """Hora simulada actual como ``datetime``."""
        return parse_sim_time(self.state()["simTime"])

    def scale(self):
        """Segundos simulados por segundo real (52,1 por defecto)."""
        return float(self.state().get("scale") or DEFAULT_SCALE)

    def sleep_sim(self, seconds=0, minutes=0, hours=0, scale=None):
        """Espera el tiempo real equivalente a un intervalo **simulado** (``sleep_sim(minutes=15)`` ≈ 17 s reales)."""
        total = seconds + 60 * minutes + 3600 * hours
        time.sleep(max(0.0, total / (scale or self.scale())))

    def docs(self):
        """Guía de la API en Markdown (``GET /api/docs.md``)."""
        return self.request("GET", "/api/docs.md", raw=True)

    # -- lecturas puntuales --------------------------------------------------------------------------------------------

    def point(self, x=None, z=None, lat=None, lon=None, radius=None):
        """Qué hay ahora cerca de un punto: coches, peatones, autobuses y semáforos (``radius`` 1–2000 m, def. 50)."""
        return self.get("/api/point", radius=radius, **_point(x, z, lat, lon))

    def roads(self, x=None, z=None, lat=None, lon=None, radius=None, limit=None):
        """Calles cercanas a un punto, de la más cercana a la más lejana. Cada una trae su ``way``."""
        return self.get("/api/roads", radius=radius, limit=limit, **_point(x, z, lat, lon))["roads"]

    def road(self, way):
        """Una calle por su identificador ``way``."""
        return self.get(f"/api/roads/{int(way)}")

    def cars(self):
        """Posiciones de los coches (``GET /api/cars``)."""
        return self.get("/api/cars")

    def pedestrians(self):
        """Posiciones de los peatones (``GET /api/pedestrians``)."""
        return self.get("/api/pedestrians")

    def weather(self, hours=None):
        """Tiempo actual y previsión horaria (``hours`` 1–48)."""
        return self.get("/api/weather", hours=hours)

    def events(self, start=None, end=None, type=None):
        """Eventos entre dos fechas simuladas (por defecto, los próximos 30 días)."""
        return self.get("/api/events", **{"from": _time(start), "to": _time(end), "type": type})["events"]

    def holidays(self, start=None, end=None):
        """Festivos entre dos fechas (por defecto, el próximo año)."""
        return self.get("/api/holidays", **{"from": _time(start), "to": _time(end)})["holidays"]

    # -- parámetros globales --------------------------------------------------------------------------------------------

    def set_params(self, max_cars=None, max_pedestrians=None, scenario=None):
        """Cambia la demanda (``PUT /api/params``). Lanza :class:`ForbiddenError` si el servidor la bloquea."""
        body = {k: v for k, v in {"maxCars": max_cars, "maxPedestrians": max_pedestrians, "scenario": scenario}.items()
                if v is not None}
        return self._write("PUT", "/api/params", body)


class _Resource:
    def __init__(self, city):
        self._city = city


# --------------------------------------------------------------------------------------------------------------------
# Sensores
# --------------------------------------------------------------------------------------------------------------------

class Sensors(_Resource):
    """Sensores de coches (``city.sensors``) o de peatones (``city.pedestrian_sensors``)."""

    def __init__(self, city, path, history):
        super().__init__(city)
        self._path = path
        self._history = history
        self._state_key = "sensors" if history == "traffic" else "pedestrianSensors"

    def list(self):
        """Sensores colocados, con ``total`` acumulado y ``current``."""
        return self._city.state()[self._state_key]

    def create(self, x=None, z=None, lat=None, lon=None, name=""):
        """Coloca un sensor en la calle más cercana al punto. Devuelve ``{id, name, x, z}``."""
        return self._city._write("POST", self._path, {**_point(x, z, lat, lon), "name": name})

    def rename(self, sensor_id, name):
        return self._city._write("PATCH", f"{self._path}/{sensor_id}", {"name": name})

    def delete(self, sensor_id):
        return self._city._write("DELETE", f"{self._path}/{sensor_id}")

    def history(self, start=None, end=None, sensor_id=None, **kwargs):
        """Histórico CSV de los sensores (ver :meth:`History.get`)."""
        return self._city.history.get(self._history, start, end, id=sensor_id, **kwargs)


# --------------------------------------------------------------------------------------------------------------------
# Parkings
# --------------------------------------------------------------------------------------------------------------------

class Parkings(_Resource):
    """Parkings subterráneos (``city.parkings``)."""

    def list(self):
        """Parkings con ``capacity``, ``occupancy`` (0–1) y ``tracked``."""
        return self._city.state()["parkings"]

    def track(self, ids):
        """Graba la ocupación de estos parkings. **Sustituye** la lista anterior."""
        return self._city._write("PUT", "/api/parking/tracked", {"ids": list(ids)})["tracked"]

    def history(self, start=None, end=None, parking_id=None, **kwargs):
        return self._city.history.get("parking", start, end, id=parking_id, **kwargs)


# --------------------------------------------------------------------------------------------------------------------
# Autobuses
# --------------------------------------------------------------------------------------------------------------------

class Buses(_Resource):
    """Líneas de autobús (``city.buses``)."""

    def list(self):
        """Estado de cada línea: ``fleet``, ``active``, ``passengers``, ``waiting``, ``suspended``..."""
        return self._city.get("/api/buses")["lines"]

    def get(self, line_id):
        for line in self.list():
            if line["id"] == line_id:
                return line
        raise error_for_status(404, "Línea no encontrada", "GET", "/api/buses")

    @staticmethod
    def occupancy(line):
        """Ocupación de una línea (0–1): pasajeros / plazas en servicio. ``None`` si no hay autobuses en servicio."""
        seats = (line.get("active") or 0) * (line.get("capacity") or 0)
        return line.get("passengers", 0) / seats if seats else None

    def set_fleet(self, line_id, fleet):
        """Fija el número de autobuses de la línea (entre ``minFleet`` y ``maxFleet``)."""
        return self._city._write("PATCH", f"/api/buses/{line_id}", {"fleet": int(fleet)})

    def track(self, ids):
        """Graba estas líneas cada 5 min simulados. **Sustituye** la lista anterior."""
        return self._city._write("PUT", "/api/buses/tracked", {"ids": list(ids)})["tracked"]

    def history(self, start=None, end=None, line_id=None, **kwargs):
        return self._city.history.get("buses", start, end, id=line_id, **kwargs)


# --------------------------------------------------------------------------------------------------------------------
# Bicicletas
# --------------------------------------------------------------------------------------------------------------------

class Bikes(_Resource):
    """Bicicletas compartidas (``city.bikes``)."""

    def state(self):
        """``inUse`` y ``stations`` (``available``, ``capacity``, ``pending``...)."""
        return self._city.get("/api/bikes")

    def stations(self):
        return self.state()["stations"]

    def set_capacity(self, changes):
        """Cambia los anclajes (1–60) de varios puestos: ``{"municipal/0": 20, "municipal/5": None}``.

        ``None`` cancela un cambio pendiente. Tarda 30 días simulados en aplicarse. Todo o nada.
        """
        return self._city._write("PUT", "/api/bikes/capacity", {"changes": dict(changes)})

    def track(self, ids):
        """Graba estos puestos cada 15 min simulados. **Sustituye** la lista anterior."""
        return self._city._write("PUT", "/api/bikes/tracked", {"ids": list(ids)})["tracked"]

    def history(self, start=None, end=None, station_id=None, **kwargs):
        return self._city.history.get("bikes", start, end, id=station_id, **kwargs)


# --------------------------------------------------------------------------------------------------------------------
# Semáforos
# --------------------------------------------------------------------------------------------------------------------

_SIGNAL_FIELDS = {"mode": "mode", "green": "green", "green_a": "greenA", "green_b": "greenB",
                  "yellow": "yellow", "schedule": "schedule"}


class Signals(_Resource):
    """Semáforos (``city.signals``)."""

    def list(self, all=False, x=None, z=None, lat=None, lon=None, radius=None):
        """Semáforos con ciclo. ``all=True`` incluye los pasos de peatones; con punto y ``radius`` filtra por zona."""
        params = {"all": 1 if all else None}
        if radius is not None:
            params.update(radius=radius, **_point(x, z, lat, lon))
        return self._city.get("/api/signals", **params)["signals"]

    def get(self, signal_id):
        return self._city.get(f"/api/signals/{int(signal_id)}")

    def update(self, signal_id, mode=_UNSET, green=_UNSET, green_a=_UNSET, green_b=_UNSET, yellow=_UNSET,
               schedule=_UNSET):
        """Cambia los ajustes de un semáforo. Los campos no indicados se conservan; ``None`` quita un ajuste.

        ``green_a`` = verde del eje este-oeste, ``green_b`` = norte-sur (5–180 s); ``yellow`` 1–10 s;
        ``mode`` en :class:`SignalMode`; ``schedule`` lista de reglas con horario.
        """
        values = locals()
        body = {api: values[name] for name, api in _SIGNAL_FIELDS.items() if values[name] is not _UNSET}
        if not body:
            raise ValueError("Indica al menos un campo que cambiar")
        return self._city._write("PATCH", f"/api/signals/{int(signal_id)}", body)

    def reset(self, signal_id):
        """Borra todos los ajustes propios del semáforo."""
        return self._city._write("PATCH", f"/api/signals/{int(signal_id)}", {"reset": True})

    def plan(self):
        """Plan de semáforos actual (``signalPlan`` de ``state()``)."""
        return self._city.state()["signalPlan"]

    def set_plan(self, default=None, signals=None):
        """Sustituye **todo** el plan: ``default`` para los semáforos sin ajustes y ``signals`` ``{id: ajustes}``."""
        plan = {"default": default or {}, "signals": {str(k): v for k, v in (signals or {}).items()}}
        return self._city._write("PUT", "/api/signals/plan", {"plan": plan})


# --------------------------------------------------------------------------------------------------------------------
# Restricciones
# --------------------------------------------------------------------------------------------------------------------

class Restrictions(_Resource):
    """Cortes de calle y zonas de acceso restringido (``city.restrictions``)."""

    def list(self):
        return self._city.get("/api/restrictions")["restrictions"]

    def get(self, restriction_id):
        return self._city.get(f"/api/restrictions/{restriction_id}")

    def create(self, mode, x=None, z=None, lat=None, lon=None, radius=None, ways=None, limit=None, name=None):
        """Crea una restricción sobre una zona circular (punto + ``radius``) o sobre calles (``ways``).

        ``mode`` en :class:`RestrictionMode`; ``limit`` solo para ``entry_limit``. Devuelve la restricción con su ``id``.
        """
        if mode not in RestrictionMode.ALL:
            raise ValueError(f"mode debe ser uno de: {', '.join(RestrictionMode.ALL)}")
        body = {"mode": mode}
        if ways is not None:
            body["ways"] = [int(w) for w in ways]
        else:
            if radius is None:
                raise ValueError("Indica ways o una zona (punto y radius)")
            body.update(_point(x, z, lat, lon), radius=radius)
        if limit is not None:
            body["limit"] = limit
        if name is not None:
            body["name"] = name
        return self._city._write("POST", "/api/restrictions", body)

    def close_streets(self, ways, buses=False, name=None):
        """Corta calles concretas: solo peatones, o también autobuses si ``buses=True``."""
        mode = RestrictionMode.BUSES_AND_PEDESTRIANS if buses else RestrictionMode.PEDESTRIANS_ONLY
        return self.create(mode, ways=ways, name=name)

    def limit_zone(self, limit, radius, x=None, z=None, lat=None, lon=None, name=None):
        """Zona circular donde solo entran coches mientras haya menos de ``limit`` dentro."""
        return self.create(RestrictionMode.ENTRY_LIMIT, x=x, z=z, lat=lat, lon=lon, radius=radius, limit=limit, name=name)

    def update(self, restriction_id, mode=None, limit=None, name=None):
        """Cambia el modo, el límite o el nombre (la zona no se cambia)."""
        body = {k: v for k, v in {"mode": mode, "limit": limit, "name": name}.items() if v is not None}
        return self._city._write("PATCH", f"/api/restrictions/{restriction_id}", body)

    def delete(self, restriction_id):
        """Quita la restricción: la calle se reabre."""
        return self._city._write("DELETE", f"/api/restrictions/{restriction_id}")

    def clear(self):
        """Quita todas las restricciones activas. Devuelve los ids borrados."""
        ids = [r["id"] for r in self.list()]
        for restriction_id in ids:
            self.delete(restriction_id)
        return ids


# --------------------------------------------------------------------------------------------------------------------
# Históricos CSV
# --------------------------------------------------------------------------------------------------------------------

class History(_Resource):
    """Históricos CSV (``city.history``). Las fechas son horas simuladas; ``start`` incluida, ``end`` excluida.

    Cada método devuelve una lista de ``dict`` con los números ya convertidos, o un ``pandas.DataFrame`` con
    ``dataframe=True`` (necesita ``pip install pandas``).
    """

    KINDS = tuple(HISTORIES)

    def csv(self, kind, start=None, end=None, **params):
        """Texto CSV sin procesar."""
        if kind not in HISTORIES:
            raise ValueError(f"kind debe ser uno de: {', '.join(HISTORIES)}")
        query = {"from": _time(start), "to": _time(end), **params}
        return self._city.request("GET", HISTORIES[kind], params=query, raw=True)

    def get(self, kind, start=None, end=None, dataframe=False, **params):
        text = self.csv(kind, start, end, **params)
        if dataframe:
            try:
                import pandas as pd
            except ImportError:  # pragma: no cover - depende del entorno
                raise ImportError("dataframe=True necesita pandas: pip install pandas") from None
            frame = pd.read_csv(io.StringIO(text))
            for column in ("timestamp", "time", "start", "end"):
                if column in frame.columns:
                    frame[column] = pd.to_datetime(frame[column], errors="coerce")
            return frame
        return parse_csv(text)

    def download(self, kind, path, start=None, end=None, **params):
        """Guarda el CSV en ``path`` y devuelve la ruta."""
        text = self.csv(kind, start, end, **params)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def traffic(self, start=None, end=None, sensor_id=None, **kwargs):
        """Coches por sensor cada 5 min: ``count``, ``count_fwd``, ``count_bwd``, ``avg_speed_kmh``."""
        return self.get("traffic", start, end, id=sensor_id, **kwargs)

    def pedestrians(self, start=None, end=None, sensor_id=None, **kwargs):
        """Peatones por sensor: ``count``, ``count_walk``, ``count_cross``, ``present``."""
        return self.get("pedestrians", start, end, id=sensor_id, **kwargs)

    def parking(self, start=None, end=None, parking_id=None, **kwargs):
        return self.get("parking", start, end, id=parking_id, **kwargs)

    def buses(self, start=None, end=None, line_id=None, **kwargs):
        return self.get("buses", start, end, id=line_id, **kwargs)

    def bikes(self, start=None, end=None, station_id=None, **kwargs):
        return self.get("bikes", start, end, id=station_id, **kwargs)

    def city(self, start=None, end=None, **kwargs):
        """Toda la ciudad cada 5 min (coches, velocidad, autobuses, bicis, cortes, viajes y retrasos...)."""
        return self.get("city", start, end, **kwargs)

    def weather(self, start=None, end=None, **kwargs):
        """Tiempo observado hora a hora (por defecto, los últimos 7 días simulados)."""
        return self.get("weather", start, end, **kwargs)

    def events(self, start=None, end=None, type=None, **kwargs):
        return self.get("events", start, end, type=type, **kwargs)
