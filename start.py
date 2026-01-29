# run app.py after starting venv in terminal
import os
os.system("sudo docker rm -f redis-local")
os.system("sudo docker run --name redis-local -p 6379:6379 -d redis")
os.system("python3 app.py")