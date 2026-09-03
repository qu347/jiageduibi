from threading import Lock


# OpenCLI controls one logged-in browser window, so all collection modes share it.
BROWSER_AUTOMATION_LOCK = Lock()
