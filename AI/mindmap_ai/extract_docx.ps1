param(
    [string]$InputPath,
    [string]$OutputPath
)

Add-Type -AssemblyName System.IO.Compression.FileSystem

$BOILERPLATE_HEADINGS = @(
    "LỜI CẢM ƠN", "LỜI CAM ĐOAN", "DANH MỤC HÌNH ẢNH", "DANH MỤC BẢNG",
    "MỤC LỤC", "DANH MỤC TỪ VIẾT TẮT", "DANH MỤC KÝ HIỆU",
    "LỜI MỞ ĐẦU", "NHẬN XÉT CỦA GIẢNG VIÊN", "TÀI LIỆU THAM KHẢO", "PHỤ LỤC"
)

function Test-IsNoiseLine {
    param([string]$Line)
    $s = $Line.Trim()
    if ([string]::IsNullOrWhiteSpace($s) -or $s.Length -lt 2) { return $true }
    
    # Số trang đơn thuần
    if ($s -match "^\d{1,4}$") { return $true }
    # Trang/Slide
    if ($s -match "(?i)^(?:trang|page|slide)\s*\d+(?:\s*(?:/\s*\d+|của\s*\d+))?$") { return $true }
    # Ngày tháng
    if ($s -match "(?i)^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$") { return $true }
    if ($s -match "(?i)^(?:tháng|ngày|january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}$") { return $true }
    # Mã môn học
    if ($s -match "(?i)^(?:học phần|mã hp|mã môn|course code)\s*[:：]?\s*[A-Z0-9_\-]+") { return $true }
    # XML rác
    if ($s -match "(?i)^<\/?(?:a|p|w|m|r|s|d):") { return $true }
    # Caption hình ảnh/bảng
    if ($s -match "(?i)^(?:hình|bảng|ảnh|sơ đồ)\s+\d+[\.:]") { return $true }

    return $false
}

function Extract-SingleDocx {
    param([string]$DocxPath, [string]$JsonPath)
    
    if (-not (Test-Path $DocxPath)) {
        Write-Error "Không tìm thấy file: $DocxPath"
        return
    }

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
    $inBoilerplate = $false

    foreach ($p in $paras) {
        $tNodes = $p.SelectNodes(".//w:t", $ns)
        $pText = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
        $t = $pText.Trim()
        
        # Bỏ dòng rỗng hoặc dòng rác
        if ([string]::IsNullOrWhiteSpace($t) -or (Test-IsNoiseLine -Line $t)) {
            continue
        }

        $style = $p.SelectSingleNode(".//w:pStyle/@w:val", $ns)
        $styleVal = if ($style) { $style.Value } else { "" }

        $isHeading = $false
        $lv = 1

        # 1. Kiểm tra Heading Style
        if ($styleVal -match "(?i)heading\s*(\d+)") {
            $isHeading = $true
            $lv = [int]$matches[1]
        }
        # 2. Fallback regex nhận diện heading (Chương, Bài, số La Mã, 1.1)
        elseif ($t.Length -le 120 -and -not ($t.EndsWith(".") -or $t.EndsWith(";") -or $t.EndsWith(":"))) {
            if ($t -match "(?i)^(?:chương|bài|phần|module|chủ đề)\s+[IVXLCDM\d]+") {
                $isHeading = $true
                $lv = 1
            } elseif ($t -match "^[IVXLCDM]+\.\s+\S+") {
                $isHeading = $true
                $lv = 1
            } elseif ($t -match "^\d+\.\d+\s+\S+") {
                $isHeading = $true
                $lv = 2
            } elseif ($t -match "^\d+\.\d+\.\d+\s+\S+") {
                $isHeading = $true
                $lv = 3
            } elseif ($t.Length -ge 4 -and $t.Length -le 80 -and $t -ceq $t.ToUpper()) {
                # In hoa toàn bộ
                $isHeading = $true
                $lv = 1
            }
        }

        if ($isHeading) {
            $upperTitle = $t.ToUpper()
            $matchedBoiler = $false
            foreach ($b in $BOILERPLATE_HEADINGS) {
                if ($upperTitle.Contains($b)) {
                    $matchedBoiler = $true
                    break
                }
            }

            if ($matchedBoiler) {
                $inBoilerplate = $true
                continue
            } else {
                $inBoilerplate = $false
            }

            $cur = [ordered]@{
                heading = $t
                level = $lv
                text = ""
            }
            $sections.Add($cur)
            $allTextList.Add($t)
        } else {
            if ($inBoilerplate) { continue }
            if ($null -ne $cur) {
                $cur["text"] += $t + "`n"
            }
            $allTextList.Add($t)
        }
    }

    # Trim các đoạn text trong section
    foreach ($sec in $sections) {
        $sec["text"] = $sec["text"].Trim()
    }

    $fileName = [System.IO.Path]::GetFileName($DocxPath)
    $outObj = [ordered]@{
        original_filename = $fileName
        extracted_text = ($allTextList -join "`n")
        sections = $sections
    }

    $outDir = [System.IO.Path]::GetDirectoryName($JsonPath)
    if ($outDir -and -not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }

    $json = ConvertTo-Json $outObj -Depth 5
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($JsonPath, $json, $utf8NoBom)
    Write-Host "Trích xuất thành công: $($sections.Count) sections -> $JsonPath"
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
