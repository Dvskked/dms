"""Exporta el esquema completo de la aplicacion a un fichero .sql de MySQL.

    python export_sql.py                 -> escribe database.sql
    python export_sql.py --salida x.sql  -> another file
    python export_sql.py --drops         -> anade DROP TABLE antes de cada CREATE

El DDL se genera desde los modelos con el dialecto de MySQL, asi que el
fichero siempre coincide con lo que la aplicacion espera.
Tambien escribe la version de Alembic para que `flask db` no intente volver
a crear lo que ya existe.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from models import db as _db  # noqa: E402,F401  (asegura que los modelos esten cargados)

DIALECT = mysql.dialect()
TABLE_OPTIONS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"


def _clean(stmt: str) -> str:
    """Quita los espacios sobrantes que deja SQLAlchemy en el DDL."""
    lines = [line.rstrip() for line in stmt.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def _ddl_for(table, if_not_exists: bool = False) -> list[str]:
    """CREATE TABLE + CREATE INDEX de una tabla, ya formateado para MySQL."""
    chunks: list[str] = []

    create = _clean(str(CreateTable(table).compile(dialect=DIALECT)))
    # El motor y el charset se anaden a mano: los modelos no los declaran.
    assert create.endswith(")"), create[-40:]
    create = f"{create[:-1].rstrip()}\n) {TABLE_OPTIONS};"
    if if_not_exists:
        create = create.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
    chunks.append(create)

    for index in sorted(table.indexes, key=lambda i: i.name or ""):
        stmt = _clean(str(CreateIndex(index).compile(dialect=DIALECT)))
        if if_not_exists:
            stmt = stmt.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
            stmt = stmt.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
        chunks.append(stmt + ";")
    return chunks



def _revision_ids() -> list[str]:
    """Revisiones de alembic ordenadas (padre -> hijo) siguiendo down_revision."""
    revisions_dir = BASE_DIR / "migrations" / "versions"
    if not revisions_dir.is_dir():
        return []

    hijos: dict[str, str] = {}      # revision -> padre
    for path in revisions_dir.glob("*.py"):
        rev = down = None
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("revision") and "=" in stripped and rev is None:
                rev = stripped.split("=", 1)[1].strip().strip("\"'")
            elif stripped.startswith("down_revision") and "=" in stripped and down is None:
                down = stripped.split("=", 1)[1].strip().strip("\"'")
        if not rev:
            continue
        parent = "" if down.lower() in ("", "none") else down
        hijos[rev] = parent

    raices = [rev for rev, parent in hijos.items() if parent not in hijos]
    orden: list[str] = []
    visitados: set[str] = set()

    def caminar(rev: str) -> None:
        if rev in visitados:
            return
        visitados.add(rev)
        orden.append(rev)
        for hijo, parent in hijos.items():
            if parent == rev:
                caminar(hijo)

    for raiz in sorted(raices):
        caminar(raiz)
    # Cabezas sueltas (ramas paralelas o ficheros raros): al final, sin romper.
    for rev in sorted(hijos):
        if rev not in visitados:
            orden.append(rev)
    return orden


def _ordered_tables(metadata) -> list:
    """Tablas ordenadas para que ninguna se cree antes que la que referencia."""
    pendientes = {name: table for name, table in metadata.tables.items()}
    orden: list = []
    vistas: set[str] = set()

    def dependencias(table) -> set[str]:
        names = set()
        for column in table.columns:
            for fk in column.foreign_keys:
                target = fk.column.table.name
                if target in pendientes and target != table.name:
                    names.add(target)
        return names

    while pendientes:
        # Primero las que ya no dependen de ninguna tabla pendiente.
        listos = sorted(
            (name for name, table in pendientes.items() if not (dependencias(table) & set(pendientes))),
            key=lambda n: n,
        )
        if not listos:
            # Ciclo imposible en este esquema; se rompe por orden alfabetico.
            listos = sorted(pendientes)
        for name in listos:
            orden.append(pendientes.pop(name))
            vistas.add(name)
    return orden


def build_sql(with_drops: bool = False) -> str:
    with app.app_context():
        metadata = db.metadata
        # Las tablas salen en orden de dependencia: los CREATE quedan legibles
        # y el fichero tambien sirve para motores que validan las claves al crear.
        tablas = _ordered_tables(metadata)
        tables = sorted(tablas, key=lambda t: t.name)

        lines: list[str] = []
        add = lines.append

        add("-- " + "=" * 74)
        add("--  THE DIAMONDS LEAGUE — esquema completo de la base de datos")
        add("--  Generado con `python export_sql.py` desde los modelos de la app.")
        add("--  Destino: MySQL 8 / MariaDB (Clever Cloud).")
        add("-- " + "-" * 74)
        add(f"-- Tablas: {len(tables)}")
        add("-- Charset: utf8mb4 (acentos y emojis).")
        add("--")
        add("-- Importar en Clever Cloud:")
        add("--   mysql -h <host> -P 3306 -u <usuario> -p <base> < database.sql")
        add("-- o desde phpMyAdmin / consola MySQL del panel.")
        add("--")
        add("-- El script es idempotente (IF NOT EXISTS): puedes volver a importarlo.")
        add("-- Con `python export_sql.py --drops` genera la version que borra y rehace todo.")
        add("-- " + "=" * 74)
        add("")

        add("SET NAMES utf8mb4;")
        add("SET FOREIGN_KEY_CHECKS = 0;")
        add("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';")
        add("")

        if with_drops:
            add("-- --- Tablas de apoyo primero (para poder borrarlas sin restriccion) ---")
            for name in ("alembic_version",):
                if name in metadata.tables:
                    add(f"DROP TABLE IF EXISTS `{name}`;")
            for table in reversed(tablas):
                add(f"DROP TABLE IF EXISTS `{table.name}`;")
            add("")

        add("-- " + "=" * 74)
        add("--  1. Tablas")
        add("-- " + "=" * 74)
        for table in tablas:
            add("")
            add(f"-- {table.name}")
            for chunk in _ddl_for(table, if_not_exists=not with_drops):
                add(chunk)

        add("")
        add("-- " + "=" * 74)
        add("--  2. Version de migraciones")
        add("--     flask db upgrade no repetira lo que ya esta importado aqui.")
        add("-- " + "=" * 74)
        # Alembic no usa los modelos, asi que su tabla se declara a mano.
        if with_drops:
            add("DROP TABLE IF EXISTS `alembic_version`;")
        add("CREATE TABLE IF NOT EXISTS `alembic_version` (")
        add("\t`version_num` VARCHAR(32) NOT NULL,")
        add("\tCONSTRAINT `alembic_version_pkc` PRIMARY KEY (`version_num`)")
        add(f") {TABLE_OPTIONS};")
        add("")
        add("DELETE FROM `alembic_version`;")
        revisions = _revision_ids()
        if revisions:
            # Alembic guarda una sola fila: la revision actual (la mas nueva).
            add(f"INSERT INTO `alembic_version` (`version_num`) VALUES ('{revisions[-1]}');")
        add("")

        add("SET FOREIGN_KEY_CHECKS = 1;")
        add("")
        return "\n".join(lines)


def main() -> int:
    salida = Path("database.sql")
    with_drops = "--drops" in sys.argv
    for index, arg in enumerate(sys.argv):
        if arg == "--salida" and index + 1 < len(sys.argv):
            salida = Path(sys.argv[index + 1])
    if not salida.is_absolute():
        salida = BASE_DIR / salida

    salida.write_text(build_sql(with_drops), encoding="utf-8")
    print(f"OK  {salida}  ({salida.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
