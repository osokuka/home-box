# Generic SOCKS5 proxy on Windows so Docker can reach any LAN IP.
# Devices are added in Home Assistant forms, not in Compose.
$listenPort = 1080
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $listenPort)
$listener.Start()
Write-Output "SOCKS5 listening on 0.0.0.0:$listenPort (generic LAN access for Docker)"

$handlerScript = {
    param($Client)
    $stream = $null
    $dest = $null
    try {
        $stream = $Client.GetStream()
        $buf = New-Object byte[] 512
        $n = $stream.Read($buf, 0, $buf.Length)
        if ($n -lt 2 -or $buf[0] -ne 5) { return }
        $stream.Write([byte[]](5, 0), 0, 2)
        $n = $stream.Read($buf, 0, $buf.Length)
        if ($n -lt 7 -or $buf[0] -ne 5 -or $buf[1] -ne 1) { return }
        $atyp = $buf[3]
        if ($atyp -eq 1) {
            $hostName = ([System.Net.IPAddress]::new($buf[4..7])).ToString()
            $port = ($buf[8] * 256) + $buf[9]
        } elseif ($atyp -eq 3) {
            $len = $buf[4]
            $hostName = [System.Text.Encoding]::ASCII.GetString($buf, 5, $len)
            $port = ($buf[5 + $len] * 256) + $buf[6 + $len]
        } else {
            return
        }
        $dest = New-Object System.Net.Sockets.TcpClient
        $dest.Connect($hostName, $port)
        $stream.Write([byte[]](5, 0, 0, 1, 0, 0, 0, 0, 0, 0), 0, 10)
        $dStream = $dest.GetStream()
        $a = $stream.CopyToAsync($dStream)
        $b = $dStream.CopyToAsync($stream)
        [void][System.Threading.Tasks.Task]::WaitAll(@($a, $b))
    } catch {
    } finally {
        if ($stream) { try { $stream.Close() } catch {} }
        if ($dest) { try { $dest.Close() } catch {} }
        try { $Client.Close() } catch {}
    }
}

while ($true) {
    try {
        $client = $listener.AcceptTcpClient()
        $ps = [PowerShell]::Create()
        [void]$ps.AddScript($handlerScript).AddArgument($client)
        [void]$ps.BeginInvoke()
    } catch {
        Write-Output "socks accept error: $_"
        Start-Sleep -Milliseconds 200
    }
}
