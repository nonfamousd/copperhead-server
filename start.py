#!/usr/bin/env python3
"""
CopperHead Server Launcher

This script starts the CopperHead server and displays connection information
prominently for beginners. It also provides a direct link to the client.
"""

import os
import sys
import subprocess
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ANSI colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    """Print a welcome banner."""
    print()
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}{BOLD}       🐍 COPPERHEAD SNAKE GAME SERVER 🐍{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print()

def get_connection_info():
    """Get the WebSocket URL based on environment."""
    codespace_name = os.environ.get("CODESPACE_NAME")
    github_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    
    if codespace_name:
        ws_url = f"wss://{codespace_name}-8000.{github_domain}/ws/"
        is_codespace = True
    else:
        ws_url = "ws://localhost:8000/ws/"
        is_codespace = False
    
    return ws_url, is_codespace

def print_connection_instructions(ws_url, is_codespace):
    """Print connection instructions for players."""
    client_url = "https://revodavid.github.io/copperhead-client/"
    
    print(f"{CYAN}📡 HOW TO PLAY:{RESET}")
    print()
    print(f"   {BOLD}Step 1:{RESET} Open the game client in your browser:")
    print(f"          {YELLOW}{client_url}{RESET}")
    print()
    print(f"   {BOLD}Step 2:{RESET} Paste this Server URL into the client:")
    print()
    print(f"          {GREEN}{BOLD}{ws_url}{RESET}")
    print()
    
    if is_codespace:
        print(f"   {BOLD}Step 3:{RESET} {YELLOW}⚠️  IMPORTANT - Make your port PUBLIC:{RESET}")
        print(f"          • Click the {BOLD}Ports{RESET} tab in the bottom panel")
        print(f"          • Right-click on port {BOLD}8000{RESET}")
        print(f"          • Select {BOLD}Port Visibility → Public{RESET}")
        print()
    
    print(f"{GREEN}{'='*60}{RESET}")
    print()

def main():
    """Main entry point."""
    print_banner()
    
    ws_url, is_codespace = get_connection_info()
    print_connection_instructions(ws_url, is_codespace)
    
    print(f"Starting server... (Press Ctrl+C to stop)")
    print()
    
    # Pass through any command-line arguments to main.py
    # Set env var to suppress duplicate connection info from main.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "main.py")
    
    env = os.environ.copy()
    env["COPPERHEAD_QUIET_STARTUP"] = "1"
    
    args = [sys.executable, main_script] + sys.argv[1:]
    
    try:
        subprocess.run(args, env=env)
    except KeyboardInterrupt:
        print()
        print(f"{YELLOW}Server stopped.{RESET}")

if __name__ == "__main__":
    main()
