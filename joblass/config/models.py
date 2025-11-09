"""
Pydantic models for scoring configuration validation

Validates YAML config files from config/default/ and config/user/
"""

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

# ============================================================================
# Profile Configuration Models
# ============================================================================


class SkillsConfig(BaseModel):
    """User's skills configuration"""

    known: List[str] = Field(default_factory=list, description="Skills already known")
    want_to_learn: List[str] = Field(
        default_factory=list, description="Skills to learn"
    )

    @field_validator("known", "want_to_learn")
    @classmethod
    def validate_skills_not_empty_strings(cls, v: List[str]) -> List[str]:
        """Ensure no empty strings in skill lists"""
        return [skill.strip() for skill in v if skill.strip()]


class RequirementsConfig(BaseModel):
    """Hard requirements for job filtering"""

    min_monthly_salary: float = Field(ge=0, description="Minimum salary requirement")
    currency: str = Field(default="EUR", description="Salary currency")
    locations: List[str] = Field(default_factory=list, description="Accepted locations")
    max_distance_km: Optional[float] = Field(
        default=None, ge=0, description="Maximum distance in km"
    )
    company_blacklist: List[str] = Field(
        default_factory=list, description="Companies to reject"
    )


class InternshipPreferences(BaseModel):
    """Preferences specific to internships"""

    require_mentorship: bool = Field(default=False)
    prefer_conversion: bool = Field(
        default=False, description="Prefer jobs with conversion potential"
    )


