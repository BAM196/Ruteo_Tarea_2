import json
import math
import os
import random
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict, deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import csv
import psycopg
from psycopg.rows import dict_row
from pyproj import CRS, Transformer
import shapefile  # pyshp

DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/resiliencia_cl",
)
SQL_FILE = "main.sql"
ZIP_PATH = Path("Respuesta_T5610.zip")
SHP_DIR = Path("Respuesta_T5610")
SISMO_GEOJSON_PATH = Path("terremoto.geojson")
HOST = "127.0.0.1"
PORT = 8000

# Activar/desactivar la red sintética sin configurar variables de entorno.
USAR_RED_SINTETICA = True

# Modelo probabilístico de daño en fibra óptica basado en Jiménez, Barrera y
# Cancela (2023), IEEE Access. El modelo supone enlaces enterrados.
MODELO_FALLA = "JIMENEZ_BARRERA_CANCELA_2023"
LONGITUD_SEGMENTO_KM = 10.0
KC_G = 0.1                 # aceleración crítica, en unidades de g (valor del paper)
ALFA_CABLE = 0.26          # 0.26: tipología más robusta; 1.07: más vulnerable
VS30_M_S = 760.0           # supuesto por defecto; reemplazar por Vs30 local si existe
EVENTO_PROFUNDIDAD_DEFAULT_KM = 30.0


# Puntos de referencia (aterrizajes de cable submarino y data centers) para anclar nodos clave
NODOS_REFERENCIA = [
    {
        "nombre": "Aterrizaje Cable Submarino Arica",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.312,
        "lat": -18.478,
        "justificacion": "Punto de aterrizaje de cables submarinos en el extremo norte (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Iquique",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.136,
        "lat": -20.231,
        "justificacion": "Punto de aterrizaje submarino del sistema Prat en la Región de Tarapacá (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Tocopilla",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.198,
        "lat": -22.092,
        "justificacion": "Punto de aterrizaje submarino intermedio en el norte grande (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Antofagasta",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.395,
        "lat": -23.650,
        "justificacion": "Punto de aterrizaje submarino en el norte grande (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Caldera",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.819,
        "lat": -27.068,
        "justificacion": "Punto de aterrizaje submarino en la Región de Atacama (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino La Serena",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -71.252,
        "lat": -29.903,
        "justificacion": "Punto de aterrizaje submarino en la zona norte-centro (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Valparaíso",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -71.627,
        "lat": -33.047,
        "justificacion": "Ingreso principal de conectividad internacional al backbone nacional (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Cartagena",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -71.600,
        "lat": -33.550,
        "justificacion": "Punto de aterrizaje costero en el litoral central (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Constitución",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -72.410,
        "lat": -35.333,
        "justificacion": "Punto de aterrizaje costero cercano al área de ruptura del 27F (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Zona Centro-Sur",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -73.050,
        "lat": -36.827,
        "justificacion": "Conexión submarina en zona centro-sur bajo influencia del sismo 8.8 (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Puerto Saavedra",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -73.400,
        "lat": -38.783,
        "justificacion": "Punto de aterrizaje submarino en la Región de La Araucanía (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Puerto Montt",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -72.942,
        "lat": -41.469,
        "justificacion": "Nodo de conexión submarina/austral hacia el sur del país (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Meimen",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -73.505,
        "lat": -41.789,
        "justificacion": "Punto de aterrizaje de cruce submarino en el Canal de Chacao (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Linao",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -73.542,
        "lat": -41.959,
        "justificacion": "Punto de aterrizaje insular de fibra óptica en Chiloé (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Caleta Tortel",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -73.532,
        "lat": -47.796,
        "justificacion": "Nodo intermedio de la Fibra Óptica Austral en la Región de Aysén (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Punta Arenas",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -70.917,
        "lat": -53.164,
        "justificacion": "Nodo troncal de la Fibra Óptica Austral en el Estrecho de Magallanes (Submarine Cable Map).",
    },
    {
        "nombre": "Aterrizaje Cable Submarino Puerto Williams",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -67.611,
        "lat": -54.934,
        "justificacion": "Punto de aterrizaje de cables submarinos en el extremo austral (Submarine Cable Map).",
    },
    {
        "nombre": "Data Center Santiago Centro",
        "tipo_infraestructura": "data_center",
        "rol": "intercambia",
        "lon": -70.650,
        "lat": -33.448,
        "justificacion": "Núcleo metropolitano de intercambio y agregación de tráfico de la red troncal.",
    },
    {
        "nombre": "Data Center Quilicura",
        "tipo_infraestructura": "data_center",
        "rol": "recibe",
        "lon": -70.735,
        "lat": -33.360,
        "justificacion": "Centro de procesamiento y alojamiento de servicios/datos en la Región Metropolitana.",
    },
    {
        "nombre": "Punto de Conexión Isla de Pascua (Rapa Nui)",
        "tipo_infraestructura": "cable_submarino",
        "rol": "genera",
        "lon": -109.3497,
        "lat": -27.1127,
        "justificacion": "Nodo insular en Rapa Nui conectado mediante enlace sintético hacia Valparaíso.",
    },
]


def run_cmd(cmd: list[str]) -> None:
    print(f"--> Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def wait_for_db(dsn: str, timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            print("Base de datos lista.")
            return
        except Exception:
            time.sleep(1.5)
    raise RuntimeError("La base de datos no respondió a tiempo.")


def apply_sql_file(dsn: str, sql_path: str) -> None:
    if not Path(sql_path).exists():
        print(f"Aviso: {sql_path} no existe, omitiendo.")
        return
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read().strip()
    if not sql_content:
        return
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_content)
    print(f"Archivo {sql_path} aplicado correctamente.")


def preparar_directorio_shp() -> Path:
    if SHP_DIR.exists() and any(SHP_DIR.glob("*.shp")):
        return SHP_DIR
    if ZIP_PATH.exists():
        print(f"--> Extrayendo {ZIP_PATH}...")
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(".")
    # Busca carpeta que contenga los .shp
    for candidate in [SHP_DIR, Path(".")]:
        if any(candidate.glob("*.shp")):
            return candidate
    raise FileNotFoundError("No se encontraron archivos .shp ni Respuesta_T5610.zip.")

