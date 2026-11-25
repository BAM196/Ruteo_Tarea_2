CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

DROP TABLE IF EXISTS enlaces_vertices_pgr CASCADE;
DROP TABLE IF EXISTS nodos_clave CASCADE;
DROP TABLE IF EXISTS enlaces CASCADE;
DROP TABLE IF EXISTS sismo_27f CASCADE;

CREATE TABLE enlaces (
  id serial PRIMARY KEY,
  id_origen integer,
  tipo_capa text NOT NULL DEFAULT 'fibra_optica',
  geom geometry(LineString, 4326) NOT NULL,
  source integer,
  target integer,
  prob_falla double precision NOT NULL DEFAULT 0.0,
  es_sintetico boolean NOT NULL DEFAULT false,
  nota_sintetico text
);

CREATE TABLE nodos_clave (
  id serial PRIMARY KEY,
  nombre text NOT NULL,
  tipo_infraestructura text NOT NULL,
  rol text NOT NULL,
  justificacion text NOT NULL,
  geom geometry(Point, 4326) NOT NULL,
  vertice_id integer
);

CREATE TABLE sismo_27f (
  id serial PRIMARY KEY,
  titulo text NOT NULL,
  magnitud double precision NOT NULL,
  geom geometry(Point, 4326) NOT NULL
);

--INSERT INTO sismo_27f (titulo, magnitud, geom)
--VALUES (
--  'M 8.8 - 2010 Maule, Chile Earthquake',
--  8.8,
--  ST_SetSRID(ST_MakePoint(-72.898, -36.122), 4326)
--);