# Qué podéis cambiar en la ciudad

Vuestro gestor actúa sobre la ciudad con unas pocas **palancas**. Casi ninguna hace efecto al instante: muchas hay que
decidirlas **antes** de que haga falta, y por eso necesitáis prever lo que va a pasar (con los históricos, el calendario
de eventos, los festivos y la previsión del tiempo).

## Cómo se evalúa

Vuestra ciudad se compara con la misma ciudad **sin gestor**, a la misma hora y con la misma demanda. Se mira:

- **Tráfico**: coches parados y velocidad media.
- **Viajes en coche**: cuánto se retrasan frente a ir sin tráfico y cuántos no se pueden hacer.
- **Transporte público**: espera en las paradas y gente que se queda sin autobús (por viajero), autobuses llenos y
  líneas sin servicio.
- **Eficiencia de la flota**: horas de autobús de más sobre las de la flota inicial (sobrecoste; cuanto más, peor).
- **Peatones**: gente esperando en los semáforos y espacio sin coches donde hay gente.
- **Bicis**: puestos vacíos o llenos.
- **Parkings**: parkings llenos y coches dando vueltas buscando sitio.
- **Coste de las intervenciones**: calles cortadas, semáforos en rojo, parkings caros, deshacer un cambio enseguida.

Ninguna mejora sale gratis: cortar calles o subir precios mejora unas cosas y empeora otras. Sin gestor, el resultado es
el de referencia; las reglas absurdas (todo apagado, todo cortado, todo caro) puntúan mal.

## Las palancas

| Palanca | API (kit) | Cuándo hace efecto | Qué hay que prever |
| --- | --- | --- | --- |
| **Semáforos**: verde de cada eje, ámbar (3–6 s), modo, horarios | `city.signals.update(...)`, `.set_plan(...)` | Al instante | Cuánto tráfico habrá en cada eje (detectores: `approaching` y `queue` en `signals.list()`) |
| **Autobuses** por línea | `city.buses.set_fleet("L1", 12)` | Quitar: al instante. **Añadir: 40 min** (`pending`) | Qué líneas se llenarán dentro de una hora: hora punta, lluvia, eventos cerca de su recorrido (`buses.route("L1")`) |
| **Calles cortadas** y zonas con límite de entrada | `city.restrictions...` | Al instante | Cuándo y dónde compensa: un evento, un sábado de sol en el centro |
| **Tarifa de cada parking** (precio y franjas horarias) | `city.parkings.set_tariff(id, 3, [{"from": "17:00", "to": "22:00", "price": 5}])` | **A las 0:00 del día siguiente** | Qué parkings se llenarán mañana: eventos, fin de semana, tiempo |
| **Furgonetas de bicis** (3, de 20 bicis) | `city.bikes.move(origen, destino, 15)` (o pestaña Bicis del visor) | **Media hora o más** por viaje (15 min cargar, 15 descargar y el trayecto) | Qué puestos se vaciarán o llenarán (cada laborable: por la mañana se vacían los barrios y se llena el centro; por la tarde, al revés) |
| **Anclajes de un puesto de bicis** | `city.bikes.set_capacity({...})` | **30 días** | Dónde faltan o sobran anclajes a la larga |

### Semáforos

- Cada cruce con semáforo tiene dos ejes (este-oeste `A` y norte-sur `B`). Un ciclo más largo deja pasar más coches en
  hora punta, pero los peatones esperan más; uno muy corto pierde tiempo en cada cambio.
- Los **detectores** de `signals.list()` cuentan, por eje, los coches que se acercan (`approaching`) y los parados
  (`queue`) en los últimos 100 m.
- Apagado (`off`) o en ámbar intermitente (`flashing`), el cruce queda sin regular: los coches ceden el paso.

### Autobuses

- La **flota total es fija** (`fleetTotal`): se reparte entre líneas y hay unos pocos en reserva (`reserve`). Para dar
  autobuses a una línea, tomadlos de la reserva o quitádselos antes a otra (si no hay, `ConflictError`).
- Los que se añaden **salen de la cochera y tardan 40 min** en entrar en servicio: `fleet` son los que ya circulan y
  `target` incluye los que van de camino. Pedir el `fleet` actual cancela los que vienen.
