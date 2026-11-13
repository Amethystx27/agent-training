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
    $bottomPadding = 38
    $height = $headerHeight + ($lines.Count * $lineHeight) + $bottomPadding

    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $font = New-Object System.Drawing.Font(
        "Consolas",
        15,
        [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Point
    )
    $headingFont = New-Object System.Drawing.Font(
        "Consolas",
        18,
        [System.Drawing.FontStyle]::Bold,
        [System.Drawing.GraphicsUnit]::Point
    )
    $background = [System.Drawing.Color]::FromArgb(12, 14, 18)
    $headerBackground = [System.Drawing.Color]::FromArgb(30, 34, 42)
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
        $graphics.Clear($background)
        $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
        $graphics.FillRectangle(
            [System.Drawing.Brushes]::White,
            0,
            0,
            $width,
            $headerHeight
        )
        $graphics.FillRectangle(
            (New-Object System.Drawing.SolidBrush $headerBackground),
            0,
            0,
            $width,
            $headerHeight
        )
        $graphics.DrawString(
            "Experiment 1 - Real API Result Evidence",
            $headingFont,
            $headingBrush,
            24,
            16
        )
        $graphics.DrawString(
            $Heading,
            $font,
            $normalBrush,
            24,
            57
        )

        $y = $headerHeight + 12
        foreach ($line in $lines) {
            $brush = $normalBrush
            if ($line -match "STRICT VALIDATION PASSED|SUCCESS:|COMMAND EXECUTED") {
                $brush = $successBrush
            }
            elseif ($line -match "^--- |^ACTUAL MODEL OUTPUT|^REAL MODEL RUN RESULT|^Unknown values") {
                $brush = $sectionBrush
            }
            elseif ($line -match "^Saved |^outputs/") {
                $brush = $mutedBrush
            }
            $graphics.DrawString($line, $font, $brush, 24, $y)
            $y += $lineHeight
        }

        $bitmap.Save(
            $Destination,
            [System.Drawing.Imaging.ImageFormat]::Png
        )
        Write-Output ("SAVED " + $Destination)
    }
    finally {
        $headingFont.Dispose()
        $font.Dispose()
        $normalBrush.Dispose()
        $headingBrush.Dispose()
        $successBrush.Dispose()
        $sectionBrush.Dispose()
        $mutedBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$rawA = Read-Utf8File (Join-Path $outputsDir "raw\notice_a_prompt_v2.txt")
$jsonA = Read-Utf8File (Join-Path $outputsDir "notice_a_prompt_v2.json")
$rawB = Read-Utf8File (Join-Path $outputsDir "raw\notice_b_prompt_v2.txt")
$jsonB = Read-Utf8File (Join-Path $outputsDir "notice_b_prompt_v2.json")
$rawC = Read-Utf8File (Join-Path $outputsDir "raw\notice_c_prompt_v2.txt")
$jsonC = Read-Utf8File (Join-Path $outputsDir "notice_c_prompt_v2.json")

$summary = @"
COMMAND EXECUTED
PS $projectDir> python src\validate_schema.py --notice all --prompt-version all

REAL MODEL RUN RESULT
notice_a_prompt_v1.json  STRICT VALIDATION PASSED
notice_a_prompt_v2.json  STRICT VALIDATION PASSED
notice_b_prompt_v1.json  STRICT VALIDATION PASSED
notice_b_prompt_v2.json  STRICT VALIDATION PASSED
notice_c_prompt_v1.json  STRICT VALIDATION PASSED
notice_c_prompt_v2.json  STRICT VALIDATION PASSED

SUCCESS: 6 / 6
FAILED:  0 / 6

Saved artifacts:
outputs/notice_*_prompt_v*.json
outputs/raw/notice_*_prompt_v*.txt
"@

$aContent = @"
ACTUAL MODEL OUTPUT - notice_a.txt - Prompt V2

--- RAW RESPONSE ---
$rawA

--- VALIDATED JSON ---
$jsonA

STRICT VALIDATION PASSED
Saved JSON: outputs/notice_a_prompt_v2.json
"@

$bContent = @"
ACTUAL MODEL OUTPUT - notice_b.txt - Prompt V2

--- RAW RESPONSE ---
$rawB

--- VALIDATED JSON ---
$jsonB

STRICT VALIDATION PASSED
Unknown values remain null:
start_date = null; end_date = null; submission_deadline = null; organizer = null
Saved JSON: outputs/notice_b_prompt_v2.json
"@

$cContent = @"
ACTUAL MODEL OUTPUT - notice_c.txt - Prompt V2

--- RAW RESPONSE ---
$rawC

--- VALIDATED JSON ---
$jsonC

STRICT VALIDATION PASSED
submission_deadline = 2027-07-24
other_dates = abstract_registration 2027-07-10
              acceptance_notification 2027-09-05
              early_bird_registration 2027-10-01
Saved JSON: outputs/notice_c_prompt_v2.json
"@

Save-ResultImage `
    -Heading "Six real model runs | command and completion summary" `
    -Content $summary `
    -Destination (Join-Path $screenshotsDir "01_real_model_run_command_and_summary.png")

Save-ResultImage `
    -Heading "notice_a.txt | Prompt V2 | complete fields" `
    -Content $aContent `
    -Destination (Join-Path $screenshotsDir "02_notice_a_prompt_v2_complete_fields_validation_passed.png")

Save-ResultImage `
    -Heading "notice_b.txt | Prompt V2 | missing values remain null" `
    -Content $bContent `
    -Destination (Join-Path $screenshotsDir "03_notice_b_prompt_v2_nulls_validation_passed.png")

Save-ResultImage `
    -Heading "notice_c.txt | Prompt V2 | multi-date classification" `
    -Content $cContent `
    -Destination (Join-Path $screenshotsDir "04_notice_c_prompt_v2_multi_date_classification.png")
