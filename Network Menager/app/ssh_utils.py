import paramiko

# Nawiązanie połączenia SSH z routerem
def connect_router(ip, username, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=22, timeout=10)
        ssh.close()
        return True, f"Połączono pomyślnie z routerem {ip}"
    except Exception as e:
        return False, f"Błąd połączenia: {e}"


# Wykonanie komendy przez SSH i zwrócenie wyniku
def exec_ssh_command(ip, username, password, command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=22, timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode(errors="ignore")
        ssh.close()
        return output or "Brak danych z routera."
    except Exception as e:
        return f"Błąd podczas wykonywania komendy: {e}"


# Pobranie danych DHCP z routera
def get_dhcp_data(ip, username, password):
    try:
        # Dane z pliku /tmp/dhcp.leases
        leases_output = exec_ssh_command(ip, username, password, "cat /tmp/dhcp.leases")

        # Podstawowe parametry DHCP
        start = exec_ssh_command(ip, username, password, "uci get dhcp.lan.start").strip()
        limit = exec_ssh_command(ip, username, password, "uci get dhcp.lan.limit").strip()
        leasetime = exec_ssh_command(ip, username, password, "uci get dhcp.lan.leasetime").strip()

        # Pełna konfiguracja DHCP
        config_output = exec_ssh_command(ip, username, password, "cat /etc/config/dhcp")

        # Parsowanie danych dzierżaw
        leases = []
        for line in leases_output.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                leases.append({
                    "timestamp": parts[0],
                    "mac": parts[1],
                    "ip": parts[2],
                    "hostname": parts[3] if len(parts) > 3 else "-"
                })

        return {
            "leases": leases,
            "settings": {"start": start, "limit": limit, "leasetime": leasetime},
            "config_raw": config_output
        }

    except Exception as e:
        return {
            "leases": [],
            "settings": {"start": "-", "limit": "-", "leasetime": "-"},
            "config_raw": f"Błąd pobierania DHCP: {e}"
        }


# Aktualizacja konfiguracji DHCP
def update_dhcp_config(ip, username, password, start, limit, leasetime):
    try:
        commands = [
            f"uci set dhcp.lan.start='{start}'",
            f"uci set dhcp.lan.limit='{limit}'",
            f"uci set dhcp.lan.leasetime='{leasetime}'",
            "uci commit dhcp",
            "/etc/init.d/dnsmasq restart"
        ]
        full_command = " && ".join(commands)
        result = exec_ssh_command(ip, username, password, full_command)
        return True, f"Konfiguracja DHCP została zaktualizowana:\n{result}"
    except Exception as e:
        return False, f"Błąd aktualizacji konfiguracji DHCP: {e}"


# Pobranie logów systemowych (logread lub dmesg)
def get_system_logs(ip, username, password):
    try:
        logs = exec_ssh_command(ip, username, password, "logread | tail -n 200")
        if "not found" in logs.lower() or logs.strip() == "":
            logs = exec_ssh_command(ip, username, password, "dmesg | tail -n 200")
        return logs or "Brak logów systemowych."
    except Exception as e:
        return f"Błąd podczas pobierania logów: {e}"



import json
import time

def get_device_status(ip, username, password):
    """
    Pobiera status routera:
    - czas działania (uptime)
    - zużycie CPU (%)
    - średnie obciążenie (load average)
    - pamięć RAM
    - bramę domyślną
    - interfejsy logiczne (LAN, WAN, itp.)
    """
    try:
        interfaces = []

        # ======================
        # 🔹 INTERFEJSY LOGICZNE
        # ======================
        uci_interfaces = exec_ssh_command(ip, username, password, "uci show network | grep '=interface' || true").splitlines()

        for line in uci_interfaces:
            if "network." in line:
                iface = line.split(".")[1].split("=")[0]
                raw_status = exec_ssh_command(ip, username, password, f"ifstatus {iface} || true").strip()

                state = "DOWN"
                if raw_status:
                    try:
                        data = json.loads(raw_status)
                        if data.get("up") is True:
                            state = "UP"
                    except json.JSONDecodeError:
                        pass

                interfaces.append({"name": iface, "state": state})

        # ======================
        # 🔹 SYSTEM: UPTIME, CPU, RAM, GATEWAY
        # ======================

        # 1️⃣ Uptime – wersja kompatybilna z BusyBox
        raw_uptime = exec_ssh_command(ip, username, password, "uptime || echo 'brak danych'").strip()
        uptime_clean = "brak danych"
        if "up" in raw_uptime:
    # przykład:  16:27:55 up 1 day,  3:12,  load average: 0.00, 0.01, 0.00
            try:
        # Wyciągamy wszystko między "up" a "load average"
                uptime_clean = raw_uptime.split("up", 1)[1].split("load average")[0].strip().rstrip(",")
            except Exception:
                uptime_clean = raw_uptime.strip()

        # 2️⃣ Load average (średnie obciążenie)
        load_avg = exec_ssh_command(ip, username, password, "awk '{print $1,$2,$3}' /proc/loadavg || echo 'brak danych'").strip()

        # 3️⃣ CPU usage (%)
        cpu1 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()
        time.sleep(0.3)
        cpu2 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()

        def parse_cpu(line):
            parts = line.split()
            return list(map(int, parts[1:])) if len(parts) > 7 else [0] * 7

        c1, c2 = parse_cpu(cpu1), parse_cpu(cpu2)
        idle1, idle2 = c1[3], c2[3]
        total1, total2 = sum(c1), sum(c2)
        diff_total = total2 - total1
        diff_idle = idle2 - idle1
        cpu_usage = 0.0
        if diff_total > 0:
            cpu_usage = (1 - diff_idle / diff_total) * 100

        # 4️⃣ RAM i brama
        memory = exec_ssh_command(ip, username, password, "free -m | awk '/Mem/ {print $3\"/\"$2\" MB\"}' || echo 'brak danych'").strip()
        gateway = exec_ssh_command(ip, username, password, "ip route | grep default | awk '{print $3}' || echo '-'").strip()

        return {
            "uptime": uptime_clean,
            "cpu_usage": f"{cpu_usage:.1f}%",
            "cpu_load": load_avg,
            "memory": memory,
            "gateway": gateway,
            "interfaces": interfaces
        }

    except Exception as e:
        return {"error": f"❌ Błąd pobierania statusu urządzenia: {e}"}



