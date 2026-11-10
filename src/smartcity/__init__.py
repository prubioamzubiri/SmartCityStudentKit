"""SmartCity Student Kit: cliente Python para la API del simulador SmartCity Donostia.

>>> from smartcity import SmartCity
>>> city = SmartCity("http://localhost:8080", token="...")
>>> city.state()["simTime"]
"""
from .client import SmartCity, parse_csv, parse_sim_time
from .constants import DEFAULT_SCALE, ORIGIN_LAT, ORIGIN_LON, RestrictionMode, Scenario, SignalMode
from .errors import (AuthError, ForbiddenError, NotFoundError, PayloadTooLargeError, SmartCityConnectionError,
                     SmartCityError, ValidationError)
from .geo import distance, latlon_to_xz, xz_to_latlon

__version__ = "0.1.0"

__all__ = [
    "SmartCity", "parse_csv", "parse_sim_time",
    "RestrictionMode", "SignalMode", "Scenario", "DEFAULT_SCALE", "ORIGIN_LAT", "ORIGIN_LON",
    "SmartCityError", "SmartCityConnectionError", "ValidationError", "AuthError", "ForbiddenError", "NotFoundError",
    "PayloadTooLargeError",
    "latlon_to_xz", "xz_to_latlon", "distance",
]