def agregar_enlace_sintetico_rapa_nui_valparaiso(conn) -> None:
    """
    Crea un enlace sintético (LineString en EPSG:4326) conectando Isla de Pascua
    (-109.3497, -27.1127) con Valparaíso (-71.627, -33.047) antes de pgr_createTopology.
    """
    lon_rapa, lat_rapa = -109.3497, -27.1127
    lon_valpo, lat_valpo = -71.627, -33.047

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO enlaces (
                id_origen,
                tipo_capa,
                geom,
                prob_falla,
                es_sintetico,
                nota_sintetico
            )
            VALUES (
                NULL,
                'cable_submarino_sintetico',
                ST_SetSRID(
                    ST_MakeLine(
                        ST_MakePoint(%s, %s),
                        ST_MakePoint(%s, %s)
                    ),
                    4326
                ),
                0.0,
                true,
                'Enlace sintético de larga distancia entre Isla de Pascua (Rapa Nui) y Valparaíso.'
            )
            RETURNING id, ROUND((ST_Length(geom::geography) / 1000.0)::numeric, 2) AS km;
            """,
            (lon_rapa, lat_rapa, lon_valpo, lat_valpo),
        )
        creado = cur.fetchone()
    conn.commit()
    print(
        f"Enlace sintético Rapa Nui -> Valparaíso creado (id={creado['id']}, longitud={creado['km']} km, es_sintetico=True)."
    )

def obtener_transformador_4326(shp_path: Path) -> Transformer | None:
    prj_path = shp_path.with_suffix(".prj")
    if not prj_path.exists():
        return None
    wkt = prj_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not wkt:
        return None
    src_crs = CRS.from_wkt(wkt)
    dst_crs = CRS.from_epsg(4326)
    if src_crs == dst_crs:
        return None
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def reproyectar_geojson_geom(geom: dict, transformer: Transformer | None) -> dict:
    if transformer is None or not geom:
        return geom

    def tx_coords(coords):
        if not coords:
            return coords
        if isinstance(coords[0], (int, float)):
            x, y = transformer.transform(coords[0], coords[1])
            return [x, y]
        return [tx_coords(c) for c in coords]

    return {
        "type": geom["type"],
        "coordinates": tx_coords(geom.get("coordinates")),
    }


def exportar_resultados_27f(
    conn,
    attr_original: dict,
    attr_sintetica: dict | None,
    attr_post_sismo: dict,
    usar_red_sintetica: bool,
) -> None:
    exportar_resultados_27f(
    conn=conn,
    attr_original=attr_antes,
    attr_sintetica=attr_red_sintetica,
    attr_post_sismo=attr_despues,
    usar_red_sintetica=usar_red_sintetica,
)
    # =========================================================
    # 1. TABLA COMPARATIVA ATTR
    # =========================================================

    valor_original = float(attr_original["attr"])
    valor_sintetica = (
        float(attr_sintetica["attr"])
        if attr_sintetica is not None else None
    )
    valor_base = (
        valor_sintetica if usar_red_sintetica else valor_original
    )
    valor_post = float(attr_post_sismo["attr"])

    def calcular_variacion(nuevo, base):
        diferencia = nuevo - base
        porcentaje = diferencia / base * 100 if base else 0.0
        return diferencia, porcentaje

    diff_sint, pct_sint = (
        calcular_variacion(valor_sintetica, valor_original)
        if valor_sintetica is not None else (None, None)
    )
    diff_post, pct_post = calcular_variacion(valor_post, valor_base)

    print("\n" + "=" * 100)
    print("TABLA 1. COMPARACIÓN DE ATTR")
    print("=" * 100)
    print(
        f"{'Escenario':48} {'ATTR':>12} "
        f"{'Diferencia':>15} {'Variación (%)':>16}"
    )
    print("-" * 100)

    filas = [
        ("Red original sin fallas", valor_original, 0.0, 0.0),
        (
            "Red con puentes sintéticos sin fallas",
            valor_sintetica, diff_sint, pct_sint
        ),
        (
            "Red después del sismo 27F simulado",
            valor_post, diff_post, pct_post
        ),
    ]

    for nombre, attr, diferencia, porcentaje in filas:
        if attr is None:
            continue
        print(
            f"{nombre:48} {attr:12.6f} "
            f"{diferencia:15.6f} {porcentaje:15.2f}%"
        )

    print("-" * 100)
    print(f"ATTR de referencia sísmica: {valor_base:.6f}")
    print(f"Variación post-sismo: {diff_post:+.6f} ({pct_post:+.2f}%)")

    # =========================================================
    # 2. RANKING DE ENLACES MÁS AFECTADOS
    # =========================================================

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                id AS enlace_id,
                tipo_capa,
                prob_falla,
                es_sintetico,
                source,
                target,
                ROUND(
                    (ST_Length(geom::geography) / 1000.0)::numeric,
                    3
                ) AS longitud_km
            FROM enlaces
            ORDER BY prob_falla DESC,
                     ST_Length(geom::geography) DESC
            LIMIT 20;
        """)
        enlaces = cur.fetchall()

    print("\n" + "=" * 115)
    print("TABLA 2. TOP 20 ENLACES CON MAYOR PROBABILIDAD DE FALLA")
    print("=" * 115)
    print(
        f"{'ID':>6} {'Tipo de enlace':28} {'P(falla)':>12} "
        f"{'Long. km':>11} {'Sintético':>11} "
        f"{'Source':>9} {'Target':>9}"
    )
    print("-" * 115)

    for e in enlaces:
        print(
            f"{e['enlace_id']:6} "
            f"{str(e['tipo_capa'])[:28]:28} "
            f"{float(e['prob_falla'] or 0):12.6f} "
            f"{float(e['longitud_km'] or 0):11.3f} "
            f"{str(bool(e['es_sintetico'])):>11} "
            f"{str(e['source']):>9} "
            f"{str(e['target']):>9}"
        )

    # =========================================================
    # 3. RANKING DE NODOS CLAVE MÁS EXPUESTOS
    # =========================================================

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            WITH incidentes AS (
                SELECT
                    x.vertice_id,
                    e.prob_falla,
                    e.es_sintetico
                FROM enlaces e
                CROSS JOIN LATERAL (
                    VALUES (e.source), (e.target)
                ) AS x(vertice_id)
                WHERE x.vertice_id IS NOT NULL
            ),
            exposicion AS (
                SELECT
                    vertice_id,
                    COUNT(*) AS enlaces_incidentes,
                    SUM(prob_falla) AS suma_probabilidades,
                    AVG(prob_falla) AS probabilidad_media,
                    MAX(prob_falla) AS probabilidad_maxima,
                    COUNT(*) FILTER (
                        WHERE prob_falla >= 0.15
                    ) AS enlaces_riesgo_medio_alto,
                    COUNT(*) FILTER (
                        WHERE es_sintetico
                    ) AS enlaces_sinteticos
                FROM incidentes
                GROUP BY vertice_id
            )
            SELECT
                n.id AS nodo_id,
                n.nombre,
                n.rol,
                n.vertice_id,
                COALESCE(x.enlaces_incidentes, 0) AS enlaces_incidentes,
                COALESCE(x.suma_probabilidades, 0) AS suma_probabilidades,
                COALESCE(x.probabilidad_media, 0) AS probabilidad_media,
                COALESCE(x.probabilidad_maxima, 0) AS probabilidad_maxima,
                COALESCE(x.enlaces_riesgo_medio_alto, 0)
                    AS enlaces_riesgo_medio_alto,
                COALESCE(x.enlaces_sinteticos, 0) AS enlaces_sinteticos
            FROM nodos_clave n
            LEFT JOIN exposicion x
                ON n.vertice_id = x.vertice_id
            ORDER BY
                COALESCE(x.suma_probabilidades, 0) DESC,
                COALESCE(x.probabilidad_maxima, 0) DESC;
        """)
        nodos = cur.fetchall()

    print("\n" + "=" * 135)
    print("TABLA 3. NODOS CLAVE CON MAYOR EXPOSICIÓN A FALLAS")
    print("=" * 135)
    print(
        f"{'Nodo':42} {'Rol':12} {'Enlaces':>9} "
        f"{'P. máxima':>11} {'P. media':>11} "
        f"{'Suma P':>11} {'Riesgo >=0.15':>15}"
    )
    print("-" * 135)

    for n in nodos:
        print(
            f"{str(n['nombre'])[:42]:42} "
            f"{str(n['rol'])[:12]:12} "
            f"{n['enlaces_incidentes']:9} "
            f"{float(n['probabilidad_maxima']):11.4f} "
            f"{float(n['probabilidad_media']):11.4f} "
            f"{float(n['suma_probabilidades']):11.4f} "
            f"{n['enlaces_riesgo_medio_alto']:15}"
        )

    # =========================================================
    # 4. RESUMEN GENERAL
    # =========================================================

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE NOT es_sintetico
                ) AS reales,
                COUNT(*) FILTER (
                    WHERE es_sintetico
                ) AS sinteticos,
                COUNT(*) FILTER (
                    WHERE prob_falla >= 0.15
                ) AS riesgo_medio_alto,
                ROUND(
                    AVG(prob_falla)::numeric, 6
                ) AS probabilidad_media,
                ROUND(
                    MAX(prob_falla)::numeric, 6
                ) AS probabilidad_maxima
            FROM enlaces;
        """)
        resumen = cur.fetchone()

    print("\n" + "=" * 85)
    print("TABLA 4. RESUMEN GENERAL DEL ESCENARIO SÍSMICO")
    print("=" * 85)
    print(f"Enlaces totales:                  {resumen['total']}")
    print(f"Enlaces reales:                   {resumen['reales']}")
    print(f"Enlaces sintéticos:               {resumen['sinteticos']}")
    print(f"Enlaces con P(falla) >= 0.15:      {resumen['riesgo_medio_alto']}")
    print(f"Probabilidad media de falla:      {resumen['probabilidad_media']}")
    print(f"Probabilidad máxima de falla:     {resumen['probabilidad_maxima']}")
    print(f"Nodos clave analizados:           {len(nodos)}")
    print("=" * 85)
    print("Fin de resultados del escenario 27F.")


