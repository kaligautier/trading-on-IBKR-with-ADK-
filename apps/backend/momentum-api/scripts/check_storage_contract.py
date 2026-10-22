"""Verify projected columns against writer source without importing its runtime."""

import ast
from pathlib import Path

from app.assembly import SECTION_MODELS
from app.dto import AnalysisDetail
from app.repository import HEADER_COLUMNS

ROOT = Path(__file__).resolve().parents[4]
MODELS = ROOT / "apps/backend/momentum-adk/app/infrastructure/models.py"


def columns(source: str) -> dict[str, set[str]]:
    tables = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        table = next(
            (
                statement.value.value
                for statement in node.body
                if isinstance(statement, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__tablename__"
                    for target in statement.targets
                )
                and isinstance(statement.value, ast.Constant)
            ),
            None,
        )
        if table:
            tables[table] = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "mapped_column"
            }
    return tables


def check(source: str) -> None:
    writer = columns(source)
    expected = {"analysis_results": set(HEADER_COLUMNS.replace(" ", "").split(","))}
    for table, model in SECTION_MODELS.items():
        expected[table] = {"id", "result_id"} | {
            str(field.validation_alias or name)
            for name, field in model.model_fields.items()
            if name != "items"
        }
    for table, projection in expected.items():
        missing = projection - writer.get(table, set())
        if missing:
            raise ValueError(f"Storage contract drift: {table}: {sorted(missing)}")
    assert not {"user_id", "session_id", "invocation_id"} & set(
        AnalysisDetail.model_fields
    )


if __name__ == "__main__":
    check(MODELS.read_text())
    print("All Momentum consultation projections exist in the writer storage contract.")
