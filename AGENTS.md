# JOBLASS Agent Guidelines

## Build/Lint/Test Commands
- **Install**: `pip install -e .` (or `pip install -e ".[dev]"` for Jupyter)
- **Init DB**: `python3 -c "from joblass.db import init_db; init_db()"`
- **Run**: Import and execute directly in Python (no CLI yet)
- **Test**: No test suite yet - manual testing only
- **Lint**: No linters configured

## Code Style Guidelines

### Imports & Structure
- Use absolute imports only: `from joblass.utils.logger import setup_logger`
- Import control singleton: `from joblass.utils.control import control`
- Setup logger at module level: `logger = setup_logger(__name__)`

### Types & Naming
- Python 3.10+ type hints required
- snake_case for functions/variables, PascalCase for classes
- Use dataclasses for data models with `__post_init__` validation
- Optional fields use `Optional[T]` with sensible defaults

### Selenium Patterns
- Always use helpers: `wait_for_element()`, `human_click()`, `human_type()`
- Check control before actions: `control.wait_if_paused()` and `control.check_should_stop()`
- Human-like delays: `human_delay()` between all interactions
- Log interactions: `logger.debug()` for element actions, `logger.info()` for progress

### Error Handling
- Catch `InterruptedError` for user stops (not an error - return False)
- Use try/except with `logger.error(f"Action failed: {e}", exc_info=True)`
- Database operations: Check `JobRepository.exists(url)` before inserting
- Foreign keys enabled: `PRAGMA foreign_keys = ON`

### Database Patterns
- Repository pattern: All DB ops through `*Repository` classes
- Context managers for connections: `get_db_cursor()` handles commit/rollback
- Unique URL constraint on jobs table for deduplication
- JSON strings for complex fields (tech_stack, penalties, etc.)

### Documentation
- Docstrings with Args/Returns sections for public methods
- TODO comments for future work
- No inline comments unless complex logic requires explanation

## Copilot Instructions
See `.github/copilot-instructions.md` for detailed project overview, architecture, and workflow patterns.