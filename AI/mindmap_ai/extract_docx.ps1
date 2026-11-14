param(
    [string]$InputPath,
    [string]$OutputPath
)

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Extract-SingleDocx {
    param([string]$DocxPath, [string]$JsonPath)
    
    $zip = [System.IO.Compression.ZipFile]::OpenRead($DocxPath)
    $entry = $zip.GetEntry("word/document.xml")
    if (-not $entry) {
        $zip.Dispose()
        Write-Error "Không tìm thấy word/document.xml trong $DocxPath"
        return
    }
    
    $stream = $entry.Open()
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
    $xml = [xml]$reader.ReadToEnd()
    $reader.Close()
    $stream.Close()
    $zip.Dispose()

    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")

    $paras = $xml.SelectNodes("//w:p", $ns)
    $sections = [System.Collections.Generic.List[PSObject]]::new()
    $allTextList = [System.Collections.Generic.List[string]]::new()
    $cur = $null

    foreach ($p in $paras) {
        $tNodes = $p.SelectNodes(".//w:t", $ns)
        $pText = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
        $t = $pText.Trim()
        if ([string]::IsNullOrWhiteSpace($t)) { continue }

        $allTextList.Add($pText)

        $style = $p.SelectSingleNode(".//w:pStyle/@w:val", $ns)
        $styleVal = if ($style) { $style.Value } else { "" }

        if ($styleVal -match "(?i)heading\s*(\d+)") {
            $lv = [int]$matches[1]
            $cur = [ordered]@{
                heading = $t
                level = $lv
                text = ""
            }
            $sections.Add($cur)
        } elseif ($null -ne $cur) {
            $cur["text"] += $t + "`n"
        }
    }

    $fileName = [System.IO.Path]::GetFileName($DocxPath)
    $outObj = [ordered]@{
        original_filename = $fileName
        extracted_text = ($allTextList -join "`n")
        sections = $sections
    }

    $json = ConvertTo-Json $outObj -Depth 5
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($JsonPath, $json, $utf8NoBom)
    Write-Host "$($sections.Count) sections -> $JsonPath"
}

if ($InputPath -and $OutputPath) {
    Extract-SingleDocx -DocxPath $InputPath -JsonPath $OutputPath
} else {
    $rawFiles = Get-ChildItem -Path "d:\AI\raw\*.docx" -ErrorAction SilentlyContinue
    if (-not $rawFiles -or $rawFiles.Count -eq 0) {
        Write-Warning "Không tìm thấy file .docx nào trong d:\AI\raw"
    } else {
        foreach ($file in $rawFiles) {
            $targetJson = Join-Path "d:\AI\docs" "$($file.BaseName).json"
            Extract-SingleDocx -DocxPath $file.FullName -JsonPath $targetJson
        }
    }
}
