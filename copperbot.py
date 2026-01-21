#!/usr/bin/env python3
"""
CopperHead Robot - Autonomous Snake game player.

Connects to a CopperHead server and plays the game using AI.
"""

import asyncio
import json
import argparse
import websockets
from collections import deque

# Game constants (must match server)
GRID_WIDTH = 30
GRID_HEIGHT = 20


class RobotPlayer:
    """Autonomous player that connects to CopperHead server and plays using AI."""
    
    def __init__(self, server_url: str, difficulty: int = 5, quiet: bool = False):
        self.server_url = server_url
        self.difficulty = max(1, min(10, difficulty))
        self.quiet = quiet
        self.player_id = None
        self.game_state = None
        self.running = False
        self.wins = 0
        self.games_played = 0
        self.room_id = None
    
    def log(self, msg: str):
        if not self.quiet:
            print(msg)
        
    async def connect(self):
        """Connect to the game server using auto-matchmaking."""
        # Use the /join endpoint for auto-matchmaking
        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        url = f"{base_url}/ws/join"
        
        try:
            self.log(f"Connecting to {url}...")
            self.ws = await websockets.connect(url)
            self.log(f"Connected! Waiting for player assignment...")
            return True
        except Exception as e:
            self.log(f"Connection failed: {e}")
            return False
    
    async def play(self):
        """Main game loop with auto-reconnect."""
        while True:
            if not await self.connect():
                self.log("Failed to connect to server. Retrying in 3 seconds...")
                await asyncio.sleep(3)
                continue
                
            self.running = True
            
            try:
                while self.running:
                    message = await self.ws.recv()
                    data = json.loads(message)
                    await self.handle_message(data)
            except websockets.ConnectionClosed:
                self.log("Connection closed. Reconnecting in 2 seconds...")
                await asyncio.sleep(2)
            except Exception as e:
                self.log(f"Error: {e}. Reconnecting in 2 seconds...")
                await asyncio.sleep(2)
            finally:
                self.running = False
            
    async def handle_message(self, data: dict):
        """Handle incoming server messages."""
        msg_type = data.get("type")
        
        if msg_type == "joined":
            # Server assigned us a player ID and room
            self.player_id = data.get("player_id")
            self.room_id = data.get("room_id")
            self.log(f"Joined Room {self.room_id} as Player {self.player_id}")
            
            # Send ready message
            await self.ws.send(json.dumps({
                "action": "ready",
                "mode": "two_player",
                "name": f"CopperBot L{self.difficulty}"
            }))
            self.log(f"Ready! Playing at difficulty {self.difficulty}")
        
        elif msg_type == "state":
            self.game_state = data.get("game")
            if self.game_state and self.game_state.get("running"):
                direction = self.calculate_move()
                if direction:
                    await self.ws.send(json.dumps({
                        "action": "move",
                        "direction": direction
                    }))
                    
        elif msg_type == "start":
            self.log("Game started!")
            
        elif msg_type == "gameover":
            self.games_played += 1
            winner = data.get("winner")
            if winner == self.player_id:
                self.wins += 1
                self.log(f"Won! ({self.wins}/{self.games_played} games)")
            elif winner:
                self.log(f"Lost! ({self.wins}/{self.games_played} games)")
            else:
                self.log(f"Draw! ({self.wins}/{self.games_played} games)")
            
            # Auto-ready for next game
            await asyncio.sleep(1)
            await self.ws.send(json.dumps({
                "action": "ready",
                "mode": "two_player",
                "name": f"CopperBot L{self.difficulty}"
            }))
            self.log("Ready for next game!")
            
        elif msg_type == "waiting":
            self.log("Waiting for opponent...")
    
    def calculate_move(self) -> str | None:
        """Calculate the best move using AI logic. Prioritizes survival."""
        if not self.game_state:
            return None
            
        snakes = self.game_state.get("snakes", {})
        my_snake = snakes.get(str(self.player_id))
        
        if not my_snake or not my_snake.get("body"):
            return None
            
        head = my_snake["body"][0]
        current_dir = my_snake.get("direction", "right")
        food = self.game_state.get("food")
        
        # Build set of dangerous positions (all snake bodies)
        dangerous = set()
        for snake_data in snakes.values():
            for segment in snake_data.get("body", []):
                dangerous.add((segment[0], segment[1]))
        
        # Possible moves
        directions = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0)
        }
        
        # Can't reverse
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
        
        def is_safe(x, y):
            """Check if position is safe (not wall, not snake)."""
            if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
                return False
            if (x, y) in dangerous:
                return False
            return True
        
        def count_safe_neighbors(x, y):
            """Count how many safe moves are available from a position."""
            count = 0
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = x + dx, y + dy
                if is_safe(nx, ny):
                    count += 1
            return count
        
        # First pass: find all safe moves
        safe_moves = []
        for direction, (dx, dy) in directions.items():
            if direction == opposites.get(current_dir):
                continue
            new_x = head[0] + dx
            new_y = head[1] + dy
            if is_safe(new_x, new_y):
                safe_moves.append({"direction": direction, "x": new_x, "y": new_y})
        
        # If no safe moves, pick any non-reversing move (we're doomed)
        if not safe_moves:
            for direction in directions:
                if direction != opposites.get(current_dir):
                    return direction
            return current_dir
        
        # Evaluate safe moves
        best_dir = None
        best_score = float('-inf')
        
        for move in safe_moves:
            score = 0
            new_x, new_y = move["x"], move["y"]
            
            # Big bonus for capturing food
            if food and new_x == food[0] and new_y == food[1]:
                score += 1000  # Always prioritize eating
            
            # Prioritize moves that don't trap us (have escape routes)
            escape_routes = count_safe_neighbors(new_x, new_y)
            score += escape_routes * 50  # Important but not more than food
            
            # Distance to food (closer is better)
            if food:
                food_dist = abs(new_x - food[0]) + abs(new_y - food[1])
                score += (GRID_WIDTH + GRID_HEIGHT - food_dist) * 10
            
            # Prefer staying away from edges
            edge_dist = min(new_x, GRID_WIDTH - 1 - new_x, 
                           new_y, GRID_HEIGHT - 1 - new_y)
            score += edge_dist * 5
            
            # Random factor based on difficulty (lower = more random)
            import random
            mistake_chance = (10 - self.difficulty) / 20
            if random.random() < mistake_chance:
                score -= random.randint(0, 30)
            
            if score > best_score:
                best_score = score
                best_dir = move["direction"]
        
        return best_dir


async def main():
    parser = argparse.ArgumentParser(description="CopperHead Robot Player")
    parser.add_argument("--server", "-s", default="ws://localhost:8000/ws/",
                        help="Server WebSocket URL (default: ws://localhost:8000/ws/)")
    parser.add_argument("--difficulty", "-d", type=int, default=5,
                        help="AI difficulty 1-10 (default: 5)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress output (for spawned bots)")
    args = parser.parse_args()
    
    robot = RobotPlayer(args.server, args.difficulty, quiet=args.quiet)
    
    if not args.quiet:
        print("CopperHead Robot Player")
        print(f"   Server: {args.server}")
        print(f"   Difficulty: {args.difficulty}")
        print()
    
    await robot.play()


if __name__ == "__main__":
    asyncio.run(main())
