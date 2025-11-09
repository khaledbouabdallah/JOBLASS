"""
Configuration loader for JOBLASS scoring system

Loads config from config/default/ and optionally overrides with config/user/
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from joblass.config import REPO_ROOT
from joblass.config.models import (
    JobLassConfig,
    ProfileConfig,
    RulesConfig,
    ScoringConfig,
)
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)

# Config directories
DEFAULT_CONFIG_DIR = REPO_ROOT / "config" / "default"
USER_CONFIG_DIR = REPO_ROOT / "config" / "user"


class ConfigLoadError(Exception):
    """Raised when config loading fails"""

    pass


def load_yaml_file(path: Path) -> dict:
    """
    Load YAML file and return as dictionary

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML data as dict

    Raises:
        ConfigLoadError: If file doesn't exist or YAML is invalid
    """
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data is None:
                return {}
            return data
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e
    except Exception as e:
        raise ConfigLoadError(f"Failed to read {path}: {e}") from e


def load_profile_config() -> ProfileConfig:
    """
    Load profile configuration from config/user/profile_template.yaml
    (falls back to default if user version doesn't exist)

    Returns:
        Validated ProfileConfig

    Raises:
        ConfigLoadError: If config is invalid or missing
    """
    # Check user config first
    user_profile = USER_CONFIG_DIR / "profile_template.yaml"
    default_profile = DEFAULT_CONFIG_DIR / "profile_template.yaml"

    if user_profile.exists():
        logger.info(f"Loading user profile config from {user_profile}")
        config_path = user_profile
    else:
        logger.info(f"Loading default profile config from {default_profile}")
        config_path = default_profile

    data = load_yaml_file(config_path)

    try:
        return ProfileConfig(**data)
    except ValidationError as e:
        raise ConfigLoadError(f"Invalid profile config in {config_path}:\n{e}") from e


def load_rules_config() -> Optional[RulesConfig]:
    """
    Load rules configuration from config/user/rules.yaml
    (falls back to default if user version doesn't exist)

    Returns:
        Validated RulesConfig or None if file doesn't exist

    Raises:
        ConfigLoadError: If config is invalid
    """
    # Check user config first
    user_rules = USER_CONFIG_DIR / "rules.yaml"
    default_rules = DEFAULT_CONFIG_DIR / "rules.yaml"

    if user_rules.exists():
        logger.info(f"Loading user rules config from {user_rules}")
        config_path = user_rules
    elif default_rules.exists():
        logger.info(f"Loading default rules config from {default_rules}")
        config_path = default_rules
    else:
        logger.info("No rules config found (optional)")
        return None

    data = load_yaml_file(config_path)

    try:
        return RulesConfig(**data)
    except ValidationError as e:
        raise ConfigLoadError(f"Invalid rules config in {config_path}:\n{e}") from e


def load_scoring_config() -> ScoringConfig:
    """
    Load scoring configuration from config/user/scoring.yaml
    (falls back to default if user version doesn't exist)

    Returns:
        Validated ScoringConfig

    Raises:
        ConfigLoadError: If config is invalid or missing
    """
    # Check user config first
    user_scoring = USER_CONFIG_DIR / "scoring.yaml"
    default_scoring = DEFAULT_CONFIG_DIR / "scoring.yaml"

    if user_scoring.exists():
        logger.info(f"Loading user scoring config from {user_scoring}")
        config_path = user_scoring
    else:
        logger.info(f"Loading default scoring config from {default_scoring}")
        config_path = default_scoring

    data = load_yaml_file(config_path)

    try:
        return ScoringConfig(**data)
    except ValidationError as e:
        raise ConfigLoadError(f"Invalid scoring config in {config_path}:\n{e}") from e


def load_config() -> JobLassConfig:
    """
    Load complete JOBLASS configuration

    Loads profile, rules (optional), and scoring configs
    User configs in config/user/ override defaults in config/default/

    Returns:
        Complete validated JobLassConfig

    Raises:
        ConfigLoadError: If any required config is invalid or missing
    """
    logger.info("Loading JOBLASS configuration")

    try:
        profile = load_profile_config()
        rules = load_rules_config()
        scoring = load_scoring_config()

        config = JobLassConfig(
            profile=profile,
            rules=rules,
            scoring=scoring,
        )

        logger.info(
            f"Configuration loaded successfully (mode: {profile.experience_level})"
        )
        return config

    except ConfigLoadError:
        raise
    except Exception as e:
        raise ConfigLoadError(f"Unexpected error loading config: {e}") from e


def validate_config_files() -> dict:
    """
    Validate all config files without creating full config object

    Returns:
        Dict with validation results for each file:
        {
            'profile': {'valid': bool, 'error': str or None, 'path': str},
            'rules': {...},
            'scoring': {...}
        }
    """
    results = {}

    # Validate profile
    user_profile = USER_CONFIG_DIR / "profile.yaml"
    default_profile = DEFAULT_CONFIG_DIR / "profile_template.yaml"
    profile_path = user_profile if user_profile.exists() else default_profile

    try:
        data = load_yaml_file(profile_path)
        ProfileConfig(**data)
        results["profile"] = {"valid": True, "error": None, "path": str(profile_path)}
    except Exception as e:
        results["profile"] = {
            "valid": False,
            "error": str(e),
            "path": str(profile_path),
        }

    # Validate rules (optional)
    user_rules = USER_CONFIG_DIR / "rules.yaml"
    default_rules = DEFAULT_CONFIG_DIR / "rules.yaml"
    if user_rules.exists():
        rules_path = user_rules
    elif default_rules.exists():
        rules_path = default_rules
    else:
        rules_path = None

    if rules_path:
        try:
            data = load_yaml_file(rules_path)
            RulesConfig(**data)
            results["rules"] = {"valid": True, "error": None, "path": str(rules_path)}
        except Exception as e:
            results["rules"] = {
                "valid": False,
                "error": str(e),
                "path": str(rules_path),
            }
    else:
        results["rules"] = {
            "valid": True,
            "error": None,
            "path": "Not found (optional)",
        }

    # Validate scoring
    user_scoring = USER_CONFIG_DIR / "scoring.yaml"
    default_scoring = DEFAULT_CONFIG_DIR / "scoring.yaml"
    scoring_path = user_scoring if user_scoring.exists() else default_scoring

    try:
        data = load_yaml_file(scoring_path)
        ScoringConfig(**data)
        results["scoring"] = {"valid": True, "error": None, "path": str(scoring_path)}
    except Exception as e:
        results["scoring"] = {
            "valid": False,
            "error": str(e),
            "path": str(scoring_path),
        }

    return results
