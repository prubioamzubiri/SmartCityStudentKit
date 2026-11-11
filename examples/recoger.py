#!/usr/bin/env python3
"""Recoge los históricos de la ciudad poco a poco en la carpeta ``datos/``: cada vez solo descarga lo nuevo.

    SMARTCITY_URL=http://localhost:8080 python3 examples/recoger.py            # una vez
    SMARTCITY_URL=http://localhost:8080 python3 examples/recoger.py --cada 10  # cada 10 minutos reales
"""
import argparse
import os
import time

from smartcity import SmartCity, SmartCityError

FILES = {"city": "ciudad.csv", "weather": "tiempo.csv", "buses": "autobuses.csv", "bikes": "bicis.csv",
         "parking": "parkings.csv"}


def recoger(city, folder):
    """Añade a cada CSV de ``folder`` las filas nuevas. Devuelve {fichero: filas añadidas}."""
    os.makedirs(folder, exist_ok=True)
    added = {}
    for kind, name in FILES.items():
        added[name] = city.history.update(kind, os.path.join(folder, name))
    # Un fichero por sensor, para poder borrar o añadir sensores sin mezclar sus datos.
    for prefix, kind, sensors in (("trafico", "traffic", city.sensors.list()),
                                  ("peatones", "pedestrians", city.pedestrian_sensors.list())):
        for sensor in sensors:
            name = f"{prefix}_{sensor['id']}.csv"
            added[name] = city.history.update(kind, os.path.join(folder, name), id=sensor["id"])
    return added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--carpeta", default="datos")
    parser.add_argument("--cada", type=float, default=0, help="minutos reales entre descargas (0 = solo una vez)")
    args = parser.parse_args()
    city = SmartCity()
    while True:
        try:
            print("Hora simulada:", city.sim_time())
            for name, count in recoger(city, args.carpeta).items():
                print(f"  {name}: +{count} filas")
        except SmartCityError as err:  # el servidor no responde: se reintenta en la siguiente vuelta
            print("Error:", err)
        if not args.cada:
            break
        time.sleep(args.cada * 60)


if __name__ == "__main__":
    main()
