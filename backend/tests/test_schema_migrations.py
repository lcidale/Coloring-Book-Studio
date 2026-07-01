from app.database import _COLUMN_MIGRATIONS, _pg_alter_statements


def test_new_columns_registered():
    assert _COLUMN_MIGRATIONS["pages"]["title"] == "VARCHAR(200)"
    pv = _COLUMN_MIGRATIONS["page_versions"]
    assert pv["label"] == "VARCHAR(120)"
    assert pv["dpi"] == "INTEGER"
    assert pv["width_px"] == "INTEGER"
    assert pv["height_px"] == "INTEGER"
    assert pv["is_pure_bw"] == "BOOLEAN"


def test_pg_alter_uses_declared_types_not_hardcoded_varchar():
    stmts = _pg_alter_statements()
    assert (
        "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS dpi INTEGER" in stmts
    )
    assert (
        "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS is_pure_bw BOOLEAN" in stmts
    )
    # Regression: no column should be forced to VARCHAR DEFAULT ''
    assert not any("VARCHAR DEFAULT ''" in s for s in stmts)