- Con más autobuses en una línea pasan más a menudo: se espera menos. Quien no cabe se queda en tierra (`leftBehind`) y
  quien espera demasiado se va (`unserved`); **esa gente acaba cogiendo el coche**.
- Las horas de autobús de más sobre las de la flota inicial (`buses.status()["today"]`) son **sobrecoste**, y cada vez
  más caro cuantas más se acumulan en el día: reforzad cuando y donde haga falta, no todo el día.
- Lo que llena las líneas: la hora, el día, la **lluvia**, los **eventos** (antes de que empiecen, las líneas que pasan
  cerca de la sede; al acabar, las paradas de alrededor), las calles cortadas y los parkings caros.

### Calles cortadas

- `pedestrians_only` corta también los autobuses (sus líneas quedan suspendidas); `buses_and_pedestrians` los deja pasar.
- Con calles cortadas hay algo menos de coches y más gente en autobús. Junto a un evento, cortar hace que menos gente
  vaya en coche (va andando o en autobús) y gana mucho espacio para los peatones.
- Cortar tiene un coste para los ciudadanos: más cuantos más km y más tiempo.

### Parkings

- Quien va a aparcar elige entre los parkings de su zona según el precio: uno más caro que sus vecinos les manda coches.
- Con los parkings caros, parte de la gente deja el coche (va en autobús, bici o andando). Los que van a un **evento**
  miran los parkings de alrededor de la sede.
- Si un parking está lleno, parte de los que llegan dan vueltas buscando sitio (`parking_search` en el histórico de la
  ciudad): más coches en la calle.
- La tarifa **solo cambia a las 0:00**: decidid hoy la de mañana. Unos precios altos tienen un coste para los
  ciudadanos.

### Bicis

- Los laborables hay **marea**: por la mañana (7–10 h) se cogen bicis en los barrios y se dejan en el centro; por la
  tarde (17–20 h), al revés.
- Lo que hace que se cojan más o menos bicis: la hora y el día, el **tiempo** (con lluvia casi nadie; con sol y buena
  temperatura, más) y los parkings caros (parte de la gente deja el coche y coge la bici).
- Un puesto **vacío** o **lleno** es un mal servicio: quien quería coger o dejar una bici no puede.
- **Furgonetas** (`city.bikes.move(origen, destino, bicis)`, o la pestaña Bicis del visor, que las dibuja en el mapa):
  - Hay 3, de 20 bicis. Va la **libre más cercana** al origen (`free_vans()`; si no hay ninguna, `ConflictError`).
  - Carga las bicis que haya en el origen (como mucho las pedidas) y descarga en el destino las que quepan; las que no
    caben vuelven a circular.
  - Van en **línea recta a unos 14 km/h** (no siguen las calles ni les afecta el tráfico) y tardan **15 min en cargar
    y otros 15 en descargar**. `city.bikes.trip_minutes(origen, destino)` calcula cuánto tardaría ahora.
  - Mientras trabaja, `vans()` dice qué hace cada una (`job`: `loaded` es `None` hasta que carga, y las horas
    `loadAt` y `unloadAt`).
  - Si esperáis a que un puesto esté vacío, llegáis tarde: movedlas **antes**, con lo que preveáis de la marea.

## Lo que no se puede cambiar

La **demanda** (cuánta gente sale a la calle) la fija el servidor y varía cada día. Lo que hacéis la cambia solo de forma
indirecta (cortes, parkings caros, autobuses que no dan abasto).

## Qué datos usar para prever

- Históricos: `city.history.update(...)` (ciudad, autobuses, bicis, parkings, sensores, tiempo).
- Calendario: `city.events(...)` (la asistencia de un evento se publica cuando termina: estimadla con los pasados del
  mismo tipo) y `city.holidays(...)`.
- Previsión del tiempo: `city.weather(hours=48)`.
- Recorridos de las líneas: `city.buses.route("L1")`.

Ojo: rara vez un dato falta o es imposible (`-47` pasajeros, `15230` esperando), falta una fila o un sensor llega sin
una coordenada, como con sensores reales. Limpiad los datos antes de entrenar y no decidáis con un dato absurdo (ver
«Datos con fallos» en el README).

Probad las ideas en una [ciudad de pruebas](ciudad-de-pruebas.md) antes de usarlas en la vuestra.
