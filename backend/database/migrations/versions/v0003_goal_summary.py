from sqlalchemy import Connection, text


def upgrade(connection: Connection) -> None:
    columns = {
        row[1] for row in connection.execute(text("PRAGMA table_info(goals)"))
    }
    if "data_sheet_summary" not in columns:
        connection.execute(
            text("ALTER TABLE goals ADD COLUMN data_sheet_summary TEXT")
        )
