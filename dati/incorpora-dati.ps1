# Incorpora dati/valutazioni-omi.js dentro Valutazione-Immobili-FAB.html,
# fra i marcatori <!-- INIZIO DATI OMI --> e <!-- FINE DATI OMI -->.
# Serve perche' la pagina deve funzionare aprendola con un doppio clic (file://),
# dove uno <script src="..."> relativo non e' sempre caricato dal browser.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$html = Join-Path $root 'Valutazione-Immobili-FAB.html'
$js   = Join-Path $PSScriptRoot 'valutazioni-omi.js'

foreach($f in @($html,$js)){ if (-not (Test-Path $f)) { throw "File mancante: $f" } }

$dati = [System.IO.File]::ReadAllText($js, [Text.Encoding]::UTF8)
$page = [System.IO.File]::ReadAllText($html, [Text.Encoding]::UTF8)

$inizio = '<!-- INIZIO DATI OMI -->'
$fine   = '<!-- FINE DATI OMI -->'
$i = $page.IndexOf($inizio); $j = $page.IndexOf($fine)
if ($i -lt 0 -or $j -lt 0 -or $j -lt $i) { throw "Marcatori non trovati in $html" }

# </script> dentro i dati romperebbe il blocco: non deve comparire
if ($dati -match '</script') { throw 'I dati contengono la sequenza </script: incorporamento annullato.' }

$blocco = $inizio + "`r`n" + '<script>' + "`r`n" + $dati + '</script>' + "`r`n"
$nuovo  = $page.Substring(0, $i) + $blocco + $page.Substring($j)

[System.IO.File]::WriteAllText($html, $nuovo, [System.Text.UTF8Encoding]::new($false))

$kb = [math]::Round((Get-Item $html).Length / 1KB, 1)
"Dati incorporati in Valutazione-Immobili-FAB.html ($kb KB)"
