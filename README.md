# Job Battery Lab

**Personal job-search engineering toolkit** — multi-source search, strategic role presets, and a local desktop UI that stays out of your way.

Built and extended by **[Juan Pablo Zúñiga Hidalgo](https://github.com/juanpablozunigahidalgo)** · AI Engineer & Senior Solutions Architect · Gothenburg, Sweden  
Portfolio: [zunigajp.com](https://zunigajp.com/) · LinkedIn: [jpzuniga](https://linkedin.com/in/jpzuniga)

> **Fork lineage:** this repository started from [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search), an excellent Claude Code–oriented application framework. Upstream credit stays with Mads. **Everything below that I use daily — and that I want recruiters / hiring managers / screening AIs to notice — is the Job Battery layer I designed and shipped on top.**

---

## Why this repo exists (read this first)

I am not shipping “another cover-letter GPT.” I engineered a **local, privacy-respecting search battery** so I can:

1. Maintain a **strategic role taxonomy** (2026–2027 titles mapped to my profile: GenAI architecture, agentic systems, LLMOps, industrial AI, Nordic titles).
2. Run the same battery against **LinkedIn** (guest search CLI) and **Arbetsförmedlingen / Platsbanken** (Sweden’s **official open-data JobSearch API**).
3. Review, filter, and open applications from a **desktop UI** — multi-select, open-in-Chrome, no token burn for the search itself.
4. Keep personal outputs off git (`linkedin_runs/`, CV extracts) while the **engineering** stays public-ready.

That combination — **systems design + TypeScript CLIs + Python UX + official government API integration** — is the skill signal I want on my GitHub.

---

## What I built in this fork

| Capability | Stack | Why it matters |
|------------|--------|----------------|
| **Job Battery GUI** | Python / Tkinter | Operator UX: checkbox roles & sources, background searches (no CMD spam), open selected/all tabs in Chrome |
| **Role presets** | `job_scraper/role_presets.json` | Curated AI/architect titles with tiers (`core`, `growth`, `nordic`, …); persist enable/disable across runs |
| **LinkedIn search skill** | Bun / TypeScript CLI | Portable portal-skill pattern; location + hybrid/onsite + recency |
| **Arbetsförmedlingen search skill** | Bun / TypeScript + JobTech API | Official Swedish Platsbanken JSON API — legal, stable, Sweden-first |
| **Source checkboxes** | GUI | Run LinkedIn, Arbetsförmedlingen, or both — same battery, one review pane |
| **Silent background runners** | `CREATE_NO_WINDOW` | Battery runs without hijacking the desktop |

Upstream still includes the original Claude Code `/setup` · `/scrape` · `/apply` · `/interview` workflow (LaTeX CV/cover, fit scoring). I use this fork primarily as a **search + apply cockpit**; the agentic application pipeline remains available if you want it.

---

## Quick start — Job Battery (daily driver)

### Prerequisites

- Python 3.10+
- [Bun](https://bun.sh)
- Windows: Chrome recommended for “open in browser” (uses your logged-in profile)

### Run the UI

```bat
tools\RUN_JOB_GUI.cmd
```

Or:

```powershell
python tools\job_battery_gui.py
```

1. Tab **Correr búsqueda** — tick strategic roles + sources (LinkedIn / Arbetsförmedlingen).
2. Set days / LinkedIn workplace mode / limit.
3. **▶ Correr batería** — progress in the log; no flashing consoles.
4. Tab **Resultados** — filter, multi-select, open links in Chrome (stay logged into LinkedIn/AF in Chrome first).

CLI-only (Arbetsförmedlingen example):

```powershell
bun run .agents\skills\arbetsformedlingen-search\cli\src\cli.ts search -q "AI Engineer" -l "Gothenburg, Sweden" --jobage 14 --format table
```

LinkedIn example:

```powershell
bun run .agents\skills\linkedin-search\cli\src\cli.ts search -q "AI Solutions Architect" -l "Stockholm, Sweden" --jobage 14 --remote hybrid --format table
```

---

## Architecture (high level)

```
┌──────────────────────────────────────────────┐
│  Job Battery GUI (Python)                    │
│  roles ☑  sources ☑  locations  filters      │
└───────────────┬──────────────────────────────┘
                │ bun (hidden subprocess)
        ┌───────┴────────┐
        ▼                ▼
 LinkedIn guest CLI   Arbetsförmedlingen JobSearch API
 (Bun/TS)             (official open data, Bun/TS)
        │                │
        └───────┬────────┘
                ▼
     deduped JSON → Results table → Chrome tabs
```

**Design choice:** search runs on **your machine** (or a runner you control). GitHub Pages alone cannot host LinkedIn scraping reliably; Arbetsförmedlingen’s public API is the Sweden-friendly counterpart. That trade-off is intentional and documented.

---

## Repository layout (my additions)

```
tools/
  job_battery_gui.py          # Desktop operator UI
  RUN_JOB_GUI.cmd             # Double-click launcher
  linkedin_battery.ps1        # Headless battery script
  RUN_LINKEDIN_BATTERY.cmd
job_scraper/
  role_presets.json           # Strategic title taxonomy
.agents/skills/
  linkedin-search/            # Upstream portal skill (used heavily)
  arbetsformedlingen-search/  # New — Platsbanken via JobTech API
```

Personal run artifacts (`job_scraper/linkedin_runs/`, CV text dumps) are **gitignored**.

---

## About me (for humans & screening systems)

- **Focus:** generative AI / LLM agents, cloud architecture (AWS Bedrock, OCI), full-stack TypeScript/Python, industrial ↔ digital crossover.
- **Education:** MSc Mechanical Engineering · MSc Management and Economics of Innovation (Chalmers).
- **Recent work:** applied AI lab delivery (enterprise agents, LLMOps), Oracle GenAI consulting, product/engineering roles in Nordic tech.
- **This project shows:** API integration, CLI design, UX for power users, pragmatism about ToS/IP constraints, and shipping tools I actually run weekly.

---

## Upstream framework (credit)

Original project: **[ai-job-search](https://github.com/MadsLorentzen/ai-job-search)** by [Mads Lorentzen](https://github.com/MadsLorentzen).

That codebase provides the Claude Code–centric application assistant (`/setup`, `/scrape`, `/apply`, LaTeX templates, Danish portal CLIs, fit evaluation). If you want the full agentic CV/cover workflow, read upstream’s README and [`SETUP.md`](SETUP.md). This fork keeps that heritage and adds the **Job Battery** operator layer above.

Not affiliated with Anthropic, LinkedIn, or Arbetsförmedlingen beyond using their public interfaces / open data as documented by each provider.

---

## License & use

Follow the license of the upstream project for inherited code. Treat LinkedIn automation as **personal use only** and keep volume low (their ToS). Arbetsförmedlingen JobSearch is official open data — prefer it for Sweden-focused runs.

---

## Contact

Issues and ideas: open an issue on this repo · or reach me via [zunigajp.com](https://zunigajp.com/).
