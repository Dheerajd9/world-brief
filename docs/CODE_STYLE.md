# CODE STYLE

- Python 3.12, standard library first; dependencies pinned in `requirements.txt`.
- `ruff` (lint + format, line length 100) recommended before committing.
- Small functions with a one-line docstring saying *why*, not *what*.
- Every network call: timeout + hard wall-clock cap; never crash the run for one bad feed /
  one failed extra (Telegram, player) — log and continue; the email is the priority.
- No personal values in code: everything from `config.py` (typed dataclasses, validated).
- Prompts in `app/prompts/*.md`, placeholders `{LIKE_THIS}` filled from config.
- Log lines start with run minutes `[12m]`; no emails or secrets in logs.
- Commit messages: imperative, short; docs and README updated in the same commit.
