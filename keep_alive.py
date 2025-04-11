from flask import Flask # type: ignore
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running smoothly!"

def run():
    print("🚀 Flask server starting on port 8080...", flush=True)
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
