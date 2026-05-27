from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings


def _enable_sqlite_vec(dbapi_conn, _conn_record):
    """Load sqlite-vec extension on every new connection."""
    try:
        import sqlite_vec
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)
    except Exception:
        # sqlite-vec is optional for P0; RAG features require it later.
        pass


settings.db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_file}",
    connect_args={"check_same_thread": False},
    future=True,
)
event.listen(engine, "connect", _enable_sqlite_vec)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Session:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db():
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def init_db():
    """Create all tables and ensure sqlite-vec virtual table for embeddings."""
    from app import models  # noqa: F401 - ensure models are registered
    models.Base.metadata.create_all(bind=engine)

    # sqlite-vec virtual table for chunk embeddings (idempotent).
    with engine.begin() as conn:
        try:
            conn.exec_driver_sql(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
                f"USING vec0(embedding FLOAT[{settings.embedding_dim}])"
            )
        except Exception:
            # sqlite-vec extension not loaded yet (P0 ok without it)
            pass
