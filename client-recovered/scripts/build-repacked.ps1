[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$LabBootstrap,
    [switch]$LabLocalAuth,
    [switch]$Sign,
    [switch]$CreateDebugKeystore,
    [string]$KeystorePath,
    [string]$RunId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($LabLocalAuth -and -not $LabBootstrap) { throw '-LabLocalAuth requires -LabBootstrap' }
$clientRoot = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $clientRoot
$ledgerPath = Join-Path $clientRoot 'recovery-ledger.json'
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$workRoot = Join-Path $root 'work/apk-vn'
$sourceRoot = Join-Path $clientRoot 'src'
$encoder = Join-Path $root 'tools/apk-recovery/encode-jsc.py'
$labBootstrapHelper = Join-Path $root 'tools/apk-recovery/prepare-lab-bootstrap.py'
$payloadVerifier = Join-Path $PSScriptRoot 'verify-apk-payloads.py'

function Resolve-ProjectPath([string]$RelativePath) {
    [System.IO.Path]::GetFullPath((Join-Path $root $RelativePath))
}
function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) { throw "$Label SHA-256 mismatch: expected $Expected, got $actual" }
}

$originalApk = Resolve-ProjectPath $ledger.original_apk.path
$baseTree = Resolve-ProjectPath $ledger.base_apktool_tree
$native = Resolve-ProjectPath $ledger.native.path
$apktoolJar = Resolve-ProjectPath $ledger.apktool.path
Assert-Hash $originalApk $ledger.original_apk.sha256 'Pinned VN APK'
Assert-Hash $native $ledger.native.sha256 'Pinned VN native library'
Assert-Hash $apktoolJar $ledger.apktool.sha256 'Pinned Apktool 3.0.3'
if (-not (Test-Path -LiteralPath $baseTree -PathType Container)) { throw "Pinned Apktool tree is missing: $baseTree" }
foreach ($name in @('settings.js', 'jsb_polyfill.js', 'project.js')) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $name) -PathType Leaf)) { throw "Editable source is missing: $name" }
}
& python $payloadVerifier --apk $originalApk --tree $baseTree --ledger $ledgerPath
if ($LASTEXITCODE -ne 0) { throw 'Base Apktool payload validation failed' }
if ($ValidateOnly) {
    Write-Output 'VALIDATED: pinned APK/native/Apktool, APK-authoritative payloads, base tree, and editable sources'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RunId)) { $RunId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-repack' }
if ($RunId -notmatch '^[0-9]{8}T[0-9]{6}Z-repack(?:-[a-z0-9-]+)?$') { throw 'RunId must be a UTC timestamp followed by -repack and optional lowercase suffix' }
$runDir = Join-Path $workRoot $RunId
if (Test-Path -LiteralPath $runDir) { throw "Run directory already exists; refusing to overwrite: $runDir" }
$stage = Join-Path $runDir 'apktool-stage'
$encodedDir = Join-Path $runDir 'encoded-jsc'
$artifactDir = Join-Path $runDir 'artifacts'
$reportPath = Join-Path $runDir 'repack-build-report.md'
$report = [System.Collections.Generic.List[string]]::new()
$report.Add('# Native APK repack build report')
$report.Add('')
$report.Add("- Run: $RunId")
$report.Add('- Status: EDITABLE_CLIENT_BUILD_PARTIAL')
$report.Add('- Scope: recovered editable JavaScript + original Apktool/smali/resources + prebuilt native libraries')
$report.Add('- Device install/launch: not performed')
$report.Add('- Network/provider access: not performed')
$report.Add('')
$report.Add('## Pinned inputs')
$report.Add('')
$report.Add("- Original APK SHA-256: $($ledger.original_apk.sha256)")
$report.Add("- Native SHA-256: $($ledger.native.sha256)")
$report.Add("- Apktool SHA-256: $($ledger.apktool.sha256)")
function Save-Report {
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    [System.IO.File]::WriteAllLines($reportPath, $report, [System.Text.UTF8Encoding]::new($false))
}
function Invoke-Recorded([string]$Display, [scriptblock]$Action) {
    $report.Add('')
    $report.Add("### ``$Display``")
    & $Action
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    $report.Add("Exit code: $code")
    if ($code -ne 0) { throw "Command failed ($code): $Display" }
}

try {
    New-Item -ItemType Directory -Path $runDir, $encodedDir, $artifactDir | Out-Null
    Copy-Item -LiteralPath $baseTree -Destination $stage -Recurse
    $sourceForBuild = $sourceRoot
    if ($LabBootstrap) {
        $sourceStage = Join-Path $runDir 'source-stage'
        Copy-Item -LiteralPath $sourceRoot -Destination $sourceStage -Recurse
        Invoke-Recorded 'python tools/apk-recovery/prepare-lab-bootstrap.py remap-source <staged-project> --reference <pinned-project>' {
            & python $labBootstrapHelper remap-source --input (Join-Path $sourceStage 'project.js') --reference (Join-Path $sourceRoot 'project.js')
        }
        if ($LabLocalAuth) {
            Invoke-Recorded 'python tools/apk-recovery/prepare-lab-bootstrap.py patch-local-auth <staged-project> --reference <pinned-project>' {
                & python $labBootstrapHelper patch-local-auth --input (Join-Path $sourceStage 'project.js') --reference (Join-Path $sourceRoot 'project.js')
            }
            $report.Add('- Lab local-auth SDK-init transform: enabled (Android uses local mmx/Android fields; native Gosu bridge call is skipped).')
            $report.Add("- Lab local-auth staged project SHA-256: $((Get-FileHash -LiteralPath (Join-Path $sourceStage 'project.js') -Algorithm SHA256).Hash.ToLowerInvariant())")
        }
        $sourceForBuild = $sourceStage
    }
    $report.Add('')
    $report.Add('## Transformations')
    $report.Add('')
    $report.Add('- Verified selected base payloads against the original APK ZIP, then staged a fresh copy. The baseline and original APK were not modified.')
    $jscMap = [ordered]@{'settings.js'='settings.jsc'; 'jsb_polyfill.js'='jsb_polyfill.jsc'; 'project.js'='project.jsc'}
    foreach ($sourceName in $jscMap.Keys) {
        $source = Join-Path $sourceForBuild $sourceName
        $encoded = Join-Path $encodedDir $jscMap[$sourceName]
        $target = Join-Path $stage "assets/src/$($jscMap[$sourceName])"
        $oldHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        Invoke-Recorded "python tools/apk-recovery/encode-jsc.py --native <pinned-native> --input <build-source>/$sourceName --output <run>/encoded-jsc/$($jscMap[$sourceName])" {
            & python $encoder --native $native --input $source --output $encoded
        }
        Copy-Item -LiteralPath $encoded -Destination $target -Force
        $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        $newHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        $report.Add("Source SHA-256: $sourceHash")
        $report.Add("Original JSC SHA-256: $oldHash")
        $report.Add("Encoded JSC SHA-256: $newHash")
    }
    if ($LabBootstrap) {
        $labManifest = Join-Path $runDir 'lab-bootstrap/project.manifest'
        Invoke-Recorded 'python tools/apk-recovery/prepare-lab-bootstrap.py rewrite-manifest <staged-manifest> --encoded-dir <staged-encoded-jsc> --output <run>/lab-bootstrap/project.manifest' {
            & python $labBootstrapHelper rewrite-manifest --manifest (Join-Path $stage 'assets/project.manifest') --encoded-dir (Join-Path $stage 'assets/src') --output $labManifest
        }
        $labManifestHash = (Get-FileHash -LiteralPath $labManifest -Algorithm SHA256).Hash.ToLowerInvariant()
        $report.Add("Lab manifest: $labManifest")
        $report.Add("Lab manifest SHA-256: $labManifestHash")
        $report.Add('- Lab bootstrap changes are opt-in; the default build keeps historical endpoints and manifest metadata unchanged.')
    }
    $unsignedApk = Join-Path $artifactDir 'vn-recovered-unsigned.apk'
    Invoke-Recorded 'java -jar tools/decompiler/apktool_3.0.3.jar build <stage> --output <unsigned-apk>' {
        & java -jar $apktoolJar build $stage --output $unsignedApk
    }
    $unsignedHash = (Get-FileHash -LiteralPath $unsignedApk -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.Add("Unsigned APK SHA-256: $unsignedHash")
    if ($Sign) {
        $buildTools = Join-Path $env:LOCALAPPDATA 'Android/Sdk/build-tools/34.0.0'
        $zipalign = Join-Path $buildTools 'zipalign.exe'
        $apksigner = Join-Path $buildTools 'apksigner.bat'
        if (-not (Test-Path -LiteralPath $zipalign) -or -not (Test-Path -LiteralPath $apksigner)) { throw 'Android build-tools 34.0.0 zipalign/apksigner are required for -Sign' }
        if ([string]::IsNullOrWhiteSpace($KeystorePath)) { $KeystorePath = Join-Path $clientRoot 'keystore/debug-repack.jks' }
        elseif (-not [System.IO.Path]::IsPathRooted($KeystorePath)) { $KeystorePath = Join-Path $root $KeystorePath }
        $KeystorePath = [System.IO.Path]::GetFullPath($KeystorePath)
        $keystoreRoot = [System.IO.Path]::GetFullPath((Join-Path $clientRoot 'keystore'))
        if (-not $KeystorePath.StartsWith($keystoreRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'KeystorePath must be project-owned under client-recovered/keystore' }
        if (-not (Test-Path -LiteralPath $KeystorePath)) {
            if (-not $CreateDebugKeystore) { throw 'Debug keystore missing; pass -CreateDebugKeystore to create the project-owned lab key' }
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $KeystorePath) | Out-Null
            Invoke-Recorded 'keytool -genkeypair <project-debug-keystore>; password omitted from report' {
                & keytool -genkeypair -keystore $KeystorePath -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 3650 -dname 'CN=KBHT Repack Debug,O=Local Lab,C=VN'
            }
        }
        $alignedApk = Join-Path $artifactDir 'vn-recovered-aligned.apk'
        $signedApk = Join-Path $artifactDir 'vn-recovered-debug-signed.apk'
        Invoke-Recorded 'zipalign -f -p 4 <unsigned-apk> <aligned-apk>' { & $zipalign -f -p 4 $unsignedApk $alignedApk }
        Invoke-Recorded 'apksigner sign --ks <project-debug-keystore> --ks-pass <omitted> <signed-apk>' {
            & $apksigner sign --ks $KeystorePath --ks-key-alias androiddebugkey --ks-pass 'pass:android' --key-pass 'pass:android' --out $signedApk $alignedApk
        }
        Invoke-Recorded 'apksigner verify --verbose <signed-apk>' { & $apksigner verify --verbose $signedApk }
        $signedHash = (Get-FileHash -LiteralPath $signedApk -Algorithm SHA256).Hash.ToLowerInvariant()
        $report.Add("Signed APK SHA-256: $signedHash")
    } else {
        $report.Add('')
        $report.Add('- Signing: skipped (opt in with -Sign).')
    }
    $report.Add('')
    $report.Add('## Result')
    $report.Add('')
    $report.Add('- Repack build completed. No APK was installed or launched.')
    $report.Add('- This does not prove boot parity and is not a full Cocos project or recovered native C++ source.')
    Save-Report
    Write-Output "BUILT: $unsignedApk"
    Write-Output "REPORT: $reportPath"
} catch {
    $report.Add('')
    $report.Add('## Failure')
    $report.Add('')
    $report.Add("- $($_.Exception.Message)")
    Save-Report
    throw
}
