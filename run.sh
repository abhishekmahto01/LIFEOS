#!/usr/bin/env bash

# ==============================================================================
# LifeOS - Unified Service Runner (Backend + Frontend)
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
VENV_DIR="${ROOT_DIR}/venv"

# Text styles
BOLD="\033[1m"
CYAN="\033[36m"
MAGENTA="\033[35m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${GREEN}⚡ Starting LifeOS Full Stack Application...${RESET}\n"

# Determine Python binary
if [ -f "${VENV_DIR}/bin/python" ]; then
    PYTHON_EXEC="${VENV_DIR}/bin/python"
    echo -e "${CYAN}[BACKEND]${RESET} Using virtualenv python: ${VENV_DIR}/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_EXEC="python3"
    echo -e "${CYAN}[BACKEND]${RESET} Using system python3: $(which python3)"
else
    PYTHON_EXEC="python"
    echo -e "${CYAN}[BACKEND]${RESET} Using python: $(which python)"
fi

# Track child PIDs
BACKEND_PID=""
FRONTEND_PID=""

# Cleanup function to terminate both processes on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down LifeOS services...${RESET}"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    # Give processes a moment to gracefully shutdown, then force kill if needed
    sleep 0.5
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -9 "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ All services stopped.${RESET}"
    exit 0
}

# Trap signals
trap cleanup SIGINT SIGTERM EXIT

# Start Backend
(
    cd "${BACKEND_DIR}" && "${PYTHON_EXEC}" app.py 2>&1 | while IFS= read -r line; do
        echo -e "${CYAN}[BACKEND]${RESET} ${line}"
    done
) &
BACKEND_PID=$!

# Start Frontend
(
    cd "${FRONTEND_DIR}" && npm run dev 2>&1 | while IFS= read -r line; do
        echo -e "${MAGENTA}[FRONTEND]${RESET} ${line}"
    done
) &
FRONTEND_PID=$!

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
