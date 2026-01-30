from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import (
    ExecCandidate,
    ExecCandidateKind,
    ExecMatrix,
    ExecScope,
    ScopeCandidate,
)


@dataclass
class ExecMatrixBuilder:
    coverage_dir: Path

    def build(self, scopes: list[ScopeCandidate]) -> ExecMatrix:
        exec_scopes: list[ExecScope] = []

        for scope in scopes:
            candidates: list[ExecCandidate] = []
            scope_id = scope.scope_id
            language = (scope.language or "").lower()

            if language in {"python", "multi"}:
                candidates.extend(self._python_candidates(scope_id))

            if language in {"node", "multi"}:
                candidates.extend(self._node_candidates(scope_id))

            if not candidates:
                candidates.append(
                    ExecCandidate(
                        candidate_id=f"{scope_id}-test-0",
                        scope_id=scope_id,
                        kind=ExecCandidateKind.TEST,
                        cmd="echo 'no test candidates detected'",
                        priority=0,
                        tooling=None,
                    )
                )

            exec_scopes.append(ExecScope(scope_id=scope_id, candidates=candidates))

        return ExecMatrix(scopes=exec_scopes)

    def _python_candidates(self, scope_id: str) -> list[ExecCandidate]:
        coverage_path = self.coverage_dir / "coverage.json"
        return [
            ExecCandidate(
                candidate_id=f"{scope_id}-install-0",
                scope_id=scope_id,
                kind=ExecCandidateKind.INSTALL,
                cmd="python -m pip install -e .",
                priority=10,
                tooling="pip",
            ),
            ExecCandidate(
                candidate_id=f"{scope_id}-test-0",
                scope_id=scope_id,
                kind=ExecCandidateKind.TEST,
                cmd="python -m pytest -q",
                priority=10,
                tooling="pytest",
            ),
            ExecCandidate(
                candidate_id=f"{scope_id}-coverage-0",
                scope_id=scope_id,
                kind=ExecCandidateKind.COVERAGE,
                cmd=f"coverage run -m pytest && coverage json -o '{coverage_path}'",
                priority=20,
                tooling="coverage",
            ),
        ]

    def _node_candidates(self, scope_id: str) -> list[ExecCandidate]:
        return [
            ExecCandidate(
                candidate_id=f"{scope_id}-install-1",
                scope_id=scope_id,
                kind=ExecCandidateKind.INSTALL,
                cmd="npm ci",
                priority=10,
                tooling="npm",
            ),
            ExecCandidate(
                candidate_id=f"{scope_id}-test-1",
                scope_id=scope_id,
                kind=ExecCandidateKind.TEST,
                cmd="npm test",
                priority=10,
                tooling="npm",
            ),
            ExecCandidate(
                candidate_id=f"{scope_id}-coverage-1",
                scope_id=scope_id,
                kind=ExecCandidateKind.COVERAGE,
                cmd="npm test -- --coverage",
                priority=20,
                tooling="npm",
            ),
        ]
