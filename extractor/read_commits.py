from git import Repo

repo = Repo(r"C:\Users\anush\practice_repo")

for c in repo.iter_commits():
    msg = c.message.strip().splitlines()[0]
    is_revert = msg.lower().startswith("revert")
    is_fix = "fix" in msg.lower()
    print(
        c.hexsha[:7],
        c.author.name,
        c.committed_datetime.date(),
        msg,
        list(c.stats.files.keys()),
        "REVERT" if is_revert else "",
        "FIX" if is_fix else "",
    )