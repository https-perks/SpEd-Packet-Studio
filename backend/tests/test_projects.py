import base64
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
    BulkProjectAction,
    DataSheetsDraft,
    DuplicateOptions,
    ExportSettingsSelection,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
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
                        "case_manager": "",
                        "case_manager_first_name": "Alex",
                        "case_manager_last_name": "Teacher",
                        "case_manager_phone": "555-0100",
                        "case_manager_email": "alex.teacher@example.edu",
                        "case_manager_notes": "Best reached before 8:00 AM.",
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
            self.assertEqual(detail.student.case_manager if detail.student else None, "Alex Teacher")
            self.assertEqual(detail.student.case_manager_email if detail.student else None, "alex.teacher@example.edu")
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
            observation_sheets = DataSheetsDraft.model_validate(
                {
                    "data_sheets": [
                        detail.data_sheets[0].model_dump(),
                        {
                            "title": "Classroom Observation",
                            "sheet_type": "notes",
                            "goal_ids": [],
                            "collection_schedule": "As needed",
                            "blank_instance_count": 1,
                            "columns": [
                                {
                                    "id": "date",
                                    "title": "Date",
                                    "column_type": "date",
                                    "position": 0,
                                },
                                {
                                    "id": "observation",
                                    "title": "Observation",
                                    "column_type": "notes",
                                    "position": 1,
                                },
                            ],
                            "notes": "General classroom observation form.",
                            "is_observation_form": True,
                            "position": 1,
                        },
                    ]
                }
            )
            detail = projects.save_data_sheets(session, created.id, observation_sheets)
            self.assertTrue(detail.data_sheets_validation.is_complete)
            self.assertEqual(
                len([sheet for sheet in detail.data_sheets if sheet.is_observation_form]),
                1,
            )
            detail = projects.save_observation_checklist(
                session,
                created.id,
                ObservationChecklistDraft(
                    items=["New concerns", "Major improvement"],
                ),
            )
            self.assertEqual(detail.observation_checklist, ["New concerns", "Major improvement"])
            detail = projects.save_project_theme(
                session,
                created.id,
                ThemeSelection.model_validate(
                    {
                        "theme_id": "teacher_friendly",
                        "packet_template_id": "mountain_illustrated",
                        "customization": {
                            "primary_color": "#24577a",
                            "secondary_color": "#35b7a9",
                            "accent_color": "#f08a24",
                            "background_color": "#f7fbff",
                            "card_color": "#ffffff",
                            "text_color": "#123247",
                            "service_area_colors": {"Reading": "#3182ce"},
                        },
                        "brand_kit": {
                            "name": "Gardiner Public Schools",
                            "district_name": "Gardiner Public Schools",
                            "school_name": "Central Middle",
                            "district_logo_label": "District logo",
                            "school_logo_label": "School logo",
                            "primary_color": "#24577a",
                            "secondary_color": "#35b7a9",
                            "accent_color": "#f08a24",
                            "preferred_cover_style": "mountain_illustrated",
                            "footer_text": "Confidential educational document",
                            "default_filename_template": "",
                        },
                    }
                ),
            )
            self.assertEqual(detail.theme_id, "teacher_friendly")
            self.assertEqual(detail.packet_template_id, "mountain_illustrated")
            self.assertEqual(detail.brand_kit.district_name, "Gardiner Public Schools")
            themes = projects.list_themes()
            self.assertEqual([theme.id for theme in themes], ["teacher_friendly", "minimal"])
            self.assertTrue(themes[0].default_customization)
            detail = projects.upload_brand_logo(
                session,
                created.id,
                projects.BrandLogoUpload(
                    filename="district.svg",
                    content_type="image/svg+xml",
                    data_base64=base64.b64encode(
                        b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><rect width="120" height="60" fill="#24577a"/></svg>'
                    ).decode("ascii"),
                ),
            )
            self.assertEqual(detail.brand_kit.logo_filename, "district.svg")
            self.assertTrue(detail.brand_kit.logo_relative_path.endswith(".svg"))
            detail = projects.save_export_settings(
                session,
                created.id,
                ExportSettingsSelection.model_validate(
                    {
                        "export_settings": {
                            "filename_template": "",
                            "last_export_location": "",
                            "export_mode": "zip_archive",
                        }
                    }
                ),
            )
            self.assertEqual(detail.export_settings.export_mode, "zip_archive")
            self.assertTrue(projects.list_packet_templates())
            self.assertTrue(projects.list_themes())
            custom_template = projects.create_template_library_item(
                projects.PacketTemplateLibraryDraft(
                    name="Ryan Template",
                    description="Dashboard managed template.",
                    category="Custom",
                    base_template_id="district_branding",
                    theme_id="minimal",
                    customization=projects.ThemeCustomization(
                        primary_color="#111827",
                        secondary_color="#4b5563",
                        accent_color="#111827",
                        background_color="#ffffff",
                        card_color="#ffffff",
                        text_color="#111827",
                    ),
                )
            )
            self.assertFalse(custom_template.is_builtin)
            self.assertIn(
                custom_template.id,
                [template.id for template in projects.list_packet_templates()],
            )
            duplicated_template = projects.duplicate_template_library_item(custom_template.id)
            self.assertTrue(duplicated_template.id.startswith("custom_"))
            self.assertTrue(
                any(template.is_default for template in projects.set_default_template(custom_template.id))
            )
            brand_kit = projects.create_brand_kit(
                projects.BrandKitLibraryDraft(
                    name="Gardiner Public Schools",
                    district_name="Gardiner Public Schools",
                    school_name="Central Middle",
                    watermark_enabled=True,
                    default_fonts="Open Sans",
                )
            )
            self.assertTrue(brand_kit.id.startswith("brand_"))
            brand_kit = projects.upload_brand_kit_logo(
                projects.BrandKitLogoUpload(
                    brand_kit_id=brand_kit.id,
                    filename="school.svg",
                    content_type="image/svg+xml",
                    data_base64=base64.b64encode(
                        b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><circle cx="30" cy="30" r="25" fill="#111827"/></svg>'
                    ).decode("ascii"),
                )
            )
            self.assertEqual(brand_kit.logo_filename, "school.svg")
            self.assertTrue(
                any(kit.is_default for kit in projects.set_default_brand_kit(brand_kit.id))
            )
            self.assertIn(
                created.id,
                [item.id for item in projects.list_projects(session, service_area="Reading")],
            )
            self.assertIn(
                created.id,
                [item.id for item in projects.list_projects(session, case_manager="Teacher")],
            )
            self.assertIn(
                created.id,
                [item.id for item in projects.list_projects(session, theme_id="teacher_friendly")],
            )
            detail = projects.save_packet_builder(
                session,
                created.id,
                PacketBuilderDraft(packet_versions=detail.packet_builder),
            )
            self.assertGreater(len(detail.packet_builder), 0)
            html = projects._build_packet_html(  # noqa: SLF001 - regression coverage for generated packet content
                detail,
                theme_id="teacher_friendly",
                packet_template_id=detail.packet_template_id,
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
            )
            self.assertIn("Classroom Observation", html)
            self.assertIn("brand-logo", html)
            self.assertIn("#24577a", html)
            self.assertIn("alex.teacher@example.edu", html)
            self.assertNotIn("Follow-up / Action", html)
            self.assertIn("New concerns", html)
            botanical_html = projects._build_packet_html(  # noqa: SLF001 - template rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="botanical_frame",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
            )
            chalkboard_html = projects._build_packet_html(  # noqa: SLF001 - template rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="chalkboard",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
            )
            self.assertIn('body class="template-botanical-frame"', botanical_html)
            self.assertIn('body class="template-chalkboard"', chalkboard_html)
            self.assertNotEqual(botanical_html, chalkboard_html)

            duplicate = projects.duplicate_project(session, created.id)
            self.assertEqual(len(duplicate.goals), 1)
            self.assertEqual(len(duplicate.data_sheets), 2)
            self.assertEqual(
                len([sheet for sheet in duplicate.data_sheets if sheet.is_observation_form]),
                1,
            )
            self.assertEqual(
                [sheet for sheet in duplicate.data_sheets if not sheet.is_observation_form][0].goal_ids,
                [duplicate.goals[0].id],
            )
            self.assertEqual(
                [sheet for sheet in duplicate.data_sheets if not sheet.is_observation_form][0].blank_instance_count,
                4,
            )
            selective = projects.duplicate_project(
                session,
                created.id,
                DuplicateOptions(
                    student_information=True,
                    service_areas=True,
                    goals=False,
                    at_a_glance=False,
                    observation_notes=False,
                    data_sheets=False,
                    theme=True,
                    template=True,
                    packet_layout=True,
                ),
            )
            self.assertEqual(len(selective.goals), 0)
            self.assertEqual(len(selective.data_sheets), 0)
            self.assertEqual(selective.theme_id, "teacher_friendly")
            bulk = projects.apply_bulk_project_action(
                session,
                BulkProjectAction(
                    project_ids=[selective.id],
                    action="assign_theme",
                    theme_id="minimal",
                ),
            )
            self.assertEqual(bulk.projects[0].theme_id, "minimal")
            bulk = projects.apply_bulk_project_action(
                session,
                BulkProjectAction(
                    project_ids=[selective.id],
                    action="update_template",
                    packet_template_id="district_branding",
                ),
            )
            self.assertEqual(len(bulk.projects), 1)
            refreshed_selective = projects.project_detail(session, selective.id)
            self.assertEqual(refreshed_selective.packet_template_id, "district_branding")
            bulk = projects.apply_bulk_project_action(
                session,
                BulkProjectAction(
                    project_ids=[selective.id],
                    action="update_school_year",
                    school_year="2027-2028",
                ),
            )
            self.assertEqual(bulk.projects[0].school_year, "2027-2028")
            bulk = projects.apply_bulk_project_action(
                session,
                BulkProjectAction(
                    project_ids=[selective.id],
                    action="assign_export_location",
                    export_location="District Folder",
                ),
            )
            refreshed_selective = projects.project_detail(session, selective.id)
            self.assertEqual(
                refreshed_selective.export_settings.last_export_location,
                "District Folder",
            )

            if renderer_available():
                export = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=None,
                )
                export_path = Path(export.absolute_path)
                self.assertTrue(export_path.exists())
                self.assertGreater(export.size_bytes, 1000)
                self.assertEqual(export_path.read_bytes()[:4], b"%PDF")
                self.assertIn("Jordan Rivera", export.filename)
                self.assertIn("Base Packet", export.filename)
                named_export = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="district_branding",
                        filename_template="Custom Packet Name",
                    ),
                )
                self.assertEqual(named_export.filename, "Custom Packet Name.pdf")
                botanical_pdf = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="botanical_frame",
                        filename_template="Botanical Packet.pdf",
                    ),
                )
                chalkboard_pdf = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="chalkboard",
                        filename_template="Chalkboard Packet.pdf",
                    ),
                )
                self.assertNotEqual(botanical_pdf.content_hash, chalkboard_pdf.content_hash)
                zip_export = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="district_branding",
                        filename_template="Sample-26.27",
                        export_mode="zip_archive",
                    ),
                )
                self.assertTrue(zip_export.filename.endswith(".zip"))
                self.assertEqual(Path(zip_export.absolute_path).read_bytes()[:2], b"PK")
                self.assertTrue(
                    export.download_url.endswith(f"/exports/{export.id}/download")
                )
                all_exports = projects.generate_all_pdf_exports(session, created.id)
                self.assertGreaterEqual(len(all_exports.exports), len(detail.packet_versions))
                bulk_exports = projects.apply_bulk_project_action(
                    session,
                    BulkProjectAction(
                        project_ids=[created.id],
                        action="export",
                    ),
                )
                self.assertGreaterEqual(
                    len(bulk_exports.exports),
                    len(detail.packet_versions),
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
            projects.set_archived(session, selective.id, True)
            deleted = projects.apply_bulk_project_action(
                session,
                BulkProjectAction(project_ids=[selective.id], action="delete"),
            )
            self.assertEqual(deleted.deleted_project_ids, [selective.id])
