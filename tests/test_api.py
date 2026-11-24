"""Integration Tests for FastAPI Backend & Asynchronous Workflow (Step 9).

Verifies:
  1. Health check endpoint
  2. Teacher authentication (Registration & Login with JWT tokens)
  3. Assignment management with teacher data isolation
  4. Document upload returning status 'queued' (HTTP 202)
  5. Async background processing transition: 'queued' -> 'processing' -> 'done'
  6. Full unified report retrieval matching the unified schema
  7. Teacher access control & security barriers

Run:  .venv/Scripts/python.exe -m unittest tests.test_api -v
  or: .venv/Scripts/python.exe tests/test_api.py
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from api.database import Base, SessionLocal, engine
from api.main import app
from api.models import Assignment, Report, Submission, User
from api.worker import process_submission_task

SAMPLE_ESSAY = (
    "Artificial intelligence is rapidly transforming modern higher education across multiple domains. "
    "Universities around the world are currently adopting automated grading systems, personalized virtual "
    "tutoring agents, and responsive adaptive learning software to enhance academic student outcomes. "
    "However, the widespread accessibility of generative large language models presents substantial challenges "
    "for scholastic integrity. Instructors must reconsider traditional assessment strategies to ensure that "
    "students genuinely develop critical thinking, synthesis, and quantitative reasoning capabilities. "
    "Furthermore, pedagogical frameworks must adapt to emphasize interactive oral examinations, supervised "
    "in-class drafting sessions, and iterative project portfolios rather than unmonitored take-home assignments. "
    "Ultimately, the goal of modern academic institutions should not be to ban artificial intelligence, but rather "
    "to foster transparent and ethical engagement while upholding rigorous standards of independent scholarship. "
    "By developing comprehensive institutional guidelines and educating students on proper attribution standards, "
    "faculties can cultivate an environment of academic integrity and innovative pedagogical excellence. "
    "This proactive approach ensures that graduates possess both technological proficiency and strong ethical grounding."
)


class TestFastAPIBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        # Register Teacher 1
        self.teacher1_email = "prof.smith@university.edu"
        self.password = "secure_teacher_pass_123"
        reg_resp = self.client.post(
            "/auth/register",
            json={
                "email": self.teacher1_email,
                "password": self.password,
                "full_name": "Professor Smith",
            },
        )
        if reg_resp.status_code == 201:
            self.token1 = reg_resp.json()["access_token"]
        else:
            # Login if already exists
            login_resp = self.client.post(
                "/auth/login",
                json={"email": self.teacher1_email, "password": self.password},
            )
            self.token1 = login_resp.json()["access_token"]

        self.headers1 = {"Authorization": f"Bearer {self.token1}"}

    def test_01_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

    def test_02_auth_me(self):
        resp = self.client.get("/auth/me", headers=self.headers1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["email"], self.teacher1_email)
        self.assertEqual(data["role"], "teacher")

    def test_03_create_and_list_assignments(self):
        # Create assignment
        create_resp = self.client.post(
            "/assignments",
            json={
                "title": "Ethics in Computing Midterm",
                "description": "Analyze societal implications of generative AI",
                "class_name": "CS 401",
            },
            headers=self.headers1,
        )
        self.assertEqual(create_resp.status_code, 201)
        assignment_id = create_resp.json()["id"]

        # List assignments
        list_resp = self.client.get("/assignments", headers=self.headers1)
        self.assertEqual(list_resp.status_code, 200)
        assignments = list_resp.json()
        self.assertGreater(len(assignments), 0)
        self.assertTrue(any(a["id"] == assignment_id for a in assignments))

    def test_04_async_submission_workflow(self):
        # 1. Create target assignment
        create_resp = self.client.post(
            "/assignments",
            json={"title": "Essay 1", "class_name": "ENG 101"},
            headers=self.headers1,
        )
        assignment_id = create_resp.json()["id"]

        # 2. Upload file (PDF / DOCX / TXT)
        file_bytes = SAMPLE_ESSAY.encode("utf-8")
        files = {"file": ("student_submission.txt", io.BytesIO(file_bytes), "text/plain")}

        upload_resp = self.client.post(
            f"/assignments/{assignment_id}/upload",
            files=files,
            headers=self.headers1,
        )
        self.assertEqual(upload_resp.status_code, 202)  # Accepted
        sub_data = upload_resp.json()
        submission_id = sub_data["id"]
        self.assertEqual(sub_data["status"], "queued")

        # 3. Process the queued task via worker
        process_submission_task(submission_id)

        # 4. Poll status: must have transitioned to 'done'
        status_resp = self.client.get(
            f"/submissions/{submission_id}/status",
            headers=self.headers1,
        )
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertEqual(status_data["status"], "done")
        self.assertIsNotNone(status_data["document_ai_pct"])
        self.assertIsNotNone(status_data["total_similarity_pct"])
        self.assertEqual(status_data["red_flags_count"], 0)

        # 5. Retrieve full Unified Report
        report_resp = self.client.get(
            f"/submissions/{submission_id}/report",
            headers=self.headers1,
        )
        self.assertEqual(report_resp.status_code, 200)
        report = report_resp.json()

        # Validate unified schema sections
        self.assertIn("report_id", report)
        self.assertIn("metadata", report)
        self.assertIn("integrity", report)
        self.assertIn("ai_detection", report)
        self.assertIn("similarity", report)
        self.assertIn("summary_card", report)

        self.assertEqual(report["metadata"]["filename"], "student_submission.txt")
        self.assertEqual(report["ai_detection"]["status"], "DONE")
        self.assertIn("Estimate only, not proof", report["summary_card"]["disclaimer"])

        # 6. Test PDF Report Export (Step 11)
        export_resp = self.client.get(
            f"/submissions/{submission_id}/export",
            headers=self.headers1,
        )
        self.assertEqual(export_resp.status_code, 200)
        self.assertEqual(export_resp.headers["content-type"], "application/pdf")
        self.assertTrue(export_resp.content.startswith(b"%PDF"))

        # 7. Test Student Data Deletion / Retention (Step 11)
        del_resp = self.client.delete(
            f"/submissions/{submission_id}",
            headers=self.headers1,
        )
        self.assertEqual(del_resp.status_code, 200)

        # Confirm submission is gone
        check_del = self.client.get(
            f"/submissions/{submission_id}/status",
            headers=self.headers1,
        )
        self.assertEqual(check_del.status_code, 404)

    def test_05_teacher_data_isolation(self):
        # Create second teacher
        teacher2_email = "prof.jones@university.edu"
        reg_resp2 = self.client.post(
            "/auth/register",
            json={
                "email": teacher2_email,
                "password": "password_jones_456",
                "full_name": "Professor Jones",
            },
        )
        token2 = reg_resp2.json()["access_token"] if reg_resp2.status_code == 201 else self.client.post(
            "/auth/login", json={"email": teacher2_email, "password": "password_jones_456"}
        ).json()["access_token"]

        headers2 = {"Authorization": f"Bearer {token2}"}

        # Teacher 1 creates assignment
        create_resp = self.client.post(
            "/assignments",
            json={"title": "Private Research", "class_name": "BIO 500"},
            headers=self.headers1,
        )
        assignment_id = create_resp.json()["id"]

        # Teacher 2 tries to access Teacher 1's assignment -> 404 (isolated)
        resp = self.client.get(f"/assignments/{assignment_id}", headers=headers2)
        self.assertEqual(resp.status_code, 404)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
