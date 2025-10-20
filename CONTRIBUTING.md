# Contributing to tiny8

Thank you for your interest in contributing to tiny8 — a compact AVR-like 8-bit CPU simulator and examples. This short guide explains how to get the project running locally, how to run tests and examples, the code style we prefer, and what to include when submitting a pull request.

## Quick setup

```bash
git clone https://github.com/sql-hkr/tiny8.git
cd tiny8
uv venv
source .venv/bin/activate
uv sync
```

> [!TIP]
> [uv](https://docs.astral.sh/uv/) is an extremely fast Python package and project manager, written in Rust. To install it, run:
>
> ```bash
> # On macOS and Linux.
> curl -LsSf https://astral.sh/uv/install.sh | sh
>
> # On Windows.
> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
> ```

This flow sets up a development virtual environment, installs development requirements, and prepares the project for local editing and testing.

## Running examples

Examples live in the `examples/` directory. Run an example like:

```bash
uv run examples/fibonacci.py
```

> [!IMPORTANT]
> You will need `ffmpeg` installed on your system to generate a GIF or MP4 file.

### Tests

- Tests live in the `tests/` folder. Add unit tests for any bug fixes or new features.
- Use Python's built-in `unittest` framework for new tests. Keep tests small, fast and deterministic when possible.
- Aim for coverage of edge cases and error paths for logic changes.

### Linting & formatting

- We use `ruff` for linting and auto-fixes. Run:

    ```bash
    ruff check .
    ruff format .
    ```

- When fixing/implementing code, make sure lint errors are resolved or justified in your PR.

## Documentation

Docs are generated from the `docs/` directory. To build the HTML docs locally:

```bash
sphinx-apidoc -efo docs/api/ src/
make -C docs html
open docs/_build/html/index.html
```

### Pull Request process

1. Open an issue first for non-trivial changes (design or API changes) so maintainers can provide feedback before you invest time.
2. Work on a topic branch (not `main`). Use a descriptive branch name: `fix/short-desc`, `feat/short-desc`, or `doc/short-desc`.
3. Commit messages should be short and descriptive. If your changes are a bug fix or feature, reference the issue number if one exists.
4. Include or update tests that cover your changes.
5. Run the test suite, linter, and build the docs locally before opening the PR.
6. In the PR description include:
   - What the change does and why
   - Any notable design decisions or trade-offs
   - How to run tests/examples to verify the change

### PR checklist

- [ ] Branched from current `main`
- [ ] Tests added/updated
- [ ] Linting passes (`ruff`) and formatting applied
- [ ] Documentation updated (if applicable)
- [ ] Clear PR description and linked issue (if any)


## Adding examples

- Place assembly programs under `examples/` and a small runner script if needed.
- Keep examples deterministic (fixed inputs) unless you document why randomness is used.
- If an example adds new instructions or behavior, add tests under `tests/`.

## Code of conduct

Be respectful and professional. Follow common community standards when discussing issues and reviewing contributions.

## Reporting security issues

If you discover a security vulnerability, please contact the maintainers directly (see `pyproject.toml` author email) instead of creating a public issue.

## License

By contributing you agree that your contributions will be licensed under the project's MIT License.

## Need help?

Open an issue describing what you'd like to do, or reach out via the author email in `pyproject.toml`.

Thank you for helping improve Tiny8!