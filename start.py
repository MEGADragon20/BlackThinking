# run app.py after starting venv in terminal
import os

os.system("sudo docker run --name redis-local -p 6379:6379 -d redis")
os.system("source .venv/bin/activate")
os.system("python app.py")
