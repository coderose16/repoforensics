from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from git import Repo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.tracker import functions_in, track_functions
from db.models import Base, Commit, Developer, File, Function, FunctionChange, Repository


class TrackerTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.repo = Repo.init(directory)
        self.addCleanup(self.repo.close)
        self.repo.git.config("user.name", "Tracker Test")
        self.repo.git.config("user.email", "tracker@example.com")
        self.path = Path(directory) / "sample.py"
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(engine)
        self.enterContext(patch("analysis.tracker.Session", self.session))
        self.output = self.enterContext(redirect_stdout(StringIO()))

    def commit(self, message, source):
        self.path.write_bytes(source)
        self.repo.index.add([self.path.name])
        self.repo.index.commit(message)

    def load_repository(self):
        with self.session.begin() as s:
            repo = Repository(name="fixture", path=str(self.path.parent))
            dev = Developer(name="Tracker Test", email="tracker@example.com")
            s.add_all([repo, dev])
            s.flush()
            s.add(File(repo_id=repo.repo_id, path=self.path.name))
            for commit in self.repo.iter_commits():
                s.add(Commit(repo_id=repo.repo_id, developer_id=dev.developer_id,
                             hash=commit.hexsha, message=commit.summary,
                             committed_at=commit.committed_datetime.replace(tzinfo=None),
                             is_fix=False, is_revert=False))
            return repo.repo_id

    def events(self, repo_id):
        with self.session() as s:
            return s.query(Function.name, Commit.message, FunctionChange.change_type).join(
                FunctionChange, Function.function_id == FunctionChange.function_id
            ).join(Commit, FunctionChange.commit_id == Commit.commit_id).filter(
                Commit.repo_id == repo_id
            ).order_by(FunctionChange.change_id).all()

    def test_function_names_include_class_and_function_scopes(self):
        source = """\
def run():
    pass

class First:
    async def run(self):
        def inner():
            pass

class Second:
    def run(self):
        async def inner():
            pass
"""
        self.assertEqual(set(functions_in(source)), {
            "run", "First.run", "First.run.inner", "Second.run", "Second.run.inner",
        })

    def test_parse_failure_preserves_history_and_empty_source_deletes(self):
        self.commit("latin-1", b'# coding: latin-1\ndef run(): return "\xe9"\n')
        self.commit("syntax error", b"def run(:\n")
        self.commit("invalid encoding", b"# coding: unknown-encoding\ndef run(): pass\n")
        self.commit("BOM, same code", b'\xef\xbb\xbfdef run(): return "\xc3\xa9"\n')
        self.commit("ordinary UTF-8", b'def run(): return "\xc3\xa0"\n')
        self.commit("no functions", b"value = 1\n")
        repo_id = self.load_repository()

        track_functions(self.repo.working_dir, repo_id)

        self.assertEqual(self.events(repo_id), [
            ("run", "latin-1", "created"),
            ("run", "ordinary UTF-8", "modified"),
            ("run", "no functions", "deleted"),
        ])
        with self.session() as s:
            fn = s.query(Function).one()
            self.assertEqual(s.get(Commit, fn.deleted_commit_id).message, "no functions")

    def test_sibling_branches_are_isolated_and_reruns_reuse_history(self):
        base = b"def shared(): pass\n"
        self.commit("base", base)
        main = self.repo.active_branch.name
        self.repo.git.checkout("-b", "side")
        self.commit("side", base + b"def only_side(): pass\n")
        self.repo.git.checkout(main)
        self.commit("main", base + b"def only_main(): pass\n")
        self.repo.git.merge("-s", "ours", "side", "-m", "merge")
        repo_id = self.load_repository()
        other_id = self.load_repository()

        track_functions(self.repo.working_dir, repo_id)
        track_functions(self.repo.working_dir, other_id)
        self.output.seek(0)
        self.output.truncate()
        track_functions(self.repo.working_dir, repo_id)

        expected = [
            ("shared", "base", "created"),
            ("only_side", "side", "created"),
            ("only_main", "main", "created"),
        ]
        self.assertCountEqual(self.events(repo_id), expected)
        self.assertCountEqual(self.events(other_id), expected)
        self.assertCountEqual(self.output.getvalue().splitlines(), [
            "shared: created", "only_side: created", "only_main: created",
        ])
