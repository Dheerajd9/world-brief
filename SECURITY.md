# Security

Please report a vulnerability privately with GitHub: **Security → Report a vulnerability**
on this repository. Do not open a public issue for security problems.

Your keys stay yours: World Brief only reads them from GitHub Secrets or a local `.env`,
never writes them to files or logs, and never sends them anywhere except the service they
belong to (Google Gemini, Gmail, Telegram...). See [docs/SECURITY.md](docs/SECURITY.md).
