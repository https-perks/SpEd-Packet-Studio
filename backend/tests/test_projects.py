import os
from pathlib import Path
import shutil
import tempfile
import unittest

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="packet-studio-sprint-one-"))
os.environ["PACKET_STUDIO_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["PACKET_STUDIO_ENV"] = "test"

from backend.database.migrations.runner import run_migrations
from backend.database.session import SessionLocal, engine
from backend.generators.pdf import renderer_available
from backend.schemas.projects import (
    AtAGlanceDraft,
    DataSheetsDraft,
    GoalsDraft,
    StudentSetupDraft,
    ThemeSelection,
)
from backend.services import projects


class ProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_migrations()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def test_sprint_one_project_workflow(self) -> None:
        with SessionLocal() as session:
            created = projects.create_project(session)
            setup = StudentSetupDraft.model_validate(
                {
                    "project_name": "",
                    "school_year": "",
                    "student": {
                        "name": "Jordan Rivera",
                        "initials": "",
                        "grade": "7",
                        "school": "Central Middle",
                        "case_manager": "A. Teacher",
                        "iep_end_date": "2027-05-20",
                    },
                    "service_areas": [
                        {
                            "name": "Reading",
                            "setting": "Resource room",
                            "minutes_per_week": 150,
                            "delivery_model": "pull_out",
                            "notes": "",
                            "position": 0,
                        }
                    ],
                    "audiences": ["case_manager", "general_education"],
                }
            )
            detail = projects.save_student_setup(session, created.id, setup)
            self.assertTrue(detail.student_setup_validation.is_complete)
            self.assertEqual(detail.student.initials if detail.student else None, "JR")
            self.assertEqual(detail.school_year, "2026-2027")
            self.assertEqual(len(detail.audiences), 2)

            goals = GoalsDraft.model_validate(
                {
                    "goals": [
                        {
                            "title": "Reading Fluency",
                            "statement": "Jordan will read grade-level text.",
                            "data_sheet_summary": (
                                "3 consecutive passages at 80 WPM with 90% accuracy."
                            ),
                            "service_area_id": detail.service_areas[0].id,
                            "mastery_criteria": "90% accuracy",
                            "progress_monitoring_method": (
                                "Weekly curriculum-based measure"
                            ),
                            "instructional_notes": "Provide preview time.",
                            "position": 0,
                        }
                    ]
                }
            )
            detail = projects.save_goals(session, created.id, goals)
            self.assertTrue(detail.goals_validation.is_complete)
            self.assertEqual(
                detail.goals[0].data_sheet_summary,
                "3 consecutive passages at 80 WPM with 90% accuracy.",
            )

            glance = AtAGlanceDraft.model_validate(
                {
                    "sections": [
                        {
                            "id": "strengths",
                            "title": "Student Strengths",
                            "content": "Persistent and collaborative.",
                            "enabled": True,
                            "position": 0,
                        }
                    ]
                }
            )
            detail = projects.save_at_a_glance(session, created.id, glance)
            self.assertTrue(detail.at_a_glance_validation.is_complete)
            self.assertFalse(detail.data_sheets_validation.is_complete)

            data_sheets = DataSheetsDraft.model_validate(
                {
                    "data_sheets": [
                        {
                            "title": "Reading Fluency Weekly Probe",
                            "sheet_type": "trial_count",
                            "goal_ids": [detail.goals[0].id],
                            "collection_schedule": "Weekly, 3 passages",
                            "blank_instance_count": 4,
                            "columns": [
                                {
                                    "id": "date",
                                    "title": "Date",
                                    "column_type": "date",
                                    "position": 0,
                                },
                                {
                                    "id": "wpm",
                                    "title": "WPM",
                                    "column_type": "number",
                                    "position": 1,
                                },
                                {
                                    "id": "accuracy",
                                    "title": "Accuracy",
                                    "column_type": "number",
                                    "position": 2,
                                },
                            ],
                            "notes": "Use the goal summary as the target.",
                            "position": 0,
                        }
                    ]
                }
            )
            detail = projects.save_data_sheets(session, created.id, data_sheets)
            self.assertTrue(detail.data_sheets_validation.is_complete)
            self.assertEqual(detail.data_sheets[0].goal_ids, [detail.goals[0].id])
            self.assertEqual(detail.data_sheets[0].blank_instance_count, 4)
            self.assertEqual(len(detail.packet_versions), 2)
            self.assertEqual(
                [column.title for column in detail.data_sheets[0].columns],
                ["Date", "WPM", "Accuracy"],
            )
            detail = projects.save_project_theme(
                session,
                created.id,
                ThemeSelection(theme_id="teacher_friendly"),
            )
            self.assertEqual(detail.theme_id, "teacher_friendly")

            duplicate = projects.duplicate_project(session, created.id)
            self.assertEqual(len(duplicate.goals), 1)
            self.assertEqual(len(duplicate.data_sheets), 1)
            self.assertEqual(
                duplicate.data_sheets[0].goal_ids,
                [duplicate.goals[0].id],
            )
            self.assertEqual(duplicate.data_sheets[0].blank_instance_count, 4)

            if renderer_available():
                export = projects.generate_pdf_export(session, created.id)
                export_path = TEST_DATA_DIR / export.relative_path
                self.assertTrue(export_path.exists())
                self.assertGreater(export.size_bytes, 1000)
                self.assertEqual(export_path.read_bytes()[:4], b"%PDF")
                self.assertTrue(
                    export.download_url.endswith(f"/exports/{export.id}/download")
                )
            else:
                self.skipTest("WeasyPrint native rendering libraries are not installed.")

            backup = projects.create_project_backup(session, created.id)
            backup_path = TEST_DATA_DIR / backup.relative_path
            self.assertTrue(backup_path.exists())
            self.assertGreater(backup.size_bytes, 1000)

            archived = projects.set_archived(session, created.id, True)
            self.assertTrue(archived.archived)
            self.assertNotIn(
                created.id, [item.id for item in projects.list_projects(session)]
            )
            self.assertIn(
                created.id,
                [
                    item.id
                    for item in projects.list_projects(session, archived=True)
                ],
            )
