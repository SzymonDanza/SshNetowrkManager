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


# Pobranie statusu routera: uptime, load, pamięć, brama, interfejsy
import time

def get_device_status(ip, username, password):
    """
    Pobiera status routera: uptime, aktualne obciążenie CPU (%), średnie load average,
    pamięć, bramę oraz status interfejsów sieciowych.
    """
    try:
        # Pobranie listy interfejsów
        raw_ifaces = exec_ssh_command(ip, username, password, "ip -o link show").splitlines()
        interfaces = []

        for line in raw_ifaces:
            parts = line.split(": ")
            if len(parts) > 1:
                name = parts[1].split(":")[0]
                state = "UP" if "UP" in parts[1] else "DOWN"
                interfaces.append({"name": name, "state": state})

        # Pobranie uptime (czyli jak długo system działa)
        raw_uptime = exec_ssh_command(ip, username, password, "uptime").strip()
        uptime_clean = ""
        if "up" in raw_uptime:
            uptime_clean = raw_uptime.split("up")[-1].split(",")[0].strip()

        # Pobranie średniego load average (1,5,15 min)
        load_avg_raw = exec_ssh_command(ip, username, password, "cat /proc/loadavg").strip()
        load_avg = " ".join(load_avg_raw.split()[:3]) if load_avg_raw else "Brak danych"

        # Pobranie aktualnego obciążenia CPU (%)
        cpu_stat_1 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()
        time.sleep(0.3)  # krótka przerwa 300ms
        cpu_stat_2 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()

        def parse_cpu_line(line):
            parts = line.split()
            return list(map(int, parts[1:8])) if len(parts) >= 8 else [0]*7

        cpu1 = parse_cpu_line(cpu_stat_1)
        cpu2 = parse_cpu_line(cpu_stat_2)

        idle1, idle2 = cpu1[3], cpu2[3]
        total1, total2 = sum(cpu1), sum(cpu2)
        total_diff = total2 - total1
        idle_diff = idle2 - idle1
        cpu_usage = 0
        if total_diff > 0:
            cpu_usage = (1 - (idle_diff / total_diff)) * 100

        return {
            "uptime": uptime_clean or raw_uptime,
            "cpu_usage": f"{cpu_usage:.1f}%",
            "cpu_load": load_avg,
            "memory": exec_ssh_command(ip, username, password, "free -m | awk '/Mem/ {print $3\"/\"$2\" MB\"}'").strip(),
            "gateway": exec_ssh_command(ip, username, password, "ip route | grep default | awk '{print $3}'").strip(),
            "interfaces": interfaces
        }

    except Exception as e:
        return {"error": f"❌ Błąd pobierania statusu urządzenia: {e}"}