def cargar_sismo_27f(conn, geojson_path: Path) -> None:
    lon, lat, mag, titulo = -72.898, -36.122, 8.8, "M 8.8 - 2010 Maule, Chile Earthquake"
    profundidad_km = EVENTO_PROFUNDIDAD_DEFAULT_KM
    if geojson_path.exists():
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
        feats = data.get("features") or []
        if feats:
            props = feats[0].get("properties") or {}
            geom = feats[0].get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) >= 2:
                lon = float(coords[0])
                lat = float(coords[1])
            if len(coords) >= 3 and coords[2] is not None:
                profundidad_km = float(coords[2])
            mag = float(props.get("mag") or mag)
            titulo = str(props.get("title") or titulo)

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sismo_27f (
                id serial PRIMARY KEY,
                titulo text NOT NULL,
                magnitud double precision NOT NULL,
                profundidad_km double precision NOT NULL DEFAULT 30.0,
                geom geometry(Point, 4326) NOT NULL
            );
            """
        )
        # Compatibilidad con bases creadas por versiones anteriores de main.py.
        cur.execute(
            "ALTER TABLE sismo_27f ADD COLUMN IF NOT EXISTS profundidad_km "
            "double precision NOT NULL DEFAULT 30.0;"
        )
        cur.execute("TRUNCATE TABLE sismo_27f RESTART IDENTITY;")
        cur.execute(
            """
            INSERT INTO sismo_27f (titulo, magnitud, profundidad_km, geom)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
            """,
            (titulo, mag, profundidad_km, lon, lat),
        )
    conn.commit()
    print(
        f"Evento sísmico cargado: Mw={mag:.2f}, profundidad={profundidad_km:.1f} km, "
        f"epicentro=({lat:.4f}, {lon:.4f})."
    )



def seleccionar_nodos_clave(conn, top_hubs: int = 3) -> None:
    """
    Selecciona nodos clave combinando:
    1) Vértices de mayor grado/conexión en la topología ('intercambia' / 'recibe').
    2) Puntos de referencia (cables submarinos y data centers) ajustados al vértice más cercano.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS nodos_clave (
                id serial PRIMARY KEY,
                nombre text NOT NULL,
                tipo_infraestructura text NOT NULL,
                rol text NOT NULL,
                justificacion text NOT NULL,
                geom geometry(Point, 4326) NOT NULL,
                vertice_id integer
            );
            """
        )
        cur.execute("TRUNCATE TABLE nodos_clave RESTART IDENTITY;")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT source, target FROM enlaces WHERE source IS NOT NULL AND target IS NOT NULL;")
        edges = cur.fetchall()

    grado = Counter()
    for e in edges:
        grado[int(e["source"])] += 1
        grado[int(e["target"])] += 1

    hubs_ordenados = [vid for vid, _ in grado.most_common(top_hubs)]

    nodos_a_insertar = []

   # 1. Nodos de referencia (cables submarinos y data centers) -> vértice más cercano
    with conn.cursor(row_factory=dict_row) as cur:
        for ref in NODOS_REFERENCIA:
            cur.execute(
                """
                SELECT
                    id,
                    ST_X(the_geom) AS lon,
                    ST_Y(the_geom) AS lat,
                    ST_Distance(
                        the_geom::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) / 1000.0 AS dist_km
                FROM enlaces_vertices_pgr
                ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                LIMIT 1;
                """,
                (ref["lon"], ref["lat"], ref["lon"], ref["lat"]),
            )
            v = cur.fetchone()
            if v:
                nodos_a_insertar.append(
                    (
                        f"{ref['nombre']} (dist. {v['dist_km']:.1f} km)",
                        ref["tipo_infraestructura"],
                        ref["rol"],
                        ref["justificacion"],
                        float(v["lon"]),
                        float(v["lat"]),
                        int(v["id"]),
                    )
                )

    # 2. Vértices troncales de mayor grado en la red como nodos adicionales ('intercambia' / 'recibe')
    usados = {item[6] for item in nodos_a_insertar}
    with conn.cursor(row_factory=dict_row) as cur:
        for idx, vid in enumerate(hubs_ordenados, start=1):
            if vid in usados:
                continue
            cur.execute(
                "SELECT id, ST_X(the_geom) AS lon, ST_Y(the_geom) AS lat FROM enlaces_vertices_pgr WHERE id = %s;",
                (vid,),
            )
            v = cur.fetchone()
            if v:
                rol_hub = "intercambia" if idx == 1 else "recibe"
                nodos_a_insertar.append(
                    (
                        f"Nodo Troncal Topológico #{vid} (grado {grado[vid]})",
                        "nodo_troncal",
                        rol_hub,
                        f"Seleccionado por alta conectividad topológica (grado={grado[vid]}) en la red construida.",
                        float(v["lon"]),
                        float(v["lat"]),
                        int(v["id"]),
                    )
                )
                usados.add(vid)
    with conn.cursor() as cur:
        for nombre, tipo_inf, rol, just, lon, lat, vid in nodos_a_insertar:
            cur.execute(
                """
                INSERT INTO nodos_clave (nombre, tipo_infraestructura, rol, justificacion, geom, vertice_id)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s);
                """,
                (nombre, tipo_inf, rol, just, lon, lat, vid),
            )
    conn.commit()
    print(f"Nodos clave seleccionados y ubicados: {len(nodos_a_insertar)}")


def _conectividad_pares(
    nodos_vertices: list[int],
    adyacencia: dict[int, list[int]],
) -> dict[tuple[int, int], bool]:
    conectados: dict[tuple[int, int], bool] = {}
    n = len(nodos_vertices)
    for i in range(n):
        origen = nodos_vertices[i]
        visitados = {origen}
        cola = deque([origen])
        while cola:
            actual = cola.popleft()
            for vec in adyacencia.get(actual, ()):
                if vec not in visitados:
                    visitados.add(vec)
                    cola.append(vec)
        for j in range(i + 1, n):
            destino = nodos_vertices[j]
            conectados[(origen, destino)] = destino in visitados
    return conectados


def calcular_attr(
    conn,
    modo: str = "actual",
    iteraciones: int = 10000,
    seed: int = 42,
) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, source, target, prob_falla, es_sintetico FROM enlaces;")
        enlaces = cur.fetchall()
        cur.execute("SELECT id, nombre, rol, vertice_id FROM nodos_clave;")
        nodos = cur.fetchall()

    vertices_clave = [int(n["vertice_id"]) for n in nodos if n["vertice_id"] is not None]
    num_pares = len(vertices_clave) * (len(vertices_clave) - 1) // 2
    if num_pares == 0:
        return {
            "modo": modo,
            "metodo": "sin_pares",
            "iteraciones": 0,
            "attr": 0.0,
            "total_nodos_clave": len(nodos),
            "total_enlaces": len(enlaces),
        }

    enlaces_eval = []
    for e in enlaces:
        p = 0.0 if modo == "operacion" else float(e["prob_falla"] or 0.0)
        p = max(0.0, min(1.0, p))
        if e["source"] is not None and e["target"] is not None:
            enlaces_eval.append((int(e["source"]), int(e["target"]), p))

    enlaces_seguros = [(u, v) for (u, v, p) in enlaces_eval if p == 0.0]
    enlaces_inciertos = [(u, v, p) for (u, v, p) in enlaces_eval if 0.0 < p < 1.0]

    if not enlaces_inciertos:
        ady = defaultdict(list)
        for u, v in enlaces_seguros:
            ady[u].append(v)
            ady[v].append(u)
        res = _conectividad_pares(vertices_clave, ady)
        attr_val = sum(1.0 for ok in res.values() if ok) / num_pares
        return {
            "modo": modo,
            "metodo": "determinista",
            "iteraciones": 1,
            "attr": attr_val,
            "total_nodos_clave": len(nodos),
            "total_enlaces": len(enlaces),
        }

    rng = random.Random(seed)
    pares = [(vertices_clave[i], vertices_clave[j]) for i in range(len(vertices_clave)) for j in range(i + 1, len(vertices_clave))]
    suma_pares = {par: 0.0 for par in pares}

    for _ in range(iteraciones):
        ady = defaultdict(list)
        for u, v in enlaces_seguros:
            ady[u].append(v)
            ady[v].append(u)
        for u, v, p in enlaces_inciertos:
            if rng.random() >= p:
                ady[u].append(v)
                ady[v].append(u)

        res_iter = _conectividad_pares(vertices_clave, ady)
        for par, ok in res_iter.items():
            if ok:
                suma_pares[par] += 1.0 / iteraciones

    attr_val = sum(suma_pares.values()) / num_pares
    return {
        "modo": modo,
        "metodo": f"monte_carlo(seed={seed})",
        "iteraciones": iteraciones,
        "attr": attr_val,
        "total_nodos_clave": len(nodos),
        "total_enlaces": len(enlaces),
    }


def obtener_datos_leaflet(conn) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id,
                nombre,
                rol,
                tipo_infraestructura,
                vertice_id,
                ST_Y(geom::geometry) AS lat,
                ST_X(geom::geometry) AS lon
            FROM nodos_clave;
            """
        )
        nodos = cur.fetchall()

        cur.execute(
            """
            SELECT
                id,
                tipo_capa,
                prob_falla,
                es_sintetico,
                ST_AsGeoJSON(ST_Transform(geom::geometry, 4326))::json AS geojson
            FROM enlaces;
            """
        )
        enlaces = cur.fetchall()

        cur.execute(
            """
            SELECT
                ST_Y(geom::geometry) AS lat,
                ST_X(geom::geometry) AS lon,
                magnitud,
                titulo
            FROM sismo_27f
            LIMIT 1;
            """
        )
        sismo = cur.fetchone()

    return {"nodos": nodos, "enlaces": enlaces, "sismo": sismo}


