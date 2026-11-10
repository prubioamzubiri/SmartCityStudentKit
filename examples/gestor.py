#!/usr/bin/env python3
"""Gestor autónomo de ejemplo hecho con la librería ``smartcity``: lee la ciudad, decide y actúa en bucle.

Es la versión con la librería de ``examples/gestor.py`` del simulador. Ejecútalo con:

    SMARTCITY_URL=http://localhost:8080 SMARTCITY_TOKEN=... python3 examples/gestor.py

Las reglas son deliberadamente simples (umbrales fijos) para que las sustituyas por tu propia IA.
"""
import os
import time

from smartcity import SmartCity, SmartCityError

PERIOD = float(os.environ.get("PERIOD_SECONDS", "5"))  # segundos reales entre decisiones (≈ 4 min simulados)

# Punto vigilado: la zona de la Plaza Gipuzkoa. Cámbialo por el que quieras (también vale x/z en metros).
WATCH = {"lat": 43.3166, "lon": -1.9800, "radius": 200}
MIN_FLEET = 4


def manage_buses(city, log):
    """Más autobuses donde van llenos; menos donde van casi vacíos."""
    for line in city.buses.list():
        occupancy = city.buses.occupancy(line)
        if line["suspended"] or occupancy is None:
            continue  # recorrido cortado o sin servicio: cambiar la flota no ayuda
        fleet = line["fleet"]
        if occupancy > 0.75 and fleet < line["maxFleet"]:
            city.buses.set_fleet(line["id"], fleet + 1)
            log.append(f"{line['id']}: {fleet} -> {fleet + 1} autobuses (ocupación {occupancy:.0%})")
        elif occupancy < 0.3 and fleet > MIN_FLEET:
            city.buses.set_fleet(line["id"], fleet - 1)
            log.append(f"{line['id']}: {fleet} -> {fleet - 1} autobuses (ocupación {occupancy:.0%})")


def manage_zone(city, log, zone):
    """Si el punto vigilado se atasca, cierra el acceso a coches nuevos; si se despeja, lo reabre."""
    cars = city.point(**WATCH)["cars"]
    jammed = cars["count"] >= 25 and cars["stopped"] / cars["count"] > 0.4
    if jammed and zone is None:
        zone = city.restrictions.limit_zone(10, name="Gestor", **WATCH)["id"]
        log.append(f"{zone}: zona con límite de 10 coches ({cars['count']} coches, {cars['stopped']} parados)")
    elif zone is not None and cars["count"] < 10:
        city.restrictions.delete(zone)
        log.append(f"{zone}: zona reabierta ({cars['count']} coches)")
        zone = None
    return zone


def main():
    city = SmartCity()  # SMARTCITY_URL y SMARTCITY_TOKEN
    zone = None
    while True:
        log = []
        try:
            state = city.state()
            manage_buses(city, log)
            zone = manage_zone(city, log, zone)
            print(f"[{state['simTime']}] {state['cars']} coches, {state['traffic']['avgKmh']} km/h de media")
        except SmartCityError as err:
            print("Error:", err)
        for line in log:
            print("   ", line)
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
