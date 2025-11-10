from flask import Flask, render_template, request, Response, redirect,url_for,session
from ssh_utils import connect_router, exec_ssh_command, get_dhcp_info

app = Flask(__name__)
app.secret_key = "supersecretkey"

@app.route("/")
def index():
    # strona z formularzem
    return render_template("index.html")

@app.route("/connect", methods=["POST"])
def connect():
    ip = request.form.get("ip")
    username = request.form.get("username")
    password = request.form.get("password")

    # wykonanie polecenia przez SSH
    success, message = connect_router(ip, username, password)

    if success:
        session['ip'] = ip
        session['username'] = username
        session['password'] = password
        return redirect(url_for('dashboard'))
    else:
        return render_template("index.html", error=message)
    
@app.route("/dashboard")
def dashboard():
    ip = session.get('ip')
    username = session.get('username')
    return render_template("dashboard.html", ip=ip, username=username)

@app.route("/lan")
def lan():

    ip = session.get('ip')
    username = session.get('username')
    password = session.get('password')
    lan_info = exec_ssh_command(ip, username, password, "ifconfig br-lan")

    return render_template("lan.html", lan_info=lan_info)

@app.route("/wireless")
def wireless():

    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")
    wifi_info = exec_ssh_command(ip, username, password, "iwinfo")
    return render_template("wireless.html", wifi_info=wifi_info)

@app.route("/dhcp")
def dhcp():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")
    leases_output, config_output = get_dhcp_info(ip, username, password)

    leases = []
    for line in leases_output.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            timestamp, mac, ip_addr, hostname, client_id = parts
            leases.append({
                "expiry": parts[0],
                "mac": parts[1],
                "ip": parts[2],
                "hostname": parts[3]
            })
    return render_template("dhcp.html", leases=leases, config=config_output)

if __name__ == "__main__":
    app.run(debug=True)