class CompanyPreferences(BaseModel):
    """Company-related preferences"""

    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    preferred_size: Optional[List[int]] = Field(
        default=None, description="[min, max] employee count"
    )
    avoid_consulting: bool = Field(default=False)

    @field_validator("preferred_size")
    @classmethod
    def validate_size_range(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """Ensure size range has exactly 2 elements and min < max"""
        if v is None:
            return v
        if len(v) != 2:
            raise ValueError("preferred_size must have exactly 2 elements [min, max]")
        if v[0] > v[1]:
            raise ValueError("preferred_size min must be <= max")
        return v


class PreferencesConfig(BaseModel):
    """User preferences (not hard requirements)"""

    target_salary: Optional[float] = Field(default=None, ge=0)
    work_arrangement: List[Literal["remote", "hybrid", "onsite"]] = Field(
        default=["remote", "hybrid", "onsite"]
    )
    company: CompanyPreferences = Field(default_factory=CompanyPreferences)
    internship: InternshipPreferences = Field(default_factory=InternshipPreferences)


class KeywordRule(BaseModel):
    """Custom keyword with scoring adjustment"""

    keyword: str = Field(min_length=1)
    points: float
    reason: Optional[str] = None


class CustomKeywords(BaseModel):
    """Custom keywords for scoring adjustments"""

    penalties: List[KeywordRule] = Field(default_factory=list)
    bonuses: List[KeywordRule] = Field(default_factory=list)


class LocationConfig(BaseModel):
    """User location information"""

    city: str
    coordinates: Tuple[float, float] = Field(description="[latitude, longitude]")

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        """Validate latitude and longitude ranges"""
        lat, lon = v
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")
        return v


class ProfileConfig(BaseModel):
    """Complete user profile configuration"""

    experience_level: Literal["internship", "entry_level", "mid_level", "senior"]
    years_experience: float = Field(ge=0)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    requirements: RequirementsConfig
    preferences: PreferencesConfig = Field(default_factory=PreferencesConfig)
    custom_keywords: Optional[CustomKeywords] = None
    location: LocationConfig
    languages: List[str] = Field(default=["en"])


# ============================================================================
# Rules Configuration Models
# ============================================================================


class KeywordPenaltyRule(BaseModel):
    """Keyword-based penalty rule"""

    type: Literal["keyword"] = "keyword"
    keywords: Dict[str, List[str]] = Field(
        description="Keywords by language (e.g., {'en': [...], 'fr': [...]})"
    )
    penalty: float = Field(lt=0, description="Negative points to apply")
    reason: str
    enabled: bool = Field(default=True)


class CompanyPatternRule(BaseModel):
    """Company name pattern matching rule"""

    type: Literal["company_pattern"] = "company_pattern"
    pattern: str = Field(description="Regex pattern for company name")
    penalty: float = Field(lt=0)
    reason: str
    enabled: bool = Field(default=True)


class SalaryRangeRule(BaseModel):
    """Salary-based penalty rule"""

    type: Literal["salary_range"] = "salary_range"
    max_acceptable: float = Field(ge=0)
    penalty: float = Field(lt=0)
    reason: str
    enabled: bool = Field(default=True)


class ExperienceGapRule(BaseModel):
    """Experience mismatch penalty rule"""

    type: Literal["experience_gap"] = "experience_gap"
    your_experience: float = Field(ge=0)
    max_gap: float = Field(ge=0)
    penalty: float = Field(lt=0)
    reason: str
    enabled: bool = Field(default=True)


class KeywordBonusRule(BaseModel):
    """Keyword-based bonus rule"""

    type: Literal["keyword"] = "keyword"
    keywords: Dict[str, List[str]]
    bonus: float = Field(gt=0, description="Positive points to apply")
    reason: str
    enabled: bool = Field(default=True)


class RatingThresholdRule(BaseModel):
    """Company rating bonus rule"""

    type: Literal["rating_threshold"] = "rating_threshold"
    min_rating: float = Field(ge=0, le=5)
    bonus: float = Field(gt=0)
    reason: str
    enabled: bool = Field(default=True)


class LocationBonusRule(BaseModel):
    """Location-based bonus rule"""

    type: Literal["location"] = "location"
    preferred_locations: List[str]
    bonus: float = Field(gt=0)
    reason: str
    enabled: bool = Field(default=True)


class KeywordRejectRule(BaseModel):
    """Keyword-based rejection rule"""

    type: Literal["keyword"] = "keyword"
    keywords: Dict[str, List[str]]
    reason: str
    enabled: bool = Field(default=True)


class JobTypeRejectRule(BaseModel):
    """Job type rejection rule"""

    type: Literal["job_type"] = "job_type"
    reject_types: List[str]
    reason: str
    enabled: bool = Field(default=True)


class DistanceRejectRule(BaseModel):
    """Distance-based rejection rule"""

    type: Literal["distance"] = "distance"
    max_distance_km: float = Field(gt=0)
    allow_remote: bool = Field(default=True)
    reason: str
    enabled: bool = Field(default=True)


class ProcessingOptions(BaseModel):
    """Rule processing configuration"""

    stop_on_reject: bool = Field(default=True)
    accumulate_penalties: bool = Field(default=True)
    accumulate_bonuses: bool = Field(default=True)
    log_matches: bool = Field(default=True)


class RulesConfig(BaseModel):
    """Advanced custom rules configuration"""

    custom_penalties: List[
        KeywordPenaltyRule | CompanyPatternRule | SalaryRangeRule | ExperienceGapRule
    ] = Field(default_factory=list)
    custom_bonuses: List[KeywordBonusRule | RatingThresholdRule | LocationBonusRule] = (
        Field(default_factory=list)
    )
    reject_rules: List[KeywordRejectRule | JobTypeRejectRule | DistanceRejectRule] = (
        Field(default_factory=list)
    )
    processing: ProcessingOptions = Field(default_factory=ProcessingOptions)


# ============================================================================
# Scoring Configuration Models
# ============================================================================


class ScoringModeWeights(BaseModel):
    """Weight configuration for a scoring mode"""

    tech_match: float = Field(ge=0, le=1)
    company_quality: float = Field(ge=0, le=1)
    compensation: Optional[float] = Field(default=None, ge=0, le=1)
    learning_potential: Optional[float] = Field(default=None, ge=0, le=1)
    conversion_potential: Optional[float] = Field(default=None, ge=0, le=1)
    career_growth: Optional[float] = Field(default=None, ge=0, le=1)
    practical_factors: Optional[float] = Field(default=None, ge=0, le=1)
    impact_potential: Optional[float] = Field(default=None, ge=0, le=1)
    team_leadership: Optional[float] = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> "ScoringModeWeights":
        """Ensure weights sum to 1.0"""
        # Collect all non-None weights
        weights = [
            getattr(self, field)
            for field in self.model_fields.keys()
            if getattr(self, field) is not None
        ]
        total = sum(weights)
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        return self


class ModesConfig(BaseModel):
    """Scoring modes for different experience levels"""

    internship: ScoringModeWeights
    entry_level: ScoringModeWeights
    mid_level: ScoringModeWeights
    senior: ScoringModeWeights


class TechMatchingConfig(BaseModel):
    """Tech stack matching parameters"""

    known_skills_weight: float = Field(ge=0, le=1)
    learning_skills_weight: float = Field(ge=0, le=1)
    min_overlap_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "TechMatchingConfig":
        """Ensure skill weights sum to 1.0"""
        total = self.known_skills_weight + self.learning_skills_weight
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"known_skills_weight + learning_skills_weight must sum to 1.0, got {total:.4f}"
            )
        return self


