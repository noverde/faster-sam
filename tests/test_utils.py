import sqlite3
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from fastapi import FastAPI
from faster_sam.utils import migrate


class TestMigrate(IsolatedAsyncioTestCase):

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.cur = self.con.cursor()

    @patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"})
    @patch.dict(os.environ, {"MIGRATION_PATH": "./fixtures/migrations"})
    async def test_migrate(self):
        await migrate(app=FastAPI())
        self.cur.execute("SELECT * FROM users")
        results = self.cur.fetchall()
        self.assertEqual(len(results), 1)
        for result in results:
            print(result)

    def tearDown(self):
        self.con.close()
