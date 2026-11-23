from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repository"
    repo_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(Text)


class Developer(Base):
    __tablename__ = "developer"
    developer_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))


class Commit(Base):
    __tablename__ = "git_commit"
    commit_id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repository.repo_id"))
    developer_id: Mapped[int] = mapped_column(ForeignKey("developer.developer_id"))
    hash: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    committed_at: Mapped[datetime]
    is_fix: Mapped[bool]
    is_revert: Mapped[bool]


class File(Base):
    __tablename__ = "file"
    file_id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repository.repo_id"))
    path: Mapped[str] = mapped_column(Text)


class CodeChange(Base):
    __tablename__ = "code_change"
    change_id: Mapped[int] = mapped_column(primary_key=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("git_commit.commit_id"))
    file_id: Mapped[int] = mapped_column(ForeignKey("file.file_id"))
    lines_added: Mapped[int]
    lines_deleted: Mapped[int]
class Function(Base):
    __tablename__ = "code_function"
    function_id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("file.file_id"))
    name: Mapped[str] = mapped_column(String(200))
    created_commit_id: Mapped[int] = mapped_column(ForeignKey("git_commit.commit_id"))
    deleted_commit_id: Mapped[int | None] = mapped_column(ForeignKey("git_commit.commit_id"))


class FunctionChange(Base):
    __tablename__ = "function_change"
    change_id: Mapped[int] = mapped_column(primary_key=True)
    function_id: Mapped[int] = mapped_column(ForeignKey("code_function.function_id"))
    commit_id: Mapped[int] = mapped_column(ForeignKey("git_commit.commit_id"))
    change_type: Mapped[str] = mapped_column(String(20))  # created / modified / deleted


class CodeFossil(Base):
    __tablename__ = "code_fossil"
    fossil_id: Mapped[int] = mapped_column(primary_key=True)
    function_id: Mapped[int] = mapped_column(ForeignKey("code_function.function_id"))
    deleted_commit_id: Mapped[int] = mapped_column(ForeignKey("git_commit.commit_id"))
    last_code: Mapped[str] = mapped_column(Text)
    replacement_function_id: Mapped[int | None] = mapped_column(ForeignKey("code_function.function_id"))

engine = create_engine("sqlite:///repoforensics.db")
Session = sessionmaker(engine)


def init_db():
    Base.metadata.create_all(engine)