#!/usr/bin/env python3
"""Transparent TCP relay: LAN destinations go through a Windows SOCKS5 proxy."""
import socket
import struct
import threading

SO_ORIGINAL_DST = 80
LISTEN_PORT = 12345
SOCKS_PORT = 1080


def socks_host():
    with open("/etc/hosts", encoding="utf-8") as fh:
        for line in fh:
            if "host.docker.internal" in line:
                return line.split()[0]
    raise RuntimeError("host.docker.internal not found")


def original_dest(conn):
    data = conn.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
    port = struct.unpack("!H", data[2:4])[0]
    ip = socket.inet_ntoa(data[4:8])
    return ip, port


def socks_connect(proxy_ip, dest_ip, dest_port):
    sock = socket.create_connection((proxy_ip, SOCKS_PORT), 8)
    sock.sendall(b"\x05\x01\x00")
    if sock.recv(2) != b"\x05\x00":
        raise RuntimeError("SOCKS5 handshake failed")
    req = b"\x05\x01\x00\x01" + socket.inet_aton(dest_ip) + dest_port.to_bytes(2, "big")
    sock.sendall(req)
    resp = sock.recv(10)
    if len(resp) < 2 or resp[1] != 0:
        raise RuntimeError(f"SOCKS5 connect failed: {dest_ip}:{dest_port}")
    return sock


def pipe(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle(client, proxy_ip):
    dest = None
    try:
        ip, port = original_dest(client)
        dest = socks_connect(proxy_ip, ip, port)
        t1 = threading.Thread(target=pipe, args=(client, dest), daemon=True)
        t2 = threading.Thread(target=pipe, args=(dest, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception as exc:
        print(f"relay error: {exc}", flush=True)
    finally:
        client.close()
        if dest is not None:
            dest.close()


def main():
    proxy_ip = socks_host()
    print(f"transparent SOCKS via {proxy_ip}:{SOCKS_PORT} on :{LISTEN_PORT}", flush=True)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", LISTEN_PORT))
    server.listen(64)
    while True:
        client, _ = server.accept()
        threading.Thread(target=handle, args=(client, proxy_ip), daemon=True).start()


if __name__ == "__main__":
    main()
