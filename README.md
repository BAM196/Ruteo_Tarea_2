# Resiliencia de Internet en Chile

Proyecto para analizar la resiliencia de la infraestructura de Internet en Chile frente a un escenario sísmico. Usa PostgreSQL con PostGIS y pgRouting para procesar la red y sirve un mapa interactivo local.

## Requisitos

- Git
- Docker con Docker Compose
- Python 3.10 o superior

## Instalación y ejecución

Clona el repositorio y entra al directorio del proyecto:

```bash
git clone <URL_DEL_REPOSITORIO>
cd resiliencia-internet-chile
```

Instala las dependencias de Python:

```bash
python -m pip install "psycopg[binary]" pyproj pyshp
```

Inicia la base de datos:

```bash
docker compose up -d
```

Ejecuta el análisis:

```bash
python main.py
```

Al finalizar el procesamiento, el mapa estará disponible en [http://127.0.0.1:8000](http://127.0.0.1:8000). El proceso de Python debe permanecer activo mientras se use el mapa.

> `main.py` también inicia Docker Compose y espera a que la base de datos esté lista. El paso manual anterior permite levantar la base de datos explícitamente antes de ejecutar el análisis.

Para detener la base de datos:

```bash
docker compose down
```