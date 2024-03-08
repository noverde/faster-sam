import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from yoyo import get_backend, read_migrations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def migrate(app: FastAPI):
    """
    Asynchronous context manager for database migration.

    This function reads database migration files from the specified path
    and applies them to the database specified by the DATABASE_URL environment variable.

    Parameters
    ----------
    app: FastAPI
        The FastAPI application instance.

    e.g
    This is an usage of the migrate function within a FastAPI application.

    >>> from fastapi import FastAPI
    >>> from faster_sam.utils import migrate
    >>> app = FastAPI(lifespan=migrate)

    Returns
    -------
        None
    """
    logger.info("Migrating database...")
    database_url = os.getenv("DATABASE_URL")
    database_migration_path = os.getenv("MIGRATION_PATH", "./migrations")
    backend = get_backend(database_url)
    migrations = read_migrations(database_migration_path)
    backend.apply_migrations(backend.to_apply(migrations))
    logger.info("Migration successful")
    yield
