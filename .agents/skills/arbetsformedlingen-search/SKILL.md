---
name: arbetsformedlingen-search
version: 1.0.0
description: >
  Search Swedish job ads on Arbetsförmedlingen Platsbanken via the official
  JobSearch open-data API (jobtechdev). Trigger: platsbanken, arbetsförmedlingen,
  Swedish public jobs, AF jobs.
enabled: true
allowed-tools: Bash(bun run .agents/skills/arbetsformedlingen-search/cli/src/cli.ts *)
---

# Arbetsförmedlingen (Platsbanken) Search

Uses the **official** JobSearch API: `https://jobsearch.api.jobtechdev.se/search`

```bash
bun run .agents/skills/arbetsformedlingen-search/cli/src/cli.ts search -q "AI Engineer" -l "Göteborg" --jobage 14 --limit 10 --format table
```

No authentication. Open data (CC0). Sweden-focused.