HTML_LEAFLET = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Resiliencia Red Chile — 27F</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { margin: 0; font-family: sans-serif; }
    #map { height: 100vh; width: 100vw; }
    .panel {
      position: absolute; bottom: 20px; left: 12px; z-index: 1000;
      background: white; padding: 12px 14px; border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 310px; font-size: 13px;
      line-height: 1.45;
    }
    .swatch {
      display: inline-block; width: 12px; height: 12px; border-radius: 2px;
      margin-right: 6px; vertical-align: middle;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="panel" id="info">Cargando datos de red...</div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    function colorPorProb(p) {
      if (p >= 0.70) return "#b91c1c";
      if (p >= 0.40) return "#ea580c";
      if (p >= 0.15) return "#eab308";
      return "#16a34a";
    }

    fetch("/api/red")
      .then(r => r.json())
      .then(data => {
        const map = L.map("map").setView([-35.0, -71.5], 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap"
        }).addTo(map);

        const capaSismo = L.layerGroup().addTo(map);
        const capaReales = L.layerGroup().addTo(map);
        const capaSinteticos = L.layerGroup().addTo(map);
        const capaNodos = L.layerGroup().addTo(map);

        if (data.sismo && data.sismo.lat != null) {
          const centro = [data.sismo.lat, data.sismo.lon];
          L.circleMarker(centro, {
            radius: 11, color: "#000", fillColor: "#dc2626", fillOpacity: 0.9
          }).addTo(capaSismo).bindPopup(
            `<b>Epicentro ${data.sismo.magnitud ?? "8.8"} Mw</b><br>${data.sismo.titulo || "27F"}`
          );

          // Anillos de referencia de decaimiento espacial (L = 180 km y 2L = 360 km)
          [
            { radioM: 180000, etiqueta: "Radio L = 180 km (decaimiento base)" },
            { radioM: 360000, etiqueta: "Radio 2L = 360 km" }
          ].forEach(anillo => {
            L.circle(centro, {
              radius: anillo.radioM,
              color: "#dc2626",
              weight: 1.5,
              dashArray: "4, 4",
              fillColor: "#ef4444",
              fillOpacity: 0.06
            }).addTo(capaSismo).bindTooltip(anillo.etiqueta);
          });
        }

        let numReales = 0;
        let numSinteticos = 0;

        (data.enlaces || []).forEach(e => {
          const p = Number(e.prob_falla || 0);
          const esSint = Boolean(e.es_sintetico);
          const destino = esSint ? capaSinteticos : capaReales;
          if (esSint) numSinteticos++; else numReales++;

          L.geoJSON(e.geojson, {
            style: {
              color: colorPorProb(p),
              weight: esSint ? 2.5 : 4,
              dashArray: esSint ? "5, 5" : null,
              opacity: 0.88
            }
          }).addTo(destino).bindPopup(
            `<b>Enlace #${e.id}</b> (${e.tipo_capa})<br>` +
            `Prob. falla: <b>${p.toFixed(4)}</b><br>` +
            `Tipo: ${esSint ? "Sintético (línea punteada)" : "Real / Fibra base"}`
          );
        });

        (data.nodos || []).forEach(n => {
          L.circleMarker([n.lat, n.lon], {
            radius: 7, color: "#1e3a8a", fillColor: "#3b82f6", fillOpacity: 0.92
          }).addTo(capaNodos).bindPopup(
            `<b>${n.nombre}</b><br>` +
            `Rol: <b>${n.rol}</b><br>` +
            `Tipo: ${n.tipo_infraestructura}<br>` +
            `Vértice: ${n.vertice_id}`
          );
        });

        L.control.layers(null, {
          "Epicentro y anillos (180 / 360 km)": capaSismo,
          "Enlaces reales (fibra óptica)": capaReales,
          "Enlaces sintéticos (ferry / camino / postes)": capaSinteticos,
          "Nodos clave": capaNodos
        }, { collapsed: false }).addTo(map);

        document.getElementById("info").innerHTML =
          `<b>Red y Daño 27F (8.8 Mw)</b><br>` +
          `Nodos clave: ${(data.nodos || []).length}<br>` +
          `Enlaces reales: ${numReales} | Sintéticos: ${numSinteticos}<br><hr style="margin:6px 0">` +
          `<div><span class="swatch" style="background:#b91c1c"></span>p &ge; 0.70</div>` +
          `<div><span class="swatch" style="background:#ea580c"></span>0.40 &le; p &lt; 0.70</div>` +
          `<div><span class="swatch" style="background:#eab308"></span>0.15 &le; p &lt; 0.40</div>` +
          `<div><span class="swatch" style="background:#16a34a"></span>p &lt; 0.15</div>`;
      });
  </script>
