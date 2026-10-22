# SECURITY & PRIVACY

_Status: APPROVED_

1. **Secrets** only in GitHub Secrets or `.env` (git-ignored). Never in `config.yaml`, logs,
   state, briefs or commit messages. Logs pass through a filter that masks emails and key
   patterns (`AIza…`, `sk-…`, `github_pat_…`, bot tokens).
2. **No phone-home**: the project never contacts any server of the author's. No analytics.
3. **Workflow hardening**: actions pinned by commit SHA; minimal `permissions:`; inputs passed
   as env vars (no script injection); `concurrency` so two runs never send twice.
4. **AI output is untrusted**: links in the email are only ones that came from the feeds
   (allow-list); no AI-invented URLs; HTML escaped.
5. **Docker**: non-root user, read-only app dir, only `/data` writable, no ports exposed.
6. **Public repo hygiene**: a test fails if any file contains the author's name, email,
   GitHub handle, or a known secret pattern (`tests/test_no_personal_data.py`).
7. **Dependencies** pinned to exact versions; Dependabot opens update PRs; CI must pass.
8. **Reporting**: `SECURITY.md` at repo root with a private contact method (GitHub Security
   Advisories), no email address published.