class MissingSalaryConfig(BaseModel):
    """How to handle missing salary data"""

    strategy: Literal["neutral", "penalty", "skip"] = "neutral"
    neutral_score: float = Field(default=0.5, ge=0, le=1)


class RatingTiersConfig(BaseModel):
    """Company rating thresholds"""

    excellent: float = Field(ge=0, le=5)
    good: float = Field(ge=0, le=5)
    acceptable: float = Field(ge=0, le=5)

    @model_validator(mode="after")
    def validate_tier_order(self) -> "RatingTiersConfig":
        """Ensure excellent > good > acceptable"""
        if not (self.excellent > self.good > self.acceptable):
            raise ValueError(
                "Rating tiers must be in descending order: excellent > good > acceptable"
            )
        return self


class PenaltiesConfig(BaseModel):
    """Automatic penalty values"""

    buzzwords: float = Field(le=0)
    vague_description: float = Field(le=0)
    experience_mismatch: float = Field(le=0)
    poor_rating: float = Field(le=0)
    consulting_detected: float = Field(le=0)


class BonusesConfig(BaseModel):
    """Automatic bonus values"""

    research_keywords: float = Field(ge=0)
    mentorship_mentioned: float = Field(ge=0)
    high_rating: float = Field(ge=0)
    open_source: float = Field(ge=0)
    remote_first: float = Field(ge=0)


class ScoringConfig(BaseModel):
    """Complete scoring configuration"""

    modes: ModesConfig
    custom_weights: Optional[ScoringModeWeights] = None
    tech_matching: TechMatchingConfig
    missing_salary: MissingSalaryConfig = Field(default_factory=MissingSalaryConfig)
    rating_tiers: RatingTiersConfig
    penalties: PenaltiesConfig
    bonuses: BonusesConfig
    max_penalty: float = Field(le=0)
    max_bonus: float = Field(ge=0)


# ============================================================================
# Complete Configuration Container
# ============================================================================


class JobLassConfig(BaseModel):
    """Complete JOBLASS configuration with all components"""

    profile: ProfileConfig
    rules: Optional[RulesConfig] = None
    scoring: ScoringConfig

    @model_validator(mode="after")
    def sync_profile_to_rules(self) -> "JobLassConfig":
        """Sync profile.years_experience to rules.custom_penalties.experience_gap"""
        if self.rules is None:
            return self

        # Update experience_gap rules with profile experience
        for penalty in self.rules.custom_penalties:
            if isinstance(penalty, ExperienceGapRule):
                penalty.your_experience = self.profile.years_experience

        return self
