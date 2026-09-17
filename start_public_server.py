#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import re
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "cloudflared"
PYTHON_BIN = Path("/home/temp/Django-website-template/venv/bin/python")

if not PYTHON_BIN.exists():
    PYTHON_BIN = Path(sys.executable)

def setup_cloudflared():
    if not CLOUDFLARED_BIN.exists():
        print("⚡ Baixando o Cloudflare Tunnel (cloudflared)...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        urllib.request.urlretrieve(url, CLOUDFLARED_BIN)
        os.chmod(CLOUDFLARED_BIN, 0o755)
        print("✅ Cloudflare Tunnel instalado com sucesso!")

def start_servers():
    setup_cloudflared()
    
    print("\n🚀 1. Iniciando o servidor web Django Bifröst...")
    django_cmd = [str(PYTHON_BIN), "manage.py", "runserver", "127.0.0.1:8000"]
    django_proc = subprocess.Popen(
        django_cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    time.sleep(2)
    
    print("🌍 2. Gerando link público seguro com Cloudflare Tunnel...")
    cf_cmd = [str(CLOUDFLARED_BIN), "tunnel", "--url", "http://127.0.0.1:8000"]
    cf_proc = subprocess.Popen(
        cf_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    public_url = None
    start_time = time.time()
    
    while time.time() - start_time < 30:
        line = cf_proc.stdout.readline()
        if not line:
            break
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match:
            public_url = match.group(0)
            break
            
    print("\n" + "=" * 65)
    print(" 🎉 SERVIDOR BIFRÖST PUBLICADO NA INTERNET COM SUCESSO!")
    print("=" * 65)
    print(f"\n 🌐 LINK PÚBLICO (Acessível de qualquer computador/rede):")
    print(f"    👉  {public_url}\n")
    print(f" 🏠 Link Local (No seu PC):")
    print(f"    👉  http://127.0.0.1:8000\n")
    print("=" * 65)
    print(" Pressione Ctrl+C para encerrar o servidor e o túnel público.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Encerrando servidor e túnel público...")
        django_proc.terminate()
        cf_proc.terminate()
        print("👋 Até logo!")

if __name__ == "__main__":
    start_servers()
