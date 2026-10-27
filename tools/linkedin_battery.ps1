# LinkedIn search battery — no Cursor, no LLM tokens.
# Personal use only; keep volume low (LinkedIn ToS).
#
# How to run (PowerShell):
#   cd C:\Users\pablo\Documents\Vida2026\ai-job-search-modified
#   powershell -ExecutionPolicy Bypass -File .\tools\linkedin_battery.ps1
#
# Results:
#   job_scraper\linkedin_runs\battery_YYYYMMDD_HHMM.jsonl
#   job_scraper\linkedin_runs\battery_YYYYMMDD_HHMM_unique.json

$ErrorActionPreference = "Continue"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
  Write-Host "ERROR: bun not found. Install with: winget install Oven-sh.Bun" -ForegroundColor Red
  Write-Host "Then close and reopen PowerShell."
  exit 1
}

$cli = Join-Path $root ".agents\skills\linkedin-search\cli\src\cli.ts"
$outDir = Join-Path $root "job_scraper\linkedin_runs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$outFile = Join-Path $outDir "battery_$stamp.jsonl"
$summary = Join-Path $outDir "battery_${stamp}_unique.json"

# --- edit these ---
$queries = @(
  "AI Solutions Architect",
  "Generative AI Engineer",
  "AI Engineer",
  "MLOps Engineer"
)
$locations = @(
  "Gothenburg, Sweden",
  "Stockholm, Sweden",
  "Malmö, Sweden",
  "Copenhagen, Denmark",
  "Berlin, Germany",
  "Munich, Germany",
  "London, United Kingdom",
  "Helsinki, Finland",
  "Oslo, Norway",
  "Barcelona, Spain"
)
$jobage = 14                 # 7 or 14
$remoteModes = @("hybrid")   # add "onsite" if you want; skip "remote" for now
$limit = 8
$delaySec = 2
# ------------------

$seen = @{}
$unique = [System.Collections.Generic.List[object]]::new()
$totalCalls = $queries.Count * $locations.Count * $remoteModes.Count
Write-Host "Planned searches: $totalCalls"
Write-Host "Output: $summary"
Write-Host ""

foreach ($q in $queries) {
  foreach ($loc in $locations) {
    foreach ($mode in $remoteModes) {
      Write-Host ">> $q | $loc | $mode"
      $raw = & bun run $cli search -q $q -l $loc --jobage $jobage --remote $mode --limit $limit --format json 2>$null | Out-String
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        Write-Host "   (empty/error)"
        Start-Sleep -Seconds $delaySec
        continue
      }
      try {
        $parsed = $raw | ConvertFrom-Json
        $rows = @($parsed.results)
        $n = 0
        foreach ($r in $rows) {
          if (-not $r.id) { continue }
          $n++
          $obj = [ordered]@{
            query          = $q
            searchLocation = $loc
            workplace      = $mode
            id             = "$($r.id)"
            title          = $r.title
            company        = $r.company
            location       = $r.location
            date           = $r.date
            url            = $r.url
          }
          # retry write if file briefly locked
          $line = ($obj | ConvertTo-Json -Compress)
          for ($t = 0; $t -lt 3; $t++) {
            try { Add-Content -Path $outFile -Value $line -Encoding utf8 -ErrorAction Stop; break }
            catch { Start-Sleep -Milliseconds 200 }
          }
          if (-not $seen.ContainsKey("$($r.id)")) {
            $seen["$($r.id)"] = $true
            $unique.Add([pscustomobject]$obj)
          }
        }
        Write-Host "   +$n  (unique so far: $($unique.Count))"
      } catch {
        Write-Host "   parse fail: $($_.Exception.Message)"
      }
      Start-Sleep -Seconds $delaySec
    }
  }
}

$unique | ConvertTo-Json -Depth 6 | Set-Content -Path $summary -Encoding utf8
Write-Host ""
Write-Host "DONE. Unique jobs: $($unique.Count)"
Write-Host "Open this file:"
Write-Host "  $summary"
explorer.exe /select,$summary
