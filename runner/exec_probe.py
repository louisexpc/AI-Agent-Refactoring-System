from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import ArtifactRef, ExecMatrix, ExecResult, ExecScope


@dataclass
class ExecProbeRunner:
    repo_dir: Path
    logs_dir: Path
    coverage_dir: Path

    def run(self, matrix: ExecMatrix) -> ExecMatrix:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.coverage_dir.mkdir(parents=True, exist_ok=True)
        exec_scopes: list[ExecScope] = []

        for scope in matrix.scopes:
            scope_results: list[ExecResult] = []
            for candidate in scope.candidates:
                result = self._run_candidate(
                    scope.scope_id, candidate.cmd, candidate.candidate_id
                )
                scope_results.append(result)
            exec_scopes.append(
                ExecScope(
                    scope_id=scope.scope_id,
                    candidates=scope.candidates,
                    results=scope_results,
                )
            )

        return ExecMatrix(scopes=exec_scopes)

    def _run_candidate(self, scope_id: str, cmd: str, candidate_id: str) -> ExecResult:
        started = time.time()
        completed = subprocess.run(
            cmd,
            shell=True,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        duration_ms = int((time.time() - started) * 1000)
        stdout_tail = self._tail(completed.stdout)
        stderr_tail = self._tail(completed.stderr)
        log_path = self.logs_dir / f"{scope_id}-{candidate_id}.log"
        log_path.write_text(
            "\n".join(
                [
                    f"cmd: {cmd}",
                    f"exit_code: {completed.returncode}",
                    "--- stdout ---",
                    completed.stdout,
                    "--- stderr ---",
                    completed.stderr,
                ]
            ),
            encoding="utf-8",
        )

        artifacts: list[ArtifactRef] = []
        coverage_path = self.coverage_dir / "coverage.json"
        if coverage_path.exists():
            artifacts.append(
                ArtifactRef(
                    name="coverage",
                    path=str(coverage_path),
                    mime="application/json",
                    size=coverage_path.stat().st_size,
                )
            )

        return ExecResult(
            candidate_id=candidate_id,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            artifacts=artifacts,
        )

    @staticmethod
    def _tail(text: str, limit: int = 4000) -> str | None:
        if not text:
            return None
        if len(text) <= limit:
            return text
        return text[-limit:]
