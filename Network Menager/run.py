from flask import Flask, render_template, request, redirect, url_for, session
from ssh_utils import connect_router, exec_ssh_command, get_dhcp_data, update_dhcp_config

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

from ssh_utils import connect_router, exec_ssh_command, update_dhcp_config, get_dhcp_data

@app.route("/dhcp", methods=["GET", "POST"])
def dhcp():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")

    if request.method == "POST":
        start = request.form.get("start")
        limit = request.form.get("limit")
        leasetime = request.form.get("leasetime")

        success, message = update_dhcp_config(ip, username, password, start, limit, leasetime)
        dhcp_data = get_dhcp_data(ip, username, password)
        return render_template("dhcp.html", data=dhcp_data, message=message, success=success)

    dhcp_data = get_dhcp_data(ip, username, password)
    return render_template("dhcp.html", data=dhcp_data)


if __name__ == "__main__":
    app.run(debug=True)
