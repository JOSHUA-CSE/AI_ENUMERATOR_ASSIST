import sqlite3
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Create SQLAlchemy engine
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

if is_sqlite:
    # Handle SQLite table creation and drop when SpatiaLite is not compiled in
    try:
        import geoalchemy2.admin.dialects.sqlite as sqlite_admin

        original_after_create = sqlite_admin.after_create
        original_before_drop = sqlite_admin.before_drop

        def safe_after_create(table, bind, **kw):
            try:
                original_after_create(table, bind, **kw)
            except Exception as e:
                if "no such function" in str(e).lower():
                    pass
                else:
                    raise

        def safe_before_drop(table, bind, **kw):
            try:
                original_before_drop(table, bind, **kw)
            except Exception as e:
                if "no such function" in str(e).lower():
                    pass
                else:
                    raise

        sqlite_admin.after_create = safe_after_create
        sqlite_admin.before_drop = safe_before_drop
    except ImportError:
        pass

if is_sqlite:

    def sqlite_geom_from_ewkt(val, srid=None):
        if not val:
            return val
        try:
            import shapely
            import shapely.wkt

            if isinstance(val, str):
                if ";" in val:
                    srid_part, wkt_part = val.split(";", 1)
                    srid_val = int(srid_part.replace("SRID=", ""))
                    geom = shapely.wkt.loads(wkt_part)
                    shapely.set_srid(geom, srid_val)
                    return shapely.to_wkb(geom, hex=False, include_srid=True)
                else:
                    geom = shapely.wkt.loads(val)
                    srid_val = int(srid) if srid is not None else 4326
                    shapely.set_srid(geom, srid_val)
                    return shapely.to_wkb(geom, hex=False, include_srid=True)
        except Exception:
            pass
        return val

    @event.listens_for(Engine, "connect")
    def setup_sqlite_gis_functions(dbapi_connection, _connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            funcs = [
                ("AsEWKB", 1, lambda x: x),
                ("AsEWKB", 2, lambda x, _srid: x),
                ("AsEWKT", 1, lambda x: x),
                ("AsEWKT", 2, lambda x, _srid: x),
                ("AsBinary", 1, lambda x: x),
                ("AsText", 1, lambda x: x),
                ("GeomFromEWKB", 1, lambda x: x),
                ("GeomFromEWKB", 2, lambda x, _srid: x),
                ("GeomFromEWKT", 1, sqlite_geom_from_ewkt),
                ("GeomFromEWKT", 2, lambda v, s: sqlite_geom_from_ewkt(v, s)),
                ("GeomFromText", 1, sqlite_geom_from_ewkt),
                ("GeomFromText", 2, lambda v, s: sqlite_geom_from_ewkt(v, s)),
                ("GeomFromWKB", 1, lambda x: x),
                ("GeomFromWKB", 2, lambda x, _srid: x),
                ("ST_AsEWKB", 1, lambda x: x),
                ("ST_AsEWKT", 1, lambda x: x),
                ("ST_GeomFromEWKB", 1, lambda x: x),
                ("ST_GeomFromEWKT", 1, sqlite_geom_from_ewkt),
                ("RecoverGeometryColumn", 5, lambda *_args: 1),
                ("AddGeometryColumn", 5, lambda *_args: 1),
                ("DiscardGeometryColumn", 2, lambda *_args: 1),
                ("CreateSpatialIndex", 2, lambda *_args: 1),
                ("DisableSpatialIndex", 2, lambda *_args: 1),
                ("CheckSpatialIndex", 2, lambda *_args: 1),
                ("CheckSpatialIndex", 3, lambda *_args: 1),
            ]
            for name, n_args, fn in funcs:
                try:
                    dbapi_connection.create_function(name, n_args, fn)
                except Exception:
                    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency to get a SQLAlchemy database session.
    Ensures that sessions are closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
