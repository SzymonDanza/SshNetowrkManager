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
    

def get_dhcp_info(ip, username, password):
    
    try:
        less_output = exec_ssh_command(ip, username, password, "cat /tmp/dhcp.leases")
        
        config_output = exec_ssh_command(ip, username, password, "cat /etc/config/dhcp")
        return less_output, config_output
    except Exception as e:
        return f"Błąd podczas pobierania informacji DHCP: {e}"