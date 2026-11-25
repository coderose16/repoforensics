import os
import sys

from db.models import Session
from extractor.load_commits import load_commits
from analysis.tracker import track_functions
from analysis.fossil import find_fossils

DB_FILE = "repoforensics.db"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <path to a git repo>")
        sys.exit(1)

    repo_path = sys.argv[1]
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)  # start fresh; close the .db viewer tab first

    repo_id = load_commits(repo_path)
    track_functions(repo_path, repo_id)

    with Session() as s:
        find_fossils(s, repo_id)
        s.commit()
    print("Fossil search done.")