import paramiko
import json
import time
import re

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

        # parametry dhcp
        start = exec_ssh_command(ip, username, password, "uci get dhcp.lan.start").strip()
        limit = exec_ssh_command(ip, username, password, "uci get dhcp.lan.limit").strip()
        leasetime = exec_ssh_command(ip, username, password, "uci get dhcp.lan.leasetime").strip()

        # konfiguracja dhcp
        config_output = exec_ssh_command(ip, username, password, "cat /etc/config/dhcp")

        # wypisywanie danych 
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
    


def get_dhcp_reservations(ip, username, password):
    
    try:
        # Pobieram listę sekcji host
        output = exec_ssh_command(ip, username, password, "uci show dhcp | grep '=host' || true")
        lines = output.splitlines()
        reservations = []

        for line in lines:
            if "dhcp." in line:
                host_id = line.split(".")[1].split("=")[0]

                # Pobranie rezerwacji
                mac = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.mac || echo '-'").strip()
                ipaddr = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.ip || echo '-'").strip()
                name = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.name || echo '-'").strip()

                reservations.append({
                    "id": host_id,
                    "mac": mac,
                    "ip": ipaddr,
                    "name": name
                })

        return reservations

    except Exception as e:
        return [{"error": f"Błąd pobierania rezerwacji DHCP: {e}"}]


def add_dhcp_reservation(ip, username, password, mac, ipaddr, name):
    
    try:
        #Dodaje nowa sekcje i pola uzupelniam
        cmd = (
            "uci add dhcp host && "
            f"uci set dhcp.@host[-1].mac='{mac}' && "
            f"uci set dhcp.@host[-1].ip='{ipaddr}' && "
            f"uci set dhcp.@host[-1].name='{name}' && "
            "uci commit dhcp && "
            "/etc/init.d/dnsmasq restart"
        )

        exec_ssh_command(ip, username, password, cmd)
        return True, f"Rezerwacja dla {mac} → {ipaddr} została dodana."

    except Exception as e:
        return False, f"Błąd dodawania rezerwacji: {e}"


def remove_dhcp_reservation(ip, username, password, host_id):
    
    try:
        cmd = f"uci delete dhcp.{host_id} && uci commit dhcp && /etc/init.d/dnsmasq restart"
        exec_ssh_command(ip, username, password, cmd)
        return True, f"Rezerwacja {host_id} została usunięta."
    except Exception as e:
        return False, f"Błąd usuwania rezerwacji: {e}"    





# Pobranie logów systemowych
def get_system_logs(ip, username, password):
    try:
        logs = exec_ssh_command(ip, username, password, "logread | tail -n 200")
        if "not found" in logs.lower() or logs.strip() == "":
            logs = exec_ssh_command(ip, username, password, "dmesg | tail -n 200")
        return logs or "Brak logów systemowych."
    except Exception as e:
        return f"Błąd podczas pobierania logów: {e}"




def get_device_status(ip, username, password):
    
    try:
        interfaces = []

        
        # INTERFEJSY 
       
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


        #Uptime – wersja kompatybilna z BusyBox
        raw_uptime = exec_ssh_command(ip, username, password, "uptime || echo 'brak danych'").strip()
        uptime_clean = "brak danych"
        if "up" in raw_uptime:
    
            try:
                uptime_clean = raw_uptime.split("up", 1)[1].split("load average")[0].strip().rstrip(",")
            except Exception:
                uptime_clean = raw_uptime.strip()

        # Load average (średnie obciążenie)
        load_avg = exec_ssh_command(ip, username, password, "awk '{print $1,$2,$3}' /proc/loadavg || echo 'brak danych'").strip()

        #CPU usage (%)
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

        # 4️⃣ Brama
        gateway = exec_ssh_command(ip, username, password, "ip route | grep default | awk '{print $3}' || echo '-'").strip()

        return {
            "uptime": uptime_clean,
            "cpu_usage": f"{cpu_usage:.1f}%",
            "cpu_load": load_avg,
            "gateway": gateway,
            "interfaces": interfaces
        }

    except Exception as e:
        return {"error": f"Błąd pobierania statusu urządzenia: {e}"}
    



