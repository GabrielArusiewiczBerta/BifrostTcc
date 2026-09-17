# Bifröst — Multi-Chain Blockchain Interoperability API

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" />
  <img src="https://img.shields.io/badge/Django-4.2-green?logo=django" />
  <img src="https://img.shields.io/badge/Blockchain-Multi--Chain-purple" />
  <img src="https://img.shields.io/badge/License-Academic-lightgrey" />
</p>

A **Django-based web platform** that provides a unified, modular API for storing, retrieving, and migrating data across multiple blockchain networks — based on the **Bifröst Notary Scheme architecture** (Scheid et al., IEEE LCN 2019).

Supported networks:
- 🟡 **Bitcoin** (OP_RETURN, 80-byte limit)
- 🔵 **Ethereum** (Calldata / Smart Contracts)
- 🚀 **Stellar** (Memo_Text, 28-byte limit)
- ⚡ **EOS** (Action Memo)
- 🔗 **MultiChain** (Private Streams)
- 🗄️ **PostgreSQL** (Redundancy Mirror)
- 🛡️ **Rede Blockchain Brasil / RBB** (Hyperledger Besu)

---

## ✨ Features

- **Store** arbitrary text payloads on any supported blockchain.
- **Automatic fragmentation** of data across multiple chained transactions if the payload exceeds the blockchain's per-transaction limit (`multiple_tx`).
- **Client-side encryption** using PBKDF2 + SHA-256 with a random salt before data ever leaves your machine.
- **Retrieve** stored payloads by transaction hash, automatically reassembling fragmented multi-transaction data.
- **Migrate** stored data from one blockchain to another in a single operation.
- **REST API** endpoints for external integrations (`/api/store/`, `/api/retrieve/`, `/api/migrate/`, `/api/transactions/`).
- **Transaction Explorer** with full ledger history, encryption status, and hash chain visualization.
- **Public tunnel** via Cloudflare (`start_public_server.py`) — share a live HTTPS link from your local machine to anyone on any network.

---

## 🏗️ Project Structure

```
BifrostTcc/
├── bifrost_app/              # Django app (views, URLs, models)
│   ├── views.py              # All page views + REST API handlers
│   ├── urls.py               # URL routing
│   └── models.py             # Django ORM models
│
├── bifrost_project/          # Django project settings
│   ├── settings.py
│   └── urls.py
│
├── core_bifrost/             # Bifröst engine (framework-independent)
│   ├── api.py                # Main API: store(), retrieve(), migrate()
│   ├── blockchain.py         # Blockchain enum (BTC, ETH, Stellar, RBB…)
│   ├── crypto_utils.py       # PBKDF2/Salt encryption & decryption
│   ├── db_manager.py         # SQLite transaction ledger (thread-safe)
│   ├── custom_errors.py      # Typed error classes
│   └── adapters/             # One adapter module per blockchain
│       ├── base_adapter.py   # Abstract base with shared logic
│       ├── btc_adapter.py
│       ├── eth_adapter.py
│       ├── stellar_adapter.py
│       ├── eos_adapter.py
│       ├── postgres_adapter.py
│       ├── rbb_adapter.py
│       └── mc_adapter.py
│
├── templates/                # Django HTML templates (glassmorphic dark UI)
│   ├── base.html
│   ├── dashboard.html
│   ├── store.html
│   ├── retrieve.html
│   ├── migrate.html
│   └── explorer.html
│
├── static/css/style.css      # Design system (dark mode, glassmorphism)
├── manage.py                 # Django management entry point
├── start_public_server.py    # 🌍 One-command public HTTPS tunnel
└── requirements.txt          # Python dependencies
```

---

## ⚙️ Setup & Installation

### Prerequisites

