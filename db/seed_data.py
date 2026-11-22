import random
from datetime import datetime, timedelta

from db.models import (Base, CodeChange, Commit, Developer, File,
                       Repository, Session, engine)

random.seed(42)  # same fake data every run


def seed():
    # wipe and rebuild tables so the script can be re-run safely
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session() as session:
        repo = Repository(name="demo-shop", path="fake/demo-shop")
        devs = [
            Developer(name="Asha", email="asha@example.com"),
            Developer(name="Ravi", email="ravi@example.com"),
            Developer(name="Meera", email="meera@example.com"),
        ]
        paths = [
            "app/main.py", "app/auth.py", "app/cart.py", "app/payment.py",
            "app/orders.py", "app/utils.py", "app/search.py",
            "app/config.py", "tests/test_cart.py", "README.md",
        ]
        files = [File(repo_id=1, path=p) for p in paths]
        session.add(repo)
        session.add_all(devs)
        session.flush()  # gives repo and devs their IDs
        for f in files:
            f.repo_id = repo.repo_id
        session.add_all(files)
        session.flush()

        start = datetime(2026, 9, 1, 10, 0)
        # first 4 files are "hot": they get changed more often
        weights = [4, 5, 4, 5, 2, 1, 1, 1, 1, 1]

        for i in range(40):
            kind = random.choices(["normal", "fix", "revert"],
                                  weights=[65, 25, 10])[0]
            msg = {
                "normal": f"Add feature {i}",
                "fix": f"Fix bug in module {i}",
                "revert": f"Revert change {i}",
            }[kind]
            commit = Commit(
                repo_id=repo.repo_id,
                developer_id=random.choice(devs).developer_id,
                hash="%040x" % random.getrandbits(160),
                message=msg,
                committed_at=start + timedelta(days=i // 2, hours=i),
                is_fix=(kind == "fix"),
                is_revert=(kind == "revert"),
            )
            session.add(commit)
            session.flush()

            touched = set()
            for f in random.choices(files, weights=weights,
                                    k=random.randint(1, 3)):
                touched.add(f)
            for f in touched:
                session.add(CodeChange(
                    commit_id=commit.commit_id,
                    file_id=f.file_id,
                    lines_added=random.randint(1, 60),
                    lines_deleted=random.randint(0, 30),
                ))

        session.commit()
        print("Seeded: 3 developers, 10 files, 40 commits")


if __name__ == "__main__":
    seed()