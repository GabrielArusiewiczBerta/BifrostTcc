#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import re
import socket
import threading
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

def get_lan_ip():
    # IP local usado para acesso por outras maquinas da mesma rede
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None

def drain(stream):
    # Continua lendo a saida do processo. Se o pipe encher, o processo trava.
    for _ in stream:
        pass

def start_servers():
    setup_cloudflared()

    print("\n🚀 1. Iniciando o servidor web Django Bifröst...")
    # 0.0.0.0 aceita conexoes de outras maquinas (rede local) alem do tunel.
    # A saida do Django vai direto para este terminal (sem PIPE), para o
    # servidor nao travar quando o buffer do pipe encher.
    # DEBUG desligado (nao expor paginas de erro detalhadas na internet);
    # --insecure permite ao runserver servir o CSS com DEBUG desligado.
    django_env = {**os.environ, "BIFROST_DEBUG": "0"}
    django_cmd = [str(PYTHON_BIN), "manage.py", "runserver", "--insecure", "0.0.0.0:8000"]
    django_proc = subprocess.Popen(
        django_cmd,
        cwd=str(BASE_DIR),
        env=django_env,
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

    # O cloudflared continua escrevendo logs; sem ler, o pipe enche e o tunel trava.
    threading.Thread(target=drain, args=(cf_proc.stdout,), daemon=True).start()

    if not public_url:
        print("\n⚠️  Nao foi possivel obter o link publico do Cloudflare Tunnel em 30s.")
        print("    Verifique a conexao com a internet e tente novamente.")

    lan_ip = get_lan_ip()

    print("\n" + "=" * 65)
    print(" 🎉 SERVIDOR BIFRÖST NO AR!" if public_url else " ⚠️  SERVIDOR LOCAL NO AR (sem link publico)")
    print("=" * 65)
    if public_url:
        print(f"\n 🌐 LINK PÚBLICO (Acessível de qualquer computador/rede):")
        print(f"    👉  {public_url}\n")
    if lan_ip:
        print(f" 📡 Link na Rede Local (outros computadores no mesmo Wi-Fi/LAN):")
        print(f"    👉  http://{lan_ip}:8000\n")
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
