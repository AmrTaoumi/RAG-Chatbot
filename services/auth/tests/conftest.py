import os

# main reads this at import time; set it before any test module imports main
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:8004,http://127.0.0.1:8004"
