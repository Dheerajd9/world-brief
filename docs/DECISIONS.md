# DECISIONS (ADR log)

| # | Decision | Why | Status |
|---|---|---|---|
| D1 | New public repo `world-brief`; personal repo unchanged | no personal history/state leaks; personal runs keep working | accepted |
| D2 | Two ways: GitHub template + Docker | template = free & zero install; Docker = private/self-host | accepted |
| D3 | Everything personal → `config.yaml`; secrets only in Secrets/.env | anyone, anywhere can use it | accepted |
| D4 | Feed packs per country + world pack | focus changes without editing code | accepted |
| D5 | Prompts with placeholders from config | sections follow the user's country/city | accepted |
| D6 | Keep the proven safety nets (time caps, backup AI, one email, watchdog, fast dedupe) | learned from the personal edition | accepted |
| D7 | No server/telemetry of ours | free, private, nothing to maintain | accepted |
| D8 | MIT license | simplest for reuse | accepted |
| D9 | Portfolio + AI Digest excluded | personal, finance-specific | accepted |
| D10 | Default = whole world, no country targeted; optional countries/cities in the wizard (suggestions given) | readers anywhere; focus is opt-in | accepted |
| D11 | English first; Telugu & Hindi optional extra podcast languages, more on request | simplest default, keeps proven prompts | accepted |
| D12 | Podcast site on its own `podcast` branch (never the code branch) | the site branch is force-replaced each day | accepted |
| D13 | One complete email (waits for the podcast up to 2 h) | readers want one message, not two | accepted |
