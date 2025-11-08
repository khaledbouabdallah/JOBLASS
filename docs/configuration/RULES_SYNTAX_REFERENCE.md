# Rules Syntax Quick Reference (Simplified)

## When Do You Need This?

**You probably don't.** The system has good defaults.

Only read this if you're creating `rules.yaml` for advanced customization.

## Rule Structure

Every rule has:

```yaml
- type: rule_type          # What kind of rule
  # ... type-specific fields
  penalty: -20             # For penalties (negative number)
  # OR
  bonus: 15                # For bonuses (positive number)
  reason: "Why applied"    # User-facing explanation
  enabled: true            # Can toggle on/off
```

## Rule Types

### 1. Keyword Rules

Match keywords in text fields.

```yaml
- type: keyword
  keywords:
    en: [word1, word2]     # English keywords
    fr: [mot1, mot2]       # French keywords (optional)
  penalty: -20             # Or bonus: 15
  reason: "Why this matters"
  enabled: true
```

**Example - Penalty:**
```yaml
- type: keyword
  keywords:
    en: [crypto, cryptocurrency, web3]
    fr: [crypto, cryptomonnaie]
  penalty: -25
  reason: Not interested in crypto positions
  enabled: true
```

**Example - Bonus:**
```yaml
- type: keyword
  keywords:
    en: [AI research, machine learning research]
    fr: [recherche IA]
  bonus: 20
  reason: Strong research focus
  enabled: true
```

### 2. Company Pattern Rules

Match company names with patterns (regex).

```yaml
- type: company_pattern
  pattern: "regex_pattern"
  penalty: -20
  reason: "Why avoid"
  enabled: true
```

**Example:**
```yaml
- type: company_pattern
  pattern: ".*consulting.*"      # Any company with "consulting"
  penalty: -30
  reason: Avoid consulting firms
  enabled: true
```

### 3. Salary Range Rules

Check if salary meets thresholds.

```yaml
- type: salary_range
  max_acceptable: 800        # Below this gets penalty
  penalty: -40
  reason: "Too low"
  enabled: true
```

**Example:**
```yaml
- type: salary_range
  max_acceptable: 800        # Monthly in EUR
  penalty: -50
  reason: Below minimum wage equivalent
  enabled: true
```

### 4. Experience Gap Rules

Penalize if job asks for too much experience.

```yaml
- type: experience_gap
  your_experience: 1         # Auto-filled from profile
  max_gap: 2                 # Tolerate up to 2 years more
  penalty: -20
  reason: "Too senior"
  enabled: true
```

**Example:**
```yaml
- type: experience_gap
  your_experience: 1         # Gets your years from profile
  max_gap: 1                 # Strict: only 1 year gap allowed
  penalty: -30
  reason: Experience requirement too high
  enabled: true
```

### 5. Rating Threshold Rules

Bonus for high company ratings.

```yaml
- type: rating_threshold
  min_rating: 4.5            # Glassdoor rating
  bonus: 15
  reason: "Excellent rating"
  enabled: true
```

**Example:**
```yaml
- type: rating_threshold
  min_rating: 4.7            # Very selective
  bonus: 20
  reason: Exceptional company rating
  enabled: true
```

### 6. Location Rules

Bonus for preferred locations.

```yaml
- type: location
  preferred_locations: [Paris, Lyon]
  bonus: 5
  reason: "In preferred city"
  enabled: true
```

**Example:**
```yaml
- type: location
  preferred_locations: [Paris, Lyon, Marseille]
  bonus: 8
  reason: In preferred French city
  enabled: true
```

## Reject Rules (Stricter)

Reject rules completely exclude jobs (not just penalties).

### Keyword Rejection

```yaml
reject_rules:
  - type: keyword
    keywords:
      en: [unpaid, no compensation, volunteer]
      fr: [non rémunéré, bénévole]
    reason: Unpaid position
    enabled: true
```

### Job Type Rejection

```yaml
reject_rules:
  - type: job_type
    reject_types: [contract, freelance, consultant]
    reason: Only looking for internship/full-time
    enabled: true
```

### Distance Rejection

```yaml
reject_rules:
  - type: distance
    max_distance_km: 100
    allow_remote: true         # Remote jobs bypass distance check
    reason: Too far from location
    enabled: true
```

