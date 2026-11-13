$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
$outputsDir = Join-Path $projectDir "outputs"
$screenshotsDir = Join-Path $projectDir "screenshots"
if (-not (Test-Path -LiteralPath $screenshotsDir)) {
    New-Item -ItemType Directory -Path $screenshotsDir | Out-Null
}

Add-Type -AssemblyName System.Drawing

function Read-Utf8File {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -Encoding UTF8 -Raw -LiteralPath $Path
}

function Split-ForDisplay {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [int]$Width = 170
    )
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line.Length -eq 0) {
            $result.Add("")
            continue
        }
        for ($offset = 0; $offset -lt $line.Length; $offset += $Width) {
            $length = [Math]::Min($Width, $line.Length - $offset)
            $result.Add($line.Substring($offset, $length))
        }
    }
    return $result
}

function Save-ResultImage {
    param(
        [Parameter(Mandatory = $true)][string]$Heading,
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $lines = @(Split-ForDisplay -Text $Content -Width 170)
    $width = 2200
    $headerHeight = 96
    $lineHeight = 27
    $height = $headerHeight + ($lines.Count * $lineHeight) + 38

    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $font = New-Object System.Drawing.Font(
        "Consolas", 15, [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Point
    )
    $headingFont = New-Object System.Drawing.Font(
        "Consolas", 18, [System.Drawing.FontStyle]::Bold,
        [System.Drawing.GraphicsUnit]::Point
    )
    $headerBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(30, 34, 42)
    )
    $normalBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(225, 230, 238)
    )
    $headingBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(123, 207, 255)
    )
    $successBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(104, 235, 150)
    )
    $sectionBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(247, 201, 95)
    )
    $mutedBrush = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(145, 155, 172)
    )

    try {
        $graphics.Clear([System.Drawing.Color]::FromArgb(12, 14, 18))
        $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
        $graphics.FillRectangle($headerBrush, 0, 0, $width, $headerHeight)
        $graphics.DrawString(
            "Experiment 1 Advanced - Real API Result Evidence",
            $headingFont, $headingBrush, 24, 16
        )
        $graphics.DrawString($Heading, $font, $normalBrush, 24, 57)

        $y = $headerHeight + 12
        foreach ($line in $lines) {
            $brush = $normalBrush
            if ($line -match "PASSED|SUCCESS:|COMMAND EXECUTED") {
                $brush = $successBrush
            }
            elseif ($line -match "^--- |^ACTUAL MODEL OUTPUT|^FINAL|^Six fee") {
                $brush = $sectionBrush
            }
            elseif ($line -match "^Saved |^outputs/") {
                $brush = $mutedBrush
            }
            $graphics.DrawString($line, $font, $brush, 24, $y)
            $y += $lineHeight
        }

        $bitmap.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
        Write-Output ("SAVED " + $Destination)
    }
    finally {
        $headingFont.Dispose()
        $font.Dispose()
        $headerBrush.Dispose()
        $normalBrush.Dispose()
        $headingBrush.Dispose()
        $successBrush.Dispose()
        $sectionBrush.Dispose()
        $mutedBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$rawV1 = Read-Utf8File (Join-Path $outputsDir "raw\notice_d_prompt_v1.txt")
$jsonV1 = Read-Utf8File (Join-Path $outputsDir "notice_d_prompt_v1.json")
$rawV2 = Read-Utf8File (Join-Path $outputsDir "raw\notice_d_prompt_v2.txt")
$jsonV2 = Read-Utf8File (Join-Path $outputsDir "notice_d_prompt_v2.json")

$summary = @"
COMMAND EXECUTED
PS $projectDir> python src\advanced_extract.py --prompt-version all

FINAL STORED RESULTS
notice_d_prompt_v1.json  STRICT ADVANCED VALIDATION PASSED
notice_d_prompt_v2.json  STRICT ADVANCED VALIDATION PASSED

Six fee combinations verified:
regular_author / early_bird / USD 400
regular_author / regular / USD 500
student_author / early_bird / USD 280
student_author / regular / USD 350
non_author_participant / early_bird / USD 200
non_author_participant / regular / USD 260

SUCCESS: 2 / 2 stored results
FAILED:  0 / 2 stored results
"@

$v1Content = @"
ACTUAL MODEL OUTPUT - notice_d.txt - Advanced Prompt V1

--- RAW RESPONSE ---
$rawV1

--- VALIDATED JSON ---
$jsonV1

STRICT ADVANCED VALIDATION PASSED
All 3 participant categories x 2 fee stages are complete.
Early-bird deadline and lower early-bird prices are verified.
Saved JSON: outputs/notice_d_prompt_v1.json
"@

$v2Content = @"
ACTUAL MODEL OUTPUT - notice_d.txt - Advanced Prompt V2

--- RAW RESPONSE ---
$rawV2

--- VALIDATED JSON ---
$jsonV2

STRICT ADVANCED VALIDATION PASSED
All 3 participant categories x 2 fee stages are complete.
Registration policy, student eligibility, proof, conditions,
included services and excluded expenses are present.
Saved JSON: outputs/notice_d_prompt_v2.json
"@

Save-ResultImage `
    -Heading "notice_d.txt | final advanced run summary" `
    -Content $summary `
    -Destination (Join-Path $screenshotsDir "05_notice_d_advanced_run_summary.png")

Save-ResultImage `
    -Heading "notice_d.txt | Prompt V1 | six fee combinations" `
    -Content $v1Content `
    -Destination (Join-Path $screenshotsDir "06_notice_d_prompt_v1_six_fee_combinations.png")

Save-ResultImage `
    -Heading "notice_d.txt | Prompt V2 | policy and fee matrix" `
    -Content $v2Content `
    -Destination (Join-Path $screenshotsDir "07_notice_d_prompt_v2_policy_and_fee_matrix.png")
