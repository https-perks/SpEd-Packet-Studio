import base64
import os
from pathlib import Path
import shutil
import tempfile
import unittest

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="packet-studio-sprint-one-"))
os.environ["SPED_PACKET_APP_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["PACKET_STUDIO_DATA_DIR"] = str(TEST_DATA_DIR / "data")
os.environ["PACKET_STUDIO_ENV"] = "test"

# Test discovery imports test_paths first; refresh the process-wide path object
# after this module installs its isolated database override.
import backend.paths as path_module
path_module.paths = path_module.AppPaths.resolve()

from backend.database.migrations.runner import run_migrations
from backend.config import settings
from backend.database.session import SessionLocal, engine
from backend.generators.pdf import renderer_available
from backend.schemas.projects import (
    AppSettings,
    AtAGlanceDraft,
    BulkProjectAction,
    CaseManagerProfile,
    DataSheetsDraft,
    DataSheetColumnDraft,
    DuplicateOptions,
    ExportSettingsSelection,
    ExportSettings,
    GoalsDraft,
    ObservationChecklistDraft,
    PacketBuilderDraft,
    PacketPageDraft,
    PacketVersionDraft,
    ServiceAreaDraft,
    StudentSetupDraft,
    ThemeSelection,
)
from backend.services import projects


class ProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings.settings_dir.mkdir(parents=True, exist_ok=True)
        (settings.settings_dir / ".legacy-data-migration-v1.json").write_text("{}", encoding="utf-8")
        settings.paths.initialize()
        run_migrations()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def test_sprint_one_project_workflow(self) -> None:
        with SessionLocal() as session:
            projects.save_app_settings(
                AppSettings(
                    terminology_preference="ese",
                    default_school_year="2027-2028",
                    default_theme_id="minimal",
                    default_packet_template_id="modern_professional",
                    default_export_settings=ExportSettings(
                        filename_template="<Student Name> - <Packet Type> - <School Year>",
                        last_export_location="",
                        export_mode="single_pdf",
                    ),
                    default_observation_checklist=["Call family", "Tell case manager"],
                    packet_versions=[
                        PacketVersionDraft(name="Case Manager", audience="case_manager"),
                        PacketVersionDraft(name="General Education", audience="general_education"),
                        PacketVersionDraft(name="Coach Packet", audience="coach_packet"),
                    ],
                    accommodations_signature_page_enabled=True,
                    accommodations_signature_page_title="Accommodation Receipt Signatures",
                    accommodations_signature_page_note=(
                        "Staff signing below have reviewed this student's accommodations."
                    ),
                    accommodations_signature_line_layout="teacher_coach_date",
                    default_data_sheet_columns=[
                        DataSheetColumnDraft(
                            id="date",
                            title="Date",
                            column_type="date",
                            position=0,
                        ),
                        DataSheetColumnDraft(
                            id="score",
                            title="Score",
                            column_type="number",
                            position=1,
                        ),
                    ],
                    service_area_presets=[
                        ServiceAreaDraft(
                            name="Math",
                            setting="Special Education",
                            minutes_per_week=90,
                            notes="",
                            position=0,
                        )
                    ],
                    case_manager_profile=CaseManagerProfile(
                        first_name="Default",
                        last_name="Manager",
                        phone="555-2222",
                        email="default.manager@example.edu",
                        school="Default School",
                        notes="Global profile note.",
                    ),
                )
            )
            created = projects.create_project(session)
            self.assertEqual(created.school_year, "2027-2028")
            self.assertEqual(created.theme_id, "minimal")
            self.assertEqual(created.export_settings.filename_template, "<Student Name> - <Packet Type> - <School Year>")
            self.assertEqual(created.observation_checklist, ["Call family", "Tell case manager"])
            self.assertEqual(created.student.case_manager if created.student else None, "Default Manager")
            self.assertEqual(projects.get_app_settings().service_area_presets[0].name, "Math")
            self.assertEqual(projects.get_app_settings().terminology_preference, "ese")
            setup = StudentSetupDraft.model_validate(
                {
                    "project_name": "",
                    "school_year": "",
                    "student": {
                        "name": "Cecilia Halpert",
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
                            "notes": "",
                            "position": 0,
                        }
                    ],
                    "audiences": ["case_manager", "general_education", "coach_packet"],
                    "accommodations": [
                        {
                            "content_area": "Instructional",
                            "custom_content_area": "",
                            "text": "Preferential seating near instruction.\nChunk multi-step assignments.",
                            "position": 0,
                        },
                        {
                            "content_area": "Other",
                            "custom_content_area": "Transportation",
                            "text": "Use a visual cue before bus dismissal.",
                            "position": 1,
                        },
                    ],
                    "accommodations_parent_strengths_enabled": True,
                    "accommodations_parent_strengths": (
                        "Parent reports Jordan is kind, curious, and persistent."
                    ),
                    "behavior_plan_sections": [
                        {
                            "title": "Defined Problem Behavior",
                            "text": "Task refusal during multi-step independent work.",
                            "position": 0,
                        },
                        {
                            "title": "Prevention Strategies",
                            "text": "Use pre-correction before transitions.\nOffer a brief reset break when needed.",
                            "position": 1,
                        },
                    ],
                    "related_service_providers": [
                        {
                            "name": "Sam SLP",
                            "email": "sam.slp@example.edu",
                            "phone": "555-0199",
                            "service_area": "Speech/Language Pathologist",
                            "position": 0,
                        }
                    ],
                }
            )
            detail = projects.save_student_setup(session, created.id, setup)
            self.assertTrue(detail.student_setup_validation.is_complete)
            self.assertEqual(detail.student.initials if detail.student else None, "CH")
            self.assertEqual(detail.student.case_manager if detail.student else None, "Alex Teacher")
            self.assertEqual(detail.student.case_manager_email if detail.student else None, "alex.teacher@example.edu")
            self.assertEqual(len(detail.accommodations), 2)
            self.assertIn("Preferential seating", detail.accommodations[0].text)
            self.assertEqual(len(detail.behavior_plan_sections), 2)
            self.assertEqual(len(detail.related_service_providers), 1)
            self.assertIn("pre-correction", detail.behavior_plan)
            self.assertEqual(detail.school_year, "2026-2027")
            self.assertEqual(len(detail.audiences), 3)
            self.assertIn("coach_packet", detail.audiences)

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
            self.assertEqual(len(detail.packet_versions), 3)
            self.assertIn("Coach Packet", [version.name for version in detail.packet_versions])
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
                        "packet_template_id": "district_branding",
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
                            "preferred_cover_style": "district_branding",
                            "footer_text": "Confidential educational document",
                            "default_filename_template": "",
                        },
                    }
                ),
            )
            self.assertEqual(detail.theme_id, "teacher_friendly")
            self.assertEqual(detail.packet_template_id, "district_branding")
            self.assertEqual(detail.brand_kit.district_name, "Gardiner Public Schools")
            themes = projects.list_themes()
            self.assertEqual(
                [theme.id for theme in themes],
                [
                    "teacher_friendly",
                    "minimal",
                    "district_colors",
                    "field_notes",
                    "editorial_ledger",
                    "modular_blocks",
                    "alpine_photo",
                    "mid_century_classroom",
                    "typographic_poster",
                    "signal_atlas",
                ],
            )
            self.assertTrue(themes[0].default_customization)
            self.assertEqual(
                next(theme for theme in themes if theme.id == "field_notes").default_customization["primary_color"],
                "#274c3b",
            )
            self.assertEqual(
                next(theme for theme in themes if theme.id == "editorial_ledger").default_customization["primary_color"],
                "#26364a",
            )
            self.assertEqual(
                next(theme for theme in themes if theme.id == "modular_blocks").default_customization["secondary_color"],
                "#00a6a6",
            )
            self.assertEqual(
                next(theme for theme in themes if theme.id == "alpine_photo").default_customization["background_color"],
                "#eaf1f6",
            )
            updated_builtin_palette = projects.update_theme_palette(
                "district_colors",
                projects.ThemePaletteDraft(
                    name="District Brand Colors",
                    description="Editable built-in district palette.",
                    category="District",
                    customization=projects.ThemeCustomization(
                        primary_color="#3b1f63",
                        secondary_color="#8756c8",
                        accent_color="#f0b429",
                        background_color="#ffffff",
                        card_color="#ffffff",
                        text_color="#1f1830",
                    ),
                ),
            )
            self.assertTrue(updated_builtin_palette.is_builtin)
            self.assertEqual(updated_builtin_palette.name, "District Brand Colors")
            self.assertEqual(
                projects._customization_from_tokens("district_colors").primary_color,  # noqa: SLF001 - palette override regression
                "#3b1f63",
            )
            projects.delete_theme_palette("district_colors")
            self.assertNotIn("district_colors", [theme.id for theme in projects.list_themes()])
            detail = projects.save_project_theme(
                session,
                created.id,
                ThemeSelection.model_validate(
                    {
                        "theme_id": "district_colors",
                        "packet_template_id": "district_branding",
                        "customization": detail.theme_customization.model_dump(),
                        "brand_kit": detail.brand_kit.model_dump(),
                    }
                ),
            )
            self.assertNotEqual(detail.theme_id, "district_colors")
            with self.assertRaises(Exception):
                projects.delete_theme_palette("minimal")
            custom_palette = projects.create_theme_palette(
                projects.ThemePaletteDraft(
                    name="Gardiner Colors",
                    description="Reusable district colors.",
                    category="District",
                    customization=projects.ThemeCustomization(
                        primary_color="#3b1f63",
                        secondary_color="#8756c8",
                        accent_color="#f0b429",
                        background_color="#ffffff",
                        card_color="#ffffff",
                        text_color="#1f1830",
                    ),
                )
            )
            self.assertFalse(custom_palette.is_builtin)
            self.assertIn(custom_palette.id, [theme.id for theme in projects.list_themes()])
            updated_palette = projects.update_theme_palette(
                custom_palette.id,
                projects.ThemePaletteDraft(
                    name="Gardiner Gold",
                    description="Updated reusable district colors.",
                    category="District",
                    customization=projects.ThemeCustomization(
                        primary_color="#123456",
                        secondary_color="#345678",
                        accent_color="#abcdef",
                        background_color="#ffffff",
                        card_color="#ffffff",
                        text_color="#111111",
                        service_area_colors={
                            "Reading": "#010203",
                            "Math": "#22C55E",
                            "Written Expression": "#8B5CF6",
                            "S/E/B": "#F59E0B",
                            "SH/I": "#E11D48",
                            "Communication": "#06B6D4",
                            "Speech/Language": "#6366F1",
                        },
                    ),
                ),
            )
            self.assertEqual(updated_palette.name, "Gardiner Gold")
            self.assertEqual(updated_palette.default_customization["primary_color"], "#123456")
            self.assertEqual(
                updated_palette.default_customization["service_area_colors"]["Reading"],
                "#010203",
            )
            reloaded_palette = next(
                theme
                for theme in projects.list_themes()
                if theme.id == custom_palette.id
            )
            self.assertEqual(
                reloaded_palette.default_customization["service_area_colors"]["Reading"],
                "#010203",
            )
            self.assertEqual(
                projects._customization_from_tokens(custom_palette.id).service_area_colors["Reading"],  # noqa: SLF001 - palette service color persistence regression
                "#010203",
            )
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
            packet_templates = projects.list_packet_templates()
            self.assertTrue(packet_templates)
            self.assertIn("field_notes", [template.id for template in packet_templates])
            self.assertIn("editorial_ledger", [template.id for template in packet_templates])
            self.assertIn("mid_century_classroom", [template.id for template in packet_templates])
            self.assertIn("typographic_poster", [template.id for template in packet_templates])
            self.assertIn("signal_atlas", [template.id for template in packet_templates])
            self.assertTrue(
                all(
                    {"category", "cover_style", "best_for"}.isdisjoint(
                        template.model_dump()
                    )
                    for template in packet_templates
                )
            )
            field_notes_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "field_notes"
            )
            self.assertEqual(
                field_notes_template.customization.primary_color,
                "#274c3b",
            )
            self.assertEqual(field_notes_template.theme_id, "field_notes")
            district_branding_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "district_branding"
            )
            self.assertEqual(district_branding_template.theme_id, "district_colors")
            self.assertEqual(
                district_branding_template.customization.primary_color,
                projects._customization_from_tokens("district_colors").primary_color,  # noqa: SLF001 - district branding palette default regression
            )
            editorial_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "editorial_ledger"
            )
            self.assertEqual(
                editorial_template.customization.primary_color,
                "#26364a",
            )
            self.assertEqual(editorial_template.theme_id, "editorial_ledger")
            modular_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "modular_blocks"
            )
            self.assertEqual(modular_template.theme_id, "modular_blocks")
            alpine_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "alpine_photo"
            )
            self.assertEqual(alpine_template.theme_id, "alpine_photo")
            mid_century_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "mid_century_classroom"
            )
            self.assertEqual(mid_century_template.theme_id, "mid_century_classroom")
            self.assertEqual(
                mid_century_template.customization.primary_color,
                "#235c64",
            )
            typographic_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "typographic_poster"
            )
            self.assertEqual(typographic_template.theme_id, "typographic_poster")
            self.assertEqual(
                typographic_template.customization.primary_color,
                "#14233c",
            )
            signal_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "signal_atlas"
            )
            self.assertEqual(signal_template.theme_id, "signal_atlas")
            self.assertEqual(
                signal_template.customization.primary_color,
                "#102a43",
            )
            self.assertTrue(projects.list_themes())
            custom_template = projects.create_template_library_item(
                projects.PacketTemplateLibraryDraft(
                    name="Ryan Template",
                    description="Dashboard managed template.",
                    base_template_id="district_branding",
                    theme_id=custom_palette.id,
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
            self.assertEqual(custom_template.theme_id, custom_palette.id)
            updated_builtin_template = projects.update_template_library_item(
                "district_branding",
                projects.PacketTemplateLibraryDraft(
                    name="District Branding",
                    description="District template with saved palette.",
                    base_template_id="district_branding",
                    theme_id=custom_palette.id,
                    customization=projects.ThemeCustomization(
                        primary_color="#123456",
                        secondary_color="#345678",
                        accent_color="#abcdef",
                        background_color="#ffffff",
                        card_color="#ffffff",
                        text_color="#111111",
                        service_area_colors={
                            "Reading": "#010203",
                            "Math": "#22C55E",
                            "Written Expression": "#8B5CF6",
                            "S/E/B": "#F59E0B",
                            "SH/I": "#E11D48",
                            "Communication": "#06B6D4",
                            "Speech/Language": "#6366F1",
                        },
                    ),
                ),
            )
            self.assertTrue(updated_builtin_template.is_builtin)
            reopened_builtin_template = next(
                template
                for template in projects.list_template_library()
                if template.id == "district_branding"
            )
            self.assertEqual(reopened_builtin_template.theme_id, custom_palette.id)
            self.assertEqual(
                projects._customization_for_template("district_branding").primary_color,  # noqa: SLF001 - template export color regression
                "#123456",
            )
            builtin_template_html = projects._build_packet_html(  # noqa: SLF001 - template export color regression
                detail,
                theme_id=reopened_builtin_template.theme_id,
                packet_template_id=reopened_builtin_template.base_template_id,
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("district_branding"),  # noqa: SLF001
            )
            self.assertIn("#123456", builtin_template_html)
            self.assertIn("background-color: #010203;", builtin_template_html)
            self.assertEqual(
                projects._service_area_icon_color(  # noqa: SLF001 - custom service area color regression
                    "Transition",
                    projects.ThemeCustomization(service_area_colors={"Transition": "#112233"}),
                ),
                "#112233",
            )
            self.assertEqual(
                projects._service_area_icon_color(  # noqa: SLF001 - service area alias color regression
                    "Social/Emotional/Behavioral",
                    projects.ThemeCustomization(service_area_colors={"S/E/B": "#445566"}),
                ),
                "#445566",
            )
            self.assertEqual(
                projects._service_area_icon_color(  # noqa: SLF001 - service area alias color regression
                    "Speech/Language",
                    projects.ThemeCustomization(service_area_colors={"Speech-Language": "#778899"}),
                ),
                "#778899",
            )
            minimal_customization = projects._customization_from_tokens("minimal")  # noqa: SLF001 - minimal palette service color regression
            self.assertTrue(
                all(color == "#4B5563" for color in minimal_customization.service_area_colors.values())
            )
            self.assertEqual(
                projects._service_area_icon_color(  # noqa: SLF001 - minimal palette custom service color regression
                    "Transition",
                    projects.ThemeCustomization(service_area_colors={"Transition": "#112233"}),
                    theme_id="minimal",
                ),
                "#4B5563",
            )
            sample_detail = projects._sample_template_project_detail(  # noqa: SLF001 - template preview sample data regression
                projects.TemplatePreviewRequest(
                    name="Sample Preview",
                    description="Sample preview data.",
                    base_template_id="district_branding",
                    theme_id=custom_palette.id,
                    customization=projects.ThemeCustomization(),
                )
            )
            self.assertEqual(sample_detail.student.school if sample_detail.student else None, "Scranton Elementary")
            self.assertEqual(sample_detail.brand_kit.school_name, "Scranton Elementary")
            self.assertNotIn("Gardiner", sample_detail.model_dump_json())
            if renderer_available():
                preview_pdf = projects.preview_template_library_item(
                    projects.TemplatePreviewRequest(
                        name="Unsaved Preview Template",
                        description="Draft template preview.",
                        base_template_id="district_branding",
                        theme_id=custom_palette.id,
                        customization=projects.ThemeCustomization(
                            primary_color="#123456",
                            secondary_color="#345678",
                            accent_color="#abcdef",
                            background_color="#ffffff",
                            card_color="#ffffff",
                            text_color="#111111",
                        ),
                    )
                )
                self.assertGreater(len(preview_pdf), 1000)
                self.assertEqual(preview_pdf[:4], b"%PDF")
            projects.delete_template_library_item("district_branding")
            self.assertNotIn(
                "district_branding",
                [template.id for template in projects.list_template_library()],
            )
            self.assertIn(
                "district_branding",
                [template.id for template in projects.list_hidden_template_library()],
            )
            self.assertEqual(
                projects._template_library_item("district_branding").id,  # noqa: SLF001 - hidden template export regression
                "district_branding",
            )
            projects.restore_template_library_item("district_branding")
            self.assertIn(
                "district_branding",
                [template.id for template in projects.list_template_library()],
            )
            self.assertFalse(projects.list_hidden_template_library())
            projects.delete_theme_palette(custom_palette.id)
            self.assertNotIn(custom_palette.id, [theme.id for theme in projects.list_themes()])
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
                    heading_font="Poppins",
                    body_font="Open Sans",
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
            detail = projects.save_project_theme(
                session,
                created.id,
                ThemeSelection.model_validate(
                    {
                        "theme_id": detail.theme_id,
                        "packet_template_id": "modern_professional",
                        "customization": detail.theme_customization.model_dump(),
                        "brand_kit": brand_kit.model_dump(exclude={"is_default"}),
                    }
                ),
            )
            self.assertEqual(detail.brand_kit.heading_font, "Poppins")
            self.assertEqual(detail.brand_kit.body_font, "Open Sans")
            brand_kit = projects.update_brand_kit(
                brand_kit.id,
                projects.BrandKitLibraryDraft(
                    name=brand_kit.name,
                    district_name=brand_kit.district_name,
                    school_name=brand_kit.school_name,
                    logo_relative_path=brand_kit.logo_relative_path,
                    logo_filename=brand_kit.logo_filename,
                    watermark_logo_relative_path=brand_kit.watermark_logo_relative_path,
                    watermark_logo_filename=brand_kit.watermark_logo_filename,
                    watermark_enabled=brand_kit.watermark_enabled,
                    default_fonts="Arial",
                    heading_font="Georgia",
                    body_font="Arial",
                    preferred_cover_style=brand_kit.preferred_cover_style,
                    footer_text=brand_kit.footer_text,
                    default_filename_template=brand_kit.default_filename_template,
                ),
            )
            detail = projects._detail(projects.get_project(session, created.id))  # noqa: SLF001 - brand kit library refresh regression
            self.assertEqual(detail.brand_kit.heading_font, "Georgia")
            self.assertEqual(detail.brand_kit.body_font, "Arial")
            font_html = projects._build_packet_html(  # noqa: SLF001 - brand kit font regression
                detail,
                theme_id=detail.theme_id,
                packet_template_id=detail.packet_template_id,
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template(detail.packet_template_id),  # noqa: SLF001
            )
            self.assertIn('font-family: Georgia, "Times New Roman", serif;', font_html)
            self.assertIn("font-family: Arial, sans-serif;", font_html)
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
            custom_packet_config = detail.packet_builder[0].model_copy(deep=True)
            custom_packet_config.pages.append(
                PacketPageDraft(
                    id="custom_para_notes",
                    title="Para Notes",
                    page_type="custom_text",
                    enabled=True,
                    position=len(custom_packet_config.pages),
                    body_text="Use this page for paraeducator notes.",
                )
            )
            detail = projects.save_packet_builder(
                session,
                created.id,
                PacketBuilderDraft(
                    packet_versions=[
                        custom_packet_config,
                        *detail.packet_builder[1:],
                    ],
                ),
            )
            self.assertGreater(len(detail.packet_builder), 0)
            self.assertTrue(
                all(
                    any(page.id == "custom_para_notes" for page in config.pages)
                    for config in detail.packet_builder
                )
            )
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
            self.assertIn("Preferential seating", html)
            self.assertIn("Transportation", html)
            self.assertIn("Use pre-correction", html)
            self.assertIn("Para Notes", html)
            self.assertIn("Use this page for paraeducator notes.", html)
            self.assertIn("sam.slp@example.edu", html)
            self.assertNotIn("Follow-up / Action", html)
            self.assertIn("New concerns", html)
            self.assertIn("Exceptional Student Education", html)
            self.assertNotIn("Special Education", html)
            modern_html = projects._build_packet_html(  # noqa: SLF001 - template rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="modern_professional",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
            )
            alpine_html = projects._build_packet_html(  # noqa: SLF001 - template rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="alpine_photo",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
            )
            self.assertIn('body class="template-modern-professional"', modern_html)
            self.assertIn("Teacher Responsibilities", modern_html)
            self.assertIn("<strong>Student:</strong> Cecilia Halpert", modern_html)
            self.assertIn("<strong>IEP End:</strong> 2027-05-20", modern_html)
            self.assertIn("specific responsibilities related to this student", modern_html)
            self.assertIn("Accommodation Receipt Signatures", modern_html)
            self.assertIn("Staff signing below have reviewed this student", modern_html)
            self.assertIn("Staff Member:", modern_html)
            self.assertIn("Date:", modern_html)
            self.assertIn("Parent Perception of Student Strengths", modern_html)
            self.assertIn("Parent reports Jordan is kind, curious, and persistent.", modern_html)
            self.assertIn('body class="template-alpine-photo"', alpine_html)
            self.assertIn("5.15in solid", alpine_html)
            self.assertIn("cover-district-mark:after", alpine_html)
            self.assertNotEqual(modern_html, alpine_html)
            field_notes_html = projects._build_packet_html(  # noqa: SLF001 - Field Notes rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="field_notes",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("field_notes"),  # noqa: SLF001
            )
            self.assertIn('body class="template-field-notes"', field_notes_html)
            self.assertIn("repeating-radial-gradient", field_notes_html)
            self.assertIn("#274c3b", field_notes_html)
            editorial_html = projects._build_packet_html(  # noqa: SLF001 - Editorial Ledger rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="editorial_ledger",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("editorial_ledger"),  # noqa: SLF001
            )
            self.assertIn('body class="template-editorial-ledger"', editorial_html)
            self.assertIn('data-year-mark="27"', editorial_html)
            self.assertIn("editorial-meta-grid", editorial_html)
            self.assertIn("cover-version-footer", editorial_html)
            self.assertIn("Packet version:", editorial_html)
            self.assertIn("#26364a", editorial_html)
            modular_html = projects._build_packet_html(  # noqa: SLF001 - Modular Blocks rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="modular_blocks",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("modular_blocks"),  # noqa: SLF001
            )
            self.assertIn('body class="template-modular-blocks"', modular_html)
            self.assertIn("SERVICE AREAS", modular_html)
            self.assertIn("#17345f", modular_html)
            self.assertNotEqual(editorial_html, modular_html)
            mid_century_html = projects._build_packet_html(  # noqa: SLF001 - Mid-Century Classroom rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="mid_century_classroom",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("mid_century_classroom"),  # noqa: SLF001
            )
            self.assertIn('body class="template-mid-century-classroom"', mid_century_html)
            self.assertIn("cover-version-footer", mid_century_html)
            self.assertIn("Packet version:", mid_century_html)
            typographic_html = projects._build_packet_html(  # noqa: SLF001 - Typographic rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="typographic_poster",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("typographic_poster"),  # noqa: SLF001
            )
            self.assertIn('body class="template-typographic-poster"', typographic_html)
            self.assertIn("typographic-watermark", typographic_html)
            self.assertIn("Packet version:", typographic_html)
            signal_html = projects._build_packet_html(  # noqa: SLF001 - Signal rendering regression coverage
                detail,
                theme_id="teacher_friendly",
                packet_template_id="signal_atlas",
                packet_version_name=detail.packet_versions[0].name,
                packet_config=detail.packet_builder[0],
                customization=projects._customization_for_template("signal_atlas"),  # noqa: SLF001
            )
            self.assertIn('body class="template-signal-atlas"', signal_html)
            self.assertIn("SERVICE AREAS", signal_html)
            self.assertIn("signal-page-mark", signal_html)
            self.assertIn("cover-version-footer", signal_html)
            self.assertIn("#102a43", signal_html)

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
                self.assertIn("Cecilia Halpert", export.filename)
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
                modern_pdf = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="modern_professional",
                        filename_template="Modern Packet.pdf",
                    ),
                )
                alpine_pdf = projects.generate_pdf_export(
                    session,
                    created.id,
                    request=projects.ExportRequest(
                        theme_id="teacher_friendly",
                        packet_template_id="alpine_photo",
                        filename_template="Alpine Packet.pdf",
                    ),
                )
                self.assertNotEqual(modern_pdf.content_hash, alpine_pdf.content_hash)
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
            backup_path = path_module.paths.root / backup.relative_path
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