</body>
</html>
"""

def obtener_datos_leaflet_con_conexion(dsn: str) -> dict:
    with psycopg.connect(dsn) as conn:
        return obtener_datos_leaflet(conn)


def servir_leaflet(payload_provider) -> None:
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/red":
                body = json.dumps(payload_provider()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML_LEAFLET.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Mapa Leaflet disponible en http://{HOST}:{PORT} (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()
# Reemplaza CAPAS_SHP en main.py para incluir nota_sintetico explícita
CAPAS_SHP = [
    {
        "stem": "fibra_optica_detectada",
        "tipo_capa": "fibra_optica",
        "es_sintetico": False,
        "nota_sintetico": None,
        "factor_falla": 1.00,
    },
    {
        "stem": "trayecto_en_ferry",
        "tipo_capa": "trayecto_en_ferry",
        "es_sintetico": True,
        "nota_sintetico": "Sintético: cruce marítimo/lacustre (ferry) para conectar tramos sin continuidad terrestre.",
        "factor_falla": 1.05,
    },
    {
        "stem": "camino_sin_postacion_detectado",
        "tipo_capa": "camino_sin_postacion",
        "es_sintetico": True,
        "nota_sintetico": "Sintético: corredor vial sin postación eléctrica como ruta alternativa o de canalización.",
        "factor_falla": 1.10,
    },
    {
        "stem": "postacion_electrica_detectada",
        "tipo_capa": "postacion_electrica",
        "es_sintetico": True,
        "nota_sintetico": "Sintético: infraestructura de postación asociada como corredor auxiliar/vulnerabilidad.",
        "factor_falla": 1.20,
    },
]


def conectar_nodos_referencia_a_red(conn, distancia_min_km: float = 0.01) -> int:
    """Inserta conectores sintéticos desde cada referencia al vértice más cercano.

    Debe ejecutarse después de una primera pgr_createTopology, para que
    enlaces_vertices_pgr exista. Los conectores terminan exactamente en un
    vértice existente y, por tanto, quedan unidos a su componente topológica.
    """
    creados = 0
    with conn.cursor(row_factory=dict_row) as cur:
        for ref in NODOS_REFERENCIA:
            cur.execute(
                """
                SELECT v.id AS vertice_id,
                       ST_X(v.the_geom) AS lon,
                       ST_Y(v.the_geom) AS lat,
                       ST_Distance(
                           v.the_geom::geography,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) / 1000.0 AS dist_km
                FROM enlaces_vertices_pgr v
                ORDER BY v.the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                LIMIT 1;
                """,
                (ref["lon"], ref["lat"], ref["lon"], ref["lat"]),
            )
            v = cur.fetchone()
            if not v:
                print(f"Aviso: no se encontró vértice para {ref['nombre']}.")
                continue

            distancia = float(v["dist_km"] or 0.0)
            if distancia <= distancia_min_km:
                continue

            cur.execute(
                """
                INSERT INTO enlaces (
                    id_origen, tipo_capa, geom, prob_falla,
                    es_sintetico, nota_sintetico
                )
                VALUES (
                    NULL,
                    'conector_nodo_clave',
                    ST_SetSRID(
                        ST_MakeLine(
                            ST_MakePoint(%s, %s),
                            ST_MakePoint(%s, %s)
                        ), 4326
                    ),
                    0.0,
                    TRUE,
                    %s
                );
                """,
                (
                    ref["lon"], ref["lat"], v["lon"], v["lat"],
                    f"Conector sintético desde {ref['nombre']} al vértice "
                    f"{v['vertice_id']} ({distancia:.2f} km). No representa fibra verificada.",
                ),
            )
            creados += 1
            print(
                f"  Conector creado: {ref['nombre']} -> vértice {v['vertice_id']} "
                f"({distancia:.2f} km)."
            )

    conn.commit()
    print(f"Conectores sintéticos de nodos clave agregados: {creados}")
    return creados


def construir_infraestructura_y_topologia(
    conn,
    shp_dir: Path,
    tol_deg: float = 0.0001,
) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE enlaces RESTART IDENTITY;")

    insertados = 0
    for cfg in CAPAS_SHP:
        shp_file = shp_dir / f"{cfg['stem']}.shp"
        if not shp_file.exists():
            print(f"Aviso: {shp_file} no encontrado, se omite.")
            continue

        transformer = obtener_transformador_4326(shp_file)
        sf = shapefile.Reader(str(shp_file))
        fields = [f[0] for f in sf.fields[1:]]
        id_idx = fields.index("id") if "id" in fields else None

        with conn.cursor() as cur:
            for sr in sf.shapeRecords():
                if sr.shape.shapeType == shapefile.NULL:
                    continue
                geom_4326 = reproyectar_geojson_geom(sr.shape.__geo_interface__, transformer)
                id_val = sr.record[id_idx] if id_idx is not None else None
                id_orig = int(id_val) if id_val is not None and str(id_val).isdigit() else None

                cur.execute(
                    """
                    INSERT INTO enlaces (id_origen, tipo_capa, geom, prob_falla, es_sintetico, nota_sintetico)
                    SELECT
                        %s,
                        %s,
                        (ST_Dump(ST_CollectionExtract(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 2))).geom,
                        0.0,
                        %s,
                        %s;
                    """,
                    (
                        id_orig,
                        cfg["tipo_capa"],
                        json.dumps(geom_4326),
                        cfg["es_sintetico"],
                        cfg["nota_sintetico"],
                    ),
                )
                insertados += cur.rowcount
        conn.commit()
        print(f"Cargada capa {cfg['stem']} (es_sintetico={cfg['es_sintetico']}).")
    agregar_enlace_sintetico_rapa_nui_valparaiso(conn)
    # Ejecución nativa de pgr_createTopology (pgRouting 3.7)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("DROP TABLE IF EXISTS enlaces_vertices_pgr CASCADE;")
        cur.execute("UPDATE enlaces SET source = NULL, target = NULL, prob_falla = 0.0;")
        print(
            f"\n--> Primera topología para localizar vértices de conexión "
            f"(tolerancia {tol_deg}°)"
        )
        cur.execute(
            "SELECT pgr_createTopology('public.enlaces', %s::double precision, 'geom', 'id', 'source', 'target') AS status;",
            (tol_deg,),
        )
        res_topo_inicial = cur.fetchone()
        print(f"    Resultado topología inicial: {res_topo_inicial['status']}")
        conn.commit()

        print("\n--> Conectando nodos clave a la red mediante enlaces sintéticos")
        conectar_nodos_referencia_a_red(conn)

        # Recalcular la topología incluyendo los nuevos conectores.
        cur.execute("DROP TABLE IF EXISTS enlaces_vertices_pgr CASCADE;")
        cur.execute("UPDATE enlaces SET source = NULL, target = NULL;")
        print(
            f"\n--> Ejecutando topología definitiva con conectores "
            f"pgr_createTopology('public.enlaces', {tol_deg}, 'geom', 'id', 'source', 'target')"
        )
        print(
            "    Tolerancia: 0.0001° en EPSG:4326 (~1.1 m)."
        )
        cur.execute(
            "SELECT pgr_createTopology('public.enlaces', %s::double precision, 'geom', 'id', 'source', 'target') AS status;",
            (tol_deg,),
        )
        res_topo = cur.fetchone()
        print(f"    Resultado pgr_createTopology definitivo: {res_topo['status']}")

        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM enlaces_vertices_pgr) AS total_vertices,
                count(*) AS total_enlaces,
                count(*) FILTER (WHERE prob_falla = 0.0) AS enlaces_prob_cero,
                count(*) FILTER (WHERE es_sintetico) AS enlaces_sinteticos,
                ROUND((SUM(ST_Length(geom::geography)) / 1000.0)::numeric, 2) AS km_totales,
                ROUND((SUM(ST_Length(geom::geography)) FILTER (WHERE NOT es_sintetico) / 1000.0)::numeric, 2) AS km_fibra_base
            FROM enlaces;
            """
        )
        stats = cur.fetchone()
    conn.commit()

    print("\n--- Estado de Topología Base (prob_falla = 0.0) ---")
    print(f"Tabla de vértices (enlaces_vertices_pgr): {stats['total_vertices']} vértices")
    print(
        f"Enlaces: {stats['total_enlaces']} | Con prob_falla=0.0: {stats['enlaces_prob_cero']} | Sintéticos: {stats['enlaces_sinteticos']}"
    )
    print(
        f"Longitud cargada -> Fibra base: {stats['km_fibra_base']} km | Total con sintéticos: {stats['km_totales']} km"
    )
    print(
        "Limitación declarada: los datos SAIP (~10.300 km aprox.) cubren solo una fracción de los ~28.000 km reportados en el Estudio de resiliencia, y los .dbf solo contienen 'id'."
    )



