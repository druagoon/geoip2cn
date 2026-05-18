# Repository Guidelines

## Project Structure & Module Organization

The repository is a small Python utility centered on a layered GeoIP pipeline:

- `main.py`: unified orchestrator that combines providers, rules, and renderer output.
- `providers/`: provider-specific database download and record normalization logic.
- `rules/`: blacklist and whitelist matching rules.
- `services/`: extraction services that combine providers with rules.
- `services/pipeline.py`: default application assembly that wires extraction jobs to the renderer.
- `renderers/`: output formatting and file rendering, currently nftables only.
- `templates/`: Jinja2 templates, including `templates/nftables.conf`.
- `db/`: local MaxMindDB input databases used by the providers.
- `outputs/`: generated renderer outputs, including `outputs/nftables.conf`.
- `.github/workflows/geoip2cn.yaml`: scheduled GitHub Actions job that runs the extractor.

Keep new logic in focused Python modules instead of expanding workflow logic or shell scripts.

## Build, Test, and Development Commands

Use `uv` and the provided `Makefile` targets:

- `make init`: install Python 3.12 if needed, create `.venv`, and sync dependencies.
- `make dev`: install development tooling and pre-commit hooks.
- `make run`: execute `main.py`. Requires `IPINFO_TOKEN` and `CITY_WHITELIST`; supports optional `ASN_DENYLIST`; whitelist values should match the country, province, and city names stored in the ip2region database for the target region.
- `make lint`: run `black --check`, `isort --check-only`, and `ruff check`.
- `make test`: run the pytest suite under `tests/`.
- `make fmt`: format imports and code, then apply safe Ruff fixes.
- `make fmt-toml`: format TOML files with `taplo`.

Example:

```sh
export IPINFO_TOKEN=your_token
export ASN_DENYLIST=AS4134,AS4811
export CITY_WHITELIST='CN|上海|上海市'
make init && make run
```

## Coding Style & Naming Conventions

Target Python 3.12. Use 4-space indentation and keep lines within 120 characters. Black formats code, isort orders imports, and Ruff handles linting. Prefer `snake_case` for functions, variables, and filenames. Keep constants uppercase when module constants are needed. Write small, direct functions and keep provider, rule, service, and renderer responsibilities separate.

## Testing Guidelines

Use `make test` for the current pytest suite and `make lint` for static validation. For behavior changes, run `make run` with valid `IPINFO_TOKEN` and `CITY_WHITELIST` values, plus `ASN_DENYLIST` when testing blacklist behavior, and verify the rendered `outputs/nftables.conf` output. Keep tests under `tests/test_*.py` using `pytest`, and keep fixtures small.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit style, for example `feat: update ASN` and `fix: update cron schedule for GeoIP2CN workflow`. Continue using prefixes like `feat:`, `fix:`, `chore:`, and keep titles imperative and concise.

Pull requests should include a short summary, the reason for the change, validation steps run locally, and sample affected paths when output files change. Link related issues when applicable. Screenshots are unnecessary unless a workflow UI problem is being discussed.

## Security & Configuration Tips

Do not commit `IPINFO_TOKEN` or other secrets. Provide credentials through environment variables or GitHub Actions secrets only. Avoid manually editing generated files in `data/` unless the change is part of verified output regeneration.
