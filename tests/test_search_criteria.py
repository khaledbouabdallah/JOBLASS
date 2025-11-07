"""
SearchCriteria Filter Conversion Tests

Tests the conversion of SearchCriteria to ExtraFilters format.
Critical for ensuring filters are passed correctly to the scraper.
"""

from joblass.db.models import SearchCriteria


def test_to_filters_dict_handles_all_filter_types():
    """Verify all filter types converted correctly"""
    criteria = SearchCriteria(
        job_title="Engineer",  # Basic field - should be excluded
        location="Paris",  # Basic field - should be excluded
        preferred_location="Île-de-France",  # Basic field - should be excluded
        is_easy_apply=True,  # Toggle - should be included
        salary_min=30000,  # Range - convert to tuple
        salary_max=50000,
        date_posted="7 jours",  # Advanced - included as-is
        job_type="Stage",  # Advanced - included as-is
        company_rating="+3",  # Advanced - included as-is
        is_remote=False,  # Toggle False - should be excluded
    )

    filters = criteria.to_filters_dict()

    # Basic fields excluded
    assert "job_title" not in filters, "Basic field job_title should be excluded"
    assert "location" not in filters, "Basic field location should be excluded"
    assert (
        "preferred_location" not in filters
    ), "Basic field preferred_location should be excluded"

    # Toggles included when True
    assert filters["is_easy_apply"] is True, "Toggle should be included when True"
    assert "is_remote" not in filters, "Toggle False should be excluded"

    # Salary range converted to tuple
    assert filters["salary_range"] == (
        30000,
        50000,
    ), "Salary range should be tuple (min, max)"

    # Advanced filters included
    assert filters["date_posted"] == "7 jours", "date_posted should be included"
    assert filters["job_type"] == "Stage", "job_type should be included"
    assert filters["company_rating"] == "+3", "company_rating should be included"

    print("✓ All filter types converted correctly")


def test_to_filters_dict_handles_partial_salary():
    """Handle edge case: only min or max salary set"""
    # Only salary_min set - should NOT be included (partial range)
    criteria1 = SearchCriteria(
        job_title="Dev",
        location="Lyon",
        salary_min=40000,
        # salary_max not set
    )

    filters1 = criteria1.to_filters_dict()
    assert (
        "salary_range" not in filters1
    ), "Partial salary (only min) should be excluded"

    # Only salary_max set - should NOT be included (partial range)
    criteria2 = SearchCriteria(
        job_title="Dev",
        location="Lyon",
        salary_max=60000,
        # salary_min not set
    )

    filters2 = criteria2.to_filters_dict()
    assert (
        "salary_range" not in filters2
    ), "Partial salary (only max) should be excluded"

    print("✓ Partial salary ranges handled correctly")


def test_to_filters_dict_handles_all_none():
    """Should return empty dict when no advanced filters set"""
    criteria = SearchCriteria(
        job_title="Software Engineer",
        location="Paris",
        # No advanced filters
    )

    filters = criteria.to_filters_dict()

    assert filters == {}, "No advanced filters should return empty dict"

    print("✓ Empty filters handled correctly")


def test_to_filters_dict_excludes_none_values():
    """None values should not appear in filters dict"""
    criteria = SearchCriteria(
        job_title="Data Scientist",
        location="Toulouse",
        is_easy_apply=True,
        date_posted=None,  # Explicitly None
        job_type=None,  # Explicitly None
        company_rating=None,  # Explicitly None
    )

    filters = criteria.to_filters_dict()

    assert filters == {
        "is_easy_apply": True
    }, "Only non-None filters should be included"
    assert "date_posted" not in filters
    assert "job_type" not in filters
    assert "company_rating" not in filters

    print("✓ None values excluded correctly")


def test_to_filters_dict_with_all_toggles():
    """Test all toggle combinations"""
    criteria = SearchCriteria(
        job_title="DevOps",
        location="Nice",
        is_easy_apply=True,
        is_remote=True,
    )

    filters = criteria.to_filters_dict()

    assert filters["is_easy_apply"] is True
    assert filters["is_remote"] is True
    assert len(filters) == 2, "Should have exactly 2 toggle filters"

    print("✓ All toggles handled correctly")


def test_to_filters_dict_complex_scenario():
    """Test realistic complex filter scenario"""
    criteria = SearchCriteria(
        job_title="Machine Learning Engineer",
        location="Paris",
        preferred_location="Île-de-France",
        is_easy_apply=True,
        is_remote=True,
        salary_min=50000,
        salary_max=80000,
        date_posted="7 jours",
        job_type="Temps plein",
        company_rating="+4",
    )

    filters = criteria.to_filters_dict()

    expected_filters = {
        "is_easy_apply": True,
        "is_remote": True,
        "salary_range": (50000, 80000),
        "date_posted": "7 jours",
        "job_type": "Temps plein",
        "company_rating": "+4",
    }

    assert filters == expected_filters, f"Expected {expected_filters}, got {filters}"

    print("✓ Complex filter scenario handled correctly")


def test_from_json_to_filters_dict_roundtrip():
    """Verify serialization/deserialization preserves filter conversion"""
    original_criteria = SearchCriteria(
        job_title="Backend Developer",
        location="Lyon",
        is_easy_apply=True,
        salary_min=40000,
        salary_max=60000,
        date_posted="3 jours",
    )

    # Convert to JSON and back
    json_str = original_criteria.to_json()
    restored_criteria = SearchCriteria.from_json(json_str)

    # Both should produce same filters dict
    original_filters = original_criteria.to_filters_dict()
    restored_filters = restored_criteria.to_filters_dict()

    assert (
        original_filters == restored_filters
    ), "Filters should be preserved after JSON roundtrip"

    print("✓ JSON roundtrip preserves filter conversion")


if __name__ == "__main__":
    print("=" * 70)
    print("SEARCHCRITERIA FILTER CONVERSION TESTS")
    print("=" * 70)

    test_to_filters_dict_handles_all_filter_types()
    print()

    test_to_filters_dict_handles_partial_salary()
    print()

    test_to_filters_dict_handles_all_none()
    print()

    test_to_filters_dict_excludes_none_values()
    print()

    test_to_filters_dict_with_all_toggles()
    print()

    test_to_filters_dict_complex_scenario()
    print()

    test_from_json_to_filters_dict_roundtrip()
    print()

    print("=" * 70)
    print("✅ ALL SEARCHCRITERIA FILTER CONVERSION TESTS PASSED!")
    print("=" * 70)
