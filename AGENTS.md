# JOBLASS Agent Guidelines

## Build/Lint/Test Commands
- **Install**: `pip install -e .` (or `pip install -e ".[dev]"` for Jupyter)
- **Init DB**: `python3 -c "from joblass.db import init_db; init_db()"`
- **Run Tests**: `python3 tests/test_<module>.py` (individual) or `python3 -m pytest tests/` (all)
- **Run Workflow**: Import and execute in Python - see `examples/` directory
- **Lint**: No linters configured yet

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
- Repository pattern: All DB ops through `*Repository` classes (Job, Application, Score, SearchSession)
- Context managers for connections: `get_db_cursor()` handles commit/rollback
- Deduplication via URL (unique constraint) - each job URL is unique
- Jobs linked to SearchSession via `session_id` foreign key (ON DELETE SET NULL)
- JSON strings for complex fields (search_criteria, tech_stack, reviews_data, etc.)
- Use Pydantic models for validation before DB insertion

### Workflow Patterns
- **Orchestration layer**: `joblass/workflows/` coordinates scrapers (don't add workflow logic to scrapers)
- **Session tracking**: All workflows create SearchSession with status tracking (in_progress/completed/failed)
- **Save at end**: Scrape jobs first, save to DB after (separation of concerns)
- **Statistics**: Track jobs_found, jobs_scraped, jobs_saved, jobs_skipped in session
- **Filter exposure**: `workflow.get_available_filters()` exposes dynamic options for CLI/webapp

### Documentation
- Docstrings with Args/Returns sections for public methods
- TODO comments for future work
- No inline comments unless complex logic requires explanation

## Copilot Instructions
See `.github/copilot-instructions.md` for detailed project overview, architecture, and workflow patterns.