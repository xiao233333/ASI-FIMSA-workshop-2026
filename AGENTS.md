# ASI_FIMSA_workshop

A self-contained subproject of the `analysis_project` tree. The tree-wide conventions in
`../AGENTS.md` (PROJECT_CONTEXT.md, layout, Bunya workflow) apply here too; this file records
only what is specific to this repo.

## Agent skills

### Issue tracker

Issues and PRDs live as **GitHub issues on this repo's own remote**, managed via the `gh` CLI — a separate queue from the parent tree's `xiao233333/analysis_projects`. No remote exists yet, so `gh` will fail until one is added. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root, both created lazily by `/domain-modeling`. See `docs/agents/domain.md`.