def activar_red_sintetica_intercomponentes(conn) -> int:
    """
    Une cada componente desconectada con la componente mayor mediante un
    enlace geométrico sintético al vértice más cercano de esa componente.
    Estos enlaces son hipótesis de conectividad, no infraestructura verificada.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH cc AS (
                SELECT component, node
                FROM pgr_connectedComponents(
                    'SELECT id, source, target, 1.0::float8 AS cost FROM enlaces WHERE source IS NOT NULL AND target IS NOT NULL'
                )
            ),
            tamanos AS (
                SELECT component, count(*) AS n
                FROM cc GROUP BY component
            ),
            principal AS (
                SELECT component FROM tamanos ORDER BY n DESC LIMIT 1
            ),
            vertices AS (
                SELECT cc.component, v.id, v.the_geom
                FROM cc JOIN enlaces_vertices_pgr v ON v.id = cc.node
            ),
            puentes AS (
                SELECT DISTINCT ON (v.component)
                    v.component, v.id AS origen_id,
                    cercano.id AS destino_id, v.the_geom AS geom_origen,
                    cercano.the_geom AS geom_destino
                FROM vertices v
                CROSS JOIN principal p
                CROSS JOIN LATERAL (
                    SELECT vp.id, vp.the_geom
                    FROM vertices vp
                    WHERE vp.component = p.component
                    ORDER BY v.the_geom <-> vp.the_geom
                    LIMIT 1
                ) cercano
                WHERE v.component <> p.component
                ORDER BY v.component, v.the_geom <-> cercano.the_geom
            )
            INSERT INTO enlaces (tipo_capa, geom, prob_falla, es_sintetico, nota_sintetico)
            SELECT
                'red_sintetica_intercomponentes',
                ST_MakeLine(geom_origen, geom_destino),
                0.0, TRUE,
                'Puente hipotético para análisis de sensibilidad: une una componente desconectada con la componente mayor. No representa fibra verificada.'
            FROM puentes
            RETURNING id;
            """
        )
        creados = len(cur.fetchall())
        if creados:
            cur.execute("DROP TABLE IF EXISTS enlaces_vertices_pgr CASCADE;")
            cur.execute("UPDATE enlaces SET source = NULL, target = NULL;")
            cur.execute(
                "SELECT pgr_createTopology('public.enlaces', 0.0001::double precision, 'geom', 'id', 'source', 'target');"
            )
    conn.commit()
    print(f"Red sintética intercomponentes: {creados} puentes hipotéticos creados.")
    return creados

