import asyncio
import os
import shutil
import sqlite3
import tempfile
import unittest

from fastapi import FastAPI

from faster_sam.utils import migrate


class TestMigrate(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.con = sqlite3.connect(self.db_path)
        self.cur = self.con.cursor()
        os.environ["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        os.environ["MIGRATION_PATH"] = "tests/fixtures/migrations"

    def tearDown(self):
        self.con.close()
        shutil.rmtree(self.temp_dir)
        del os.environ["DATABASE_URL"]
        del os.environ["MIGRATION_PATH"]

    def test_migrate(self):
        async def migrate_and_check():
            async with migrate(FastAPI()):
                self.cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
                table_exists = self.cur.fetchone()
                self.assertTrue(table_exists)

        asyncio.run(migrate_and_check())