- **Python 3.10 or newer** — [Download here](https://www.python.org/downloads/)
- **pip** (included with Python)
- **Git** (to clone the repository)

---

### 1. Clone the Repository

```bash
git clone https://github.com/GabrielArusiewiczBerta/BifrostTcc.git
cd BifrostTcc
```

---

### 2. Create a Virtual Environment

```bash
# Create the virtual environment
python3 -m venv venv

# Activate it:
# On Linux / macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install django
```

> **Optional** — For production deployments, also install:
> ```bash
> pip install gunicorn
> ```

---

### 4. Apply Database Migrations

```bash
python manage.py migrate
```

This creates the Django SQLite database (`db.sqlite3`) and auto-initializes the Bifröst transaction ledger (`bifrost_db.sqlite3`) with default credentials for all supported adapters.

---

## 🚀 Running the Application

### Local Development Server

```bash
python manage.py runserver
```

Open your browser at: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

### Access from Computers on the Same Network (Local Wi-Fi / LAN)

```bash
python manage.py runserver 0.0.0.0:8000
```

1. Find your local IP address:
   ```bash
   # Linux / macOS
   hostname -I | awk '{print $1}'
   ```
2. Other computers on the same network can access: `http://YOUR_LOCAL_IP:8000`

---

### 🌍 Public Access from Any Network (Cloudflare Tunnel)

This is the recommended way to share the running server with people on different networks — no router configuration, no port forwarding, **free**:

```bash
python start_public_server.py
```

The script will:
1. Start the Django server locally.
2. Download and launch **Cloudflare Tunnel** automatically (first run only).
3. Print a **public HTTPS link** like:

```
=================================================================
 🎉 SERVIDOR BIFRÖST PUBLICADO NA INTERNET COM SUCESSO!
=================================================================

 🌐 LINK PÚBLICO (Acessível de qualquer computador/rede):
    👉  https://xxxx-yyyy-zzzz.trycloudflare.com

 🏠 Link Local (No seu PC):
    👉  http://127.0.0.1:8000

=================================================================
```

Send that link to anyone — they can use the site directly in their browser!

Press `Ctrl+C` to stop the server and close the tunnel.

---

## 🌐 REST API Reference

The platform exposes JSON API endpoints for external integration or testing.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/store/` | Store a payload on a blockchain |
| `GET` | `/api/retrieve/?hash=TX_HASH` | Retrieve payload by transaction hash |
| `POST` | `/api/migrate/` | Migrate payload to another blockchain |
| `GET` | `/api/transactions/` | List all recorded transactions |

### Example: Store Data

```bash
curl -X POST http://localhost:8000/api/store/ \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "Hello, Blockchain!",
    "blockchain": "STELLAR",
    "password": "mysecretpassword",
    "multiple_tx": true
  }'
```

**Response:**
```json
{
  "status": "success",
  "hashes": ["a1b2c3d4e5f6..."],
  "blockchain": "STELLAR"
}
```

### Example: Retrieve Data

```bash
curl "http://localhost:8000/api/retrieve/?hash=a1b2c3d4e5f6...&password=mysecretpassword"
```

### Example: Migrate Data

```bash
curl -X POST http://localhost:8000/api/migrate/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_hash": "a1b2c3d4e5f6...",
    "target_blockchain": "ETHEREUM",
    "multiple_tx": true
  }'
```

---

## 🔐 How Security Works

1. If you provide a **password** when storing data, the payload is **encrypted on your machine** before being sent to the blockchain.
2. Encryption uses **PBKDF2-HMAC-SHA256** with 100,000 iterations and a random **16-byte salt**.
3. The salt is stored locally in the `bifrost_db.sqlite3` ledger alongside the transaction hash.
4. Only someone with the **original password** can decrypt and read the data.

> **Important:** The password is **never stored** anywhere. If you lose it, the data cannot be recovered.

---

## 🧩 Supported Blockchains & Limits

| Blockchain | Adapter | Max Payload/TX | Node Required |
|---|---|---|---|
| Rede Blockchain Brasil (RBB) | `rbb_adapter.py` | 512 bytes | RBB RPC Node |
| Bitcoin | `btc_adapter.py` | **80 bytes** | `bitcoind -testnet` |
| Ethereum | `eth_adapter.py` | 1024 bytes | Ganache / Infura |
| Stellar | `stellar_adapter.py` | **28 bytes** | Public Horizon API |
| EOS | `eos_adapter.py` | 256 bytes | Jungle Testnet |
| PostgreSQL | `postgres_adapter.py` | 4096 bytes | Local Docker |
| MultiChain | `mc_adapter.py` | 512 bytes | Local Docker |

> **Note:** The platform currently runs all adapters in **simulation mode** by default. This allows full testing of the API logic (fragmentation, encryption, chaining, migration) without requiring local blockchain nodes to be running. To connect to real testnets, configure the adapter credentials in the database.

---

## 📚 Academic References

This project is based on the following published research:

1. **E. J. Scheid, T. Hegnauer, B. Rodrigues, and B. Stiller**, *"Bifröst: a Modular Blockchain Interoperability API"*, in 2019 IEEE 44th Conference on Local Computer Networks (LCN), Osnabrück, Germany, 2019. **DOI:** 10.1109/LCN44214.2019.8990860

2. **E. J. Scheid, T. Hegnauer, B. Rodrigues, and B. Stiller**, *"Security and Standardization of a Notary-based Blockchain Interoperability API"*, 2021.

---

## 📄 License

This project is for **academic and research purposes**.
