from pathlib import Path
import sqlite3


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT_DIR / "database" / "local_schema.sql"
RUNTIME_DIR = ROOT_DIR / "runtime"
DB_PATH = RUNTIME_DIR / "ai_secretary_local.db"


def initialize_database() -> None:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"SQL 스키마 파일이 없습니다: {SCHEMA_PATH}")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_sql)
        conn.commit()

        tables = [
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]

        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    print(f"SQLite initialized: {DB_PATH}")
    print(f"생성된 테이블 수: {len(tables)}")

    for table in tables:
        print(f"- {table}")

    print(f"Foreign Key: {'ON' if foreign_keys else 'OFF'}")


if __name__ == "__main__":
    initialize_database()
