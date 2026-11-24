import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.fossil import NO_CODE, find_fossils
from db.models import (Base, CodeFossil, Commit, Developer, File, Function,
                       Repository)

START = datetime(2026, 1, 1)


@pytest.fixture
def session():
    """A fresh, empty in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        s.add(Repository(name="test", path="fake"))  # not a real git repo
        s.add(Developer(name="A", email="a@x.com"))
        s.flush()  # repo_id is 1, developer_id is 1
        yield s


def make_file(session, path):
    f = File(repo_id=1, path=path)
    session.add(f)
    session.flush()
    return f


def make_commit(session, day):
    """A commit made `day` days after START."""
    c = Commit(repo_id=1, developer_id=1, hash=f"{day:040x}",
               message=f"commit on day {day}",
               committed_at=START + timedelta(days=day),
               is_fix=False, is_revert=False)
    session.add(c)
    session.flush()
    return c


def make_function(session, file, name, created, deleted=None):
    fn = Function(file_id=file.file_id, name=name,
                  created_commit_id=created.commit_id,
                  deleted_commit_id=deleted.commit_id if deleted else None)
    session.add(fn)
    session.flush()
    return fn


def test_function_that_is_still_alive_is_not_a_fossil(session):
    f = make_file(session, "a.py")
    make_function(session, f, "alive", make_commit(session, 0))
    assert find_fossils(session, 1) == []


def test_deleted_function_is_reported_with_its_commit(session):
    f = make_file(session, "a.py")
    born, died = make_commit(session, 0), make_commit(session, 10)
    make_function(session, f, "old_total", born, deleted=died)

    result = find_fossils(session, 1)
    assert len(result) == 1
    assert result[0]["function"] == "old_total"
    assert result[0]["file"] == "a.py"
    assert result[0]["deleted_hash"] == died.hash
    assert result[0]["deleted_message"] == "commit on day 10"


def test_similar_new_function_is_found_as_replacement(session):
    f = make_file(session, "cart.py")
    born, died, later = (make_commit(session, d) for d in (0, 10, 11))
    make_function(session, f, "apply_discount", born, deleted=died)
    make_function(session, f, "apply_coupon", later)

    result = find_fossils(session, 1)
    assert result[0]["replacement"] == "apply_coupon"
    assert result[0]["score"] >= 0.5


def test_no_replacement_when_nothing_similar_appears_nearby(session):
    a = make_file(session, "a.py")
    b = make_file(session, "b.py")
    born, died, much_later = (make_commit(session, d) for d in (0, 10, 40))
    make_function(session, a, "fuzzy_search", born, deleted=died)
    make_function(session, b, "zzz", much_later)  # 30 days later, other file

    result = find_fossils(session, 1)
    assert result[0]["replacement"] is None
    assert result[0]["score"] is None


def test_fossil_row_is_saved_once_even_if_run_twice(session):
    f = make_file(session, "a.py")
    born, died = make_commit(session, 0), make_commit(session, 10)
    dead = make_function(session, f, "old_total", born, deleted=died)

    find_fossils(session, 1)
    find_fossils(session, 1)  # re-running must not create duplicates

    rows = session.query(CodeFossil).all()
    assert len(rows) == 1
    assert rows[0].function_id == dead.function_id
    assert rows[0].deleted_commit_id == died.commit_id
    assert rows[0].last_code == NO_CODE  # fake repo path has no real code