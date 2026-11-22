from git import Repo
from db.models import (Session, init_db, Repository, Developer,
                       Commit, File, CodeChange)

REPO_PATH = r"C:\Users\anush\practice_repo"
git_repo = Repo(REPO_PATH)

init_db()
with Session() as s:
    repo_row = Repository(name="practice_repo", path=REPO_PATH)
    s.add(repo_row)
    s.flush()

    devs, files = {}, {}
    for c in git_repo.iter_commits():
        email = c.author.email
        if email not in devs:
            d = Developer(name=c.author.name, email=email)
            s.add(d)
            s.flush()
            devs[email] = d

        msg = c.message.strip().splitlines()[0]
        commit = Commit(
            repo_id=repo_row.repo_id,
            developer_id=devs[email].developer_id,
            hash=c.hexsha,
            message=msg,
            committed_at=c.committed_datetime.replace(tzinfo=None),
            is_fix="fix" in msg.lower(),
            is_revert=msg.lower().startswith("revert"),
        )
        s.add(commit)
        s.flush()

        for path, st in c.stats.files.items():
            if path not in files:
                f = File(repo_id=repo_row.repo_id, path=path)
                s.add(f)
                s.flush()
                files[path] = f
            s.add(CodeChange(
                commit_id=commit.commit_id,
                file_id=files[path].file_id,
                lines_added=st["insertions"],
                lines_deleted=st["deletions"],
            ))

    s.commit()
    print("Loaded", s.query(Commit).count(), "commits,",
          s.query(Developer).count(), "developers,",
          s.query(File).count(), "files,",
          s.query(CodeChange).count(), "changes")