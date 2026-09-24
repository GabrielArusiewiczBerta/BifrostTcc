# NodeConnect — Multi-Chain Blockchain Interoperability Platform

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" />
  <img src="https://img.shields.io/badge/Django-4.2-green?logo=django" />
  <img src="https://img.shields.io/badge/Blockchain-Multi--Chain-purple" />
  <img src="https://img.shields.io/badge/License-Academic-lightgrey" />
</p>

**NodeConnect** is a Django-based web platform that provides a unified, modular API for storing, retrieving, and migrating data across multiple blockchain networks — built on the **Bifröst Notary Scheme architecture** (Scheid et al., IEEE LCN 2019).

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
- **Password encryption** performed on the server (PBKDF2-derived key with a random salt) before the payload is written to the adapter. It is not client-side encryption: the server sees the password and the plaintext.
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
├── requirements.txt          # Python dependencies
├── manage.py                 # Django management entry point
├── start_public_server.py    # 🌍 One-command public HTTPS tunnel
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
pip install -r requirements.txt
```

> **Optional** — For production deployments, also install:
> ```bash
> pip install gunicorn
> ```

---

### 4. Apply Database Migrations

```bash
python manage.py migrate
python manage.py create_admin   # optional: administrator account
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
 🎉 SERVIDOR NODECONNECT PUBLICADO NA INTERNET COM SUCESSO!
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

## 👤 Accounts, API keys and accounting

- Register at `/register/`; every account has its own ledger (users never see each other's transactions).
- **Account page** (`/account/`): generate a personal API key (shown once, stored hashed) and see your request usage.
- **Administrator**: create one with `python manage.py create_admin` (random password printed once; `--username`, `--password`, `--reset` available). The admin area `/painel-admin/` ranks blockchains by estimated spend, with totals per period, per-user ranking, transactions and volume. Django's own admin is at `/admin/`.
- Every web and API request is logged (`RequestLog`); store/migrate operations also record transactions, bytes and estimated cost.

## 🧮 Cost shown before sending

The **Store** and **Migrate** forms show the estimated cost live, before anything is written: price in the network's token and in USD, number of transactions, bytes after encryption, and the cheapest alternative for that payload. The send button shows the price and is disabled when the data does not fit without fragmentation. API clients can call `POST /api/estimate/` (and `store` returns `estimated_cost`).

Estimates use closed-form formulas: Ethereum gas (EIP-2028 + EIP-7623 floor), Bitcoin OP_RETURN vsize, Stellar per-operation fee, exact Fernet size overhead and fragmentation. Results are mainnet-equivalent; gas price, fee rate and token prices are reference values, not live quotes. Formulas are documented in `core_bifrost/costs.py`.

## 🌐 REST API Reference

All endpoints require `Authorization: Bearer <your API key>`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/store/` | Store a payload on a blockchain |
| `GET` / `POST` | `/api/retrieve/?hash=TX_HASH` | Retrieve payload by transaction hash (password via `X-Bifrost-Password` header or POST body, never in the URL) |
| `POST` | `/api/migrate/` | Migrate payload to another blockchain |
| `GET` | `/api/transactions/` | List your recorded transactions |
| `POST` | `/api/estimate/` | Estimate the cost of a payload on every network before sending |

### Example: Store Data

```bash
curl -X POST http://localhost:8000/api/store/ \
  -H "Authorization: Bearer $BIFROST_KEY" \
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
curl -H "Authorization: Bearer $BIFROST_KEY" \
  -H "X-Bifrost-Password: mysecretpassword" \
  "http://localhost:8000/api/retrieve/?hash=a1b2c3d4e5f6..."
```

### Example: Migrate Data

```bash
curl -X POST http://localhost:8000/api/migrate/ \
  -H "Authorization: Bearer $BIFROST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "source_hash": "a1b2c3d4e5f6...",
    "target_blockchain": "ETHEREUM",
    "multiple_tx": true
  }'
```

---

## 🔐 How Security Works

1. If you provide a **password** when storing data, the payload is **encrypted on the server** before being written to the blockchain adapter.
2. Encryption uses **Fernet** (AES-128-CBC + HMAC). Two keys are derived with **PBKDF2-HMAC-SHA256** (100,000 iterations, random **16-byte salt**): one to verify the password, one to encrypt.
3. The salt and a SHA-256 password verifier are stored in the local ledger (`bifrost_db.sqlite3`); they are never returned by the API.
4. A wrong password raises an explicit error (HTTP 403 in the API). Migration preserves the salt and verifier, so migrated data stays readable with the original password.

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

> **Note:** All adapters currently run in **simulation mode**: payloads are kept in the local SQLite ledger (`sim_storage` table) and no real network is called. The UI marks every network as "Simulado". HYPERLEDGER and IOTA are in the enum but have no adapter yet. This allows full testing of the API logic (fragmentation, encryption, chaining, migration) without requiring local blockchain nodes to be running. To connect to real testnets, configure the adapter credentials in the database.

---

## 📚 Academic References

This project is based on the following published research:

1. **E. J. Scheid, T. Hegnauer, B. Rodrigues, and B. Stiller**, *"Bifröst: a Modular Blockchain Interoperability API"*, in 2019 IEEE 44th Conference on Local Computer Networks (LCN), Osnabrück, Germany, 2019. **DOI:** 10.1109/LCN44214.2019.8990860

2. **E. J. Scheid, T. Hegnauer, B. Rodrigues, and B. Stiller**, *"Security and Standardization of a Notary-based Blockchain Interoperability API"*, 2021.

---

## 📄 License

This project is for **academic and research purposes**.
