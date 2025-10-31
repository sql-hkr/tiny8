# Contributing to Tiny8

Thank you for your interest in contributing to Tiny8! This guide will help you get started with contributing to our educational 8-bit CPU simulator.

Whether you're fixing a bug, adding a feature, improving documentation, or creating new assembly examples, your contributions are welcome and appreciated.

## 🌟 Ways to Contribute

### 🐛 Bug Reports
- Search [existing issues](https://github.com/sql-hkr/tiny8/issues) first
- Provide a clear description and minimal reproduction steps
- Include your Python version and operating system
- Add relevant code snippets or assembly programs

### 💡 Feature Requests
- Open an issue describing the feature and its use case
- Discuss design decisions before implementing large changes
- Consider backward compatibility and educational value

### 📝 Documentation
- Fix typos and improve clarity
- Add more code examples
- Enhance API documentation
- Create tutorials or guides

### 🎓 Assembly Examples
- Create educational assembly programs
- Document algorithms and implementation details
- Add visualizations demonstrating key concepts

### 🧪 Testing
- Improve test coverage
- Add edge case tests
- Test on different platforms

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** (3.11, 3.12, or 3.13 recommended)
- **Git** for version control
- **uv** (optional but recommended) for fast package management

### Development Setup

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/tiny8.git
   cd tiny8
   ```

2. **Set up development environment:**

   Using `uv` (recommended):
   ```bash
   # Install uv if you haven't already
   # macOS/Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv sync
   ```

   Using standard `pip`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Verify your setup:**

   ```bash
   # Run tests
   pytest
   
   # Check linting
   ruff check .
   
   # Try the CLI
   tiny8 examples/fibonacci.asm
   ```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/tiny8 --cov-report=html

# Run specific test file
pytest tests/test_arithmetic.py

# Run specific test
pytest tests/test_arithmetic.py::test_add_basic

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Writing Tests

- Tests are located in the `tests/` directory
- Use `pytest` framework (configured in `pytest.ini`)
- Follow existing test patterns for consistency
- Test both success and failure cases
- Keep tests fast, focused, and deterministic

**Example test structure:**

```python
def test_feature_name():
    """Test description."""
    # Arrange
    cpu = CPU()
    cpu.load_program(...)
    
    # Act
    cpu.step()
    
    # Assert
    assert cpu.read_reg(16) == expected_value
```

## 🎨 Code Style

### Linting and Formatting

We use **ruff** for both linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .

# Check formatting without changing
ruff format . --check
```

### Style Guidelines

- **Type hints**: Use type annotations for function signatures
- **Docstrings**: Use Google-style docstrings for public APIs
- **Line length**: 88 characters (ruff default)
- **Imports**: Group stdlib, third-party, and local imports
- **Naming**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_CASE`
  - Private methods: `_leading_underscore`

**Example:**

```python
def execute_instruction(self, opcode: int, operands: list[int]) -> None:
    """Execute a single instruction.
    
    Args:
        opcode: The instruction opcode.
        operands: List of operand values.
        
    Raises:
        InvalidOpcodeError: If opcode is not recognized.
    """
    # Implementation
```

## 📚 Documentation

### Building Documentation

```bash
# Generate API documentation
sphinx-apidoc -efo docs/api/ src/

# Build HTML docs
cd docs
make html

# View docs
open _build/html/index.html  # macOS
# or
xdg-open _build/html/index.html  # Linux
# or
start _build/html/index.html  # Windows
```

### Documentation Guidelines

- Keep documentation synchronized with code changes
- Add docstrings to all public functions, classes, and modules
- Update `README.md` for user-facing changes
- Update `docs/index.rst` for significant features
- Include code examples in docstrings when helpful

## 🎯 Assembly Examples

### Creating Examples

1. Place assembly files in `examples/` directory
2. Use `.asm` extension
3. Include comprehensive comments
4. Start with a header comment explaining the algorithm

**Example template:**

```asm
; Algorithm Name
; Brief description of what this program does
; 
; Algorithm explanation:
; - Step 1 description
; - Step 2 description
;
; Registers used:
; - R16: Purpose
; - R17: Purpose
;
; Expected result: Description

    ldi r16, 0          ; Initialize
    ; ... your code
    
done:
    jmp done            ; Halt
```

### Example Best Practices

- **Educational value**: Demonstrate a clear concept
- **Comments**: Explain the "why", not just the "what"
- **Deterministic**: Use fixed inputs for reproducibility
- **Test coverage**: Add corresponding unit tests
- **Documentation**: Reference in README or docs if significant

## 🔄 Pull Request Process

### Before Submitting

1. **Create an issue** for non-trivial changes to discuss approach
2. **Branch from main**: Use descriptive branch names
   - `fix/short-description` for bug fixes
   - `feat/short-description` for features
   - `docs/short-description` for documentation
   - `test/short-description` for tests
3. **Make atomic commits** with clear messages
4. **Update tests** to cover your changes
5. **Run the full test suite** and linter
6. **Update documentation** if needed

### Commit Message Guidelines

Write clear, concise commit messages:

```
feat: add MUL instruction support

- Implement 8-bit multiplication
- Update instruction decoder
- Add comprehensive tests
- Update documentation

Closes #123
```

**Format:**
- First line: `<type>: <summary>` (50 chars max)
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`
- Body: Explain what and why (optional)
- Footer: Reference issues (optional)

### PR Checklist

Before submitting your PR, ensure:

- [ ] Code follows style guidelines (`ruff check` passes)
- [ ] All tests pass (`pytest` succeeds)
- [ ] New tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] Commit messages are clear and descriptive
- [ ] PR description explains changes and motivation
- [ ] Branch is up-to-date with main
- [ ] No unrelated changes included

## 🔍 Code Review Process

- Maintainers will review PRs within a few days
- Address feedback constructively
- Push additional commits to the same branch
- Request re-review after addressing comments

## 🌐 Community Guidelines

### Code of Conduct

- **Be respectful**: Treat everyone with respect and professionalism
- **Be welcoming**: Foster an inclusive environment for all contributors
- **Be collaborative**: Work together constructively
- **Be patient**: Remember we're all volunteers with varying experience levels

### Communication

- **Issues**: Use for bug reports, feature requests, and discussions
- **Pull Requests**: Use for code contributions
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Email**: For security issues only (see below)

## 🔒 Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email the maintainers directly (see `pyproject.toml` for contact info)
3. Provide detailed information about the vulnerability
4. Allow time for a fix before public disclosure

## 📄 License

By contributing to Tiny8, you agree that your contributions will be licensed under the [MIT License](LICENSE).

Your contributions will be attributed in the project's commit history and release notes.

## ❓ Questions?

- Check the [documentation](https://sql-hkr.github.io/tiny8/)
- Search [existing issues](https://github.com/sql-hkr/tiny8/issues)
- Open a new issue for discussion
- Join [GitHub Discussions](https://github.com/sql-hkr/tiny8/discussions)

## 🙏 Thank You!

Thank you for taking the time to contribute to Tiny8! Your efforts help make this project a better learning tool for everyone exploring computer architecture.

Every contribution, no matter how small, makes a difference. We appreciate your support! ⭐