def get_wifi_info(ip, username, password):
    
    output = exec_ssh_command(ip, username, password, "iwinfo")
    wifi_list = []
    blocks = output.split("\n\n")  # każdy interfejs osobno

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        info = {
            "interface": lines[0].split()[0],
            "ssid": "-",
            "channel": "-",
            "frequency": "-",
            "txpower": "-",
            "encryption": "-",
        }

        for line in lines:
            # ESSID
            if "ESSID:" in line:
                info["ssid"] = line.split("ESSID:")[1].strip().strip('"')

            # Kanał + częstotliwość "Channel: 36 (5.180 GHz)"
            elif "Channel:" in line:
                match = re.search(r"Channel:\s*([0-9]+)\s*\(([\d\.]+)\s*GHz\)", line)
                if match:
                    info["channel"] = match.group(1)
                    info["frequency"] = f"{match.group(2)} GHz"

            # Moc nadawania
            elif "Tx-Power:" in line:
                power = line.split("Tx-Power:")[1].split()[0]
                info["txpower"] = f"{power} dBm"

            # Szyfrowanie
            elif "Encryption:" in line:
                info["encryption"] = line.split("Encryption:")[1].strip()

        wifi_list.append(info)

    return wifi_list


def get_wifi_details(ip, username, password, interface):
    
    
    output = exec_ssh_command(ip, username, password, f"iwinfo {interface} info")

    if not output.strip():
        return {"Błąd": "Brak odpowiedzi z routera (iwinfo zwrócił pusty wynik)."}

    if "Usage:" in output:
        return {"Błąd": f"Polecenie iwinfo {interface} info nie działa na tym interfejsie."}

    details = {}
    last_key = None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            details[key.strip()] = val.strip()
            last_key = key.strip()
        else:
      
            
            if last_key:
                details[last_key] += " " + line

    return details

def update_wifi_config(ip, username, password, interface, ssid=None, key=None, encryption=None):
    """
    Aktualizuje konfigurację Wi-Fi (SSID, hasło, szyfrowanie) dla interfejsu w OpenWrt.
    Działa z sekcjami default_radio0 i default_radio1.
    """
    try:
        # Mapowanie interfejsów iwinfo → sekcje UCI
        if "phy0" in interface or "wlan0" in interface:
            section_name = "wireless.default_radio0"
        elif "phy1" in interface or "wlan1" in interface:
            section_name = "wireless.default_radio1"
        else:
            return False, f"Nie rozpoznano interfejsu ({interface}) — nie znaleziono odpowiadającej sekcji UCI."

        commands = []
        if ssid:
            commands.append(f"uci set {section_name}.ssid='{ssid}'")
        if key:
            commands.append(f"uci set {section_name}.key='{key}'")
        if encryption:
            commands.append(f"uci set {section_name}.encryption='{encryption}'")

        # Zapis i restart Wi-Fi
        commands.append("uci commit wireless")
        commands.append("wifi reload")

        full_command = " && ".join(commands)
        result = exec_ssh_command(ip, username, password, full_command)

        return True, f" Zaktualizowano konfigurację dla {section_name}.\n{result}"

    except Exception as e:
        return False, f" Błąd podczas aktualizacji Wi-Fi: {e}"
    



MNC_PROVIDERS = {
    "01": "Plus",
    "02": "T-Mobile",
    "03": "Orange",
    "06": "Play",
    "15": "Aero2 / Plus LTE",
}


