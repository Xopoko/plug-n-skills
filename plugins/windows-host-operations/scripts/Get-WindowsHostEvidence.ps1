#Requires -Version 5.1

<#
.SYNOPSIS
Capture a read-only, target-bounded Windows host evidence receipt.

.DESCRIPTION
The helper performs no mutation. It reports denied, unavailable, or failed
probes as UNKNOWN coverage and hashes path-like command data and device
identifiers by default. Raw host output can still be private; keep receipts
local and untracked.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('EffectiveSetting', 'StartupRemoval', 'Device')]
    [string] $Area,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:Coverage = @()

function Get-TextSha256 {
    param([AllowNull()][object] $Value)

    $text = [string] $Value
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $algorithm.Dispose()
    }
}

function Test-TargetMatch {
    param([AllowNull()][object[]] $Values)

    foreach ($value in $Values) {
        if ($null -ne $value -and ([string] $value).IndexOf($Target, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

function Add-Coverage {
    param(
        [Parameter(Mandatory = $true)][string] $Surface,
        [Parameter(Mandatory = $true)][ValidateSet('COVERED', 'UNKNOWN', 'NOT_PROBED')][string] $State,
        [string] $Reason = '',
        [bool] $NeedsAdmin = $false
    )

    $script:Coverage += [pscustomobject][ordered]@{
        surface = $Surface
        state = $State
        reason = $Reason
        needs_admin = $NeedsAdmin
    }
}

function Invoke-ReadOnlyProbe {
    param(
        [Parameter(Mandatory = $true)][string] $Surface,
        [Parameter(Mandatory = $true)][scriptblock] $Action
    )

    try {
        $result = @(& $Action)
        Add-Coverage -Surface $Surface -State COVERED
        return $result
    }
    catch [System.UnauthorizedAccessException] {
        Add-Coverage -Surface $Surface -State UNKNOWN -Reason 'access-denied' -NeedsAdmin $true
    }
    catch {
        $reason = 'probe-failed-' + $_.Exception.GetType().Name
        Add-Coverage -Surface $Surface -State UNKNOWN -Reason $reason
    }
    return @()
}

function Get-CommandAvailability {
    param([Parameter(Mandatory = $true)][string] $Name)
    return $null -ne (Get-Command -Name $Name -ErrorAction SilentlyContinue)
}

function Get-NativeSummary {
    param(
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter(Mandatory = $true)][string[]] $Arguments
    )

    $lines = @(& $FilePath @Arguments 2>&1 | ForEach-Object { [string] $_ })
    $exitCode = $LASTEXITCODE
    return [pscustomobject][ordered]@{
        exit_code = $exitCode
        line_count = $lines.Count
        output_sha256 = Get-TextSha256 ($lines -join "`n")
    }
}

function Get-IsAdministrator {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

function Get-HostContext {
    $osRows = @(Invoke-ReadOnlyProbe -Surface 'operating_system' -Action {
        Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
    })
    $os = if ($osRows.Count -gt 0) { $osRows[0] } else { $null }
    return [pscustomobject][ordered]@{
        windows = $true
        os = $os
        powershell_edition = [string] $PSVersionTable.PSEdition
        powershell_version = [string] $PSVersionTable.PSVersion
        process_bitness = [IntPtr]::Size * 8
        elevated = Get-IsAdministrator
    }
}

function Get-MatchingServices {
    return Invoke-ReadOnlyProbe -Surface 'services' -Action {
        Get-CimInstance -ClassName Win32_Service |
            Where-Object { Test-TargetMatch @($_.Name, $_.DisplayName) } |
            Select-Object Name, DisplayName, State, StartMode, StartName, ExitCode
    }
}

function Get-EffectiveSettingEvidence {
    $services = Get-MatchingServices
    $powerScheme = @()
    $powerRequests = @()
    if (Get-CommandAvailability 'powercfg.exe') {
        $powerScheme = Invoke-ReadOnlyProbe -Surface 'active_power_scheme' -Action {
            Get-NativeSummary -FilePath 'powercfg.exe' -Arguments @('/getactivescheme')
        }
        $powerRequests = Invoke-ReadOnlyProbe -Surface 'active_power_requests' -Action {
            Get-NativeSummary -FilePath 'powercfg.exe' -Arguments @('/requests')
        }
    }
    else {
        Add-Coverage -Surface 'active_power_scheme' -State UNKNOWN -Reason 'powercfg-unavailable'
        Add-Coverage -Surface 'active_power_requests' -State UNKNOWN -Reason 'powercfg-unavailable'
    }
    Add-Coverage -Surface 'resultant_policy' -State NOT_PROBED -Reason 'setting-specific-query-required'
    Add-Coverage -Surface 'consent_and_privacy' -State NOT_PROBED -Reason 'setting-specific-query-required'
    Add-Coverage -Surface 'vendor_driver_firmware' -State NOT_PROBED -Reason 'target-specific-owner-required'
    Add-Coverage -Surface 'observed_effect' -State NOT_PROBED -Reason 'functional-test-required'
    return [pscustomobject][ordered]@{
        services = @($services)
        active_power_scheme = @($powerScheme)
        active_power_requests = @($powerRequests)
    }
}

function Get-StartupRemovalEvidence {
    $processes = Invoke-ReadOnlyProbe -Surface 'processes' -Action {
        Get-CimInstance -ClassName Win32_Process |
            Where-Object { Test-TargetMatch @($_.Name, $_.ExecutablePath) } |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    name = $_.Name
                    process_id = $_.ProcessId
                    executable_path_sha256 = Get-TextSha256 $_.ExecutablePath
                    executable_path_present = -not [string]::IsNullOrWhiteSpace([string] $_.ExecutablePath)
                }
            }
    }
    $services = Get-MatchingServices

    $tasks = @()
    if (Get-CommandAvailability 'Get-ScheduledTask') {
        $tasks = Invoke-ReadOnlyProbe -Surface 'scheduled_tasks' -Action {
            Get-ScheduledTask |
                Where-Object { Test-TargetMatch @($_.TaskName, $_.TaskPath) } |
                Select-Object TaskName, TaskPath, State
        }
    }
    else {
        Add-Coverage -Surface 'scheduled_tasks' -State UNKNOWN -Reason 'scheduledtasks-module-unavailable'
    }

    $runEntries = Invoke-ReadOnlyProbe -Surface 'run_keys' -Action {
        $locations = @(
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce'
        )
        foreach ($location in $locations) {
            if (-not (Test-Path -LiteralPath $location)) { continue }
            $item = Get-ItemProperty -LiteralPath $location
            foreach ($property in $item.PSObject.Properties) {
                if ($property.Name -like 'PS*') { continue }
                $data = [string] $property.Value
                if (-not (Test-TargetMatch @($property.Name, $data))) { continue }
                [pscustomobject][ordered]@{
                    location = $location
                    value_name = $property.Name
                    data_sha256 = Get-TextSha256 $data
                    data_length = $data.Length
                }
            }
        }
    }

    $startupFiles = Invoke-ReadOnlyProbe -Surface 'startup_folders' -Action {
        $folders = @(
            [pscustomobject]@{ scope = 'user'; path = [Environment]::GetFolderPath('Startup') },
            [pscustomobject]@{ scope = 'machine'; path = [Environment]::GetFolderPath('CommonStartup') }
        )
        foreach ($folder in $folders) {
            if ([string]::IsNullOrWhiteSpace($folder.path) -or -not (Test-Path -LiteralPath $folder.path)) { continue }
            Get-ChildItem -LiteralPath $folder.path -Force -ErrorAction Stop |
                Where-Object { Test-TargetMatch @($_.Name) } |
                ForEach-Object {
                    [pscustomobject][ordered]@{
                        scope = $folder.scope
                        name = $_.Name
                        item_type = if ($_.PSIsContainer) { 'directory' } else { 'file' }
                    }
                }
        }
    }

    $packages = Invoke-ReadOnlyProbe -Surface 'classic_uninstall_registry' -Action {
        $roots = @(
            [pscustomobject]@{ path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; scope = 'machine'; architecture = 'native' },
            [pscustomobject]@{ path = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'; scope = 'machine'; architecture = 'x86' },
            [pscustomobject]@{ path = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; scope = 'user'; architecture = 'current' }
        )
        foreach ($root in $roots) {
            Get-ItemProperty -Path $root.path -ErrorAction SilentlyContinue |
                Where-Object { Test-TargetMatch @($_.DisplayName, $_.Publisher, $_.PSChildName) } |
                ForEach-Object {
                    [pscustomobject][ordered]@{
                        display_name = $_.DisplayName
                        display_version = $_.DisplayVersion
                        publisher = $_.Publisher
                        package_key = $_.PSChildName
                        scope = $root.scope
                        architecture = $root.architecture
                        windows_installer = [bool] $_.WindowsInstaller
                    }
                }
        }
    }

    $appx = @()
    if (Get-CommandAvailability 'Get-AppxPackage') {
        $appx = Invoke-ReadOnlyProbe -Surface 'appx_packages' -Action {
            Get-AppxPackage |
                Where-Object { Test-TargetMatch @($_.Name, $_.PackageFullName, $_.Publisher) } |
                ForEach-Object {
                    [pscustomobject][ordered]@{
                        name = $_.Name
                        version = [string] $_.Version
                        package_full_name_sha256 = Get-TextSha256 $_.PackageFullName
                        publisher_sha256 = Get-TextSha256 $_.Publisher
                    }
                }
        }
    }
    else {
        Add-Coverage -Surface 'appx_packages' -State UNKNOWN -Reason 'appx-module-unavailable'
    }

    Add-Coverage -Surface 'advanced_persistence' -State NOT_PROBED -Reason 'active-setup-winlogon-policy-scripts-require-targeted-review'
    Add-Coverage -Surface 'user_and_shared_data' -State NOT_PROBED -Reason 'explicit-preserve-or-purge-decision-required'
    Add-Coverage -Surface 'file_locks' -State NOT_PROBED -Reason 'targeted-lock-owner-query-required'
    return [pscustomobject][ordered]@{
        processes = @($processes)
        services = @($services)
        scheduled_tasks = @($tasks)
        run_entries = @($runEntries)
        startup_folder_items = @($startupFiles)
        classic_packages = @($packages)
        appx_packages = @($appx)
    }
}

function Get-DeviceEvidence {
    $pnp = @()
    if (Get-CommandAvailability 'Get-PnpDevice') {
        $pnp = Invoke-ReadOnlyProbe -Surface 'pnp_devices' -Action {
            $presentIds = @{}
            $presentProbeSucceeded = $false
            try {
                Get-PnpDevice -PresentOnly -ErrorAction Stop | ForEach-Object { $presentIds[$_.InstanceId] = $true }
                $presentProbeSucceeded = $true
                Add-Coverage -Surface 'pnp_present_only' -State COVERED
            }
            catch {
                Add-Coverage -Surface 'pnp_present_only' -State UNKNOWN -Reason ('probe-failed-' + $_.Exception.GetType().Name)
            }
            Get-PnpDevice |
                Where-Object { Test-TargetMatch @($_.FriendlyName, $_.Class, $_.InstanceId) } |
                ForEach-Object {
                    $present = if ($presentProbeSucceeded) {
                        [bool] $presentIds.ContainsKey([string] $_.InstanceId)
                    }
                    else {
                        $null
                    }
                    [pscustomobject][ordered]@{
                        friendly_name = $_.FriendlyName
                        class = $_.Class
                        status = $_.Status
                        present = $present
                        instance_id_sha256 = Get-TextSha256 $_.InstanceId
                    }
                }
        }
    }
    else {
        Add-Coverage -Surface 'pnp_devices' -State UNKNOWN -Reason 'pnpdevice-module-unavailable'
    }

    $sound = Invoke-ReadOnlyProbe -Surface 'sound_devices' -Action {
        Get-CimInstance -ClassName Win32_SoundDevice |
            Where-Object { Test-TargetMatch @($_.Name, $_.Manufacturer, $_.PNPDeviceID) } |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    name = $_.Name
                    manufacturer = $_.Manufacturer
                    status = $_.Status
                    pnp_device_id_sha256 = Get-TextSha256 $_.PNPDeviceID
                }
            }
    }

    $printers = @()
    if (Get-CommandAvailability 'Get-Printer') {
        $printers = Invoke-ReadOnlyProbe -Surface 'printer_queues' -Action {
            Get-Printer |
                Where-Object { Test-TargetMatch @($_.Name, $_.DriverName, $_.PortName) } |
                ForEach-Object {
                    [pscustomobject][ordered]@{
                        name = $_.Name
                        driver_name = $_.DriverName
                        printer_status = [string] $_.PrinterStatus
                        shared = [bool] $_.Shared
                        port_sha256 = Get-TextSha256 $_.PortName
                    }
                }
        }
    }
    else {
        Add-Coverage -Surface 'printer_queues' -State UNKNOWN -Reason 'printmanagement-module-unavailable'
    }

    Add-Coverage -Surface 'driver_package_details' -State NOT_PROBED -Reason 'exact-instance-query-required'
    Add-Coverage -Surface 'endpoint_and_default_roles' -State NOT_PROBED -Reason 'function-specific-provider-required'
    Add-Coverage -Surface 'vendor_software_and_firmware' -State NOT_PROBED -Reason 'target-specific-owner-required'
    Add-Coverage -Surface 'observed_function' -State NOT_PROBED -Reason 'live-functional-test-required'
    return [pscustomobject][ordered]@{
        pnp_devices = @($pnp)
        sound_devices = @($sound)
        printer_queues = @($printers)
    }
}

$hostContext = Get-HostContext
$evidence = switch ($Area) {
    'EffectiveSetting' { Get-EffectiveSettingEvidence }
    'StartupRemoval' { Get-StartupRemovalEvidence }
    'Device' { Get-DeviceEvidence }
}

$receipt = [pscustomobject][ordered]@{
    schema = 'windows_host_operations.evidence.v1'
    captured_at = [DateTime]::UtcNow.ToString('o')
    area = $Area
    target = [pscustomobject][ordered]@{
        sha256 = Get-TextSha256 $Target
        length = $Target.Length
        raw_value_included = $false
    }
    host_context = $hostContext
    coverage = @($script:Coverage)
    evidence = $evidence
    classification = 'unknown'
    mutation_performed = $false
    privacy = [pscustomobject][ordered]@{
        command_lines_included = $false
        raw_device_identifiers_included = $false
        raw_target_included = $false
        receipt_may_still_contain_local_names = $true
    }
}

$receipt | ConvertTo-Json -Depth 10
