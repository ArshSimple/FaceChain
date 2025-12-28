import webbrowser
from threading import Timer
from app import app  # your Flask app

# Open browser after server starts
def open_browser():
    webbrowser.open("http://127.0.0.1:5000/upload.html")

# Start a timer to open the browser shortly after server launch
Timer(1, open_browser).start()

# Run Flask server
app.run(debug=True)
