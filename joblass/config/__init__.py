"""
JOBLASS Configuration Module

Path constants and configuration loaders
"""

import os
from pathlib import Path

# This file is at: repo_root/joblass/config/__init__.py
# JOBLASS_ROOT should be: repo_root/joblass/
# REPO_ROOT should be: repo_root/
JOBLASS_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)  # Go up to joblass/
REPO_ROOT: Path = Path(os.path.dirname(JOBLASS_ROOT))  # Go up to repo root
CHROME_PROFILE_DIR: str = os.path.join(REPO_ROOT, "chrome_user_data")

# Import config models and loaders
# These imports must come after path constants are defined (loader.py uses REPO_ROOT)
from joblass.config.loader import (  # noqa: E402
    ConfigLoadError,
    load_config,
    load_profile_config,
    load_rules_config,
    load_scoring_config,
    validate_config_files,
)
from joblass.config.models import (  # noqa: E402
    BonusesConfig,
    CompanyPatternRule,
    CompanyPreferences,
    CustomKeywords,
    DistanceRejectRule,
    ExperienceGapRule,
    InternshipPreferences,
    JobLassConfig,
    JobTypeRejectRule,
    KeywordBonusRule,
    KeywordPenaltyRule,
    KeywordRejectRule,
    KeywordRule,
    LocationBonusRule,
    LocationConfig,
    MissingSalaryConfig,
    ModesConfig,
    PenaltiesConfig,
    PreferencesConfig,
    ProcessingOptions,
    ProfileConfig,
    RatingThresholdRule,
    RatingTiersConfig,
    RequirementsConfig,
    RulesConfig,
    SalaryRangeRule,
    ScoringConfig,
    ScoringModeWeights,
    SkillsConfig,
    TechMatchingConfig,
)

__all__ = [
    # Path constants
    "JOBLASS_ROOT",
    "REPO_ROOT",
    "CHROME_PROFILE_DIR",
    # Config loader
    "load_config",
    "load_profile_config",
    "load_rules_config",
    "load_scoring_config",
    "validate_config_files",
    "ConfigLoadError",
    # Main config models
    "JobLassConfig",
    "ProfileConfig",
    "RulesConfig",
    "ScoringConfig",
    # Profile models
    "SkillsConfig",
    "RequirementsConfig",
    "PreferencesConfig",
    "CompanyPreferences",
    "InternshipPreferences",
    "CustomKeywords",
    "KeywordRule",
    "LocationConfig",
    # Rules models
    "KeywordPenaltyRule",
    "CompanyPatternRule",
    "SalaryRangeRule",
    "ExperienceGapRule",
    "KeywordBonusRule",
    "RatingThresholdRule",
    "LocationBonusRule",
    "KeywordRejectRule",
    "JobTypeRejectRule",
    "DistanceRejectRule",
    "ProcessingOptions",
    # Scoring models
    "ScoringModeWeights",
    "ModesConfig",
    "TechMatchingConfig",
    "MissingSalaryConfig",
    "RatingTiersConfig",
    "PenaltiesConfig",
    "BonusesConfig",
]
