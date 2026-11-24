import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.risk import get_risk_scores
from db.models import (Base, CodeChange, Commit, Developer, File,
                       Repository)


@pytest.fixture
def session():
    """A fresh, empty in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        s.add(Repository(name="test", path="fake"))
        s.add_all([Developer(name="A", email="a@x.com"),
                   Developer(name="B", email="b@x.com")])
        s.flush()  # repo_id is 1, developer ids are 1 and 2
        yield s


def make_file(session, path):
    f = File(repo_id=1, path=path)
    session.add(f)
    session.flush()
    return f


def make_commit(session, files, dev_id=1, fix=False, revert=False):
    c = Commit(repo_id=1, developer_id=dev_id, hash="a" * 40, message="m",
               committed_at=datetime(2026, 1, 1), is_fix=fix, is_revert=revert)
    session.add(c)
    session.flush()
    for f in files:
        session.add(CodeChange(commit_id=c.commit_id, file_id=f.file_id,
                               lines_added=1, lines_deleted=0))
    session.flush()


def test_repo_with_no_files_gives_empty_list(session):
    assert get_risk_scores(session, 1) == []


def test_untouched_file_is_low_with_zero_score(session):
    make_file(session, "idle.py")
    result = get_risk_scores(session, 1)
    assert result[0]["score"] == 0
    assert result[0]["label"] == "LOW"


def test_busy_fixed_file_ranks_above_quiet_file(session):
    hot = make_file(session, "hot.py")
    quiet = make_file(session, "quiet.py")
    make_commit(session, [hot], dev_id=1, fix=True)
    make_commit(session, [hot], dev_id=2, fix=True)
    make_commit(session, [hot], dev_id=1)
    make_commit(session, [hot, quiet], dev_id=2)

    result = get_risk_scores(session, 1)
    assert [r["path"] for r in result] == ["hot.py", "quiet.py"]
    assert result[0]["score"] == pytest.approx(85.0)
    assert result[0]["label"] == "HIGH"
    assert result[1]["score"] == pytest.approx(17.5)
    assert result[1]["label"] == "LOW"


def test_revert_raises_the_score(session):
    plain = make_file(session, "plain.py")
    reverted = make_file(session, "reverted.py")
    make_commit(session, [plain])
    make_commit(session, [reverted], revert=True)

    scores = {r["path"]: r["score"] for r in get_risk_scores(session, 1)}
    assert scores["reverted.py"] > scores["plain.py"]