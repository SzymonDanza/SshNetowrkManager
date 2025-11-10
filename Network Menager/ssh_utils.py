import paramiko

def connect_router(ip, username, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=22, timeout=10)
        ssh.close()
        # ZWRACAMY DOKŁADNIE DWA ELEMENTY!
        return True, f"✅ Połączono pomyślnie z routerem {ip}"
    except Exception as e:
        # Również DWA ELEMENTY (False + wiadomość)
        return False, f"❌ Błąd połączenia: {e}"

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
    

def get_dhcp_data(ip, username, password):
    """
    Pobiera dane o DHCP:
      - aktywne dzierżawy z /tmp/dhcp.leases
      - podstawowe ustawienia (start, limit, leasetime)
      - pełną konfigurację DHCP (opcjonalnie do podglądu)
    """
    try:
        # aktywne dzierżawy
        leases_output = exec_ssh_command(ip, username, password, "cat /tmp/dhcp.leases")

        # aktualne parametry DHCP
        start = exec_ssh_command(ip, username, password, "uci get dhcp.lan.start").strip()
        limit = exec_ssh_command(ip, username, password, "uci get dhcp.lan.limit").strip()
        leasetime = exec_ssh_command(ip, username, password, "uci get dhcp.lan.leasetime").strip()

        # pełna konfiguracja (opcjonalna)
        config_output = exec_ssh_command(ip, username, password, "cat /etc/config/dhcp")

        # parsowanie listy klientów
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
    
def update_dhcp_config(ip, username, password, start,limit,leasetime):

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
    
def get_system_logs(ip, username, password):
    try:
        logs = exec_ssh_command(ip, username, password, "logread | tail -n 200")
        if "not found" in logs.lower() or logs.strip() == "":
            logs = exec_ssh_command(ip, username, password, "dmesg | tail -n 200")
        return logs or "Brak logów systemowych."
    except Exception as e:
        return f"Błąd podczas pobierania logów: {e}"