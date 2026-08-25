# LIFEOS

Unified Full Stack Management System.

## 🚀 Quick Start (Run Frontend & Backend with One Command)

From the project root directory (`LIFEOS`), you can start both the Flask backend and React/Vite frontend using any of the following options:

### Option 1: Using npm (Recommended)
```bash
npm run dev
```
*(or `npm start`)*

### Option 2: Using the Shell Script
```bash
./run.sh
```

### Option 3: Using Make
```bash
make dev
```

---

## 🛠 Project Structure & Available Scripts

```text
LIFEOS/
├── backend/          # Flask REST API (Port 5000)
├── frontend/         # React + Vite Client (Port 5173)
├── venv/             # Python Virtual Environment
├── package.json      # Unified project orchestrator
├── run.sh            # Standalone bash runner
└── Makefile          # Make shortcuts
```

### Individual Service Scripts

- **Run only Backend:**
  ```bash
  npm run backend
  ```
- **Run only Frontend:**
  ```bash
  npm run frontend
  ```
- **Install All Dependencies:**
  ```bash
  npm run install:all
  ```
- **Build Frontend:**
  ```bash
  npm run build:frontend
  ```

  - **Build Frontend:**
  ```bash
  npm run build:frontend
  ```