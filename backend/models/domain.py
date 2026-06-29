from __future__ import annotations
from datetime import date, datetime
from typing import Any
from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.base import Base
from backend.models.mixins import IdentifierMixin, TimestampMixin

goal_data_sheet = Table(
    "goal_data_sheets", Base.metadata,
    Column("goal_id", ForeignKey("goals.id", ondelete="CASCADE"), primary_key=True),
    Column("data_sheet_id", ForeignKey("data_sheets.id", ondelete="CASCADE"), primary_key=True),
)

class Project(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    school_year: Mapped[str | None] = mapped_column(String(20), index=True)
    schema_version: Mapped[str] = mapped_column(String(32))
    app_version: Mapped[str] = mapped_column(String(32))
    default_export_filename: Mapped[str | None] = mapped_column(String(240))
    theme_id: Mapped[str | None] = mapped_column(ForeignKey("themes.id"))
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    student: Mapped[Student | None] = relationship(back_populates="project", cascade="all, delete-orphan", single_parent=True)
    service_areas: Mapped[list[ServiceArea]] = relationship(back_populates="project", cascade="all, delete-orphan")
    goals: Mapped[list[Goal]] = relationship(back_populates="project", cascade="all, delete-orphan")
    at_a_glance: Mapped[AtAGlance | None] = relationship(back_populates="project", cascade="all, delete-orphan", single_parent=True)
    data_sheets: Mapped[list[DataSheet]] = relationship(back_populates="project", cascade="all, delete-orphan")
    packet_versions: Mapped[list[PacketVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list[Asset]] = relationship(back_populates="project", cascade="all, delete-orphan")
    theme: Mapped[Theme | None] = relationship(back_populates="projects")

class Student(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "students"; __table_args__ = (UniqueConstraint("project_id"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), index=True)
    last_name: Mapped[str | None] = mapped_column(String(100), index=True)
    initials: Mapped[str | None] = mapped_column(String(12))
    grade: Mapped[str | None] = mapped_column(String(32)); school: Mapped[str | None] = mapped_column(String(200)); case_manager: Mapped[str | None] = mapped_column(String(200)); case_manager_first_name: Mapped[str | None] = mapped_column(String(100)); case_manager_last_name: Mapped[str | None] = mapped_column(String(100)); case_manager_phone: Mapped[str | None] = mapped_column(String(80)); case_manager_email: Mapped[str | None] = mapped_column(String(200)); case_manager_notes: Mapped[str | None] = mapped_column(Text)
    iep_start_date: Mapped[date | None] = mapped_column(Date); iep_end_date: Mapped[date | None] = mapped_column(Date)
    project: Mapped[Project] = relationship(back_populates="student")

class ServiceArea(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "service_areas"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True); minutes: Mapped[int | None] = mapped_column(Integer); setting: Mapped[str | None] = mapped_column(String(200)); delivery_model: Mapped[str | None] = mapped_column(String(32)); notes: Mapped[str | None] = mapped_column(Text); position: Mapped[int] = mapped_column(Integer, default=0)
    project: Mapped[Project] = relationship(back_populates="service_areas"); goals: Mapped[list[Goal]] = relationship(back_populates="service_area")

class Goal(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "goals"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    service_area_id: Mapped[str] = mapped_column(ForeignKey("service_areas.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(240), index=True); statement: Mapped[str] = mapped_column(Text); data_sheet_summary: Mapped[str | None] = mapped_column(Text); mastery_criteria: Mapped[str | None] = mapped_column(Text); progress_monitoring_method: Mapped[str | None] = mapped_column(Text); notes: Mapped[str | None] = mapped_column(Text); position: Mapped[int] = mapped_column(Integer, default=0)
    project: Mapped[Project] = relationship(back_populates="goals"); service_area: Mapped[ServiceArea] = relationship(back_populates="goals"); data_sheets: Mapped[list[DataSheet]] = relationship(secondary=goal_data_sheet, back_populates="goals")

class AtAGlance(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "at_a_glance"; __table_args__ = (UniqueConstraint("project_id"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); sections_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    project: Mapped[Project] = relationship(back_populates="at_a_glance")

class DataSheet(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "data_sheets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); title: Mapped[str] = mapped_column(String(240), index=True); sheet_type: Mapped[str] = mapped_column(String(80)); configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    project: Mapped[Project] = relationship(back_populates="data_sheets"); goals: Mapped[list[Goal]] = relationship(secondary=goal_data_sheet, back_populates="data_sheets")

class PacketVersion(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "packet_versions"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); name: Mapped[str] = mapped_column(String(200), index=True); audience: Mapped[str] = mapped_column(String(120)); settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    project: Mapped[Project] = relationship(back_populates="packet_versions"); pages: Mapped[list[Page]] = relationship(back_populates="packet_version", cascade="all, delete-orphan", order_by="Page.position"); exports: Mapped[list[Export]] = relationship(back_populates="packet_version", cascade="all, delete-orphan")

class Page(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "pages"
    packet_version_id: Mapped[str] = mapped_column(ForeignKey("packet_versions.id", ondelete="CASCADE"), index=True); page_type: Mapped[str] = mapped_column(String(120)); title: Mapped[str | None] = mapped_column(String(240)); position: Mapped[int] = mapped_column(Integer, default=0); layout_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    packet_version: Mapped[PacketVersion] = relationship(back_populates="pages"); components: Mapped[list[Component]] = relationship(back_populates="page", cascade="all, delete-orphan", order_by="Component.position")

class Component(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "components"
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True); component_type: Mapped[str] = mapped_column(String(120)); source_type: Mapped[str | None] = mapped_column(String(120)); source_id: Mapped[str | None] = mapped_column(String(36), index=True); position: Mapped[int] = mapped_column(Integer, default=0); presentation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    page: Mapped[Page] = relationship(back_populates="components")

class Asset(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); name: Mapped[str] = mapped_column(String(240)); media_type: Mapped[str] = mapped_column(String(160)); relative_path: Mapped[str] = mapped_column(String(1024)); size_bytes: Mapped[int] = mapped_column(Integer); checksum: Mapped[str] = mapped_column(String(128), index=True); metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    project: Mapped[Project] = relationship(back_populates="assets")

class Theme(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "themes"
    name: Mapped[str] = mapped_column(String(160), unique=True); is_builtin: Mapped[bool] = mapped_column(Boolean, default=False); tokens_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    projects: Mapped[list[Project]] = relationship(back_populates="theme")

class Export(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "exports"
    packet_version_id: Mapped[str] = mapped_column(ForeignKey("packet_versions.id", ondelete="CASCADE"), index=True); format: Mapped[str] = mapped_column(String(32), default="pdf"); relative_path: Mapped[str] = mapped_column(String(1024)); content_hash: Mapped[str] = mapped_column(String(128), index=True); generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)); metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    packet_version: Mapped[PacketVersion] = relationship(back_populates="exports")

class Setting(IdentifierMixin, Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True); value_json: Mapped[Any] = mapped_column(JSON); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
