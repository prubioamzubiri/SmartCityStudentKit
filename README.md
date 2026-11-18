# SmartCity Student Kit

Librería de Python para manejar desde un programa la API REST del simulador
[SmartCity Donostia](https://github.com/prubioamzubiri/SmartCity): leer el estado de la ciudad, descargar
históricos y actuar sobre ella (cortar calles, cambiar semáforos, mover autobuses, limitar el acceso de coches...).

- Solo usa la biblioteca estándar (Python ≥ 3.10). `pandas` es opcional, para recibir los históricos como `DataFrame`.
- Cubre todos los endpoints de la [guía de la API](https://github.com/prubioamzubiri/SmartCity/blob/main/docs/API.md).
- Las respuestas son los mismos `dict` / `list` que devuelve el servidor; los errores son excepciones con el mensaje
  del servidor.

> **¿Qué se puede cambiar y cuánto tarda?** Semáforos, autobuses, calles, tarifas de parking, furgonetas de bicis: lo
> resume [Qué podéis cambiar en la ciudad](docs/palancas.md), con cómo se evalúa.
>
> **¿Dónde probar?** La ciudad de vuestro grupo puntúa. Para explorar, entrenar y romper cosas, levantad vuestra
> propia ciudad acelerada: [Tu ciudad de pruebas](docs/ciudad-de-pruebas.md).

## Instalación

```bash
pip install git+https://github.com/prubioamzubiri/SmartCityStudentKit
```

Con pandas:

```bash
pip install "smartcity-student-kit[pandas] @ git+https://github.com/prubioamzubiri/SmartCityStudentKit"
```

O, desde una copia del repositorio, `pip install -e .`

## Primeros pasos

```python
from smartcity import SmartCity

city = SmartCity("http://localhost:8080", token="mi-token")
# Sin argumentos usa las variables SMARTCITY_URL y SMARTCITY_TOKEN (por defecto, http://localhost:8080 y sin token).

state = city.state()
print(state["simTime"], state["cars"], "coches,", state["traffic"]["avgKmh"], "km/h")
```

Las lecturas son públicas; las escrituras necesitan el token si el servidor lo tiene configurado.

### Puntos del mapa

Todo lo que pide un punto acepta `x`/`z` (metros desde el origen, `x` hacia el este y `z` hacia el sur) **o**
`lat`/`lon`:

```python
city.point(lat=43.3166, lon=-1.9800, radius=200)   # coches, peatones, autobuses y semáforos cercanos
city.point(x=97, z=188, radius=200)                  # lo mismo en metros

from smartcity import latlon_to_xz, xz_to_latlon
latlon_to_xz(43.3166, -1.98)    # (97.19, 187.98)
```

### Tiempo simulado

1 s real = 52,1 s simulados (una semana real = un año simulado).

```python
city.sim_time()          # datetime de la hora simulada
city.scale()             # 52.1
city.sleep_sim(minutes=15)   # espera ≈ 17 s reales
city.wait_until("2026-01-06T08:00")   # espera a esa hora simulada (aunque la ciudad vaya por detrás)
```

### Tu ciudad

Cada grupo tiene su propia ciudad: `state()` dice su semilla (`seed`, de la que salen su tráfico, su tiempo y sus
eventos), el segundo simulado en que arrancó (`startSeconds`) y si las escrituras necesitan token (`writeProtected`).

La **demanda** (coches y peatones en hora punta) la fija el servidor y varía un poco cada día: se puede leer en
`state()["params"]`, pero no cambiar.

Algunos detalles del simulador que importan al gestionar:

- Un semáforo **apagado** (`off`) o en **ámbar intermitente** (`flashing`) deja el cruce sin regular: los coches
  llegan despacio y ceden el paso a la calle con prioridad, y paran cuando cruzan peatones (en ámbar los peatones
  tienen prioridad y cruzan más). De noche puede ahorrar esperas; en hora punta forma colas.
- En los **pasos de cebra sin semáforo** los coches paran mientras cruza gente, más a menudo cuanta más gente hay en
  la calle.
- Los **autobuses** que se añaden a una línea tardan **40 min** en entrar en servicio (van en `pending`; `target` los
  cuenta). La flota total es fija y las horas de más sobre la flota inicial son sobrecoste.
- La **tarifa de un parking** solo cambia a las 0:00: se programa la de mañana.
- Las **furgonetas de bicis** tardan media hora o más por viaje (cargar, descargar y el trayecto).
- Los coches eligen ruta con el tráfico de ahora (evitan los atascos) y van a los lugares con actividad: zonas de
  trabajo por la mañana de los laborables; centro, Parte Vieja y playas en el tiempo libre.

## Referencia rápida

| Qué | Métodos |
| --- | --- |
| Estado general | `city.state()`, `city.health()`, `city.sim_time()`, `city.scale()`, `city.sleep_sim(...)`, `city.wait_until(hora)`, `city.docs()` |
| Cerca de un punto | `city.point(...)`, `city.roads(..., radius, limit)`, `city.road(way)` |
| Entorno | `city.weather(hours)`, `city.events(start, end, type)`, `city.holidays(start, end)` |
| Posiciones | `city.cars()`, `city.pedestrians()` |
| Autobuses | `city.buses.list()`, `.status()`, `.get("L1")`, `.route("L1")`, `.occupancy(line)`, `.set_fleet("L1", 12)`, `.track([...])`, `.history(...)` |
| Bicicletas | `city.bikes.state()`, `.stations()`, `.vans()`, `.move(origen, destino, bicis)`, `.set_capacity({"municipal/0": 20})`, `.track([...])`, `.history(...)` |
| Parkings | `city.parkings.list()`, `.set_tariff(id, precio, franjas)`, `.track([...])`, `.history(...)` |
| Sensores de coches | `city.sensors.list()`, `.create(lat=, lon=, name=)`, `.rename(id, name)`, `.delete(id)`, `.history(...)` |
| Sensores de peatones | `city.pedestrian_sensors.…` (los mismos métodos) |
| Semáforos | `city.signals.list(all=, lat=, lon=, radius=)`, `.get(id)`, `.update(id, mode=, green=, green_a=, green_b=, yellow=, schedule=)`, `.reset(id)`, `.plan()`, `.set_plan(default, signals)` |
| Restricciones | `city.restrictions.list()`, `.get(id)`, `.create(mode, ...)`, `.close_streets(ways, buses=)`, `.limit_zone(limit, radius, lat=, lon=)`, `.update(id, mode=, limit=, name=)`, `.delete(id)`, `.clear()` |
| Demanda | `city.state()["params"]` (solo lectura: la fija el servidor) |
| Históricos | `city.history.traffic()`, `.pedestrians()`, `.parking()`, `.buses()`, `.bikes()`, `.city()`, `.weather()`, `.events()`, `.download(kind, path)`, `.update(kind, path)` (incremental), `.csv(kind)` |
| Cualquier otra ruta | `city.request(method, path, params=, body=)`, `city.get(path, **params)` |

Constantes con los valores admitidos: `RestrictionMode`, `SignalMode` y `Scenario`.

## Ejemplos

### Cortar una calle

```python
from smartcity import RestrictionMode

road = city.roads(lat=43.3166, lon=-1.9800, radius=60, limit=1)[0]
closed = city.restrictions.close_streets([road["way"]], buses=True, name="Calle peatonal con bus")
...
city.restrictions.delete(closed["id"])   # reabrir
```

### Limitar el acceso de coches a una zona

```python
zone = city.restrictions.limit_zone(10, radius=300, lat=43.3166, lon=-1.98, name="Centro")
city.restrictions.update(zone["id"], limit=0)   # ya no entra ninguno
```

### Semáforos

```python
from smartcity import SignalMode

signal = city.signals.list(lat=43.3166, lon=-1.98, radius=300)[0]
city.signals.update(signal["id"], mode=SignalMode.NORMAL, green_a=45, green_b=15)
city.signals.update(signal["id"], schedule=[
    {"when": {"start": "07:00", "end": "09:00", "weekdays": [1, 2, 3, 4, 5]}, "greenA": 40},
])
city.signals.update(signal["id"], green_a=None)   # None quita un ajuste
city.signals.reset(signal["id"])                  # quita todos
```

### Autobuses

```python
status = city.buses.status()                  # reserva, horas de autobús del día, minutos hasta entrar en servicio
for line in status["lines"]:
    occ = city.buses.occupancy(line)          # pasajeros / plazas en servicio (None si no hay servicio)
    # `target` cuenta los que van de camino (tardan 40 min): compara con él, no con `fleet`.
    if occ and occ > 0.75 and line["target"] < line["maxFleet"] and status["reserve"] > 0:
        city.buses.set_fleet(line["id"], line["target"] + 1)

city.buses.route("L1")["stops"]               # paradas con x, z: qué líneas pasan cerca de un evento
```

### Parkings y bicis

```python
# Tarifa de mañana (se aplica a las 0:00): 2 €/h y 5 €/h de 17 a 22 h (por ejemplo, si hay un partido cerca).
city.parkings.set_tariff("U-125_53", 2, [{"from": "17:00", "to": "22:00", "price": 5}])

# Una furgoneta lleva 15 bicis de un puesto a otro (tarda media hora o más).
city.bikes.move("municipal/3", "municipal/17", 15)
```

### Históricos

Solo se graba lo que actives y desde que lo actives (salvo `city`, `weather` y `events`, siempre disponibles):

```python
sensor = city.sensors.create(lat=43.3166, lon=-1.98, name="Plaza Gipuzkoa")
city.buses.track(["L1", "L2"])
city.sleep_sim(hours=2)

rows = city.history.traffic(start="2026-01-05T08:00", end="2026-01-06", sensor_id=sensor["id"])
rows[0]["count"], rows[0]["avg_speed_kmh"]       # números ya convertidos

df = city.history.city(dataframe=True)           # pandas.DataFrame con timestamp como fecha
city.history.download("buses", "autobuses.csv", line_id="L1")
```

Las fechas pueden ser texto ISO (`"2026-01-05"`, `"2026-01-05T08:00"`), `date` o `datetime`; son horas simuladas,
`start` incluida y `end` excluida.

### Recoger datos poco a poco

Durante el proyecto se acumulan años simulados de datos: no hace falta descargarlo todo cada vez.
`history.update(kind, path)` añade a un CSV solo las filas nuevas desde la última que tiene (la primera vez lo crea
con todo). Devuelve cuántas filas ha añadido:

```python
city.history.update("city", "datos/ciudad.csv")
city.history.update("traffic", "datos/trafico_S1.csv", id="S1")   # un fichero por filtro
city.history.update("weather", "datos/tiempo.csv")
```

Ejecútalo cada cierto tiempo (a mano, con `cron` o en un bucle: ver [`examples/recoger.py`](examples/recoger.py)).
Cada fila se graba cuando su intervalo termina, así que nunca llega una a medias; los eventos (`events`) no admiten
descarga incremental porque su asistencia se publica al terminar. Con la API directamente es lo mismo: pide
`?from=` la última hora que tienes más un segundo (`from` es inclusivo).

### Errores

```python
from smartcity import SmartCityError, AuthError, ValidationError, NotFoundError, ForbiddenError, ConflictError

try:
    city.buses.set_fleet("L1", 99)
except ValidationError as err:
    print(err.status, err.message)    # 400 fleet debe ser un entero entre 1 y 30
```

| Excepción | Cuándo |
| --- | --- |
| `ValidationError` | 400 / 422: datos no válidos o no hay calle cerca del punto |
| `AuthError` | 401: falta el token o no es válido |
| `ForbiddenError` | 403: acción bloqueada (p. ej. `LOCK_PARAMS=1`) |
| `NotFoundError` | 404: sensor, semáforo, calle, línea o restricción inexistente |
| `ConflictError` | 409: no quedan autobuses en la reserva, no hay ninguna furgoneta libre |
| `PayloadTooLargeError` | 413: cuerpo mayor de 64 KB |
| `SmartCityConnectionError` | No se puede contactar con el servidor |

Todas heredan de `SmartCityError`.

### Gestor autónomo

[`examples/gestor.py`](examples/gestor.py) es el gestor de ejemplo del simulador reescrito con la librería
(leer → decidir → actuar en bucle) y [`examples/historicos.py`](examples/historicos.py) activa registros y descarga
los CSV.

```bash
SMARTCITY_URL=http://localhost:8080 SMARTCITY_TOKEN=... python3 examples/gestor.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Los tests levantan un servidor HTTP local que imita la API, así que no hace falta el simulador.