def get_lte_info(ip, username, password):
    """
    Pobiera parametry LTE z RUT955 (AT+QENG, CSQ, QNWINFO).
    """
    try:
        eng = exec_ssh_command(ip, username, password, 'gsmctl -A \'AT+QENG="servingcell"\'')
        csq = exec_ssh_command(ip, username, password, 'gsmctl -A "AT+CSQ"')
        nwinfo = exec_ssh_command(ip, username, password, 'gsmctl -A "AT+QNWINFO"')

        result = {}

        # =============== QENG ===============
        if "+QENG:" in eng:
            line = [l for l in eng.splitlines() if "+QENG:" in l][0]
            parts = line.split(",")

            result["mcc"] = parts[4]
            result["mnc"] = parts[5]
            result["cell_id_hex"] = parts[6]
            result["tac"] = parts[7]
            result["earfcn"] = parts[8]
            result["band"] = "B" + parts[9]
            result["pci"] = parts[10]

            result["rsrp"] = parts[13] + " dBm"
            result["rsrq"] = parts[14] + " dB"
            result["rssi"] = parts[15] + " dBm"
            result["sinr"] = parts[16] + " dB"

            mnc = parts[5].zfill(2)
            result["operator_name"] = MNC_PROVIDERS.get(mnc, "Nieznany operator")

        # =============== QNWINFO ===============
        if "+QNWINFO:" in nwinfo:
            parts = nwinfo.split(":")[1].replace('"', "").split(",")
            result["rat_mode"] = parts[0]
            result["plmn_raw"] = parts[1]
            result["band_full"] = parts[2]

        # =============== CSQ ===============
        if "+CSQ:" in csq:
            val = int(csq.split(":")[1].split(",")[0])
            if val != 99:
                result["csq_rssi"] = f"{-113 + 2 * val} dBm"
            else:
                result["csq_rssi"] = "Brak"

        # =============== Moc sygnału (signal_quality) ===============
        if "rsrp" in result:
            result["signal_quality"] = result["rsrp"]
        elif "csq_rssi" in result and result["csq_rssi"] != "Brak":
            result["signal_quality"] = result["csq_rssi"]
        else:
            result["signal_quality"] = "Brak danych"

        # =============== Moc urządzenia (bateria/zasilanie) ===============
        power_level = exec_ssh_command(ip, username, password, "cat /sys/class/power_supply/battery/capacity 2>/dev/null || cat /sys/class/power_supply/usb/capacity 2>/dev/null || cat /sys/class/power_supply/ac/capacity 2>/dev/null || echo 'brak danych'").strip()
        if power_level and power_level != "brak danych" and power_level.isdigit():
            result["power"] = f"{power_level}%"
        else:
            result["power"] = "brak danych"

        return result

    except Exception as e:
        return {"error": f"Błąd LTE: {e}"}
    
def set_hostname(ip, username, password, new_hostname):
    try:
        cmd = (
            f"uci set system.@system[0].hostname='{new_hostname}' && "
            "uci commit system && "
            "/etc/init.d/system restart"
        )
        exec_ssh_command(ip, username, password, cmd)
        return True, f"Nazwa hosta została zmieniona na: {new_hostname}"
    except Exception as e:
        return False, f"Błąd zmiany hostname: {e}"
    

def get_hostname(ip, username, password):
    try:
        result = exec_ssh_command(ip, username, password, "uci get system.@system[0].hostname")
        return result.strip()
    except Exception:
        return "unknown"

def get_lan_config(ip, username, password):
    config = {
        "ipaddr": exec_ssh_command(ip, username, password, "uci get network.lan.ipaddr || echo '-'").strip(),
        "netmask": exec_ssh_command(ip, username, password, "uci get network.lan.netmask || echo '-'").strip(),
    }

    # DNS: pobierz albo z LAN, albo z WAN
    dns = exec_ssh_command(ip, username, password, "uci get network.lan.dns 2>/dev/null")
    if not dns.strip():
        dns = exec_ssh_command(ip, username, password,
            "ubus call network.interface.wan status | grep dns-server -A1 | grep -oE '[0-9\\.]{7,15}' || echo '-'"
        )
    config["dns"] = dns.strip()

    # Gateway: pobieramy z WAN
    gateway = exec_ssh_command(ip, username, password,
        "ip route | grep default | awk '{print $3}' || echo '-'"
    )
    config["gateway"] = gateway.strip()

    return config


