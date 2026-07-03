import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from rinse.interfaces.api import create_app


class ApiTests(unittest.TestCase):
    def test_upload_profile_preview_clean_report_and_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(Path(directory)))
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
            self.assertEqual(job.json()["status"], "completed")

            status = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["status"], "completed")

            result = client.get(f"/api/jobs/{job_id}/result")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["rows"][0]["name"], "Alice")

            report = client.get(f"/api/jobs/{job_id}/report")
            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.json()["report"]["validation_issue_count"], 1)
            self.assertEqual(report.json()["report"]["export_artifacts"][1]["kind"], "html")

            download = client.get(f"/api/jobs/{job_id}/download")
            self.assertEqual(download.status_code, 200)
            self.assertIn("Alice", download.text)

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
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
