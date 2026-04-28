import re
from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user
from app.db.base import SessionLocal
from app.models.device import Device

devices_bp = Blueprint("devices", __name__)

IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
HOST_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9]$")


def _valid_host(host):
    return bool(IP_RE.match(host) or HOST_RE.match(host))


@devices_bp.route("/devices")
@login_required
def device_list():
    db = SessionLocal()
    devices = db.query(Device).all()
    db.close()
    return render_template("devices/list.html", devices=devices)


@devices_bp.route("/devices/new", methods=["GET", "POST"])
@login_required
def device_new():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        host = request.form.get("host", "").strip()
        ssh_user = request.form.get("ssh_user", "").strip()
        password = request.form.get("password", "").strip()
        model = request.form.get("model", "").strip()
        location = request.form.get("location", "").strip()

        if not name:
            error = "Nazwa nie może być pusta."
        elif not _valid_host(host):
            error = "Nieprawidłowy adres IP lub hostname."
        elif not ssh_user:
            error = "Użytkownik SSH nie może być pusty."
        elif len(password) < 4:
            error = "Hasło musi mieć min. 4 znaki."
        else:
            db = SessionLocal()
            device = Device(
                name=name,
                host=host,
                ssh_user=ssh_user,
                model=model or None,
                location=location or None,
                created_by_id=current_user.id,
            )
            device.ssh_password = password
            db.add(device)
            db.commit()
            db.close()
            return redirect(url_for("devices.device_list"))

    return render_template("devices/form.html", device=None, error=error)


@devices_bp.route("/devices/<int:device_id>")
@login_required
def device_detail(device_id):
    db = SessionLocal()
    device = db.get(Device, device_id)
    db.close()
    if not device:
        abort(404)
    return render_template("devices/detail.html", device=device)


@devices_bp.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
@login_required
def device_edit(device_id):
    db = SessionLocal()
    device = db.get(Device, device_id)
    if not device:
        db.close()
        abort(404)

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        host = request.form.get("host", "").strip()
        ssh_user = request.form.get("ssh_user", "").strip()
        password = request.form.get("password", "").strip()
        model = request.form.get("model", "").strip()
        location = request.form.get("location", "").strip()

        if not name:
            error = "Nazwa nie może być pusta."
        elif not _valid_host(host):
            error = "Nieprawidłowy adres IP lub hostname."
        elif not ssh_user:
            error = "Użytkownik SSH nie może być pusty."
        else:
            device.name = name
            device.host = host
            device.ssh_user = ssh_user
            device.model = model or None
            device.location = location or None
            if password:
                device.ssh_password = password
            db.commit()
            db.close()
            return redirect(url_for("devices.device_list"))

    db.close()
    return render_template("devices/form.html", device=device, error=error)


@devices_bp.route("/devices/<int:device_id>/delete", methods=["POST"])
@login_required
def device_delete(device_id):
    db = SessionLocal()
    device = db.get(Device, device_id)
    if not device:
        db.close()
        abort(404)
    db.delete(device)
    db.commit()
    db.close()
    return redirect(url_for("devices.device_list"))