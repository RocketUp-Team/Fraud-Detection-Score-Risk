"""Engine + session SQLAlchemy 2.0.

Không dùng Alembic cho demo 8 ngày — schema tạo bằng `Base.metadata.create_all`
lúc startup (xem `main.lifespan`). Nếu sau này cần migration thật thì thêm
Alembic, nhưng với 2 bảng và DB tạo lại được thì đó là chi phí không cần thiết.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# SQLite in-memory: mỗi connection là một DB riêng, nên phải dùng StaticPool để
# cả app (và test) dùng đúng một connection — nếu không, bảng vừa tạo sẽ "mất".
_kwargs = {"poolclass": StaticPool} if config.DATABASE_URL in ("sqlite://", "sqlite:///:memory:") else {}

engine = create_engine(
    config.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args, **_kwargs
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency — 1 session cho mỗi request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