def set_lan_config(ip, username, password, ipaddr, netmask, gateway, dns):
    try:
        cmd = (
            f"uci set network.lan.ipaddr='{ipaddr}' && "
            f"uci set network.lan.netmask='{netmask}' && "
            f"uci set network.lan.gateway='{gateway}' && "
            f"uci set network.lan.dns='{dns}' && "
            "uci commit network && "
            "/etc/init.d/network restart"
        )
        exec_ssh_command(ip, username, password, cmd)
        return True, "Konfiguracja LAN została zaktualizowana."
    except Exception as e:
        return False, f"Błąd aktualizacji LAN: {e}"

def get_ports_info(ip, username, password):
    """
    Automatyczna autodetekcja portów LAN/WAN/CPU na OpenWrt i Teltonika.
    Zwraca listę portów z czytelnymi nazwami.
    """

    ports = {}
    vlan_map = {}

    # Pobierz swconfig
    swconfig_output = exec_ssh_command(ip, username, password, "swconfig dev switch0 show")

    # Pobierz definicje VLAN
    vlan_output = exec_ssh_command(ip, username, password, "uci show network | grep switch_vlan")

    # --------------------------
    # PARSOWANIE VLANÓW
    # --------------------------
    for line in vlan_output.splitlines():
        if "ports" in line:
            parts = line.split("ports='")
            if len(parts) < 2:
                continue

            ports_str = parts[1].split("'")[0]
            vlan_id = line.split("[")[1].split("]")[0]
            vlan_map[vlan_id] = ports_str.split()

    # --------------------------
    # PARSOWANIE PORTÓW
    # --------------------------
    current_port = None

    for line in swconfig_output.splitlines():
        line = line.strip()

        if line.startswith("Port "):
            current_port = line.split()[1].replace(":", "")
            ports[current_port] = {
                "id": current_port,
                "status": "DOWN",
                "speed": "-",
                "desc": "Unknown",
                "label": f"Port {current_port}"   # <-- domyślna nazwa
            }
            continue

        if "link:" in line and current_port is not None:
            if "link:up" in line:
                ports[current_port]["status"] = "UP"
            else:
                ports[current_port]["status"] = "DOWN"

            if "speed:" in line:
                try:
                    speed = line.split("speed:")[1].split("base")[0]
                    ports[current_port]["speed"] = speed + " Mb/s"
                except:
                    pass

    # --------------------------
    # WYKRYWANIE CPU PORTÓW
    # --------------------------
    cpu_ports = set()
    for vlan_id, plist in vlan_map.items():
        for p in plist:
            if p.endswith("t"):
                cpu_ports.add(p.replace("t", ""))

    for p in cpu_ports:
        if p in ports:
            ports[p]["desc"] = "CPU"
            ports[p]["label"] = "CPU"

    # --------------------------
    # WYKRYWANIE LAN PORTÓW
    # --------------------------
    lan_vlan_id = None
    for vlan_id, plist in vlan_map.items():
        non_cpu = [p for p in plist if not p.endswith("t")]
        if len(non_cpu) >= 2:
            lan_vlan_id = vlan_id
            break

    lan_counter = 1

    if lan_vlan_id is not None:
        for p in vlan_map[lan_vlan_id]:
            if p.endswith("t"):
                continue
            p = p.replace("t", "")
            if p in ports:
                ports[p]["desc"] = "LAN"
                ports[p]["label"] = f"LAN{lan_counter}"
                lan_counter += 1

    # --------------------------
    # WYKRYWANIE WAN
    # --------------------------
    wan_device = exec_ssh_command(ip, username, password, "uci get network.wan.device 2>/dev/null").strip()

    if wan_device.startswith("eth"):
        wan_port = wan_device.replace("eth", "")
        if wan_port in ports:
            ports[wan_port]["desc"] = "WAN"
            ports[wan_port]["label"] = "WAN"

    # --------------------------
    # ZWRÓĆ LISTĘ
    # --------------------------
    return list(ports.values())

