"""Valores admitidos por la API (ver docs/API.md del simulador)."""

#: Origen del mapa: ``x`` crece hacia el este y ``z`` hacia el sur, en metros.
ORIGIN_LAT = 43.3183
ORIGIN_LON = -1.9812

#: 1 segundo real = 52,1 segundos simulados (por defecto; el real está en ``state()["scale"]``).
DEFAULT_SCALE = 52.1


class RestrictionMode:
    """Modos de ``POST /api/restrictions``."""

    PEDESTRIANS_ONLY = "pedestrians_only"            #: no pasan coches ni autobuses
    BUSES_AND_PEDESTRIANS = "buses_and_pedestrians"  #: no pasan coches; los autobuses sí
    ENTRY_LIMIT = "entry_limit"                      #: solo entran coches si hay menos de ``limit`` dentro
    ALL = (PEDESTRIANS_ONLY, BUSES_AND_PEDESTRIANS, ENTRY_LIMIT)


class SignalMode:
    """Modos de ``PATCH /api/signals/<id>``."""

    NORMAL = "normal"      #: ciclo normal
    OFF = "off"            #: apagado: nadie se detiene
    FLASHING = "flashing"  #: ámbar intermitente: nadie se detiene
    ALL_RED = "all_red"    #: todos se detienen
    ALL = (NORMAL, OFF, FLASHING, ALL_RED)


class Scenario:
    """Escenarios de demanda de ``PUT /api/params``."""

    AUTO = "auto"
    WEEKDAY = "weekday"
    PREHOLIDAY = "preholiday"
    WEEKEND = "weekend"
    SUNDAY = "sunday"
    ALL = (AUTO, WEEKDAY, PREHOLIDAY, WEEKEND, SUNDAY)


#: Históricos CSV: nombre -> ruta.
HISTORIES = {
    "traffic": "/api/traffic.csv",
    "pedestrians": "/api/pedestrians.csv",
    "parking": "/api/parking.csv",
    "buses": "/api/buses.csv",
    "bikes": "/api/bikes.csv",
    "city": "/api/city.csv",
    "weather": "/api/weather.csv",
    "events": "/api/events.csv",
}
