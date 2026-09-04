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
- **Run Automated Test Suite:**
  ```bash
  npm run test:backend
  # or: source venv/bin/activate && pytest
  ```

---

## 📚 Integration & Setup Guides

Comprehensive step-by-step guides for connecting social media platforms to the LifeOS Social Media Hub:

- **YouTube OAuth 2.0 & Publishing Setup**: [docs/YOUTUBE_OAUTH_SETUP.md](docs/YOUTUBE_OAUTH_SETUP.md) & [docs/YOUTUBE_PUBLISHING_GUIDE.md](docs/YOUTUBE_PUBLISHING_GUIDE.md)
- **Meta & Instagram Graph API Setup**: [docs/INSTAGRAM_SETUP_GUIDE.md](docs/INSTAGRAM_SETUP_GUIDE.md)
##another test file vommit
##weferniernen