"""CopperHead Server - 2-player Snake game server."""

import asyncio
import json
import os
import random
import logging
import subprocess
import sys
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("copperhead")

app = FastAPI(title="CopperHead Server")


@app.on_event("startup")
async def startup_event():
    logger.info("🐍 CopperHead Server started")
    logger.info(f"   Grid: {GRID_WIDTH}x{GRID_HEIGHT}, Tick rate: {TICK_RATE}s")
    
    # Detect Codespaces environment
    codespace_name = os.environ.get("CODESPACE_NAME")
    github_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    
    if codespace_name:
        ws_url = f"wss://{codespace_name}-8000.{github_domain}/ws/"
        logger.info("")
        logger.info("=" * 60)
        logger.info("📡 CLIENT CONNECTION URL:")
        logger.info(f"   {ws_url}")
        logger.info("")
        logger.info("⚠️  IMPORTANT: Make port 8000 public!")
        logger.info("   1. Open the Ports tab (bottom panel)")
        logger.info("   2. Right-click port 8000 → Port Visibility → Public")
        logger.info("=" * 60)
        logger.info("")
    else:
        logger.info("")
        logger.info("📡 Client connection URL: ws://localhost:8000/ws/")
        logger.info("")

GRID_WIDTH = 30
GRID_HEIGHT = 20
TICK_RATE = 0.15  # seconds between game updates


class Snake:
    def __init__(self, player_id: int, start_pos: tuple[int, int], direction: str):
        self.player_id = player_id
        self.body = [start_pos]
        self.direction = direction
        self.next_direction = direction
        self.input_queue: list[str] = []
        self.alive = True

    def head(self) -> tuple[int, int]:
        return self.body[0]

    def queue_direction(self, direction: str):
        """Queue a direction change. Only queue if it's valid relative to the last queued or current direction."""
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
        # Check against the last queued direction, or next_direction if queue is empty
        last_dir = self.input_queue[-1] if self.input_queue else self.next_direction
        if direction in opposites and opposites[direction] != last_dir and direction != last_dir:
            self.input_queue.append(direction)
            # Limit queue size to prevent flooding
            if len(self.input_queue) > 3:
                self.input_queue.pop(0)

    def process_input(self):
        """Process one input from the queue."""
        if self.input_queue:
            new_dir = self.input_queue.pop(0)
            opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
            if opposites.get(new_dir) != self.direction:
                self.next_direction = new_dir

    def get_next_head(self) -> tuple[int, int]:
        """Get where the head will be after processing input and moving."""
        # Peek at next direction (process input without consuming)
        next_dir = self.next_direction
        if self.input_queue:
            candidate = self.input_queue[0]
            opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
            if opposites.get(candidate) != self.direction:
                next_dir = candidate
        
        hx, hy = self.head()
        moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        dx, dy = moves[next_dir]
        return (hx + dx, hy + dy)

    def move(self, grow: bool = False):
        self.process_input()
        self.direction = self.next_direction
        hx, hy = self.head()
        moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        dx, dy = moves[self.direction]
        new_head = (hx + dx, hy + dy)
        self.body.insert(0, new_head)
        if not grow:
            self.body.pop()

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "body": self.body,
            "direction": self.direction,
            "alive": self.alive,
        }


