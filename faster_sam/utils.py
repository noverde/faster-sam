import logging
import os
from yoyo import read_migrations
from yoyo import get_backend
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def migrate(app):
    import ipdb

    ipdb.set_trace()
    logger.info("Migrating database...")
    database_url = os.getenv("DATABASE_URL")
    database_migration_path = os.getenv("MIGRATION_PATH", "./migrations")
    backend = get_backend(database_url)
    migrations = read_migrations(database_migration_path)
    backend.apply_migrations(backend.to_apply(migrations))
    logger.info("Migration successful")
    yield
