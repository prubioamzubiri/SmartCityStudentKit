"""Conversión entre latitud/longitud y las coordenadas del mapa (metros desde el origen).

Es la misma proyección que usa el simulador (``src/city/projection.js``): ``x`` crece hacia el este y ``z`` hacia el
sur. La API acepta las dos formas, así que solo hace falta convertir para cálculos propios (distancias, rejillas...).
"""
import math

from .constants import ORIGIN_LAT, ORIGIN_LON

_K_LAT = 110574.0


def _k_lon(origin_lat):
    return 111320.0 * math.cos(math.radians(origin_lat))


def latlon_to_xz(lat, lon, origin=(ORIGIN_LAT, ORIGIN_LON)):
    """Devuelve ``(x, z)`` en metros para una latitud y longitud."""
    o_lat, o_lon = origin
    return (lon - o_lon) * _k_lon(o_lat), -(lat - o_lat) * _K_LAT


def xz_to_latlon(x, z, origin=(ORIGIN_LAT, ORIGIN_LON)):
    """Devuelve ``(lat, lon)`` para un punto del mapa en metros."""
    o_lat, o_lon = origin
    return o_lat - z / _K_LAT, o_lon + x / _k_lon(o_lat)


def distance(a, b):
    """Distancia en metros entre dos puntos ``(x, z)`` del mapa."""
    return math.hypot(a[0] - b[0], a[1] - b[1])
