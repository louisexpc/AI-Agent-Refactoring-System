# Ingestion artifacts → schema mapping

## Artifact name → path

| Artifact name | Path |
| --- | --- |
| run_meta | artifacts/<run_id>/run_meta.json |
| repo_meta | artifacts/<run_id>/snapshot/repo_meta.json |
| repo_snapshot | artifacts/<run_id>/snapshot/repo.tar (or .tar.zst) |
| repo_index | artifacts/<run_id>/index/repo_index.json |
| scope_candidates | artifacts/<run_id>/index/scope_candidates.json |
| exec_matrix | artifacts/<run_id>/exec/exec_matrix.json |
| exec_probe_results | artifacts/<run_id>/exec/exec_probe_results.json |
| exec_probe_logs | artifacts/<run_id>/logs/exec_probe/*.log |
| coverage | artifacts/<run_id>/coverage/coverage.json |
| dep_graph_l0 | artifacts/<run_id>/depgraph/dep_graph_l0.json |
| db_assets_index | artifacts/<run_id>/data/db_assets_index.json |
| sql_inventory | artifacts/<run_id>/data/sql_inventory.json |
| evidence_index | artifacts/<run_id>/evidence/evidence_index.json |
| evidence_issues | artifacts/<run_id>/evidence/issues/*.json |
| evidence_prs | artifacts/<run_id>/evidence/prs/*.json |
| evidence_checks | artifacts/<run_id>/evidence/checks/*.json |

## Core run

- run_meta.json → RunRecord

## Snapshot

- snapshot/repo_meta.json → RepoMeta
- snapshot/repo.tar.zst → (binary)

## Indexing

- index/repo_index.json → RepoIndex (TBD)
- index/scope_candidates.json → ScopeCandidates (list[ScopeCandidate])

## Execution

- exec/exec_matrix.json → ExecMatrix
- exec/exec_probe_results.json → ExecMatrix/ExecResult (TBD)
- logs/exec_probe/*.log → (text)
- coverage/coverage.json → CoverageReport (external)

## Dependency graph

- depgraph/dep_graph_l0.json → DepGraphL0

## Data assets & SQL inventory

- data/db_assets_index.json → DbAssetsIndex
- data/sql_inventory.json → SqlInventory

## Evidence

- evidence/evidence_index.json → EvidenceIndex
- evidence/issues/*.json → EvidenceIssue (TBD)
- evidence/prs/*.json → EvidencePR (TBD)
- evidence/checks/*.json → EvidenceCheckRun (TBD)
