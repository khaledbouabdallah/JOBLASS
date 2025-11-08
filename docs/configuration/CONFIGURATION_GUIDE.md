# JOBLASS Configuration Guide (Simplified)

## Quick Start

1. Copy `profile.yaml.template` to `profile.yaml`
2. Fill in your info (takes 5 minutes)
3. Start searching

That's it. Everything else uses smart defaults.

## Configuration Files

### Required: `profile.yaml`

Your personal information and requirements.

```yaml
# What level are you at?
experience_level: internship  # internship, entry_level, mid_level, senior
years_experience: 1

# Your skills
skills:
  known:              # Skills you have
    - python
    - pytorch
  want_to_learn:      # Skills you want to develop
    - rust
    - kubernetes

# Hard requirements (jobs not meeting these are rejected)
requirements:
  min_monthly_salary: 1000
  currency: EUR
  locations:
    - Paris
    - Remote
  company_blacklist:
    - Capgemini
```

**That's the minimum.** Everything else is optional.

### Optional: `scoring.yaml`

Only create this if you want to override default scoring weights.

```yaml
# Override default weights for your mode
custom_weights:
  tech_match: 0.40          # Increase from default 0.30
  learning_potential: 0.25  # Increase from default 0.20
  compensation: 0.10        # Decrease from default 0.15
  company_quality: 0.25
```

Most users never create this file.

### Optional: `rules.yaml`

Advanced customization for power users.

```yaml
# Add custom penalty rules
custom_penalties:
  - type: keyword
    keywords:
      en: [crypto, web3]
    penalty: -20
    reason: Not interested in crypto

# Add custom bonus rules
custom_bonuses:
  - type: keyword
    keywords:
      en: [AI research]
    bonus: 20
    reason: Strong research focus
```

Most users never create this file either.

## How It Works

### 1. You Fill Profile

The only required file. Contains:
- Your experience level (auto-selects scoring mode)
- Your skills (known + want to learn)
- Hard requirements (salary, location, blacklist)
- Optional preferences

### 2. System Uses Defaults

Everything else has sensible defaults:

**Default scoring weights** (varies by mode):
- Internship: Learning 30%, Tech 30%, Company 25%, Salary 15%
- Entry-level: Tech 32%, Company 28%, Learning 22%, Salary 18%
- Mid-level: Tech 35%, Company 30%, Salary 25%, Practical 10%
- Senior: Salary 30%, Tech 28%, Company 25%, Impact 17%

**Default penalties** (automatic):
- Buzzwords (rockstar, ninja): -15 pts
- Consulting keywords: -25 pts
- Vague description: -10 pts
- Experience gap >3 years: -20 pts
- Poor rating <3.0: -15 pts

**Default bonuses** (automatic):
- Research keywords: +15 pts
- Mentorship mentioned: +12 pts
- High rating >4.5: +15 pts
- Open source: +10 pts
- Remote first: +10 pts

### 3. You Override If Needed

Don't like the defaults? Create `scoring.yaml` or `rules.yaml` to customize.

## Scoring Modes Explained

Your `experience_level` in profile.yaml automatically selects a mode:

### Internship Mode
**Focus:** Learning over compensation
- Learning potential: 20%
- Tech match: 30%
- Company quality: 25%
- Compensation: 15%
- Conversion potential: 10%

**Extra bonuses for:**
- Mentorship programs
- Training budgets
- CDI/full-time conversion mentioned

### Entry Level Mode
**Focus:** Balance of learning and fair pay
- Tech match: 32%
- Company quality: 28%
- Compensation: 22%
- Learning potential: 12%
- Career growth: 6%

### Mid Level Mode
**Focus:** Balanced professional scoring
- Tech match: 35%
- Company quality: 30%
- Compensation: 25%
- Practical factors: 10%

### Senior Mode
**Focus:** Compensation and impact
- Compensation: 30%
- Tech match: 28%
- Company quality: 25%
- Impact potential: 12%
- Team leadership: 5%

## Custom Keywords

Add in `profile.yaml` without creating extra files:

```yaml
# In profile.yaml
custom_keywords:
  penalties:
    - keyword: crypto
      points: -20
      reason: Not interested in crypto/web3

  bonuses:
    - keyword: research
      points: 15
      reason: Interested in research positions
```

This is simpler than creating `rules.yaml` for basic customization.

## Examples

### Minimal Config (Most Users)

```yaml
# profile.yaml
experience_level: internship
years_experience: 1

skills:
  known: [python, pytorch]
  want_to_learn: [rust]

requirements:
  min_monthly_salary: 1000
  currency: EUR
  locations: [Paris, Remote]
```

Uses all defaults. Ready to search.

### With Custom Keywords

```yaml
# profile.yaml
experience_level: internship
years_experience: 1

skills:
  known: [python, pytorch]
  want_to_learn: [rust]

requirements:
  min_monthly_salary: 1000
  currency: EUR
  locations: [Paris, Remote]

custom_keywords:
  penalties:
    - keyword: sales
      points: -30
  bonuses:
    - keyword: research
      points: 20
```

Still just one file, custom scoring.

### With Custom Weights

