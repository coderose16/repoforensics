import ast
import io
import tokenize

from git import Repo
from sqlalchemy import select

from db.models import (Session, Commit, File, Function,
                       FunctionChange, CodeFossil)


def read_source(blob):
    """Decode bytes using the file's own encoding declaration (UTF-8 by default)."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(blob).readline)
        return blob.decode(encoding)
    except (SyntaxError, UnicodeDecodeError, LookupError):
        return None


def functions_in(source):
    """Return {'ClassName.method': code}. Returns None if the code can't be parsed,
    which is different from {} (a valid file with no functions)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None

    found = {}

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = ".".join(scope + [child.name])
                found[name] = ast.unparse(child)
                visit(child, scope + [child.name])
            elif isinstance(child, ast.ClassDef):
                visit(child, scope + [child.name])
            else:
                visit(child, scope)

    visit(tree, [])
    return found


def track_functions(repo_path, repo_id):
    git_repo = Repo(repo_path)
    with Session() as s:
        commits = {c.hash: c for c in s.query(Commit).filter_by(repo_id=repo_id)}
        files = {f.path: f for f in s.query(File).filter_by(repo_id=repo_id)}

        # Re-running replaces old results instead of duplicating them.
        file_ids = select(File.file_id).where(File.repo_id == repo_id)
        fn_ids = select(Function.function_id).where(Function.file_id.in_(file_ids))
        s.query(CodeFossil).filter(CodeFossil.function_id.in_(fn_ids)).delete(synchronize_session=False)
        s.query(FunctionChange).filter(FunctionChange.function_id.in_(fn_ids)).delete(synchronize_session=False)
        s.query(Function).filter(Function.file_id.in_(file_ids)).delete(synchronize_session=False)

        snapshots = {}  # commit hash -> {path: {name: (Function row, code)}}

        for gc in git_repo.iter_commits(topo_order=True, reverse=True):  # parents first
            commit_row = commits[gc.hexsha]
            parent_state = snapshots[gc.parents[0].hexsha] if gc.parents else {}
            state = dict(parent_state)  # start from this commit's own parent

            for path in gc.stats.files:
                if not path.endswith(".py"):
                    continue
                try:
                    blob = gc.tree[path].data_stream.read()
                except KeyError:
                    source = ""  # file deleted in this commit
                else:
                    source = read_source(blob)

                new = functions_in(source) if source is not None else None
                if new is None:
                    continue  # unreadable snapshot: keep the previous state

                old = parent_state.get(path, {})
                current = {}

                for name, code in new.items():
                    if name not in old:
                        fn = Function(file_id=files[path].file_id, name=name,
                                      created_commit_id=commit_row.commit_id)
                        s.add(fn)
                        s.flush()
                        kind = "created"
                    else:
                        fn = old[name][0]
                        kind = "modified" if old[name][1] != code else None
                    if kind:
                        s.add(FunctionChange(function_id=fn.function_id,
                                             commit_id=commit_row.commit_id,
                                             change_type=kind))
                    current[name] = (fn, code)

                for name, (fn, _) in old.items():
                    if name not in new:
                        fn.deleted_commit_id = commit_row.commit_id
                        s.add(FunctionChange(function_id=fn.function_id,
                                             commit_id=commit_row.commit_id,
                                             change_type="deleted"))
                state[path] = current

            snapshots[gc.hexsha] = state
        s.commit()

        for fn in s.query(Function).filter(Function.file_id.in_(file_ids)):
            kinds = [c.change_type for c in s.query(FunctionChange)
                     .filter_by(function_id=fn.function_id)
                     .order_by(FunctionChange.change_id)]
            print(fn.name + ":", " -> ".join(kinds))


if __name__ == "__main__":
    track_functions(r"C:\Users\anush\practice_repo", 1)