## Complete Examples

### Example 1: Avoid Crypto & Sales

```yaml
custom_penalties:
  - type: keyword
    keywords:
      en: [crypto, cryptocurrency, blockchain, web3, NFT]
      fr: [crypto, cryptomonnaie, blockchain]
    penalty: -25
    reason: Not interested in crypto/web3
    enabled: true

  - type: keyword
    keywords:
      en: [sales, cold calling, business development, SDR]
      fr: [vente, prospection, développement commercial]
    penalty: -30
    reason: Not interested in sales roles
    enabled: true
```

### Example 2: Prefer Research

```yaml
custom_bonuses:
  - type: keyword
    keywords:
      en: [research, R&D, publications, academic, PhD]
      fr: [recherche, publications, académique, thèse]
    bonus: 20
    reason: Strong preference for research work
    enabled: true

  - type: keyword
    keywords:
      en: [open source, OSS, contribute to, github]
      fr: [open source, logiciel libre, contribuer]
    bonus: 12
    reason: Value open source culture
    enabled: true
```

### Example 3: Strict Requirements

```yaml
custom_penalties:
  - type: salary_range
    max_acceptable: 1200       # Higher minimum
    penalty: -40
    reason: Below acceptable compensation
    enabled: true

  - type: experience_gap
    your_experience: 1         # From profile
    max_gap: 1                 # Very strict
    penalty: -35
    reason: Experience requirement too high
    enabled: true

reject_rules:
  - type: keyword
    keywords:
      en: [unpaid, no salary, volunteer]
    reason: Unpaid positions not acceptable
    enabled: true
```

### Example 4: Startup Preference

```yaml
custom_bonuses:
  - type: keyword
    keywords:
      en: [startup, early stage, seed funded, Series A]
      fr: [startup, jeune pousse]
    bonus: 15
    reason: Prefer startup environment
    enabled: true

  - type: company_pattern
    pattern: ".*\\s(Inc|Ltd|GmbH)$"  # Not corporate
    penalty: -10
    reason: Prefer smaller companies
    enabled: false               # Can enable later
```

## Processing Options

Control how rules are applied:

```yaml
processing:
  stop_on_reject: true         # Stop after first rejection
  accumulate_penalties: true   # Apply all matching penalties
  accumulate_bonuses: true     # Apply all matching bonuses
  log_matches: true            # Log which rules triggered
```

## Tips

1. **Start simple** - Add one or two rules, test, iterate
2. **Test with explains** - `joblass explain <job_id>` shows which rules fired
3. **Enable/disable** - Toggle `enabled: false` to test without rules
4. **Reasonable penalties** - Don't make penalties too harsh (-50 is very harsh)
5. **Combine with profile** - Use `profile.yaml` custom_keywords for simple cases

## Common Patterns

### Block Consulting Firms

```yaml
custom_penalties:
  - type: company_pattern
    pattern: ".*(consulting|conseil).*"
    penalty: -30
    reason: Consulting firms
    enabled: true

  - type: keyword
    keywords:
      en: [client projects, consulting services]
      fr: [projets clients, prestations]
    penalty: -25
    reason: Consulting work detected
    enabled: true
```

### Boost for Good Culture

```yaml
custom_bonuses:
  - type: keyword
    keywords:
      en: [work-life balance, flexible hours, remote-first]
      fr: [équilibre vie pro, horaires flexibles]
    bonus: 10
    reason: Good work culture indicators
    enabled: true

  - type: rating_threshold
    min_rating: 4.5
    bonus: 15
    reason: High employee satisfaction
    enabled: true
```

### Strict Location

```yaml
reject_rules:
  - type: distance
    max_distance_km: 30        # Very close
    allow_remote: true         # Unless remote
    reason: Must be nearby or remote
    enabled: true
```

## Debugging

Check which rules are triggering:

```bash
# See all rules
joblass config show --rules

# Explain a specific job score
joblass explain 123

# Test with logging
joblass score --sample 5 --verbose
```

## Don't Overuse

**Remember:** The default rules work well for most people.

Only add custom rules when:
- You have specific preferences not covered
- You've tested defaults and need adjustment
- You know exactly what you want to change

Start simple, add complexity only when needed.

---

**Most users never create rules.yaml.** Use profile.yaml custom_keywords for basic customization.