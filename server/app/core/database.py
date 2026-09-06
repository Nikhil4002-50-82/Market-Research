from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

connection_args = {}
if settings.database_url.startswith("sqlite"):
    connection_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connection_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def initialize_database():
    Base.metadata.create_all(bind=engine)
