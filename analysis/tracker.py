import ast
from collections import Counter

from git import Repo
from db.models import (Session, Commit, File, Function, FunctionChange)


def functions_in(source):
    """Return code by qualified function name, or None if parsing fails."""
    try:
        # Parsing bytes lets Python honor source encoding cookies and BOMs.
        tree = ast.parse(source)
    except SyntaxError:
        return None

    functions = {}

    def visit(node, scope):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
            if not isinstance(node, ast.ClassDef):
                functions[".".join(scope)] = ast.unparse(node)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, ())
    return functions


def _record_history(git_repo, s, repo_id):
    commits = {c.hash: c for c in s.query(Commit).filter_by(repo_id=repo_id)}
    files = {f.path: f for f in s.query(File).filter_by(repo_id=repo_id)}
    history = list(git_repo.iter_commits(topo_order=True))
    # GitPython's stats compare each commit to its first parent, also for merges.
    remaining = Counter(gc.parents[0].hexsha for gc in history if gc.parents)
    snapshots = {}  # commit SHA -> {path: {qualified name: (Function row, code)}}

    for gc in reversed(history):
        commit_row = commits[gc.hexsha]
        if gc.parents:
            parent = gc.parents[0].hexsha
            remaining[parent] -= 1
            # Preserve the parent's snapshot until its last child uses it.
            if remaining[parent]:
                state = snapshots[parent].copy()
            else:
                state = snapshots.pop(parent)
        else:
            state = {}

        for path in gc.stats.files:
            if not path.endswith(".py"):
                continue
            try:
                source = gc.tree[path].data_stream.read()
            except KeyError:
                source = b""  # the file was deleted in this commit

            new = functions_in(source)
            if new is None:
                continue
            old = state.get(path, {})
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
            if current:
                state[path] = current
            else:
                state.pop(path, None)

        if remaining[gc.hexsha]:
            snapshots[gc.hexsha] = state


def track_functions(repo_path, repo_id):
    """Build history once per repository and reuse it on subsequent runs."""
    with Session() as s:
        repo_functions = s.query(Function).join(File).filter(File.repo_id == repo_id)
        if repo_functions.first() is None:
            _record_history(Repo(repo_path), s, repo_id)
            s.commit()

        for fn in repo_functions:
            kinds = [c.change_type for c in s.query(FunctionChange)
                     .filter_by(function_id=fn.function_id)
                     .order_by(FunctionChange.change_id)]
            print(fn.name + ":", " -> ".join(kinds))


if __name__ == "__main__":
    track_functions(r"C:\Users\anush\practice_repo", 1)
