from collections import Counter

from db.models import Session, Commit, Developer, File, CodeChange


def get_ownership(session, repo_id, recent=5):
    result = []
    for f in session.query(File).filter_by(repo_id=repo_id):
        rows = (session.query(Commit, Developer, CodeChange)
                .join(CodeChange, CodeChange.commit_id == Commit.commit_id)
                .join(Developer, Developer.developer_id == Commit.developer_id)
                .filter(CodeChange.file_id == f.file_id)
                .order_by(Commit.committed_at, Commit.commit_id.desc())
                .all())
        if not rows:
            continue
        names = {d.developer_id: d.name for _, d, _ in rows}
        original_id = rows[0][1].developer_id
        counts = Counter()
        for _, dev, ch in rows[-recent:]:
            counts[dev.developer_id] += ch.lines_added + ch.lines_deleted
        top_id = counts.most_common(1)[0][0]
        result.append({
            "file": f.path,
            "original_author": names[original_id],
            "top_recent_author": names[top_id],
            "contributors": len(names),
            "drift": original_id != top_id,
        })
    return result


if __name__ == "__main__":
    with Session() as s:
        for r in get_ownership(s, 1):
            print(r)