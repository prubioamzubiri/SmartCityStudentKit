#!/usr/bin/env python3
"""Activa sensores y registros, espera un rato simulado y descarga los históricos.

    SMARTCITY_URL=http://localhost:8080 SMARTCITY_TOKEN=... python3 examples/historicos.py
"""
from smartcity import SmartCity

city = SmartCity()

# 1. Activar lo que queremos grabar (solo se graba desde que se activa).
sensor = city.sensors.create(lat=43.3166, lon=-1.9800, name="Plaza Gipuzkoa")
city.pedestrian_sensors.create(lat=43.3166, lon=-1.9800, name="Plaza Gipuzkoa")
city.buses.track([line["id"] for line in city.buses.list()])
city.parkings.track([p["id"] for p in city.parkings.list()])
print("Grabando desde", city.sim_time())

# 2. Esperar una hora simulada (≈ 70 s reales).
city.sleep_sim(hours=1)

# 3. Descargar: como lista de diccionarios, como DataFrame (si hay pandas) o a un fichero.
rows = city.history.traffic(sensor_id=sensor["id"])
for row in rows:
    print(row["timestamp"], row["count"], "coches", row["avg_speed_kmh"], "km/h")
city.history.download("city", "ciudad.csv")
print("Guardado ciudad.csv")
