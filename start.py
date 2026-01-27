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

def update_readme_with_url(ws_url):
    """Update README.md with the actual WebSocket URL for this Codespace."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.join(script_dir, "README.md")
    
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if there's already a connection info section, replace it
        marker_start = "<!-- CODESPACE_CONNECTION_START -->"
        marker_end = "<!-- CODESPACE_CONNECTION_END -->"
        
        connection_block = f"""{marker_start}
## 🎮 Connect Now!

**Your Server URL:**
```
{ws_url}
```

1. Open the client: **https://revodavid.github.io/copperhead-client/**
2. Paste the Server URL above into the client
3. ⚠️ Make sure port 8000 is **Public** (Ports tab → right-click → Port Visibility → Public)

{marker_end}"""
        
        if marker_start in content:
            # Replace existing block
            import re
            pattern = f"{marker_start}.*?{marker_end}"
            content = re.sub(pattern, connection_block, content, flags=re.DOTALL)
        else:
            # Insert after the first heading line
            lines = content.split("\n")
            insert_idx = 1  # After first line
            for i, line in enumerate(lines):
                if line.startswith("# "):
                    insert_idx = i + 1
                    break
            lines.insert(insert_idx, "\n" + connection_block + "\n")
            content = "\n".join(lines)
        
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"{GREEN}✓ Updated README.md with your connection URL{RESET}")
        
    except Exception as e:
        # Don't fail startup if README update fails
        print(f"{YELLOW}Note: Could not update README.md: {e}{RESET}")

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
    
    # In Codespaces, update README.md so the URL is visible in the Explorer
    if is_codespace:
        update_readme_with_url(ws_url)
    
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
