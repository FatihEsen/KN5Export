# Syncs development repository to Blender 5.2 user extension folder
$src = $PSScriptRoot
$dst = "C:\Users\Fatih\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\kn5_studio"

if (Test-Path $dst) {
    Get-ChildItem -Path $src -Filter "*.py" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $dst -Force
        Write-Host "Synced: $($_.Name)"
    }
    if (Test-Path "$dst\__pycache__") {
        Remove-Item -Path "$dst\__pycache__\*" -Recurse -Force
    }
    Write-Host "All KN5 Studio addon files synced to Blender 5.2 extensions successfully!"
} else {
    Write-Warning "Blender 5.2 extensions path not found: $dst"
}