def get_devices(ip, username, password):
    """
    Lista urządzeń z ARP + hostname z DHCP.
    Działa na OpenWrt i Teltonice.
    """
    devices = []

    # Pobierz DHCP leases
    dhcp = get_dhcp_data(ip, username, password)
    leases = dhcp.get("leases", []) if isinstance(dhcp, dict) else []

    lease_by_ip = {entry["ip"]: entry for entry in leases}
    lease_by_mac = {entry["mac"].lower(): entry for entry in leases}

    # Pobierz ARP z /proc/net/arp
    arp_output = exec_ssh_command(ip, username, password, "cat /proc/net/arp || echo ''")

    for line in arp_output.splitlines():
        if line.startswith("IP") or len(line.strip()) < 10:
            continue

        parts = line.split()
        if len(parts) < 6:
            continue

        ip_addr = parts[0]
        mac_addr = parts[3].lower()
        iface = parts[5]

        hostname = "-"
        if ip_addr in lease_by_ip:
            hostname = lease_by_ip[ip_addr].get("hostname", "-")
        elif mac_addr in lease_by_mac:
            hostname = lease_by_mac[mac_addr].get("hostname", "-")

        devices.append({
            "ip": ip_addr,
            "mac": mac_addr,
            "iface": iface,
            "hostname": hostname,
            "online": True,
        })

    return devices


def ping_device(ip, username, password, target_ip):
    """
    Ping urządzenia przez router (nie lokalnie!).
    """
    cmd = f"ping -c 1 -W 1 {target_ip}"
    output = exec_ssh_command(ip, username, password, cmd)

    if "1 packets transmitted, 1 packets received" in output:
        return True, f"Host {target_ip} odpowiada."
    else:
        return False, f"Brak odpowiedzi od {target_ip}."

def get_port_forwarding(ip, username, password):
    """
    Pobiera listę przekierowań portów z firewall w OpenWrt.
    """
    output = exec_ssh_command(ip, username, password, "uci show firewall | grep '=redirect' -A 5")

    rules = []
    current = {}

    for line in output.splitlines():
        line = line.strip()

        if "=redirect" in line:  # nowa sekcja
            if current:
                rules.append(current)
            current = {"id": line.split(".")[1].split("=")[0]}

        elif ".name=" in line:
            current["name"] = line.split("'")[1]
        elif ".src_dip=" in line or ".dest_ip=" in line:
            current["ip"] = line.split("'")[1]
        elif ".src_dport=" in line:
            current["wanport"] = line.split("'")[1]
        elif ".dest_port=" in line:
            current["lanport"] = line.split("'")[1]
        elif ".proto=" in line:
            current["proto"] = line.split("'")[1]

    if current:
        rules.append(current)

    return rules


def add_port_forwarding(ip, username, password, name, ipdest, wanport, lanport, proto):
    """
    Dodaje nową regułę port forwarding.
    """
    cmd = (
        "uci add firewall redirect && "
        f"uci set firewall.@redirect[-1].name='{name}' && "
        "uci set firewall.@redirect[-1].src='wan' && "
        f"uci set firewall.@redirect[-1].src_dport='{wanport}' && "
        f"uci set firewall.@redirect[-1].dest_ip='{ipdest}' && "
        f"uci set firewall.@redirect[-1].dest_port='{lanport}' && "
        f"uci set firewall.@redirect[-1].proto='{proto}' && "
        "uci commit firewall && "
        "/etc/init.d/firewall restart"
    )

    exec_ssh_command(ip, username, password, cmd)
    return True, "Reguła została dodana."


def delete_port_forwarding(ip, username, password, rule_id):
    """
    Usuwa regułę firewall redirect.
    """
    cmd = (
        f"uci delete firewall.{rule_id} && "
        "uci commit firewall && "
        "/etc/init.d/firewall restart"
    )
    exec_ssh_command(ip, username, password, cmd)
    return True, "Reguła została usunięta."
