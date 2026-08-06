# Contributing to Storage Analyzer

Thank you for your interest in contributing to Storage Analyzer! This document provides guidelines and information for contributors.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/Dragon-01-you/storage-analyzer/issues)
2. If not, create a new issue using the [Bug Report template](https://github.com/Dragon-01-you/storage-analyzer/issues/new?template=bug_report.md)
3. Include as much detail as possible: OS, Python version, steps to reproduce

### Suggesting Features

1. Check if the feature has already been suggested in [Issues](https://github.com/Dragon-01-you/storage-analyzer/issues)
2. If not, create a new issue using the [Feature Request template](https://github.com/Dragon-01-you/storage-analyzer/issues/new?template=feature_request.md)
3. Explain why this feature would be useful

### Submitting Code

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Add tests if applicable
5. Run tests: `python -m pytest tests/ -v`
6. Commit your changes: `git commit -m "Add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a Pull Request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Dragon-01-you/storage-analyzer.git
cd storage-analyzer

# Install dependencies
pip install pydantic psutil pytest

# Run tests
python -m pytest tests/ -v

# Run the tool
python run.py --confidence
```

## Adding a New Cleaner

1. Create a new file in `cleaners/` (e.g., `_my_app.py`)
2. Define a Cleaner subclass:

```python
from ._base import Cleaner, Entry, ScanContext

class MyAppCleaner(Cleaner):
    name = "my-app-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "My App cache files"

    def analyze(self, ctx: ScanContext) -> list[Entry]:
        # Your scanning logic here
        return []
```

3. Register in `cleaners/__init__.py`:

```python
from ._my_app import MY_APP_CLEANERS

REGISTRY = [
    # ... existing cleaners ...
    *MY_APP_CLEANERS,
]
```

## Code Style

- Follow PEP 8
- Use type hints where possible
- Add docstrings for public functions
- Keep functions small and focused

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_v8.py -v

# Run with coverage
python -m pytest tests/ -v --cov=v8
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
