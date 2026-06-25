from sqlalchemy import Connection, text


def _columns(connection: Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(text(f"PRAGMA table_info({table})"))
    }


def upgrade(connection: Connection) -> None:
    project_columns = _columns(connection, "projects")
    if "default_export_filename" not in project_columns:
        connection.execute(
            text("ALTER TABLE projects ADD COLUMN default_export_filename VARCHAR(240)")
        )

    student_columns = _columns(connection, "students")
    if "initials" not in student_columns:
        connection.execute(
            text("ALTER TABLE students ADD COLUMN initials VARCHAR(12)")
        )

    service_columns = _columns(connection, "service_areas")
    if "delivery_model" not in service_columns:
        connection.execute(
            text("ALTER TABLE service_areas ADD COLUMN delivery_model VARCHAR(32)")
        )
