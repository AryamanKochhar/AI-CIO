"""Exercise the legacy CHECK upgrade, not only metadata-created test tables."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def migration():
    path=Path(__file__).resolve().parents[1]/"alembic/versions/0009_fire_goal_type.py"
    spec=importlib.util.spec_from_file_location("fire_type_migration",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_goal_constraint_upgrades_without_changing_existing_rows(pg_engine):
    revision=migration()
    with pg_engine.begin() as conn:
        # TEMP shadows public.goals on this connection and drops at commit.
        conn.execute(text("CREATE TEMP TABLE goals (id integer PRIMARY KEY, goal_type varchar(64), CONSTRAINT ck_goals_type CHECK ("+revision.OLD_TYPES+")) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO goals VALUES (1,'retirement'),(2,'home'),(3,NULL)"))
        with pytest.raises(IntegrityError),conn.begin_nested():
            conn.execute(text("INSERT INTO goals VALUES (4,'fire')"))
        before=conn.execute(text("SELECT id,goal_type FROM goals ORDER BY id")).all()
        with Operations.context(MigrationContext.configure(conn)):
            revision.upgrade()
        assert conn.execute(text("SELECT id,goal_type FROM goals ORDER BY id")).all()==before
        conn.execute(text("INSERT INTO goals VALUES (4,'fire')"))
        with pytest.raises(IntegrityError),conn.begin_nested():
            conn.execute(text("INSERT INTO goals VALUES (5,'not-a-goal')"))
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError,match="no records were changed"):
                revision.downgrade()
        assert conn.execute(text("SELECT goal_type FROM goals WHERE id=4")).scalar_one()=="fire"
        conn.execute(text("DELETE FROM goals WHERE id=4"))
        with Operations.context(MigrationContext.configure(conn)):
            revision.downgrade()
        with pytest.raises(IntegrityError),conn.begin_nested():
            conn.execute(text("INSERT INTO goals VALUES (4,'fire')"))
        assert conn.execute(text("SELECT id,goal_type FROM goals ORDER BY id")).all()==before


def test_metadata_contains_the_same_fire_goal_type_guard():
    from ai_cio.db.models import Goal
    guard=next(c for c in Goal.__table__.constraints if c.name=="ck_goals_type")
    assert str(guard.sqltext)==migration().NEW_TYPES
