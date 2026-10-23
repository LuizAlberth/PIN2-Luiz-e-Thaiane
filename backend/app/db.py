import os
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL and os.getenv('POSTGRES_HOST'):
    DATABASE_URL = URL.create('postgresql+psycopg', username='pin2',
        password=os.getenv('POSTGRES_PASSWORD'), host=os.getenv('POSTGRES_HOST'), database='pin2')
DATABASE_URL = DATABASE_URL or 'sqlite:///./pin2.db'
kwargs = {'connect_args': {'check_same_thread': False, 'timeout': 30}} if str(DATABASE_URL).startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **kwargs)
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def sqlite_busy_timeout(connection, _):
        connection.execute('PRAGMA busy_timeout=30000')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def initialize():
    # Geometries are generated from the immutable configuration snapshot.
    # SQLite remains available for local tests and development without Docker.
    if engine.dialect.name == 'sqlite':
        with engine.begin() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode=WAL')
    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            connection.execute(text('''ALTER TABLE monitoring_configs ADD COLUMN IF NOT EXISTS aoi geometry(Polygon,4326)
                GENERATED ALWAYS AS (ST_MakeEnvelope((bbox->>0)::float8, (bbox->>1)::float8,
                (bbox->>2)::float8, (bbox->>3)::float8, 4326)) STORED'''))
            connection.execute(text('''ALTER TABLE monitoring_configs ADD COLUMN IF NOT EXISTS station_location geometry(Point,4326)
                GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(station_lon, station_lat),4326)) STORED'''))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_configs_aoi_gist ON monitoring_configs USING GIST(aoi)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_configs_station_gist ON monitoring_configs USING GIST(station_location)'))
