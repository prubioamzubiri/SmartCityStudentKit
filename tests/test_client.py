import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_server import TOKEN, FakeServer  # noqa: E402

import smartcity  # noqa: E402
from smartcity import (AuthError, ForbiddenError, NotFoundError, RestrictionMode, SignalMode, SmartCity,  # noqa: E402
                       SmartCityConnectionError, ValidationError)


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeServer().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def setUp(self):
        self.server.calls.clear()
        self.city = SmartCity(self.server.url, token=TOKEN)

    def last(self):
        return self.server.calls[-1]

    # -- lecturas -----------------------------------------------------------------------------------------------------

    def test_state_and_clock(self):
        self.assertTrue(self.city.health())
        self.assertEqual(self.city.state()["cars"], 812)
        self.assertEqual(self.city.sim_time(), dt.datetime(2026, 1, 5, 8, 30))
        self.assertAlmostEqual(self.city.scale(), 52.1)
        self.assertEqual(self.city.docs(), "# API")

    def test_point_accepts_xz_or_latlon(self):
        self.city.point(lat=43.3166, lon=-1.98, radius=200)
        self.assertEqual(self.last()["query"], {"lat": "43.3166", "lon": "-1.98", "radius": "200"})
        self.city.point(x=10, z=-20)
        self.assertEqual(self.last()["query"], {"x": "10", "z": "-20"})
        with self.assertRaises(ValueError):
            self.city.point(x=10)

    def test_roads(self):
        roads = self.city.roads(lat=43.3, lon=-1.98, radius=60, limit=3)
        self.assertEqual(roads[0]["way"], 2325)
        self.assertEqual(self.last()["query"]["limit"], "3")
        self.assertEqual(self.city.road(2325)["class"], "primary")

    def test_reads_do_not_need_token(self):
        SmartCity(self.server.url, token="").state()
        self.assertIsNone(self.last()["auth"])

    def test_events_holidays_weather(self):
        self.city.events(start=dt.date(2026, 1, 5), end=dt.datetime(2026, 2, 1, 8, 0), type="concert")
        self.assertEqual(self.last()["query"], {"from": "2026-01-05", "to": "2026-02-01T08:00:00", "type": "concert"})
        self.assertEqual(self.city.holidays()[0]["name"], "San Sebastián")
        self.assertEqual(self.city.weather(hours=6)["current"]["condition"], "rain")

    # -- recursos -------------------------------------------------------------------------------------------------------

    def test_buses(self):
        lines = self.city.buses.list()
        self.assertEqual(self.city.buses.occupancy(lines[0]), 0.5)
        self.assertIsNone(self.city.buses.occupancy(lines[1]))
        self.assertEqual(self.city.buses.get("L2")["suspended"], True)
        self.assertEqual(self.city.buses.set_fleet("L1", 8)["fleet"], 8)
        self.assertEqual(self.last(), {"method": "PATCH", "path": "/api/buses/L1", "query": {}, "body": {"fleet": 8},
                                       "auth": f"Bearer {TOKEN}"})
        self.assertEqual(self.city.buses.track(["L1", "L2"]), ["L1", "L2"])
        with self.assertRaises(NotFoundError):
            self.city.buses.set_fleet("L9", 3)

    def test_sensors(self):
        self.assertEqual(self.city.sensors.list()[0]["id"], "S1")
        self.assertEqual(self.city.pedestrian_sensors.list()[0]["id"], "P1")
        self.assertEqual(self.city.sensors.create(lat=43.31, lon=-1.98, name="Mío")["id"], "S2")
        self.assertEqual(self.last()["body"], {"lat": 43.31, "lon": -1.98, "name": "Mío"})
        self.city.pedestrian_sensors.create(x=1, z=2)
        self.assertEqual(self.last()["path"], "/api/pedestrian-sensors")
        self.city.sensors.rename("S2", "Nuevo")
        self.assertEqual((self.last()["method"], self.last()["body"]), ("PATCH", {"name": "Nuevo"}))
        self.city.sensors.delete("S2")
        self.assertEqual((self.last()["method"], self.last()["path"]), ("DELETE", "/api/sensors/S2"))

    def test_parkings_and_bikes(self):
        self.assertEqual(self.city.parkings.list()[0]["id"], "U-1")
        self.city.parkings.track(("U-1",))
        self.assertEqual(self.last()["body"], {"ids": ["U-1"]})
        self.assertEqual(self.city.bikes.stations()[0]["id"], "municipal/0")
        self.city.bikes.set_capacity({"municipal/0": 20, "municipal/5": None})
        self.assertEqual(self.last()["body"], {"changes": {"municipal/0": 20, "municipal/5": None}})

    def test_signals(self):
        self.assertEqual(self.city.signals.list()[0]["mode"], "normal")
        self.city.signals.list(all=True, lat=43.3, lon=-1.98, radius=300)
        self.assertEqual(self.last()["query"], {"all": "1", "radius": "300", "lat": "43.3", "lon": "-1.98"})
        self.city.signals.update(13965274528, mode=SignalMode.NORMAL, green_a=45, green_b=15, yellow=None)
        self.assertEqual(self.last()["body"], {"mode": "normal", "greenA": 45, "greenB": 15, "yellow": None})
        self.city.signals.reset(13965274528)
        self.assertEqual(self.last()["body"], {"reset": True})
        self.city.signals.set_plan(default={"green": 30}, signals={13965274528: {"mode": "off"}})
        self.assertEqual(self.last()["body"], {"plan": {"default": {"green": 30}, "signals": {"13965274528": {"mode": "off"}}}})
        with self.assertRaises(ValueError):
            self.city.signals.update(1)

    def test_restrictions(self):
        created = self.city.restrictions.close_streets([2325], buses=True, name="Peatonal con bus")
        self.assertEqual(created["id"], "R3")
        self.assertEqual(self.last()["body"], {"mode": "buses_and_pedestrians", "ways": [2325], "name": "Peatonal con bus"})
        self.city.restrictions.limit_zone(10, 300, lat=43.3166, lon=-1.98)
        self.assertEqual(self.last()["body"], {"mode": "entry_limit", "lat": 43.3166, "lon": -1.98, "radius": 300, "limit": 10})
        self.city.restrictions.update("R3", limit=0)
        self.assertEqual((self.last()["method"], self.last()["body"]), ("PATCH", {"limit": 0}))
        self.assertEqual(self.city.restrictions.clear(), ["R1", "R2"])
        self.assertEqual([c["method"] for c in self.server.calls[-2:]], ["DELETE", "DELETE"])
        with self.assertRaises(ValueError):
            self.city.restrictions.create("cerrado", ways=[1])
        with self.assertRaises(ValueError):
            self.city.restrictions.create(RestrictionMode.PEDESTRIANS_ONLY, x=1, z=2)

    # -- históricos ---------------------------------------------------------------------------------------------------

    def test_history_rows(self):
        rows = self.city.history.traffic(start="2026-01-05T08:00", end=dt.date(2026, 1, 6), sensor_id="S1")
        self.assertEqual(self.last()["path"], "/api/traffic.csv")
        self.assertEqual(self.last()["query"], {"from": "2026-01-05T08:00", "to": "2026-01-06", "id": "S1"})
        self.assertEqual(rows[0]["count"], 42)
        self.assertEqual(rows[0]["avg_speed_kmh"], 31.5)
        self.assertIsNone(rows[1]["avg_speed_kmh"])
        self.assertEqual(rows[0]["sensor_name"], "Avenida")
        self.city.sensors.history(sensor_id="S1")
        self.assertEqual(self.last()["query"], {"id": "S1"})
        self.city.buses.history(line_id="L1")
        self.assertEqual(self.last()["path"], "/api/buses.csv")

    def test_history_download(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.city.history.download("city", os.path.join(folder, "ciudad.csv"))
            with open(path, encoding="utf-8") as handle:
                self.assertTrue(handle.read().startswith("timestamp,"))
        with self.assertRaises(ValueError):
            self.city.history.csv("aviones")

    def test_history_dataframe(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas no está instalado")
        frame = self.city.history.traffic(dataframe=True)
        self.assertEqual(len(frame), 2)
        self.assertTrue(str(frame["timestamp"].dtype).startswith("datetime64"))

    # -- errores ------------------------------------------------------------------------------------------------------

    def test_errors(self):
        with self.assertRaises(AuthError) as ctx:
            SmartCity(self.server.url, token="malo").buses.set_fleet("L1", 2)
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.message, "Token no válido")
        with self.assertRaises(ForbiddenError):
            self.city.set_params(max_cars=100)
        with self.assertRaises(NotFoundError):
            self.city.get("/api/nada")
        with self.assertRaises(ValidationError):
            self.city.get("/api/point")
        with self.assertRaises(SmartCityConnectionError):
            SmartCity("http://127.0.0.1:9", timeout=2).state()
        self.assertFalse(SmartCity("http://127.0.0.1:9", timeout=2).health())

    def test_env_defaults(self):
        old = dict(os.environ)
        try:
            os.environ["SMARTCITY_URL"] = "http://ejemplo:1234/"
            os.environ["SMARTCITY_TOKEN"] = "abc"
            city = SmartCity()
            self.assertEqual((city.url, city.token), ("http://ejemplo:1234", "abc"))
            self.assertNotIn("abc", repr(city))
        finally:
            os.environ.clear()
            os.environ.update(old)


class GeoTest(unittest.TestCase):
    def test_round_trip(self):
        x, z = smartcity.latlon_to_xz(43.3166, -1.98)
        self.assertAlmostEqual(x, 97.2, places=0)
        self.assertAlmostEqual(z, 188.0, places=0)
        lat, lon = smartcity.xz_to_latlon(x, z)
        self.assertAlmostEqual(lat, 43.3166, places=9)
        self.assertAlmostEqual(lon, -1.98, places=9)
        self.assertEqual(smartcity.latlon_to_xz(smartcity.ORIGIN_LAT, smartcity.ORIGIN_LON), (0.0, 0.0))
        self.assertEqual(smartcity.distance((0, 0), (3, 4)), 5)


if __name__ == "__main__":
    unittest.main()
