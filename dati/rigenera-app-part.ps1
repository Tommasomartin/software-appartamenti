# Rigenera app/valutazione.part.html dalla pagina principale, per tenere le due
# copie allineate. La versione "part" e' la stessa pagina senza involucro
# <!doctype>/<html>/<head>/<body>: parte dal <title> e finisce all'ultimo </script>.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src  = Join-Path $root 'Valutazione-Immobili-FAB.html'
$dst  = Join-Path $root 'app\valutazione.part.html'

$t = [System.IO.File]::ReadAllText($src, [Text.Encoding]::UTF8)

$i = $t.IndexOf('<title>')
if ($i -lt 0) { throw "<title> non trovato in $src" }
$j = $t.LastIndexOf('</script>')
if ($j -lt 0) { throw "</script> di chiusura non trovato in $src" }

$body = $t.Substring($i, $j + '</script>'.Length - $i)
# via i tag di struttura che nella versione "part" non devono comparire
$body = $body -replace '(?i)</?(head|body)>\s*', ''

[System.IO.File]::WriteAllText($dst, $body + "`r`n", [System.Text.UTF8Encoding]::new($false))
"Rigenerato app/valutazione.part.html ($([math]::Round((Get-Item $dst).Length/1KB,1)) KB)"
