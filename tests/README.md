# JOBLASS Tests

## Structure

```
tests/
├── fixtures/                      # HTML snapshots for testing
│   └── glassdoor_job_search_page.html
├── test_database.py              # Database operations tests
├── test_deduplication.py         # Job deduplication tests
├── test_glassdoor.py            # Glassdoor scraper tests
└── test_modals.py               # Modal handling tests
```

## Test Files

### `test_glassdoor.py`
Tests for Glassdoor scraper extraction methods using **real Selenium WebDriver** with saved HTML fixtures.

**Test Classes:**
- `TestScraperMethods`: Tests utility methods (modal handling, etc.)
- `TestJobDataExtraction`: Tests extraction methods with real browser + HTML fixtures
- `TestValidation`: Tests Pydantic validation logic

**Fixtures:**
- `chrome_driver` (session-scoped): Real headless Chrome WebDriver
- `job_search_page_url`: file:// URL to HTML fixture
- `scraper_with_fixture_loaded`: GlassdoorScraper with HTML fixture loaded in real browser

**What Makes These Tests Valuable:**
- ✅ Use real Selenium WebDriver (headless Chrome)
- ✅ Load actual HTML fixtures into browser
- ✅ Test actual CSS selectors against real DOM
- ✅ Will fail if selectors break or HTML structure changes
- ✅ Validate complete extraction pipeline end-to-end

### `test_database.py`
Database operations and CRUD tests.

### `test_deduplication.py`
Tests for job posting deduplication logic.

### `test_modals.py`
Tests for modal detection and handling.

## Fixtures Directory

### `fixtures/glassdoor_job_search_page.html`
Saved HTML snapshot of a Glassdoor job search results page. Used for:
- Testing extraction methods without network calls
- Verifying HTML structure changes
- Developing new selectors

**Source:** Copy-pasted from browser "View Source" on:
- URL: https://www.glassdoor.fr/Emploi/paris-data-scientist-intern-emplois-...
- Date saved: 2025-11-02
- Search: "data scientist intern" in "Paris, Île-de-France"

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run specific test file
```bash
pytest tests/test_glassdoor.py -v
```

### Run with output (see print statements)
```bash
pytest tests/test_glassdoor.py -v -s
```

### Run specific test class
```bash
pytest tests/test_glassdoor.py::TestGlassdoorExtraction -v
```

### Run specific test method
```bash
pytest tests/test_glassdoor.py::TestGlassdoorExtraction::test_fixture_exists -v
```

### Run with coverage
```bash
pytest tests/ --cov=joblass --cov-report=html
```

## Test Categories

### Real Selenium Tests (Fixture-based)
- **Load HTML fixtures into real headless Chrome browser**
- Test extraction methods with actual CSS selectors
- Validate selectors work on real DOM structure
- Slower than mocks but much more reliable
- Example: `TestJobDataExtraction`
- **Why this matters:** Tests fail when selectors break (not just when method logic breaks)

### Utility Tests (Mock-based where needed)
- Test helper methods that don't require DOM
- Use mocks only when testing error conditions
- Example: `TestScraperMethods.test_close_modal_when_not_present`

### Validation Tests
- Test Pydantic model validation
- Ensure data quality and completeness
- Example: `TestValidation`

## Adding New Tests

### 1. Save a new HTML fixture
```bash
# In browser, go to page you want to test
# Right-click -> "View Page Source"
# Copy all HTML
# Save to tests/fixtures/descriptive_name.html
```

### 2. Create fixture URL in test file
```python
@pytest.fixture
def my_page_url():
    html_path = FIXTURES_DIR / "my_page.html"
    if not html_path.exists():
        pytest.skip(f"Test fixture not found: {html_path}")
    return f"file://{html_path.absolute()}"
```

### 3. Write test using real Selenium
```python
def test_extract_something(self, chrome_driver, my_page_url):
    # Load HTML into real browser
    chrome_driver.get(my_page_url)
    scraper = GlassdoorScraper(chrome_driver)

    # Call actual extraction method (tests real selectors!)
    result = scraper._extract_something()

    # Verify it extracted real data from the HTML
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0
```

## Development Workflow

1. **Save HTML fixture** from browser (View Source → Copy → Save as .html)
2. **Implement extraction** in scraper with CSS selectors
3. **Write test** that loads fixture in real browser and calls extraction method
4. **Run test** - it will fail if selectors don't work on real HTML
5. **Validate** extracted data with Pydantic model

## Notes

- **Real Selenium tests are slower** but catch actual selector bugs (worth the trade-off)
- HTML fixtures may become outdated when Glassdoor updates their UI
- Update fixtures periodically to match current site structure
- Use `data-test` attributes when available (more stable than CSS classes)
- Chrome runs in headless mode (no GUI) for CI/CD compatibility
- Session-scoped `chrome_driver` fixture reuses browser across tests for speed

## Why Real Selenium Instead of Mocks?

**Mocks test method behavior, not selector correctness:**
```python
# ❌ Mock test - passes even if selector is wrong
mock_element = Mock(text="Job Title")
mock_driver.find_element.return_value = mock_element
result = scraper._extract_job_title()  # Always passes
```

**Real Selenium tests actual extraction:**
```python
# ✅ Real test - fails if selector doesn't find element in HTML
chrome_driver.get(fixture_url)  # Load real HTML
result = scraper._extract_job_title()  # Uses real selector
# Fails if: selector wrong, HTML changed, element missing
```
