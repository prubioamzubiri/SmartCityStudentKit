import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from fake_server import TOKEN, FakeServer  # noqa: E402

from smartcity import SmartCity  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", "examples", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GestorTest(unittest.TestCase):
    def test_one_cycle(self):
        gestor = load("gestor")
        with FakeServer() as server:
            city = SmartCity(server.url, token=TOKEN)
            log = []
            gestor.manage_buses(city, log)  # L1 al 50 %: no cambia; L2 suspendida: se ignora
            self.assertEqual(log, [])
            zone = gestor.manage_zone(city, log, None)  # 30 coches, 15 parados: atasco
            self.assertEqual(zone, "R3")
            created = server.calls[-1]
            self.assertEqual(created["body"]["mode"], "entry_limit")
            self.assertEqual(created["body"]["radius"], 200)



class RecogerTest(unittest.TestCase):
    def test_second_run_only_asks_for_new_rows(self):
        import tempfile
        recoger = load("recoger")
        with FakeServer() as server, tempfile.TemporaryDirectory() as folder:
            city = SmartCity(server.url)
            first = recoger.recoger(city, folder)
            self.assertEqual(first["trafico_S1.csv"], 2)
            self.assertIn("peatones_P1.csv", first)
            second = recoger.recoger(city, folder)
            self.assertEqual(set(second.values()), {0})
            asked = [c["query"] for c in server.calls if c["path"] == "/api/traffic.csv"]
            self.assertEqual(asked[-1], {"from": "2026-01-05T08:05:01", "id": "S1"})


if __name__ == "__main__":
    unittest.main()
