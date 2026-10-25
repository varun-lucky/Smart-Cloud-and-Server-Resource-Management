"""Opt-in MySQL integration tests.

Set SMARTCLOUD_MYSQL_INTEGRATION_TESTS=1 and configure .env to point to a dedicated
MySQL test database before running these. The tests create sample jobs/reservations.
"""
import os
import unittest
import uuid


_RUN_MYSQL_TESTS = os.getenv("SMARTCLOUD_MYSQL_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(_RUN_MYSQL_TESTS, "Set SMARTCLOUD_MYSQL_INTEGRATION_TESTS=1 to run MySQL integration tests")
class MySQLResourceStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cloud import db, resource_store
        import app as app_module
        cls.db = db
        cls.resources = resource_store
        cls.app_module = app_module
        cls.db.init_db()
        app_module.DB_READY = True
        app_module.app.config.update(TESTING=True)
        cls.client = app_module.app.test_client()
        cls.headers = {"Authorization": "Bearer " + os.getenv("ADMIN_TOKEN", "")}
        cls.prefix = "it-" + uuid.uuid4().hex[:8]

    def setUp(self):
        self.owner = self.prefix + "-" + uuid.uuid4().hex[:8]

    def test_allocation_and_release_restore_capacity(self):
        before = self.resources.snapshot()
        result = self.resources.allocate(self.owner, {"cpu_cores": 1, "ram_mb": 256, "disk_mb": 512})
        self.assertTrue(result["allocated"])
        after = self.resources.snapshot()
        self.assertEqual(len(after["allocations"]), len(before["allocations"]) + 1)
        server_before = next(s for s in before["servers"] if s["server_id"] == result["server"]["server_id"])
        server_after = next(s for s in after["servers"] if s["server_id"] == result["server"]["server_id"])
        self.assertEqual(server_before["cpu_available"] - server_after["cpu_available"], 1)
        self.assertTrue(self.resources.release(self.owner)["released"])
        final = self.resources.snapshot()
        server_final = next(s for s in final["servers"] if s["server_id"] == result["server"]["server_id"])
        self.assertEqual(server_final["cpu_available"], server_before["cpu_available"])

    def test_insufficient_request_does_not_mutate_capacity(self):
        before = self.resources.snapshot()
        result = self.resources.allocate(self.owner, {"cpu_cores": 999, "ram_mb": 1, "disk_mb": 1})
        self.assertFalse(result["allocated"])
        self.assertEqual(before["servers"], self.resources.snapshot()["servers"])

    def test_duplicate_active_owner_is_rejected(self):
        self.assertTrue(self.resources.allocate(self.owner, {"cpu_cores": 1})["allocated"])
        self.assertFalse(self.resources.allocate(self.owner, {"ram_mb": 1})["allocated"])
        self.resources.release(self.owner)

    def test_invalid_request_is_rejected(self):
        with self.assertRaises(ValueError):
            self.resources.allocate(self.owner, {"cpu_cores": -1})
        with self.assertRaises(ValueError):
            self.resources.allocate(self.owner, {"gpu": 1})
        with self.assertRaises(ValueError):
            self.resources.allocate(self.owner, {"ram_mb": "not-a-number"})

    def test_concurrent_allocations_do_not_overcommit(self):
        from concurrent.futures import ThreadPoolExecutor
        def reserve(owner):
            return self.resources.allocate(owner, {"cpu_cores": 8, "ram_mb": 1024, "disk_mb": 100})["allocated"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(reserve, [self.owner + "a", self.owner + "b"]))
        self.assertEqual(sum(bool(value) for value in outcomes), 1)
        self.resources.release(self.owner + "a")
        self.resources.release(self.owner + "b")

    def test_queue_claim_and_job_state_updates(self):
        job = self.db.create_job(self.owner, "system_info", 1, 128, 100, None)
        worker_id = self.owner + "-worker"
        self.db.upsert_worker(worker_id, worker_id, {}, {})
        claimed = self.db.assign_next_job(worker_id)
        self.assertEqual(claimed["job_id"], job["job_id"])
        self.assertEqual(claimed["status"], "DISPATCHED")
        self.assertFalse(self.db.update_job_result(job["job_id"], "other-worker", {"status": "COMPLETED"}))
        self.assertTrue(self.db.update_job_result(job["job_id"], worker_id, {"status": "RUNNING", "os_pid": 99}))
        self.assertTrue(self.db.update_job_result(job["job_id"], worker_id, {"status": "COMPLETED", "result": {"ok": True}}))
        self.assertFalse(self.db.update_job_result(job["job_id"], worker_id, {"status": "FAILED"}))

    def test_resource_api_protects_admin_endpoint(self):
        self.assertEqual(self.client.get("/api/phase2/resources").status_code, 401)
        response = self.client.get("/api/phase2/resources", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.get_json()["servers"]), 3)