def auditar_conectividad(conn) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH cc AS (
                SELECT component, node
                FROM pgr_connectedComponents(
                    'SELECT id, source, target, 1.0::float8 AS cost FROM enlaces WHERE source IS NOT NULL AND target IS NOT NULL'
                )
            ),
            resumen_comp AS (
                SELECT component, count(*) AS nodos
                FROM cc
                GROUP BY component
                ORDER BY nodos DESC
            )
            SELECT
                (SELECT count(*) FROM resumen_comp) AS total_componentes,
                (SELECT nodos FROM resumen_comp LIMIT 1) AS mayor_componente,
                (SELECT count(*) FROM enlaces_vertices_pgr v WHERE NOT EXISTS (
                    SELECT 1 FROM enlaces e WHERE e.source = v.id OR e.target = v.id
                )) AS vertices_aislados;
            """
        )
        comp = cur.fetchone()

        cur.execute(
            """
            WITH cc AS (
                SELECT component, node
                FROM pgr_connectedComponents(
                    'SELECT id, source, target, 1.0::float8 AS cost FROM enlaces WHERE source IS NOT NULL AND target IS NOT NULL'
                )
            )
            SELECT nc.id, nc.nombre, nc.rol, nc.vertice_id, cc.component
            FROM nodos_clave nc
            LEFT JOIN cc ON cc.node = nc.vertice_id
            ORDER BY nc.id;
            """
        )
        nodos_comp = cur.fetchall()

    print("\n--- Auditoría de Conectividad (pgr_connectedComponents) ---")
    componentes_clave = {n["component"] for n in nodos_comp if n["component"] is not None}
    nodos_clave_en_red = sum(1 for n in nodos_comp if n["component"] is not None)
    print(
        f"Componentes conexas: {comp['total_componentes']} | Mayor componente: {comp['mayor_componente']} vértices | Vértices aislados (grado 0): {comp['vertices_aislados']}"
    )
    print(
        f"Nodos clave asociados a la red: {nodos_clave_en_red}/{len(nodos_comp)} | "
        f"Componentes distintas entre nodos clave: {len(componentes_clave)}"
    )
    for n in nodos_comp:
        print(
            f"  - Nodo #{n['id']} [{n['rol']}] {n['nombre']} -> vertice_id={n['vertice_id']}, componente={n['component']}"
        )



def pga_montalva_2017_interface(
    magnitud: float,
    distancia_hyp_km: float,
    vs30_m_s: float = VS30_M_S,
) -> float:
    """
    Mediana de PGA (en g) para subducción interplaca usando Montalva et al. (2017).

    Se implementa la forma Montalva-2017 SInter con los coeficientes PGA
    publicados. Como la base solo contiene un punto epicentral y no la geometría
    finita de ruptura, Rhyp se usa como aproximación de Rrup; esto debe declararse
    como limitación del escenario.
    """
    # Coeficientes PGA Montalva et al. (2017), tabla de coeficientes.
    theta1 = 5.87504394
    theta2 = -1.75359772
    theta3 = 0.13125248
    theta4 = 0.80276784
    theta5 = -0.33486952
    theta6 = -0.00039095
    theta12 = 1.01494528
    vlin = 865.1
    b = -1.186
    n = 1.18
    c = 1.88
    theta9 = 0.4
    c4 = 10.0
    c1 = 7.2
    dc1 = 0.2

    if magnitud <= 0 or distancia_hyp_km < 0 or vs30_m_s <= 0:
        raise ValueError("Mw, distancia y Vs30 deben ser valores positivos.")

    # Término de magnitud.
    dmag = c1 + dc1
    f_mag = theta4 * (magnitud - dmag) if magnitud <= dmag else theta5 * (magnitud - dmag)
    f_mag += theta1 + theta4 * dc1

    # Término de atenuación con distancia.
    r = max(float(distancia_hyp_km), 0.1)
    f_path = (
        (theta2 + theta3 * (magnitud - c1))
        * math.log(r + c4 * math.exp((magnitud - 6.0) * theta9))
        + theta6 * r
    )

    # Término de sitio no lineal de Abrahamson et al. (2015),
    # con coeficientes Montalva et al. (2017).
    arg_rock = 1000.0 / vlin
    site_rock = (theta12 + b * n) * math.log(arg_rock)
    pga_rock = math.exp(f_mag + f_path + site_rock)

    vs_star = min(float(vs30_m_s), 1000.0)
    arg_site = vs_star / vlin
    site = theta12 * math.log(arg_site)
    if vs30_m_s >= vlin:
        site += b * n * math.log(arg_site)
    else:
        site += (
            -b * math.log(pga_rock + c)
            + b * math.log(pga_rock + c * (arg_site ** n))
        )

    return max(math.exp(f_mag + f_path + site), 1e-8)


def pgd_saygili_rathje_2008(pga_g: float, kc_g: float = KC_G) -> float:
    """
    Desplazamiento permanente PGD en metros según Saygili & Rathje (2008).
    La regresión original entrega D en centímetros; se convierte a metros
    antes de aplicar la tasa de reparación empírica de cables. PGA y kc en g.
    """
    pga = max(float(pga_g), 1e-8)
    ratio = float(kc_g) / pga
    ln_pgd = (
        5.52
        - 4.43 * ratio
        - 20.39 * ratio**2
        + 42.61 * ratio**3
        - 28.74 * ratio**4
        + 0.72 * math.log(pga)
    )
    # Saygili & Rathje (2008) reportan D en cm. Convertir a m porque la
    # relación empírica de reparación de cables usa PGD en metros.
    pgd_cm = math.exp(max(-50.0, min(20.0, ln_pgd)))
    return pgd_cm / 100.0


def tasa_falla_fibra_por_km(
    pgd_m: float,
    alpha: float = ALFA_CABLE,
) -> float:
    """
    Tasa FR (fallas esperadas/km) derivada del modelo de fibra enterrada
    reproducido por Jiménez, Barrera & Cancela (2023), basado en Esposito et al.
    La forma empírica es FR = alpha * 4.317 * PGD^0.324, con PGD en metros.
    """
    if pgd_m <= 0:
        return 0.0
    return max(0.0, float(alpha) * 4.317 * (float(pgd_m) ** 0.324))


def aplicar_escenario_sismo_27f(
    conn,
    alpha: float = ALFA_CABLE,
    kc_g: float = KC_G,
    vs30_m_s: float = VS30_M_S,
    longitud_segmento_km: float = LONGITUD_SEGMENTO_KM,
) -> None:
    """
    Asigna probabilidad de falla por enlace mediante el modelo de Jiménez et al.
    (2023): discretización espacial de 10 km, PGA Montalva-2017, PGD
    Saygili-Rathje y tasa Poisson por segmento.

    Para cada segmento l:
        FR_l = alpha * 4.317 * PGD_l**0.324
    Para el enlace:
        Lambda_L = sum_l (longitud_l * FR_l)
        P_f,L = 1 - exp(-Lambda_L)

    El modelo publicado supone cables ópticos enterrados. En esta adaptación,
    todos los enlaces geométricos del grafo se tratan como corredores equivalentes
    de fibra enterrada; enlaces sintéticos siguen siendo hipótesis de modelación.
    """
    if not (0.0 < alpha <= 5.0):
        raise ValueError("alpha debe estar en el intervalo (0, 5].")
    if kc_g <= 0 or vs30_m_s <= 0 or longitud_segmento_km <= 0:
        raise ValueError("kc, Vs30 y longitud de segmento deben ser positivos.")

    segmento_m = longitud_segmento_km * 1000.0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT magnitud, profundidad_km,
                   ST_X(geom) AS epicentro_lon,
                   ST_Y(geom) AS epicentro_lat
            FROM sismo_27f
            ORDER BY id DESC
            LIMIT 1;
            """
        )
        evento = cur.fetchone()
        if not evento:
            raise RuntimeError("No hay un evento en sismo_27f.")

        # Segmentos geodésicos de hasta 10 km; PGA se evalúa en el punto medio.
        cur.execute(
            """
            WITH s AS (
                SELECT geom, magnitud, profundidad_km
                FROM sismo_27f
                ORDER BY id DESC
                LIMIT 1
            ),
            segmentos AS (
                SELECT
                    e.id AS enlace_id,
                    e.tipo_capa,
                    ST_Length(d.geom::geography) / 1000.0 AS longitud_km,
                    ST_Distance(
                        ST_LineInterpolatePoint(d.geom, 0.5)::geography,
                        s.geom::geography
                    ) / 1000.0 AS distancia_epicentral_km,
                    s.magnitud,
                    s.profundidad_km
                FROM enlaces e
                CROSS JOIN s
                CROSS JOIN LATERAL ST_DumpSegments(
                    ST_Segmentize(e.geom::geography, %s)::geometry
                ) AS d
                WHERE e.geom IS NOT NULL
                  AND GeometryType(e.geom) IN ('LINESTRING')
            )
            SELECT enlace_id, tipo_capa, longitud_km,
                   distancia_epicentral_km, magnitud, profundidad_km
            FROM segmentos
            ORDER BY enlace_id;
            """,
            (segmento_m,),
        )
        segmentos = cur.fetchall()

    if not segmentos:
        raise RuntimeError("No se generaron segmentos para calcular las fallas.")

    lambda_por_enlace = defaultdict(float)
    pga_min = float("inf")
    pga_max = 0.0
    pgd_max = 0.0

    for seg in segmentos:
        d_epi = float(seg["distancia_epicentral_km"] or 0.0)
        profundidad = float(seg["profundidad_km"] or EVENTO_PROFUNDIDAD_DEFAULT_KM)
        # Punto fuente: distancia hipocentral como aproximación de Rrup.
        r_hyp = math.sqrt(d_epi**2 + profundidad**2)

        pga_g = pga_montalva_2017_interface(
            magnitud=float(seg["magnitud"]),
            distancia_hyp_km=r_hyp,
            vs30_m_s=vs30_m_s,
        )
        pgd_m = pgd_saygili_rathje_2008(pga_g=pga_g, kc_g=kc_g)
        fr_km = tasa_falla_fibra_por_km(pgd_m=pgd_m, alpha=alpha)

        lambda_por_enlace[int(seg["enlace_id"])] += (
            float(seg["longitud_km"]) * fr_km
        )
        pga_min = min(pga_min, pga_g)
        pga_max = max(pga_max, pga_g)
        pgd_max = max(pgd_max, pgd_m)

    actualizaciones = [
        (1.0 - math.exp(-lam), enlace_id)
        for enlace_id, lam in lambda_por_enlace.items()
    ]

    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE enlaces SET prob_falla = %s WHERE id = %s;",
            actualizaciones,
        )
    conn.commit()

    print("\\n--- Modelo probabilístico de falla: Jiménez et al. (2023) ---")
    print(f"Segmentos evaluados: {len(segmentos)} (máximo {longitud_segmento_km:.1f} km)")
    print(f"Enlaces evaluados: {len(actualizaciones)}")
    print(f"Mw={evento['magnitud']:.2f} | profundidad={evento['profundidad_km']:.1f} km")
    print(f"Parámetros: alpha={alpha:.2f} | kc={kc_g:.2f} g | Vs30={vs30_m_s:.0f} m/s")
    print(f"PGA mediana por segmentos: {pga_min:.5f}–{pga_max:.5f} g")
    print(f"PGD máximo estimado: {pgd_max:.4f} m")
    print(
        "Nota: Rrup se aproxima con distancia hipocentral porque el GeoJSON solo "
        "aporta un epicentro puntual; Vs30 es un valor uniforme supuesto."
    )
    print(
        "Nota: se asume que todos los enlaces modelados equivalen a fibra enterrada; "
        "los enlaces sintéticos no son infraestructura verificada."
    )

