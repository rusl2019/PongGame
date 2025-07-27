#!/usr/bin/env python

import asyncio
import json
import logging
import random
import string
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

logging.basicConfig(level=logging.INFO)

# --- State & Konstanta Game ---
WIDTH, HEIGHT = 800, 600
PADDLE_HEIGHT = 100
PADDLE_WIDTH = 20

# --- Struktur Data Baru ---
GAME_ROOMS = {}  # Menyimpan state dari semua room aktif
CLIENTS = {}     # Menyimpan koneksi -> game_id

def create_new_game_state():
    """Membuat objek state baru untuk sebuah room."""
    return {
        "ball": {"x": WIDTH / 2, "y": HEIGHT / 2},
        "paddles": {
            "player1": {"x": 10, "y": HEIGHT / 2 - PADDLE_HEIGHT / 2},
            "player2": {"x": WIDTH - PADDLE_WIDTH - 10, "y": HEIGHT / 2 - PADDLE_HEIGHT / 2},
        },
        "score": {"player1": 0, "player2": 0},
        "ball_speed": {"x": 5, "y": 5},
        "players": {}, # Menyimpan websocket -> player_id (player1/player2)
        "loop_task": None # Untuk menyimpan task game loop
    }

def generate_game_id(length=5):
    """Membuat ID game acak."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def broadcast_to_room(game_id, message):
    """Mengirim pesan ke semua pemain dalam satu room."""
    if game_id in GAME_ROOMS:
        room = GAME_ROOMS[game_id]
        active_clients = [client for client in room["players"].keys()]
        if active_clients:
            tasks = [asyncio.create_task(client.send(message)) for client in active_clients]
            await asyncio.wait(tasks)

async def game_loop_for_room(game_id):
    """Loop yang berjalan khusus untuk satu room game."""
    room = GAME_ROOMS[game_id]
    logging.info(f"Starting game loop for room {game_id}")
    while len(room["players"]) == 2:
        state = room
        # Update posisi bola
        ball = state["ball"]
        speed = state["ball_speed"]
        ball["x"] += speed["x"]
        ball["y"] += speed["y"]

        # Logika tabrakan dan skor
        if ball["y"] <= 0 or ball["y"] >= HEIGHT - 15:
            speed["y"] *= -1
        p1 = state["paddles"]["player1"]
        p2 = state["paddles"]["player2"]
        if (
            speed["x"] < 0
            and p1["x"] <= ball["x"] <= p1["x"] + PADDLE_WIDTH
            and p1["y"] < ball["y"] < p1["y"] + PADDLE_HEIGHT
        ):
            speed["x"] *= -1.1
        if (
            speed["x"] > 0
            and p2["x"] <= ball["x"] <= p2["x"] + PADDLE_WIDTH
            and p2["y"] < ball["y"] < p2["y"] + PADDLE_HEIGHT
        ):
            speed["x"] *= -1.1
        if ball["x"] <= 0:
            state["score"]["player2"] += 1
            reset_ball(state)
        elif ball["x"] >= WIDTH:
            state["score"]["player1"] += 1
            reset_ball(state)

        # Remove non-serializable fields before sending
        state_to_send = {
            "ball": state["ball"],
            "paddles": state["paddles"],
            "score": state["score"],
            "ball_speed": state["ball_speed"]
        }
        message = json.dumps({"type": "update_state", "state": state_to_send})

        # Kirim update ke room
        await broadcast_to_room(game_id, message)
        await asyncio.sleep(1 / 60)
    logging.info(f"Stopping game loop for room {game_id} as a player left.")
    room["loop_task"] = None

def reset_ball(state):
    state["ball"] = {"x": WIDTH / 2, "y": HEIGHT / 2}
    state["ball_speed"]["x"] = 5 if state["ball_speed"]["x"] > 0 else -5
    state["ball_speed"]["y"] = 5 if state["ball_speed"]["y"] > 0 else -5

# --- Handler Utama (Dispatcher) ---
async def handler(websocket):
    logging.info(f"New connection: {websocket.remote_address}")
    CLIENTS[websocket] = None # Awalnya client belum masuk room manapun
    try:
        async for message in websocket:
            event = json.loads(message)
            action = event.get("action")
            
            if action == "create":
                game_id = generate_game_id()
                while game_id in GAME_ROOMS: game_id = generate_game_id() # Pastikan ID unik
                
                GAME_ROOMS[game_id] = create_new_game_state()
                GAME_ROOMS[game_id]["players"][websocket] = "player1"
                CLIENTS[websocket] = game_id
                
                logging.info(f"Player created game {game_id}")
                await websocket.send(json.dumps({"type": "game_created", "gameId": game_id}))

            elif action == "join":
                game_id = event.get("gameId")
                if game_id not in GAME_ROOMS:
                    await websocket.send(json.dumps({"type": "error", "message": "Game ID not found"}))
                    continue
                
                room = GAME_ROOMS[game_id]
                if len(room["players"]) >= 2:
                    await websocket.send(json.dumps({"type": "error", "message": "Game is full"}))
                    continue
                
                # Pemain kedua bergabung
                room["players"][websocket] = "player2"
                CLIENTS[websocket] = game_id
                logging.info(f"Player joined game {game_id}")
                await websocket.send(json.dumps({"type": "game_joined", "gameId": game_id}))
                
                # Beri tahu kedua pemain bahwa game dimulai
                await broadcast_to_room(game_id, json.dumps({"type": "game_start"}))
                
                # Mulai game loop karena sudah ada 2 pemain
                if room["loop_task"] is None:
                    room["loop_task"] = asyncio.create_task(game_loop_for_room(game_id))

            elif action == "move":
                game_id = CLIENTS.get(websocket)
                if game_id and game_id in GAME_ROOMS:
                    room = GAME_ROOMS[game_id]
                    player_id = room["players"].get(websocket)
                    if player_id:
                        paddle = room["paddles"][player_id]
                        y_position = event.get("y")
                        direction = event.get("direction")
                        if isinstance(y_position, (int, float)):
                            # Mouse control: set paddle position directly
                            paddle["y"] = max(0, min(y_position, HEIGHT - PADDLE_HEIGHT))
                        elif direction == "up" and paddle["y"] > 0:
                            # Keyboard control: move up
                            paddle["y"] -= 30
                        elif direction == "down" and paddle["y"] < HEIGHT - PADDLE_HEIGHT:
                            # Keyboard control: move down
                            paddle["y"] += 30
                        
    except ConnectionClosed:
        logging.info(f"Connection closed: {websocket.remote_address}")
    finally:
        game_id = CLIENTS.pop(websocket)
        if game_id and game_id in GAME_ROOMS:
            room = GAME_ROOMS[game_id]
            # Hapus pemain dari room
            if websocket in room["players"]:
                del room["players"][websocket]
                logging.info(f"Player removed from room {game_id}")
            
            # Jika room kosong, hapus room
            if not room["players"]:
                if room["loop_task"]: room["loop_task"].cancel() # Hentikan loop jika masih jalan
                del GAME_ROOMS[game_id]
                logging.info(f"Room {game_id} is empty and has been deleted.")

async def main():
    async with serve(handler, "localhost", 6789) as server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())