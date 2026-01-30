from __future__ import annotations

import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shared.ingestion_types import RepoMeta


@dataclass
class SnapshotResult:
    """Snapshot 執行結果。

    Args:
        repo_dir: snapshot repo 的目錄。
        meta: RepoMeta 資訊。
        archive_path: snapshot archive 路徑（可為 None）。
    """

    repo_dir: Path
    meta: RepoMeta
    archive_path: Path | None


@dataclass
class Snapshotter:
    """負責 clone repo、固定 SHA、輸出 snapshot。

    Args:
        work_dir: snapshot 工作目錄。
    """

    work_dir: Path

    def run(
        self, repo_url: str, output_dir: Path, create_archive: bool = True
    ) -> SnapshotResult:
        """執行 snapshot 流程。

        Args:
            repo_url: git repo URL 或本機路徑。
            output_dir: snapshot repo 輸出目錄。
            create_archive: 是否建立 tar archive。

        Returns:
            `SnapshotResult`。
        """
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        clone_url = repo_url
        repo_path = Path(repo_url)
        if repo_path.exists():
            clone_url = f"file://{repo_path.resolve()}"

        self._git(["clone", "--depth", "1", clone_url, str(output_dir)])

        commit_sha = self._git_output(
            ["-C", str(output_dir), "rev-parse", "HEAD"]
        ).strip()
        default_branch = self._default_branch(output_dir)

        git_dir = output_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        file_count, total_bytes = self._count_files(output_dir)

        meta = RepoMeta(
            repo_url=repo_url,
            commit_sha=commit_sha,
            default_branch=default_branch,
            file_count=file_count,
            total_bytes=total_bytes,
            created_at=datetime.now(tz=UTC),
        )

        archive_path = None
        if create_archive:
            archive_path = output_dir.parent / "repo.tar"
            with tarfile.open(archive_path, "w") as tar:
                tar.add(output_dir, arcname="repo")

        return SnapshotResult(repo_dir=output_dir, meta=meta, archive_path=archive_path)

    def _git(self, args: list[str]) -> None:
        """執行 git 指令。

        Args:
            args: git 子命令參數。
        """
        subprocess.run(["git", *args], check=True)

    def _git_output(self, args: list[str]) -> str:
        """執行 git 指令並回傳 stdout。

        Args:
            args: git 子命令參數。

        Returns:
            stdout 文字。
        """
        result = subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        )
        return result.stdout

    def _default_branch(self, repo_dir: Path) -> str | None:
        """解析 default branch 名稱。

        Args:
            repo_dir: repo 工作目錄。

        Returns:
            default branch 名稱或 None。
        """
        try:
            head_ref = self._git_output(
                ["-C", str(repo_dir), "symbolic-ref", "refs/remotes/origin/HEAD"]
            ).strip()
        except subprocess.CalledProcessError:
            return None
        prefix = "refs/remotes/origin/"
        if head_ref.startswith(prefix):
            return head_ref[len(prefix) :]
        return None

    def _count_files(self, repo_dir: Path) -> tuple[int, int]:
        """統計檔案數與總大小。

        Args:
            repo_dir: repo 工作目錄。

        Returns:
            (file_count, total_bytes)。
        """
        file_count = 0
        total_bytes = 0
        for path in repo_dir.rglob("*"):
            if not path.is_file():
                continue
            file_count += 1
            total_bytes += path.stat().st_size
        return file_count, total_bytes
