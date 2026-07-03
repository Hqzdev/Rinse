import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from rinse.interfaces.api import create_app


class ApiTests(unittest.TestCase):
    def test_upload_profile_preview_clean_report_and_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = TestClient(create_app(root))
            upload = client.post(
                "/api/datasets/upload",
                files={"file": ("dirty.csv", b"name,email\n Alice ,ALICE@EXAMPLE.COM\nBob,\n")},
            )
            self.assertEqual(upload.status_code, 200)
            dataset_id = upload.json()["dataset_id"]
            self.assertEqual(upload.json()["rows"], 2)
            self.assertEqual(upload.json()["column_names"], ["name", "email"])

            profile = client.get(f"/api/datasets/{dataset_id}/profile")
            self.assertEqual(profile.status_code, 200)
            self.assertEqual(profile.json()["rows"], 2)
            self.assertEqual(profile.json()["columns"], 2)

            preview = client.post(
                f"/api/datasets/{dataset_id}/preview",
                json={
                    "options": {
                        "normalize": "text,email",
                        "text_columns": "name",
                        "email_columns": "email",
                        "text_case": "title",
                        "validate": "required",
                        "required_columns": "name,email",
                    },
                    "limit": 2,
                },
            )
            self.assertEqual(preview.status_code, 200)
            self.assertTrue(preview.json()["preview"])
            self.assertEqual(preview.json()["rows"][0]["name"], "Alice")
            self.assertEqual(preview.json()["rows"][0]["email"], "alice@example.com")
            self.assertEqual(preview.json()["report"]["validation_issue_count"], 1)

            job = client.post(
                "/api/jobs/clean",
                json={
                    "dataset_id": dataset_id,
                    "output_format": "json",
                    "report_format": "html",
                    "options": {
                        "normalize": "text,email",
                        "text_columns": "name",
                        "email_columns": "email",
                        "text_case": "title",
                        "validate": "required",
                        "required_columns": "name,email",
                    },
                },
            )
            self.assertEqual(job.status_code, 200)
            job_id = job.json()["job_id"]
            self.assertEqual(job.json()["status"], "queued")

            status = self.wait_for_job(client, job_id)
            self.assertEqual(status.json()["status"], "completed")
            self.assertEqual(status.json()["artifacts"][0]["label"], "Audit report")
            self.assertEqual(status.json()["artifacts"][1]["label"], "Clean output")

            result = client.get(f"/api/jobs/{job_id}/result")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["rows"][0]["name"], "Alice")

            report = client.get(f"/api/jobs/{job_id}/report")
            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.json()["report"]["validation_issue_count"], 1)
            self.assertEqual(report.json()["report"]["export_artifacts"][1]["kind"], "html")

            report_download = client.get(f"/api/jobs/{job_id}/report/download")
            self.assertEqual(report_download.status_code, 200)
            self.assertIn("<!doctype html>", report_download.text.lower())

            download = client.get(f"/api/jobs/{job_id}/download")
            self.assertEqual(download.status_code, 200)
            self.assertIn("Alice", download.text)

            reopened = TestClient(create_app(root))
            persisted = reopened.get(f"/api/jobs/{job_id}")
            self.assertEqual(persisted.status_code, 200)
            self.assertEqual(persisted.json()["status"], "completed")
            self.assertEqual(len(persisted.json()["artifacts"]), 2)

            persisted_report = reopened.get(f"/api/jobs/{job_id}/report")
            self.assertEqual(persisted_report.status_code, 200)
            self.assertEqual(persisted_report.json()["report"]["validation_issue_count"], 1)

    def test_api_returns_structured_not_found_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(Path(directory)))
            response = client.get("/api/datasets/missing/profile")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"]["code"], "not_found")

    def test_clean_rejects_unsupported_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(Path(directory)))
            upload = client.post(
                "/api/datasets/upload",
                files={"file": ("dirty.csv", b"name,email\nAlice,alice@example.com\n")},
            )
            response = client.post(
                "/api/jobs/clean",
                json={
                    "dataset_id": upload.json()["dataset_id"],
                    "output_format": "html",
                    "report_format": "json",
                },
            )
            self.assertEqual(response.status_code, 200)
            status = self.wait_for_job(client, response.json()["job_id"], "failed")
            self.assertEqual(status.json()["status"], "failed")
            self.assertIn("Unsupported clean output format", status.json()["error"])

    def wait_for_job(self, client: TestClient, job_id: str, status: str = "completed"):
        last_response = None
        for _ in range(100):
            last_response = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(last_response.status_code, 200)
            if last_response.json()["status"] == status:
                return last_response
        self.fail(f"Job {job_id} did not reach {status}: {last_response.json() if last_response else None}")


if __name__ == "__main__":
    unittest.main()