def main() -> None:
    run_cmd(["docker", "compose", "up", "-d", "--wait"])
    wait_for_db(DB_DSN)
    apply_sql_file(DB_DSN, SQL_FILE)

    shp_dir = preparar_directorio_shp()

    with psycopg.connect(DB_DSN) as conn:
        cargar_sismo_27f(conn, SISMO_GEOJSON_PATH)
        construir_infraestructura_y_topologia(conn, shp_dir, tol_deg=0.0001)
        seleccionar_nodos_clave(conn, top_hubs=3)
        auditar_conectividad(conn)

        # Escenario base: red cargada, sin fallas.
        attr_antes = calcular_attr(conn, modo="operacion")
        print(f"\nATTR base (operación, sin fallas): {attr_antes['attr']:.6f}")

        # Opción experimental controlada desde la configuración al inicio del archivo.
        usar_red_sintetica = USAR_RED_SINTETICA
        print(f"\nRed sintética intercomponentes: {'ACTIVADA' if usar_red_sintetica else 'DESACTIVADA'}")
        if usar_red_sintetica:
            puentes = activar_red_sintetica_intercomponentes(conn)
            # La topología puede haber cambiado; volver a asociar nodos clave.
            seleccionar_nodos_clave(conn, top_hubs=3)
            auditar_conectividad(conn)
            attr_red_sintetica = calcular_attr(conn, modo="operacion")
            print(f"ATTR con red sintética (operación, sin fallas): {attr_red_sintetica['attr']:.6f}")
            print(f"Cambio atribuible a puentes hipotéticos: {attr_red_sintetica['attr'] - attr_antes['attr']:+.6f}")
            print(f"Puentes sintéticos agregados: {puentes}")

        # Aplicar sismo y calcular ATTR en el escenario actualmente seleccionado.
        aplicar_escenario_sismo_27f(
            conn, alpha=ALFA_CABLE, kc_g=KC_G, vs30_m_s=VS30_M_S,
            longitud_segmento_km=LONGITUD_SEGMENTO_KM
        )
        attr_despues = calcular_attr(conn, modo="post_sismo")
        attr_referencia = attr_red_sintetica["attr"] if usar_red_sintetica else attr_antes["attr"]
        diff = attr_despues["attr"] - attr_referencia
        pct = (diff / attr_referencia * 100.0) if attr_referencia else 0.0
        print(f"ATTR después (sismo 8.8):             {attr_despues['attr']:.6f}")
        print(f"Variación respecto al escenario operativo seleccionado: {diff:+.6f} ({pct:+.2f}%)")
    servir_leaflet(lambda: obtener_datos_leaflet_con_conexion(DB_DSN))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando comando externo: {exc}", file=sys.stderr)
        sys.exit(1)