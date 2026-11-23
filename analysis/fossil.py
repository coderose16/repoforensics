import ast
from datetime import timedelta
from difflib import SequenceMatcher

from git import Repo

from db.models import CodeFossil, Commit, Developer, File, Function, Repository

WINDOW = timedelta(days=7)   # how long after a deletion a replacement may appear
LOOKBACK = timedelta(days=1)  # or this long before it
MIN_SCORE = 0.5
NO_CODE = "# Source code not available (repository not found on this computer)"


def get_old_code(repo_path, commit_hash, file_path, func_name):
    """Return the function's source as it was just before `commit_hash`, or None."""
    try:
        commit = Repo(repo_path).commit(commit_hash)
        before = commit.parents[0]  # the commit just before the deletion
        source = (before.tree / file_path).data_stream.read().decode("utf-8")
        tree = ast.parse(source)
    except Exception:
        return None
    short = func_name.split(".")[-1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == short:
            return ast.get_source_segment(source, node)
    return None


def find_fossils(session, repo_id):
    """Save a CodeFossil row for every deleted function and return the details."""
    repo = session.get(Repository, repo_id)
    funcs = (
        session.query(Function, File)
        .join(File, Function.file_id == File.file_id)
        .filter(File.repo_id == repo_id)
        .all()
    )
    commits = {c.commit_id: c for c in
               session.query(Commit).filter(Commit.repo_id == repo_id)}
    devs = {d.developer_id: d.name for d in session.query(Developer)}
    paths = {f.file_id: f.path for _, f in funcs}
    names = {fn.function_id: fn.name for fn, _ in funcs}

    # start fresh so this can be re-run safely
    ids = [fn.function_id for fn, _ in funcs]
    if ids:
        session.query(CodeFossil).filter(
            CodeFossil.function_id.in_(ids)
        ).delete(synchronize_session=False)

    results = []
    for dead, _ in funcs:
        if dead.deleted_commit_id is None:
            continue
        del_commit = commits[dead.deleted_commit_id]
        dead_short = dead.name.split(".")[-1]

        best, best_score = None, 0.0
        for cand, _ in funcs:
            if cand.function_id == dead.function_id:
                continue
            gap = commits[cand.created_commit_id].committed_at - del_commit.committed_at
            if not (-LOOKBACK <= gap <= WINDOW):
                continue
            name_sim = SequenceMatcher(
                None, dead_short, cand.name.split(".")[-1]).ratio()
            same_file = 1.0 if cand.file_id == dead.file_id else 0.0
            closeness = 1 - abs(gap) / WINDOW
            score = 0.5 * name_sim + 0.3 * same_file + 0.2 * closeness
            if score > best_score:
                best, best_score = cand, score
        if best_score < MIN_SCORE:
            best = None

        code = get_old_code(repo.path, del_commit.hash, paths[dead.file_id], dead.name)
        session.add(CodeFossil(
            function_id=dead.function_id,
            deleted_commit_id=del_commit.commit_id,
            last_code=code or NO_CODE,
            replacement_function_id=best.function_id if best else None,
        ))
        results.append({
            "function": dead.name,
            "file": paths[dead.file_id],
            "deleted_hash": del_commit.hash,
            "deleted_message": del_commit.message,
            "deleted_at": del_commit.committed_at,
            "deleted_by": devs.get(del_commit.developer_id, "unknown"),
            "replacement": names[best.function_id] if best else None,
            "score": round(best_score, 2) if best else None,
            "last_code": code or NO_CODE,
        })

    session.commit()
    results.sort(key=lambda r: r["deleted_at"], reverse=True)
    return results