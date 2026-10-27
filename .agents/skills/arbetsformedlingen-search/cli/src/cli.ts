#!/usr/bin/env bun
/**
 * Arbetsförmedlingen JobSearch CLI — official open-data API (Platsbanken).
 * https://jobsearch.api.jobtechdev.se/search
 */

const API = "https://jobsearch.api.jobtechdev.se/search"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  const alias: Record<string, string> = { q: "query", l: "location", n: "limit" }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("--") || a.startsWith("-")) {
      const key = alias[a.replace(/^-+/, "")] ?? a.replace(/^-+/, "")
      const next = argv[i + 1]
      if (next === undefined || next.startsWith("-")) {
        flags[key] = true
      } else {
        flags[key] = next
        i++
      }
    } else {
      ;(flags._ as string[]).push(a)
    }
  }
  return flags
}

/** Map LinkedIn-style place strings to a Swedish city keyword for AF freetext. */
function cityKeyword(location: string): string {
  const raw = location.trim()
  const lower = raw.toLowerCase()
  const map: Record<string, string> = {
    "gothenburg, sweden": "Göteborg",
    "göteborg, sweden": "Göteborg",
    gothenburg: "Göteborg",
    göteborg: "Göteborg",
    "stockholm, sweden": "Stockholm",
    stockholm: "Stockholm",
    "malmö, sweden": "Malmö",
    "malmo, sweden": "Malmö",
    malmö: "Malmö",
    malmo: "Malmö",
    "copenhagen, denmark": "",
    "berlin, germany": "",
    "munich, germany": "",
    "london, united kingdom": "",
    "helsinki, finland": "",
    "oslo, norway": "",
    "barcelona, spain": "",
    "warsaw, poland": "",
  }
  if (lower in map) return map[lower]
  // Strip country suffix: "Stockholm, Sweden" → Stockholm
  const beforeComma = raw.split(",")[0]?.trim() || raw
  // Skip non-Sweden locations explicitly listed empty above
  if (/(denmark|germany|united kingdom|finland|norway|spain|poland)/i.test(raw)) {
    return ""
  }
  return beforeComma
}

function publishedAfter(days: number): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 19)
}

type Hit = {
  id?: string
  headline?: string
  webpage_url?: string
  publication_date?: string
  employer?: { name?: string; workplace?: string }
  workplace_address?: { municipality?: string; city?: string; region?: string }
}

async function runSearch(opts: {
  query: string
  location: string
  jobage?: number
  limit: number
  format: string
}): Promise<number> {
  const city = cityKeyword(opts.location)
  if (!city && opts.location.trim()) {
    // Non-Sweden location: emit empty result set (not an error)
    const empty = { meta: { count: 0, page: 1, source: "arbetsformedlingen", skippedLocation: opts.location }, results: [] }
    if (opts.format === "table") {
      console.log(`(skip Arbetsförmedlingen — location outside Sweden: ${opts.location})`)
    } else {
      console.log(JSON.stringify(empty, null, 2))
    }
    return 0
  }

  const q = [opts.query, city].filter(Boolean).join(" ").trim()
  const params = new URLSearchParams()
  params.set("q", q)
  params.set("limit", String(Math.min(Math.max(opts.limit, 1), 100)))
  params.set("offset", "0")
  if (opts.jobage && opts.jobage > 0) {
    params.set("published-after", publishedAfter(opts.jobage))
  }

  const url = `${API}?${params.toString()}`
  const res = await fetch(url, { headers: { Accept: "application/json" } })
  if (!res.ok) {
    console.error(JSON.stringify({ error: `HTTP ${res.status}`, code: "http_error", url }))
    return 1
  }
  const data = (await res.json()) as { total?: { value?: number }; hits?: Hit[] }
  const hits = data.hits || []
  const results = hits.slice(0, opts.limit).map((h) => ({
    id: h.id || "",
    title: h.headline || "",
    company: h.employer?.name || h.employer?.workplace || "",
    location: [h.workplace_address?.municipality || h.workplace_address?.city, h.workplace_address?.region]
      .filter(Boolean)
      .join(", "),
    date: (h.publication_date || "").slice(0, 10),
    url: h.webpage_url || (h.id ? `https://arbetsformedlingen.se/platsbanken/annonser/${h.id}` : ""),
    source: "arbetsformedlingen",
  }))

  if (opts.format === "table") {
    console.log("ID        TITLE                                      COMPANY                    LOCATION                 DATE")
    console.log("-".repeat(110))
    for (const r of results) {
      const row = [
        (r.id || "").padEnd(9).slice(0, 9),
        (r.title || "").padEnd(42).slice(0, 42),
        (r.company || "").padEnd(26).slice(0, 26),
        (r.location || "").padEnd(24).slice(0, 24),
        r.date || "",
      ].join(" ")
      console.log(row)
    }
  } else {
    console.log(
      JSON.stringify(
        {
          meta: { count: results.length, total: data.total?.value ?? results.length, page: 1, source: "arbetsformedlingen", q },
          results,
        },
        null,
        2,
      ),
    )
  }
  return 0
}

const HELP = `arbetsformedlingen-cli — search Platsbanken via official JobSearch API

USAGE
  bun run src/cli.ts search -q "<keywords>" [-l "<city>"] [--jobage 14] [-n 10] [--format json|table]

EXAMPLES
  bun run src/cli.ts search -q "AI Engineer" -l "Göteborg" --jobage 14 --format table
  bun run src/cli.ts search -q "fullstack" -l "Stockholm, Sweden" --limit 20 --format json
`

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]
  if (!cmd || cmd === "help" || flags.help || flags.h) {
    console.log(HELP)
    return 0
  }
  if (cmd !== "search") {
    console.error(JSON.stringify({ error: `unknown command: ${cmd}`, code: "usage" }))
    return 1
  }
  const query = String(flags.query || "").trim()
  if (!query) {
    console.error(JSON.stringify({ error: "--query / -q is required", code: "usage" }))
    return 1
  }
  const location = String(flags.location || "").trim()
  const jobage = flags.jobage ? Number(flags.jobage) : undefined
  const limit = flags.limit ? Number(flags.limit) : 10
  const format = String(flags.format || "json")
  return runSearch({ query, location, jobage, limit, format })
}

main().then((code) => process.exit(code))
