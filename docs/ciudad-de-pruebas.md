# Tu ciudad de pruebas

La ciudad de vuestro grupo es la que puntúa: todo lo que hacéis en ella cuenta. Para **aprender** qué acción conviene
en cada situación hay que probar acciones distintas, también malas, y eso no se puede hacer en la ciudad que puntúa.

Para eso está la ciudad de pruebas: el mismo simulador, en vuestro equipo, con el reloj acelerado. Podéis tener las
que queráis, romperlas y empezar de cero, y en una hora acumuláis semanas simuladas de datos.

## Qué necesitáis

- [Docker](https://docs.docker.com/get-docker/) (Docker Desktop en Windows y Mac).
- [Git](https://git-scm.com/).
- Unos 300 MB de memoria y un núcleo de CPU libre por ciudad.

## 1. Construir el simulador (una vez)

```sh
git clone https://github.com/prubioamzubiri/SmartCity.git
cd SmartCity
docker build -t smartcity-sim .
```

Si el profesor actualiza el simulador, haced `git pull` y volved a construir la imagen.

## 2. Arrancar una ciudad

```sh
docker run -d --name pruebas -p 8080:8080 \
  -e SMARTCITY_TOKEN=pruebas -e SCENARIO_SEED=1 -e SIM_SCALE=300 \
  -v pruebas-datos:/data smartcity-sim
```

| Variable | Qué es |
| --- | --- |
| `SMARTCITY_TOKEN` | El token de escritura de esta ciudad (el que queráis) |
| `SCENARIO_SEED` | La semilla: tráfico, tiempo, eventos y variación de la demanda. Con otra semilla, otra ciudad |
| `SCENARIO_START` | Opcional: fecha y hora simulada de inicio, p. ej. `2026-08-15T00:00` (por defecto, lunes 5-1-2026 a las 7:00) |
| `SIM_SCALE` | Segundos simulados por segundo real. La del curso es 52 (una semana real = un año). Con 300, un día simulado dura unos 5 minutos |

Comprobad que funciona:

```sh
curl http://localhost:8080/api/state
```

Y usadla con el kit igual que la del grupo:

```python
from smartcity import SmartCity

city = SmartCity("http://localhost:8080", token="pruebas")
print(city.sim_time(), city.state()["seed"])
```

### Qué velocidad poner

Con 300 un equipo normal va al día. Si ponéis más, en hora punta el simulador no da abasto y va por detrás: no pasa
nada (la simulación es la misma, solo tarda más), pero `state()["caughtUp"]` sale `false` y `city.sleep_sim(...)`
espera de menos, porque supone que la ciudad va a su ritmo. Para esperar a una hora simulada concreta, usad
`city.wait_until("2026-01-06T08:00")`, que espera lo que haga falta.

## 3. Empezar de cero o probar otra ciudad

La semilla, el inicio y la escala solo se aplican al **crear** la ciudad (su volumen). Si arrancáis el mismo volumen
con otra semilla, el servidor se niega y lo explica. Para empezar de cero:

```sh
docker rm -f pruebas
docker volume rm pruebas-datos
```

y volved a arrancarla. Para tener varias a la vez, cambiad el nombre, el puerto y el volumen:

```sh
docker run -d --name pruebas2 -p 8081:8080 -e SMARTCITY_TOKEN=pruebas -e SCENARIO_SEED=2 -e SIM_SCALE=300 \
  -v pruebas2-datos:/data smartcity-sim
```

Para pararla sin perderla: `docker stop pruebas` (y `docker start pruebas` para seguir donde estaba).

## 4. Explorar y recoger datos

Lo útil de la ciudad de pruebas es ver qué pasa con acciones distintas en situaciones distintas. Un esquema:

1. Activad el registro de lo que os interese (líneas de autobús, parkings, bicis, sensores).
2. Cada hora simulada, elegid una acción (por ejemplo, al azar entre varias) y **apuntad cuál** con su hora.
3. Recoged los históricos con la descarga incremental (`city.history.update(...)`, ver
   [`examples/recoger.py`](../examples/recoger.py)).
4. Juntad acciones y resultados por hora: ese es el conjunto de datos con el que entrenar.

```python
import csv
import datetime as dt
import random

from smartcity import SmartCity

city = SmartCity("http://localhost:8080", token="pruebas")
with open("acciones.csv", "a", newline="") as f:
    out = csv.writer(f)
    hora = city.sim_time().replace(minute=0, second=0, microsecond=0)
    while True:
        verde = random.choice([10, 14, 18, 24])
        city.signals.set_plan(default={"green": verde, "yellow": 3}, signals={})
        out.writerow([hora.isoformat(), verde])
        f.flush()
        hora += dt.timedelta(hours=1)
        city.wait_until(hora)  # espera a la hora simulada siguiente
```

Probad también días distintos: con `SCENARIO_START` podéis empezar en verano, en fiestas o en un mes con lluvia.

## 5. Ver la ciudad en el visor (opcional)

La imagen anterior solo tiene el API. Para ver también el mapa, arrancad el simulador completo con `docker compose`
desde la carpeta `SmartCity`, en HTTP y en otro puerto:

```sh
DOMAIN=:80 HTTP_PORT=8090 HTTPS_PORT=8453 SMARTCITY_TOKEN=pruebas SCENARIO_SEED=1 SIM_SCALE=300 docker compose up -d --build
```

y abrid `http://localhost:8090` (el API queda en `http://localhost:8090/api`).

## Lo que debéis saber

- **La ciudad de pruebas no puntúa.** Lo que hagáis en ella no lo ve nadie.
- **No es vuestra ciudad del grupo**: tiene otra semilla y otras fechas, igual que las ciudades de la evaluación final.
  Un gestor que solo funciona en una ciudad concreta funcionará mal en la evaluación: probadlo en varias semillas.
- Lo que aprendáis en la ciudad de pruebas aplicadlo en la del grupo **con cuidado**: allí cada acción cuenta.
