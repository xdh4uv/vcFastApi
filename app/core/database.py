from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# Bound connections per process. Neon pooling alone does not reuse our TLS sockets.
pool_options = {
    "pool_size": 5, "max_overflow": 5, "pool_timeout": 10,
    "pool_recycle": 300, "pool_use_lifo": True,
} if settings.database_url.startswith(("postgresql", "postgres:")) else {}
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    **pool_options,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
