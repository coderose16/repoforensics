import ast
from git import Repo
from db.models import (Session, Commit, File, Function, FunctionChange)


def functions_in(source):
    """Turn source code into {function_name: its code}."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    return {
        n.name: ast.unparse(n)
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def track_functions(repo_path, repo_id):
    git_repo = Repo(repo_path)
    with Session() as s:
        commits = {c.hash: c for c in s.query(Commit).filter_by(repo_id=repo_id)}
        files = {f.path: f for f in s.query(File).filter_by(repo_id=repo_id)}
        state = {}  # file path -> {function name: (Function row, code)}

        for gc in reversed(list(git_repo.iter_commits())):  # oldest first
            commit_row = commits[gc.hexsha]
            for path in gc.stats.files:
                if not path.endswith(".py"):
                    continue
                try:
                    source = gc.tree[path].data_stream.read().decode("utf-8")
                except KeyError:
                    source = ""  # the file was deleted in this commit

                new = functions_in(source)
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
                state[path] = current
        s.commit()

        for fn in s.query(Function):
            kinds = [c.change_type for c in s.query(FunctionChange)
                     .filter_by(function_id=fn.function_id)
                     .order_by(FunctionChange.change_id)]
            print(fn.name + ":", " -> ".join(kinds))


if __name__ == "__main__":
    track_functions(r"C:\Users\anush\practice_repo", 1)