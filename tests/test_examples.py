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


if __name__ == "__main__":
    unittest.main()
