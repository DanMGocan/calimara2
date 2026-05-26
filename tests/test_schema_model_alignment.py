import re
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from app import models


ROOT = Path(__file__).resolve().parents[1]


def _schema_sql() -> str:
    return (ROOT / "schema.sql").read_text(encoding="utf-8")


def _create_table_blocks(schema: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"^CREATE TABLE\s+([a-zA-Z_][\w]*)\s*\(\n(.*?)^\);",
            schema,
            flags=re.M | re.S,
        )
    }


def _schema_columns() -> dict[str, set[str]]:
    ignored = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE"}
    tables = {}
    for table_name, body in _create_table_blocks(_schema_sql()).items():
        columns = set()
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            first_token = line.split(None, 1)[0].strip('"')
            if first_token.upper() in ignored:
                continue
            if re.match(r"^[A-Za-z_][\w]*$", first_token):
                columns.add(first_token)
        tables[table_name] = columns
    return tables


def _split_top_level(value: str) -> list[str]:
    parts = []
    current = []
    depth = 0
    in_single_quote = False

    for char in value:
        if char == "'":
            in_single_quote = not in_single_quote
        if not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
        current.append(char)

    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _normalize_expression(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().replace('"', "")).lower()


FK_RE = re.compile(
    r"(?:CONSTRAINT\s+(?P<name>[a-zA-Z_][\w]*)\s+)?"
    r"FOREIGN KEY\s*\((?P<cols>[^)]+)\)\s+"
    r"REFERENCES\s+(?P<ref_table>[a-zA-Z_][\w]*)\s*"
    r"\((?P<ref_cols>[^)]+)\)"
    r"(?:\s+ON DELETE\s+(?P<ondelete>[A-Z ]+))?",
    flags=re.I,
)

UNIQUE_INDEX_RE = re.compile(
    r"CREATE UNIQUE INDEX\s+\w+\s+ON\s+([a-zA-Z_]\w*)\s*\(([^)]+)\)",
    flags=re.I,
)


def _split_columns(value: str) -> tuple[str, ...]:
    return tuple(item.strip().strip('"').lower() for item in value.split(","))


def _normalize_ondelete(value: str | None) -> str | None:
    normalized = " ".join((value or "").upper().split())
    return normalized or None


def _schema_foreign_keys() -> set[tuple[str, tuple[str, ...], str, tuple[str, ...], str | None]]:
    schema = _schema_sql()
    foreign_keys = set()

    for table_name, body in _create_table_blocks(schema).items():
        for match in FK_RE.finditer(body):
            foreign_keys.add(
                (
                    table_name,
                    _split_columns(match.group("cols")),
                    match.group("ref_table"),
                    _split_columns(match.group("ref_cols")),
                    _normalize_ondelete(match.group("ondelete")),
                )
            )

    for statement in re.finditer(
        r"^ALTER TABLE\s+([a-zA-Z_][\w]*)\s+(.*?);",
        schema,
        flags=re.M | re.S,
    ):
        table_name = statement.group(1)
        for match in FK_RE.finditer(statement.group(2)):
            foreign_keys.add(
                (
                    table_name,
                    _split_columns(match.group("cols")),
                    match.group("ref_table"),
                    _split_columns(match.group("ref_cols")),
                    _normalize_ondelete(match.group("ondelete")),
                )
            )
    return foreign_keys


def _schema_unique_signatures() -> set[tuple[str, tuple[str, ...], str | None]]:
    schema = _schema_sql()
    unique_signatures = set()
    ignored = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE"}

    for table_name, body in _create_table_blocks(schema).items():
        for item in _split_top_level(body):
            line = " ".join(item.split())
            table_match = re.search(
                r"(?:CONSTRAINT\s+\w+\s+)?UNIQUE\s*\(([^)]+)\)",
                line,
                flags=re.I,
            )
            if table_match:
                unique_signatures.add((table_name, _split_columns(table_match.group(1)), None))

            first_token = line.split(None, 1)[0].strip('"') if line else ""
            if (
                first_token.upper() not in ignored
                and re.match(r"^[A-Za-z_]\w*$", first_token)
                and re.search(r"\bUNIQUE\b", line, flags=re.I)
            ):
                unique_signatures.add((table_name, (first_token.lower(),), None))

    for match in re.finditer(
        r"CREATE UNIQUE INDEX\s+\w+\s+ON\s+([a-zA-Z_]\w*)\s*\(([^)]+)\)(?:\s+WHERE\s+(.*?))?;",
        schema,
        flags=re.I,
    ):
        unique_signatures.add(
            (
                match.group(1),
                _split_columns(match.group(2)),
                _normalize_expression(match.group(3)) if match.group(3) else None,
            )
        )

    return unique_signatures


def _schema_check_constraints() -> set[tuple[str, str]]:
    checks = set()
    for table_name, body in _create_table_blocks(_schema_sql()).items():
        for item in _split_top_level(body):
            line = " ".join(item.split())
            for match in re.finditer(r"CHECK\s*\((.*)\)", line, flags=re.I):
                checks.add((table_name, _normalize_expression(match.group(1))))
    return checks


def _model_foreign_keys() -> set[tuple[str, tuple[str, ...], str, tuple[str, ...], str | None]]:
    foreign_keys = set()
    for table in models.Base.metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            elements = list(constraint.elements)
            foreign_keys.add(
                (
                    table.name,
                    tuple(column.name for column in constraint.columns),
                    elements[0].column.table.name,
                    tuple(element.column.name for element in elements),
                    _normalize_ondelete(constraint.ondelete),
                )
            )
    return foreign_keys


def _model_unique_signatures() -> set[tuple[str, tuple[str, ...], str | None]]:
    unique_signatures = set()
    for table in models.Base.metadata.tables.values():
        for column in table.columns:
            if column.unique:
                unique_signatures.add((table.name, (column.name.lower(),), None))
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                unique_signatures.add((table.name, tuple(column.name.lower() for column in constraint.columns), None))
        for index in table.indexes:
            if index.unique:
                where = index.dialect_options["postgresql"].get("where")
                if where is None:
                    where = index.dialect_options["sqlite"].get("where")
                unique_signatures.add(
                    (
                        table.name,
                        tuple(expression.name.lower() for expression in index.expressions if hasattr(expression, "name")),
                        _normalize_expression(str(where)) if where is not None else None,
                    )
                )
    return unique_signatures


def _model_check_constraints() -> set[tuple[str, str]]:
    checks = set()
    for table in models.Base.metadata.tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint):
                checks.add((table.name, _normalize_expression(str(constraint.sqltext))))
    return checks


def test_sqlalchemy_tables_and_columns_match_schema_sql():
    schema_columns = _schema_columns()
    model_tables = models.Base.metadata.tables

    assert set(model_tables) == set(schema_columns)
    for table_name, columns in schema_columns.items():
        assert set(model_tables[table_name].columns.keys()) == columns


def test_sqlalchemy_foreign_keys_match_schema_sql():
    assert _model_foreign_keys() == _schema_foreign_keys()


def test_sqlalchemy_unique_constraints_match_schema_sql():
    assert _model_unique_signatures() == _schema_unique_signatures()


def test_sqlalchemy_check_constraints_match_schema_sql():
    assert _model_check_constraints() == _schema_check_constraints()
