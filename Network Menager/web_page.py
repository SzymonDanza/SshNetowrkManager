from flask import Flask, redirect, url_for

app = Flask(__name__)

@app.route("/")
def home():
    return "Welcome to the Home Page!"

@app.route("/<name>")
def page1(name):
    return f"Hello, {name}! This is Page 1."

@app.route("/admin")
def admin():
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run() 