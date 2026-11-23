from db.models import CodeChange, Commit, File

WEIGHTS = {"changes": 0.40, "fixes": 0.30, "reverts": 0.15, "contributors": 0.15}


def get_risk_scores(session, repo_id):
    """Return a list of files with a risk score (0-100) and a HIGH/MED/LOW label."""
    # start every file with zeros, so untouched files still appear
    files = session.query(File).filter(File.repo_id == repo_id).all()
    stats = {
        f.file_id: {"path": f.path, "changes": 0, "fixes": 0,
                    "reverts": 0, "devs": set()}
        for f in files
    }

    # one row per (commit, file) change
    rows = (
        session.query(CodeChange.file_id, Commit.is_fix,
                      Commit.is_revert, Commit.developer_id)
        .join(Commit, CodeChange.commit_id == Commit.commit_id)
        .filter(Commit.repo_id == repo_id)
        .all()
    )
    for file_id, is_fix, is_revert, dev_id in rows:
        s = stats[file_id]
        s["changes"] += 1
        s["fixes"] += int(is_fix)
        s["reverts"] += int(is_revert)
        s["devs"].add(dev_id)

    # biggest value in each category (or 1, to avoid dividing by zero)
    max_changes = max((s["changes"] for s in stats.values()), default=0) or 1
    max_fixes = max((s["fixes"] for s in stats.values()), default=0) or 1
    max_reverts = max((s["reverts"] for s in stats.values()), default=0) or 1
    max_devs = max((len(s["devs"]) for s in stats.values()), default=0) or 1

    results = []
    for file_id, s in stats.items():
        score = 100 * (
            WEIGHTS["changes"] * s["changes"] / max_changes
            + WEIGHTS["fixes"] * s["fixes"] / max_fixes
            + WEIGHTS["reverts"] * s["reverts"] / max_reverts
            + WEIGHTS["contributors"] * len(s["devs"]) / max_devs
        )
        label = "HIGH" if score >= 60 else "MED" if score >= 30 else "LOW"
        results.append({
            "file_id": file_id,
            "path": s["path"],
            "changes": s["changes"],
            "fixes": s["fixes"],
            "reverts": s["reverts"],
            "contributors": len(s["devs"]),
            "score": round(score, 1),
            "label": label,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results