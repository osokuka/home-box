# Forwards Docker host.docker.internal TCP to Tuya devices on the Windows LAN.
$ErrorActionPreference = "Stop"
$routesPath = Join-Path $PSScriptRoot "lan-routes.json"
$routes = @(Get-Content -Raw $routesPath | ConvertFrom-Json)

function Listen-Route {
    param($Route)
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, [int]$Route.listen_port)
    $listener.Start()
    Write-Output "LAN proxy 0.0.0.0:$($Route.listen_port) -> $($Route.lan_ip):$($Route.device_port) ($($Route.name))"
    while ($true) {
        $client = $listener.AcceptTcpClient()
        $dest = New-Object System.Net.Sockets.TcpClient
        try {
            $dest.Connect($Route.lan_ip, [int]$Route.device_port)
            $cStream = $client.GetStream()
            $dStream = $dest.GetStream()
            $a = $cStream.CopyToAsync($dStream)
            $b = $dStream.CopyToAsync($cStream)
            [void][System.Threading.Tasks.Task]::WaitAny(@($a, $b))
        } catch {
            Write-Output "proxy error $($Route.name): $_"
        } finally {
            $client.Close()
            $dest.Close()
        }
    }
}

if ($routes.Count -eq 1) {
    Listen-Route -Route $routes[0]
} else {
    $jobs = foreach ($route in $routes) {
        Start-Job -ScriptBlock ${function:Listen-Route} -ArgumentList $route
    }
    Wait-Job $jobs
}
