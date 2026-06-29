from sqlalchemy import Connection, text


def upgrade(connection: Connection) -> None:
    columns = {
        row[1] for row in connection.execute(text("PRAGMA table_info(students)"))
    }
    additions = {
        "case_manager_first_name": "VARCHAR(100)",
        "case_manager_last_name": "VARCHAR(100)",
        "case_manager_phone": "VARCHAR(80)",
        "case_manager_email": "VARCHAR(200)",
        "case_manager_notes": "TEXT",
    }
    for name, column_type in additions.items():
        if name not in columns:
            connection.execute(
                text(f"ALTER TABLE students ADD COLUMN {name} {column_type}")
            )
