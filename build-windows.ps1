$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path $PSScriptRoot).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python environment not found. Create .venv and install requirements-build.txt first."
}

Push-Location $repoRoot
try {
    & $python -m PyInstaller --clean --noconfirm --windowed --onedir `
        --specpath build --name WindowsTTSApp app.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $distribution = Join-Path $repoRoot "dist\WindowsTTSApp"
    $executable = Join-Path $distribution "WindowsTTSApp.exe"
    if (-not (Test-Path $executable)) {
        throw "PyInstaller did not produce $executable."
    }

    $archive = Join-Path $repoRoot "dist\WindowsTTSApp-windows-x64.zip"
    if (Test-Path $archive) {
        Remove-Item -LiteralPath $archive -Force
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $distribution,
        $archive,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $archiveFiles = @($zip.Entries | Where-Object {
            -not $_.FullName.EndsWith("/")
        }).Count
        $sourceFiles = @(Get-ChildItem -LiteralPath $distribution -File -Recurse).Count
        if ($archiveFiles -ne $sourceFiles) {
            throw "Archive contains $archiveFiles files; expected $sourceFiles."
        }
        if (-not ($zip.Entries | Where-Object {
            $_.FullName -eq "WindowsTTSApp\_internal\base_library.zip"
        })) {
            throw "Archive is missing the Python base library."
        }
    }
    finally {
        $zip.Dispose()
    }

    Write-Output "Created $archive"
}
finally {
    Pop-Location
}
