![Header](./assets/images/github-header-banner.png)

> Too lazy to click 500 times, too smart to auto-apply

**JOBLASS** is a job search automation tool that scrapes, filters, and ranks positions so you can focus on applying to jobs that actually matter.

## The Problem

The hiring process is fundamentally broken and nobody wants to admit it.

Companies use ATS systems that auto-reject candidates based on keyword matching. HR departments post job descriptions written by people who've never done the job. Recruiters demand 5 years of experience for entry-level positions. Your CV gets filtered by an algorithm before a human ever sees it.

Meanwhile you're expected to:
- Manually browse through hundreds of identical job posts
- Research every company like you're writing a thesis
- Craft personalized cover letters that nobody reads
- Apply through broken portals that lose your information
- Wait weeks for auto-generated rejection emails

They automated their side. Time to automate yours.

## Why This Exists

JOBLASS automates the boring parts: scraping, filtering, organizing, tracking. You stay in control of the actual decisions.

## What It Does

1. Scrapes job postings from Glassdoor (other sources may be added later) with a visible browser, you control it.
2. Filters out obvious garbage (consulting firms, unpaid internships, "rockstar" descriptions)
3. Analyzes jobs with LLM (extracts tech stack, spots red flags, gauges quality)
4. Ranks by customizable criteria (tech match, learning opportunity, company quality)
5. Stores everything locally in SQLite (your data, your control)
6. Tracks applications (applied, rejected, interview)
7. Optionally generates motivation letters

## What It Doesn't Do

- Auto-apply (risky, sends bad applications)
- Store your credentials (you log in yourself)
- Make decisions for you (it ranks, you choose)
- Pretend to be magic (it's a tool, not a guarantee)

## Philosophy

**Your Data:** Everything stored locally, no cloud accounts, export anytime
**Transparent:** See what's scraped, how it's scored, change the logic
**Determinism over Hallucination:** Use rules where possible, LLM only when needed
**Human Control:** Bot suggests, you decide
**Open Source:** Audit the code, customize it, no black boxes

## Installation

```bash
git clone https://github.com/yourusername/joblass.git
cd joblass
pip install -r requirements.txt
python joblass.py
```

**Requirements:** Python 3.10+, Chrome browser, job search account (Glassdoor)

## Quick Start

```bash
# Scrape jobs
python joblass.py scrape --search "data scientist paris"

# View dashboard
python joblass.py dashboard

# Export to CSV
python joblass.py export
```

## Configuration

Customize filters and scoring in `config.yaml`:

```yaml
filters:
  exclude_keywords: [consulting, rockstar, unpaid]
  exclude_companies: [Capgemini, Accenture]
  min_score: 50

scoring:
  tech_match: 30
  learning_opportunity: 25
  company_quality: 20
  practical_factors: 25

llm:
  provider: anthropic  # or openai, ollama
  model: claude-sonnet-4-5
```

## Scoring

Jobs scored 0-100 based on:
- **Tech stack match** (30%): Uses skills you know/want to learn
- **Learning opportunity** (25%): Mentorship, training, growth potential
- **Company quality** (20%): Reputation, funding, engineering culture
- **Practical factors** (25%): Location, compensation, start date

**Penalties for red flags:**
- "Rockstar/ninja/guru" = -15
- Unpaid internship = -30
- Consulting company = -25

Weights are configurable. Logic is transparent Python code.

## Example Output

```
Top Matches (Sorted by Score)

1. [92] Mirakl - AI Research Intern
   📍 Paris | 💰 €1600/mo | 🏢 Unicorn
   ✅ LLM fine-tuning, PyTorch, research

2. [89] Rakuten - ML Research Intern
   📍 Paris | 💰 €1100/mo | 🏢 Global
   ✅ Research lab, publication potential
```

## Status

**Current:** MVP - scraping + storage + basic UI
**Next:** Scoring + LLM analysis
**Future:** Application tracking, motivation letters

Built while job searching. Functional but rough. PRs welcome.

## Why Open Source?

If companies automate rejection, candidates can automate searching. This tool helps you find better matches faster and organize your job search in one place.

Use it, fork it, improve it, share it.

## Legal

- For personal use organizing your job search
- No credentials stored (you log in manually)
- Respectful scraping with delays
- Use responsibly, don't spam apply

Job sites may not like scrapers. Use at your own risk. Educational/research project.

## Contributing

Found a bug? Have an idea?

```bash
fork → branch → commit → PR
```

**Help wanted:**
- Better scraping (job sites change constantly)
- More job board support
- Improved scoring
- UI improvements

## License

MIT - Use however you want

---

**JOBLASS automates tedium, not decisions. You still need good applications and real skills. This just saves you time finding the right opportunities.**

---

**Status:** 🚧 Active development
**Version:** 0.1.0-alpha