```yaml
# profile.yaml (same as above)
# ...

# scoring.yaml (create only if needed)
custom_weights:
  tech_match: 0.40
  learning_potential: 0.30
  company_quality: 0.20
  compensation: 0.10
```

Override default weights for your mode.

### Power User

```yaml
# profile.yaml (basic config)
# scoring.yaml (custom weights)
# rules.yaml (advanced rules)

custom_penalties:
  - type: keyword
    keywords:
      en: [consulting, staffing]
      fr: [conseil, prestation]
    penalty: -30
    reason: Avoid consulting firms

  - type: experience_gap
    max_gap: 1
    penalty: -30
    reason: Strict experience matching

reject_rules:
  - type: keyword
    keywords:
      en: [unpaid, volunteer]
    reason: Unpaid positions not acceptable
```

Full control when you need it.

## Field Reference

### profile.yaml

```yaml
experience_level: string        # Required: internship, entry_level, mid_level, senior
years_experience: int           # Required: your years of experience

skills:
  known: list[string]           # Required: skills you have
  want_to_learn: list[string]   # Optional: skills you want to develop

requirements:
  min_monthly_salary: int       # Required: minimum acceptable
  currency: string              # Required: EUR, USD, etc.
  locations: list[string]       # Required: acceptable locations
  max_distance_km: int          # Optional: default 50
  company_blacklist: list[str]  # Optional: companies to reject

preferences:                    # All optional
  target_salary: int
  work_arrangement: list        # [remote, hybrid, onsite]
  company:
    min_rating: float           # Glassdoor rating
    preferred_size: [min, max]  # Employee count
    avoid_consulting: bool
  internship:                   # Only for internship mode
    require_mentorship: bool
    prefer_conversion: bool

custom_keywords:                # Optional
  penalties:
    - keyword: string
      points: int (negative)
      reason: string
  bonuses:
    - keyword: string
      points: int (positive)
      reason: string

location:                       # For distance calculations
  city: string
  coordinates: [lat, lon]

languages: list[string]         # Default: [en, fr]
```

### scoring.yaml (optional)

```yaml
custom_weights:                 # Override mode defaults
  tech_match: float             # Must sum to 1.0
  company_quality: float
  compensation: float
  # ... other dimensions based on mode

tech_matching:
  known_skills_weight: float    # Default: 0.6
  learning_skills_weight: float # Default: 0.4
  min_overlap_ratio: float      # Default: 0.2

missing_salary:
  strategy: string              # neutral, penalty, skip
  neutral_score: float          # Default: 0.5

rating_tiers:
  excellent: float              # Default: 4.5
  good: float                   # Default: 4.0
  acceptable: float             # Default: 3.5

penalties:                      # Override default amounts
  buzzwords: int
  consulting_detected: int
  # ... etc

bonuses:                        # Override default amounts
  research_keywords: int
  mentorship_mentioned: int
  # ... etc

max_penalty: int                # Default: -50
max_bonus: int                  # Default: 40
```

### rules.yaml (optional, advanced)

```yaml
custom_penalties:
  - type: keyword | company_pattern | salary_range | experience_gap
    # ... type-specific fields
    penalty: int (negative)
    reason: string
    enabled: bool

custom_bonuses:
  - type: keyword | rating_threshold | location
    # ... type-specific fields
    bonus: int (positive)
    reason: string
    enabled: bool

reject_rules:                   # Stricter than penalties
  - type: keyword | job_type | distance
    # ... type-specific fields
    reason: string
    enabled: bool

processing:
  stop_on_reject: bool
  accumulate_penalties: bool
  accumulate_bonuses: bool
  log_matches: bool
```

## Validation

Check your config:

```bash
joblass config validate
```

See what mode and weights are active:

```bash
joblass config show
```

Test with sample job:

```bash
joblass score --sample 1 --explain
```

## Tips

1. **Start minimal** - Just fill profile.yaml essentials
2. **Test defaults** - Run a search, see if results make sense
3. **Iterate** - Adjust weights only if scores feel wrong
4. **Don't overthink** - Default penalties/bonuses work for most people

## Common Questions

**Q: Do I need all three files?**
A: No, just `profile.yaml`. Others are optional.

**Q: How do I know what mode I'm in?**
A: Run `joblass config show` - it shows your active mode and weights.

**Q: Can I change weights per dimension?**
A: Yes, create `scoring.yaml` with `custom_weights` section.

**Q: What if I want to reject certain companies?**
A: Add them to `requirements.company_blacklist` in profile.yaml.

**Q: Can I add my own penalty keywords?**
A: Yes, use `custom_keywords.penalties` in profile.yaml for simple cases, or `rules.yaml` for complex rules.

**Q: How do I see why a job scored X?**
A: `joblass explain <job_id>` shows complete breakdown.

## Migration from Old Config

If you have the original 5-file system:

```bash
# Extract essentials into new format
joblass config migrate
```

Or manually:
1. Copy skills from old user_profile.yaml → profile.yaml
2. Copy salary/location → profile.yaml requirements
3. Copy blacklist → profile.yaml requirements
4. Done - use defaults for everything else

## Need More Help?

- Examples: `examples/` directory
- Rule syntax: See rules.yaml comments
- Default values: Run `joblass config show --defaults`

---

**Remember:** Simple config = happy users. Fill in profile.yaml and start searching.