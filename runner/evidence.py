from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.ingestion_types import EvidenceIndex, EvidenceRef


@dataclass
class GitHubEvidenceFetcher:
    artifacts_dir: Path

    def fetch(self, repo_url: str) -> EvidenceIndex:
        repo = _parse_github_repo(repo_url)
        if not repo:
            return EvidenceIndex()

        owner, name = repo
        issues = self._fetch_issues(owner, name)
        prs, checks = self._fetch_prs_and_checks(owner, name)
        return EvidenceIndex(issues=issues, prs=prs, checks=checks)

    def _fetch_issues(self, owner: str, name: str) -> list[EvidenceRef]:
        issues_dir = self.artifacts_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        issues_data = self._get_json(
            f"https://api.github.com/repos/{owner}/{name}/issues?state=all&per_page=30"
        )
        if not isinstance(issues_data, list):
            return []
        refs: list[EvidenceRef] = []
        for issue in issues_data:
            if "pull_request" in issue:
                continue
            number = issue.get("number")
            if number is None:
                continue
            comments = self._get_json(
                f"https://api.github.com/repos/{owner}/{name}/issues/{number}/comments"
            )
            payload = {"issue": issue, "comments": comments}
            filename = f"issue_{number}.json"
            path = issues_dir / filename
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            refs.append(EvidenceRef(name=f"issue-{number}", path=str(path)))
        return refs

    def _fetch_prs_and_checks(
        self, owner: str, name: str
    ) -> tuple[list[EvidenceRef], list[EvidenceRef]]:
        prs_dir = self.artifacts_dir / "prs"
        checks_dir = self.artifacts_dir / "checks"
        prs_dir.mkdir(parents=True, exist_ok=True)
        checks_dir.mkdir(parents=True, exist_ok=True)

        prs_data = self._get_json(
            f"https://api.github.com/repos/{owner}/{name}/pulls?state=all&per_page=10"
        )
        if not isinstance(prs_data, list):
            return [], []

        pr_refs: list[EvidenceRef] = []
        check_refs: list[EvidenceRef] = []
        for pr in prs_data:
            number = pr.get("number")
            if number is None:
                continue
            reviews = self._get_json(
                f"https://api.github.com/repos/{owner}/{name}/pulls/{number}/reviews"
            )
            comments = self._get_json(
                f"https://api.github.com/repos/{owner}/{name}/pulls/{number}/comments"
            )
            files = self._get_json(
                f"https://api.github.com/repos/{owner}/{name}/pulls/{number}/files"
            )
            payload = {
                "pull": pr,
                "reviews": reviews,
                "comments": comments,
                "files": files,
            }
            pr_filename = f"pr_{number}.json"
            pr_path = prs_dir / pr_filename
            pr_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            pr_refs.append(EvidenceRef(name=f"pr-{number}", path=str(pr_path)))

            head_sha = pr.get("head", {}).get("sha")
            if head_sha:
                checks = self._get_json(
                    f"https://api.github.com/repos/{owner}/{name}/commits/{head_sha}/check-runs"
                )
                check_payload = {"head_sha": head_sha, "checks": checks}
                check_filename = f"checks_{number}.json"
                check_path = checks_dir / check_filename
                check_path.write_text(
                    json.dumps(check_payload, indent=2), encoding="utf-8"
                )
                check_refs.append(
                    EvidenceRef(name=f"checks-{number}", path=str(check_path))
                )

        return pr_refs, check_refs

    @staticmethod
    def _get_json(url: str) -> Any:
        request = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []


def _parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    if repo_url.startswith("git@github.com:"):
        repo_url = repo_url.replace("git@github.com:", "https://github.com/")
    if repo_url.startswith("https://github.com/"):
        parsed = urllib.parse.urlparse(repo_url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            owner = parts[0]
            name = parts[1].removesuffix(".git")
            return owner, name
    return None
