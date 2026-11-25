# RepoForensics

**An intelligent Git archaeologist for code evolution and lost context recovery.**

Git remembers every change, but only as raw commits and diffs. RepoForensics mines a repository's history, stores it in a relational database, and turns it into answers: which functions were created, changed or deleted, which files are risky, who really owns each file, and what code was thrown away. Every finding links back to the commits that prove it.

Built for the 24CSE57 Societal Based Mini Project, Dept. of CSE, New Horizon College of Engineering. The societal angle: public and open-source software outlives its authors, and this tool helps whoever inherits it understand why it looks the way it does.

## What it does

| Page | What you get |
|---|---|
| **Home** | Commit count, fix commits, revert commits, full commit table |
| **Timeline** | Pick any function and see its life: created, modified, deleted, with commit, author and date |
| **Risk** | Every file scored 0 to 100 and labelled HIGH, MED or LOW |
| **Fossils** | Deleted functions, their last known code, and a likely replacement if one exists |
| **Ownership** | Who started each file, who maintains it now, and whether ownership has drifted |

**Risk score** = change count (40%) + fix commits (30%) + reverts (15%) + contributors (15%).
A *fix commit* is one whose message contains the word "fix". A *revert* is a commit whose message starts with "Revert".

**Code fossil** = a function that existed at some point and was later deleted. RepoForensics recovers its old source from the commit just before the deletion.

## How it works

```
Git repository
      |
      v
Extractor (GitPython)  ->  commits, authors, files, line changes
      |
      v
Database (SQLAlchemy / SQLite)
      |
      v
Analysis engines
  tracker    parses each commit's Python files with the ast module
             and records function created / modified / deleted events
  risk       scores and labels files
  fossil     recovers deleted functions and looks for replacements
  ownership  original author vs. recent top contributor
      |
      v
Streamlit dashboard
```

## Setup

You need Python 3.11 or newer and Git.

```bash
git clone https://github.com/coderose16/repoforensics.git
cd repoforensics
python -m venv venv
```

Activate the virtual environment:

- Windows (PowerShell): `venv\Scripts\Activate.ps1`
- Mac / Linux: `source venv/bin/activate`

If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Then install the packages:

```bash
pip install gitpython sqlalchemy streamlit pytest
```

## Run it

Analyse any local Git repository:

```bash
python analyze.py <path to a git repo>
```

For example, `python analyze.py C:\Users\you\some_project`. This loads the commits, tracks the functions and searches for fossils.

Then open the dashboard:

```bash
streamlit run dashboard/app.py
```

Notes:

- `analyze.py` deletes and recreates `repoforensics.db` every time, so each run starts fresh. Close any database viewer first, or Windows will refuse to delete the file.
- Run it on a repo with a few hundred commits. The tracker reads every Python file at every commit, so very large histories take a while.
- Only `.py` files are tracked at function level.

## Tests

```bash
python -m pytest
```

## Project structure

```
analyze.py              one command: load, track functions, find fossils
extractor/
  load_commits.py       reads Git history into the database
analysis/
  tracker.py            function-level history using the ast module
  ownership.py          original vs. current owner per file
  risk.py               risk scores and HIGH / MED / LOW labels
  fossil.py             deleted-function recovery
dashboard/
  app.py                home page
  pages/                Timeline, Risk, Fossils, Ownership
db/
  models.py             database tables
tests/                  pytest tests for tracker, risk and fossils
```

## Database tables

`repository`, `developer`, `git_commit`, `file`, `code_change`, `code_function`, `function_change`, `code_fossil`

The schema is defined with SQLAlchemy, so it can be moved from SQLite to PostgreSQL by changing the connection string in `db/models.py`.

## Known limitations

- A **renamed function** appears as one deleted function and one new function.
- **Merge commits** are compared against their first parent only, so a function that arrives through a merge can show up as created again.
- A property **getter and setter with the same name** are tracked as one function.
- Bug fixes are found by keyword in commit messages, so a fix with an unhelpful message is missed.
- Function-level tracking works for **Python files only**.
- The risk score is an indicator based on history, not proof that code is buggy.

## Team

| | Parts built |
|---|---|
| **Anushka Sahoo** (1NZ24CS024) | Git extractor, function tracker, ownership analysis, Timeline and Ownership pages, `analyze.py` |
| **Chelsi Jain** (1NZ24CS046) | Risk scoring, fossil finder, Home, Risk and Fossils pages, tests for risk and fossils |

Work was done on separate branches and merged through pull requests, so the commit history shows who built what.