class Game:
    def __init__(self, mode: str = "two_player"):
        self.mode = mode
        self.reset()

    def reset(self):
        self.snakes: dict[int, Snake] = {
            1: Snake(1, (5, GRID_HEIGHT // 2), "right"),
            2: Snake(2, (GRID_WIDTH - 6, GRID_HEIGHT // 2), "left"),
        }
        self.food: Optional[tuple[int, int]] = None
        self.running = False
        self.winner: Optional[int] = None
        self.spawn_food()

    def spawn_food(self):
        occupied = set()
        for snake in self.snakes.values():
            occupied.update(snake.body)
        available = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if (x, y) not in occupied
        ]
        if available:
            self.food = random.choice(available)

    def update(self):
        if not self.running:
            return

        for snake in self.snakes.values():
            if snake.alive:
                # Calculate where the snake will actually move to (accounting for input queue)
                next_head = snake.get_next_head()
                
                # Check if next position has food - eating makes snake grow
                grow = next_head == self.food if self.food else False
                snake.move(grow)
                if grow:
                    self.spawn_food()

        # Check collisions
        for snake in self.snakes.values():
            if not snake.alive:
                continue
            hx, hy = snake.head()
            # Wall collision
            if hx < 0 or hx >= GRID_WIDTH or hy < 0 or hy >= GRID_HEIGHT:
                snake.alive = False
            # Self collision
            if snake.head() in snake.body[1:]:
                snake.alive = False
            # Other snake collision
            for other in self.snakes.values():
                if other.player_id != snake.player_id:
                    if snake.head() in other.body:
                        snake.alive = False

        # Check game over
        alive_snakes = [s for s in self.snakes.values() if s.alive]
        if len(alive_snakes) <= 1:
            self.running = False
            if len(alive_snakes) == 1:
                self.winner = alive_snakes[0].player_id
            else:
                self.winner = None  # Draw

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "grid": {"width": GRID_WIDTH, "height": GRID_HEIGHT},
            "snakes": {pid: s.to_dict() for pid, s in self.snakes.items()},
            "food": self.food,
            "running": self.running,
            "winner": self.winner,
        }


class GameRoom:
    """Manages a single game room with two players and optional observers."""
    
    def __init__(self, room_id: int, room_manager: "RoomManager" = None):
        self.room_id = room_id
        self.room_manager = room_manager
        self.game = Game()
        self.connections: dict[int, WebSocket] = {}
        self.observers: list[WebSocket] = []
        self.ready: set[int] = set()
        self.game_task: Optional[asyncio.Task] = None
        self.pending_mode: str = "two_player"
        self.bot_process: Optional[subprocess.Popen] = None
        self.wins: dict[int, int] = {1: 0, 2: 0}
        self.names: dict[int, str] = {1: "Player 1", 2: "Player 2"}

    def is_empty(self) -> bool:
        return len(self.connections) == 0

    def is_waiting_for_player(self) -> bool:
        """Returns True if room has one player and space for another."""
        # Room is waiting if it has exactly 1 connection and game not running
        return len(self.connections) == 1 and not self.game.running

    def is_full(self) -> bool:
        return len(self.connections) >= 2

    def is_active(self) -> bool:
        return self.game.running

    def get_available_slot(self) -> Optional[int]:
        if 1 not in self.connections:
            return 1
        if 2 not in self.connections:
            return 2
        return None

    async def connect_player(self, player_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[player_id] = websocket
        logger.info(f"✅ [Room {self.room_id}] Player {player_id} connected ({len(self.connections)} player(s))")
        await self.broadcast_state()

    async def connect_observer(self, websocket: WebSocket):
        await websocket.accept()
        self.observers.append(websocket)
        logger.info(f"👁️ [Room {self.room_id}] Observer connected ({len(self.observers)} observer(s))")
        # Send current state to observer
        await websocket.send_json({
            "type": "observer_joined",
            "room_id": self.room_id,
            "game": self.game.to_dict(),
            "wins": self.wins,
            "names": self.names
        })

    def disconnect_player(self, player_id: int):
        self.connections.pop(player_id, None)
        self.ready.discard(player_id)
        if self.game_task:
            self.game_task.cancel()
            self.game_task = None
            logger.info(f"⏹️ [Room {self.room_id}] Game stopped (player disconnected)")
        self._stop_bot()
        self.game = Game()
        self.pending_mode = "two_player"
        self.wins = {1: 0, 2: 0}
        self.names = {1: "Player 1", 2: "Player 2"}
        logger.info(f"❌ [Room {self.room_id}] Player {player_id} disconnected ({len(self.connections)} player(s))")

    def _stop_bot(self):
        """Terminate the spawned CopperBot process if running."""
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=2)
                logger.info(f"🤖 [Room {self.room_id}] CopperBot process terminated")
            except Exception as e:
                logger.warning(f"⚠️ [Room {self.room_id}] Failed to terminate CopperBot: {e}")
            self.bot_process = None

    def disconnect_observer(self, websocket: WebSocket):
        if websocket in self.observers:
            self.observers.remove(websocket)
            logger.info(f"👁️ [Room {self.room_id}] Observer disconnected ({len(self.observers)} observer(s))")

    async def handle_message(self, player_id: int, data: dict):
        action = data.get("action")
        if action == "move" and self.game.running:
            direction = data.get("direction")
            if direction in ("up", "down", "left", "right"):
                if player_id in self.game.snakes:
                    self.game.snakes[player_id].queue_direction(direction)
        elif action == "ready":
            mode = data.get("mode", "two_player")
            # Only the first player sets the mode (not the bot joining later)
            if len(self.ready) == 0 and mode in ("two_player", "vs_ai"):
                self.pending_mode = mode
            
            name = data.get("name", f"Player {player_id}")
            self.names[player_id] = name
            
            if mode == "vs_ai" and not self.bot_process:
                ai_difficulty = data.get("ai_difficulty", 5)
                ai_difficulty = max(1, min(10, ai_difficulty))
                self._spawn_bot(ai_difficulty)
            
            self.ready.add(player_id)
            logger.info(f"👍 [Room {self.room_id}] {name} ready (mode: {self.pending_mode}, ready: {len(self.ready)})")
            
            # Start game when we have 2 ready players
            if len(self.ready) >= 2 and not self.game.running:
                await self.start_game()
            elif len(self.ready) < 2:
                if player_id in self.connections:
                    msg = "Launching CopperBot..." if self.pending_mode == "vs_ai" else "Waiting for Player 2..."
                    await self.connections[player_id].send_json({
                        "type": "waiting",
                        "message": msg
                    })

    def _spawn_bot(self, difficulty: int):
        """Spawn a CopperBot process to play against the human player."""
        self._stop_bot()  # Clean up any existing bot
        
        # Get the server URL
        codespace_name = os.environ.get("CODESPACE_NAME")
        github_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        
        if codespace_name:
            server_url = f"wss://{codespace_name}-8000.{github_domain}/ws/"
        else:
            server_url = "ws://localhost:8000/ws/"
        
        # Path to copperbot.py (same directory as main.py)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "copperbot.py")
        
        try:
            self.bot_process = subprocess.Popen(
                [sys.executable, script_path, "--server", server_url, "--difficulty", str(difficulty), "--quiet"],
                cwd=script_dir
            )
            logger.info(f"🤖 [Room {self.room_id}] CopperBot L{difficulty} spawned (PID: {self.bot_process.pid})")
        except Exception as e:
            logger.error(f"❌ [Room {self.room_id}] Failed to spawn CopperBot: {e}")

    async def start_game(self):
        self.game = Game(mode="two_player")
        self.game.running = True
        
        logger.info(f"🎮 [Room {self.room_id}] Game started! Mode: {self.pending_mode}")
        
        await self.broadcast({"type": "start", "mode": self.pending_mode, "room_id": self.room_id})
        self.game_task = asyncio.create_task(self.game_loop())
        
        # Notify all observers about updated room list
        if self.room_manager:
            await self.room_manager.broadcast_room_list_to_all_observers()

    async def game_loop(self):
        try:
            while self.game.running:
                self.game.update()
                await self.broadcast_state()
                if not self.game.running:
                    if self.game.winner:
                        self.wins[self.game.winner] += 1
                        logger.info(f"🏆 [Room {self.room_id}] Game over! Winner: {self.names.get(self.game.winner, 'Unknown')}")
                    else:
                        logger.info(f"🏁 [Room {self.room_id}] Game over! Draw.")
                    await self.broadcast({"type": "gameover", "winner": self.game.winner, "wins": self.wins, "names": self.names, "room_id": self.room_id})
                    self.ready.clear()
                    # Notify all observers about updated room list (game ended)
                    if self.room_manager:
                        await self.room_manager.broadcast_room_list_to_all_observers()
                await asyncio.sleep(TICK_RATE)
        except asyncio.CancelledError:
            pass

    async def broadcast_state(self):
        await self.broadcast({"type": "state", "game": self.game.to_dict(), "wins": self.wins, "names": self.names, "room_id": self.room_id})

    async def broadcast(self, message: dict):
        disconnected_players = []
        disconnected_observers = []
        
        # Send to players
        for pid, ws in self.connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected_players.append(pid)
        
        # Send to observers
        for ws in self.observers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected_observers.append(ws)
        
        for pid in disconnected_players:
            self.disconnect_player(pid)
        for ws in disconnected_observers:
            self.disconnect_observer(ws)


class RoomManager:
    """Manages multiple game rooms."""
    
    MAX_ROOMS = 10
    
    def __init__(self):
        self.rooms: dict[int, GameRoom] = {}
        self._matchmaking_lock = asyncio.Lock()
        self.lobby_observers: list[WebSocket] = []  # Observers waiting for a game
    
    async def find_or_create_room(self) -> tuple[Optional[GameRoom], int]:
        """Thread-safe matchmaking: find a waiting room or create a new one."""
        async with self._matchmaking_lock:
            # First, try to find a waiting room
            for room in self.rooms.values():
                if room.is_waiting_for_player():
                    player_id = room.get_available_slot() or 2
                    return room, player_id
            
            # No waiting room, create a new one
            for room_id in range(1, self.MAX_ROOMS + 1):
                if room_id not in self.rooms or self.rooms[room_id].is_empty():
                    room = GameRoom(room_id, self)
                    self.rooms[room_id] = room
                    logger.info(f"🏠 Room {room_id} created ({len([r for r in self.rooms.values() if not r.is_empty()])} active rooms)")
                    return room, 1
            
            return None, 0
    
    def find_waiting_room(self) -> Optional[GameRoom]:
        """Find a room waiting for a second player."""
        for room in self.rooms.values():
            if room.is_waiting_for_player():
                return room
        return None
    
    def find_active_room(self) -> Optional[GameRoom]:
        """Find any room with an active game (for observers)."""
        for room in self.rooms.values():
            if room.is_active():
                return room
        return None
    
    def get_active_rooms(self) -> list[GameRoom]:
        """Get all rooms with active games."""
        return [room for room in self.rooms.values() if room.is_active()]
    
    def get_room_by_id(self, room_id: int) -> Optional[GameRoom]:
        """Get a specific room by ID."""
        return self.rooms.get(room_id)
    
    async def broadcast_room_list_to_all_observers(self):
        """Send updated room list to all observers in all rooms."""
        rooms = self.get_active_rooms()
        room_data = [
            {
                "room_id": r.room_id,
                "names": r.names,
                "wins": r.wins
            }
            for r in rooms
        ]
        
        # Notify observers in rooms
        for room in self.rooms.values():
            for ws in room.observers[:]:  # Copy list to avoid modification during iteration
                try:
                    await ws.send_json({
                        "type": "room_list",
                        "rooms": room_data,
                        "current_room": room.room_id
                    })
                except Exception:
                    pass  # Observer disconnected, will be cleaned up later
        
        # Notify lobby observers and auto-join them to first active game
        if rooms and self.lobby_observers:
            first_room = rooms[0]
            room_data = [
                {
                    "room_id": r.room_id,
                    "names": r.names,
                    "wins": r.wins
                }
                for r in rooms
            ]
            for ws in self.lobby_observers[:]:
                try:
                    # Move from lobby to room
                    first_room.observers.append(ws)
                    await ws.send_json({
                        "type": "observer_joined",
                        "room_id": first_room.room_id,
                        "game": first_room.game.to_dict(),
                        "wins": first_room.wins,
                        "names": first_room.names
                    })
                    # Also send room list immediately
                    await ws.send_json({
                        "type": "room_list",
                        "rooms": room_data,
                        "current_room": first_room.room_id
                    })
                    logger.info(f"👁️ Lobby observer joined Room {first_room.room_id}")
                except Exception:
                    pass
            self.lobby_observers.clear()
        elif not rooms:
            # Send empty room list to lobby observers
            for ws in self.lobby_observers[:]:
                try:
                    await ws.send_json({
                        "type": "room_list",
                        "rooms": [],
                        "current_room": None
                    })
                except Exception:
                    pass
    
    def create_room(self) -> Optional[GameRoom]:
        """Create a new room if slots available."""
        for room_id in range(1, self.MAX_ROOMS + 1):
            if room_id not in self.rooms or self.rooms[room_id].is_empty():
                room = GameRoom(room_id, self)
                self.rooms[room_id] = room
                logger.info(f"🏠 Room {room_id} created ({len([r for r in self.rooms.values() if not r.is_empty()])} active rooms)")
                return room
        return None
    
    def spawn_bot_vs_bot(self, difficulty1: int = 5, difficulty2: int = 5):
        """Spawn two bots to play against each other for observers to watch."""
        codespace_name = os.environ.get("CODESPACE_NAME")
        github_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        
        if codespace_name:
            server_url = f"wss://{codespace_name}-8000.{github_domain}/ws/"
        else:
            server_url = "ws://localhost:8000/ws/"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "copperbot.py")
        
        try:
            # Spawn two bots with different difficulties for variety
            bot1 = subprocess.Popen(
                [sys.executable, script_path, "--server", server_url, "--difficulty", str(difficulty1), "--quiet"],
                cwd=script_dir
            )
            bot2 = subprocess.Popen(
                [sys.executable, script_path, "--server", server_url, "--difficulty", str(difficulty2), "--quiet"],
                cwd=script_dir
            )
            logger.info(f"🤖 Spawned bot-vs-bot match: CopperBot L{difficulty1} (PID: {bot1.pid}) vs CopperBot L{difficulty2} (PID: {bot2.pid})")
            return bot1, bot2
        except Exception as e:
            logger.error(f"❌ Failed to spawn bot-vs-bot match: {e}")
            return None, None
    
    def get_room(self, room_id: int) -> Optional[GameRoom]:
        return self.rooms.get(room_id)
    
    def cleanup_empty_rooms(self):
        """Remove empty rooms."""
        empty_rooms = [rid for rid, room in self.rooms.items() if room.is_empty()]
        for rid in empty_rooms:
            del self.rooms[rid]
            logger.info(f"🧹 Room {rid} cleaned up")
    
    def get_status(self) -> dict:
        """Get status of all rooms."""
        return {
            "total_rooms": len(self.rooms),
            "rooms": [
                {
                    "room_id": room.room_id,
                    "players": list(room.connections.keys()),
                    "observers": len(room.observers),
                    "game_running": room.game.running,
                    "waiting_for_player": room.is_waiting_for_player()
                }
                for room in self.rooms.values()
                if not room.is_empty()
            ]
        }


room_manager = RoomManager()


@app.websocket("/ws/join")
async def join_game(websocket: WebSocket):
    """Auto-matchmaking: join a waiting game or create a new one."""
    # Use thread-safe matchmaking
    room, player_id = await room_manager.find_or_create_room()
    
    if not room:
        await websocket.close(code=4002, reason="Server full - no room available")
        return
    
    await room.connect_player(player_id, websocket)
    
    # Send player their assignment
    await websocket.send_json({
        "type": "joined",
        "room_id": room.room_id,
        "player_id": player_id
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            await room.handle_message(player_id, data)
    except WebSocketDisconnect:
        room.disconnect_player(player_id)
        room_manager.cleanup_empty_rooms()


@app.websocket("/ws/observe")
async def observe_game(websocket: WebSocket):
    """Observe an active game. Supports switching rooms via messages."""
    await websocket.accept()
    
    room = room_manager.find_active_room()
    current_room = room
    in_lobby = False
    
    if not room:
        # No active games - spawn two bots to play for the observer
        await websocket.send_json({
            "type": "observer_lobby",
            "message": "No active games. Launching bot-vs-bot match..."
        })
        logger.info(f"👁️ Observer joined - spawning bot-vs-bot match")
        
        # Spawn bots with random difficulties for variety
        import random
        d1 = random.randint(3, 8)
        d2 = random.randint(3, 8)
        room_manager.spawn_bot_vs_bot(d1, d2)
        
        # Put observer in lobby - they'll be moved to the room once bots connect
        room_manager.lobby_observers.append(websocket)
        in_lobby = True
    else:
        room.observers.append(websocket)
        await websocket.send_json({
            "type": "observer_joined",
            "room_id": room.room_id,
            "game": room.game.to_dict(),
            "wins": room.wins,
            "names": room.names
        })
        logger.info(f"👁️ [Room {room.room_id}] Observer connected ({len(room.observers)} observer(s))")
    
    try:
        while True:
            # Handle observer commands (room switching)
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                action = data.get("action")
                
                if action == "switch_room" and current_room:
                    target_room_id = data.get("room_id")
                    target_room = room_manager.get_room_by_id(target_room_id)
                    
                    if target_room and target_room.is_active():
                        # Disconnect from current room
                        current_room.disconnect_observer(websocket)
                        # Connect to new room
                        current_room = target_room
                        current_room.observers.append(websocket)
                        in_lobby = False
                        await websocket.send_json({
                            "type": "observer_joined",
                            "room_id": current_room.room_id,
                            "game": current_room.game.to_dict(),
                            "wins": current_room.wins,
                            "names": current_room.names
                        })
                        logger.info(f"👁️ Observer switched to Room {target_room_id}")
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Room {target_room_id} not available"
                        })
                
                elif action == "get_rooms":
                    # Send list of active rooms
                    rooms = room_manager.get_active_rooms()
                    await websocket.send_json({
                        "type": "room_list",
                        "rooms": [
                            {
                                "room_id": r.room_id,
                                "names": r.names,
                                "wins": r.wins
                            }
                            for r in rooms
                        ],
                        "current_room": current_room.room_id if current_room else None
                    })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        if in_lobby:
            if websocket in room_manager.lobby_observers:
                room_manager.lobby_observers.remove(websocket)
            logger.info(f"👁️ Observer left lobby")
        elif current_room:
            current_room.disconnect_observer(websocket)


# Legacy endpoint for backward compatibility
@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    """Legacy endpoint - redirects to join."""
    if player_id not in (1, 2):
        await websocket.close(code=4000, reason="Invalid player_id. Use /ws/join instead.")
        return
    
    # Find or create a room
    room = None
    if player_id == 2:
        room = room_manager.find_waiting_room()
    
    if not room:
        room = room_manager.create_room()
        if not room:
            await websocket.close(code=4002, reason="Server full")
            return
        player_id = 1  # Override to player 1 for new room
    else:
        player_id = room.get_available_slot() or 2
    
    await room.connect_player(player_id, websocket)
    await websocket.send_json({
        "type": "joined",
        "room_id": room.room_id,
        "player_id": player_id
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            await room.handle_message(player_id, data)
    except WebSocketDisconnect:
        room.disconnect_player(player_id)
        room_manager.cleanup_empty_rooms()


@app.get("/")
async def root():
    return {"name": "CopperHead Server", "status": "running"}


@app.get("/status")
async def status():
    return room_manager.get_status()


@app.get("/rooms/active")
async def active_rooms():
    """Get list of active rooms for observers."""
    rooms = room_manager.get_active_rooms()
    return {
        "rooms": [
            {
                "room_id": room.room_id,
                "names": room.names,
                "wins": room.wins
            }
            for room in rooms
        ]
    }
