import json
import os
import unittest
from unittest.mock import patch

from worker.tasks import text_analysis


class ClientApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as app_module
        cls.app_module = app_module
        app_module.DB_READY = True
        app_module.app.config.update(TESTING=True)
        cls.client = app_module.app.test_client()

    def test_text_analysis_counts_real_input(self):
        result = text_analysis({"text": "Cloud jobs\ncloud"})
        self.assertEqual(result["word_count"], 3)
        self.assertEqual(result["line_count"], 2)
        self.assertEqual(result["most_frequent_words"][0], {"word": "cloud", "count": 2})

    def test_client_auth_and_submission(self):
        token_json = json.dumps({"pc2": "test-client-token"})
        with patch.dict(os.environ, {"CLIENT_TOKENS_JSON": token_json}):
            unauth = self.client.post("/api/client/jobs", json={"task_type": "text_analysis", "parameters": {"text": "hi"}})
            self.assertEqual(unauth.status_code, 401)
            with patch.object(self.app_module, "list_jobs", return_value=[]), \
                 patch.object(self.app_module, "list_workers", return_value=[]), \
                 patch.object(self.app_module, "choose_worker", return_value=None), \
                 patch.object(self.app_module, "create_job", return_value={"job_id": "JOB-TEST", "status": "QUEUED"}) as create:
                response = self.client.post("/api/client/jobs", headers={"Authorization": "Bearer test-client-token"},
                                            json={"task_type": "text_analysis", "parameters": {"text": "hello"}})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(create.call_args.kwargs["client_id"], "pc2")
            self.assertEqual(create.call_args.kwargs["input_data"], {"text": "hello"})

    def test_client_cannot_retrieve_another_clients_job(self):
        with patch.dict(os.environ, {"CLIENT_TOKENS_JSON": '{"pc2":"test-client-token"}'}), \
             patch.object(self.app_module, "get_job", return_value=None) as get_job:
            response = self.client.get("/api/client/jobs/JOB-OTHER", headers={"Authorization": "Bearer test-client-token"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(get_job.call_args.kwargs["client_id"], "pc2")


if __name__ == "__main__":
    unittest.main()
