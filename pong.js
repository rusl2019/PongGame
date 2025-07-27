window.addEventListener("DOMContentLoaded", () => {
  // --- Elemen UI ---
  const lobby = document.getElementById("lobby");
  const gameArea = document.getElementById("game-area");
  const createGameBtn = document.getElementById("createGameBtn");
  const joinGameBtn = document.getElementById("joinGameBtn");
  const gameIdInput = document.getElementById("gameIdInput");
  const lobbyError = document.getElementById("lobbyError");
  const gameIdDisplay = document.getElementById("gameIdDisplay");
  const waitingMessage = document.getElementById("waitingMessage");
  const canvas = document.getElementById("pongCanvas");
  const ctx = canvas.getContext("2d");

  let websocket;

  function connectWebSocket() {
    websocket = new WebSocket("ws://localhost:6789/");

    // --- Event Listeners WebSocket ---
    websocket.onmessage = ({ data }) => {
      lobbyError.textContent = ""; // Clear any previous errors
      const event = JSON.parse(data);
      handleServerMessage(event);
    };

    websocket.onclose = () => {
      lobbyError.textContent = "Disconnected. Attempting to reconnect...";
      setTimeout(connectWebSocket, 2000); // Coba konek lagi setelah 2 detik
    };

    websocket.onerror = (error) => {
      lobbyError.textContent = "Cannot connect to server.";
    };
  }

  // --- Fungsi Logika UI ---
  function showLobby() {
    lobby.classList.remove("hidden");
    gameArea.classList.add("hidden");
  }

  function showGameArea() {
    lobby.classList.add("hidden");
    gameArea.classList.remove("hidden");
    resizeCanvas(); // Ensure canvas is resized
  }

  function resizeCanvas() {
    const container = document.getElementById("game-container");
    const aspectRatio = 4 / 3;
    const containerWidth = container.clientWidth || 800; // Fallback to 800px
    const containerHeight = container.clientHeight || 600; // Fallback to 600px

    let newWidth = containerWidth;
    let newHeight = newWidth / aspectRatio;

    if (newHeight > containerHeight) {
      newHeight = containerHeight;
      newWidth = newHeight * aspectRatio;
    }

    canvas.width = newWidth;
    canvas.height = newHeight;
  }

  // --- Penanganan Pesan Server ---
  function handleServerMessage(event) {
    try {
      const parsedEvent = event;
      switch (parsedEvent.type) {
        case "game_created":
          gameIdDisplay.textContent = parsedEvent.gameId;
          waitingMessage.style.display = "block";
          showGameArea();
          break;
        case "game_joined":
          gameIdDisplay.textContent = parsedEvent.gameId;
          showGameArea();
          break;
        case "game_start":
          waitingMessage.style.display = "none";
          break;
        case "update_state":
          draw(parsedEvent.state);
          break;
        case "error":
          lobbyError.textContent = parsedEvent.message;
          break;
        default:
          console.error("Unsupported event type:", parsedEvent.type);
      }
    } catch (error) {
      console.error(
        "Error parsing WebSocket message:",
        error,
        "Raw data:",
        event.data
      );
    }
  }

  // --- Fungsi Menggambar Game ---
  function draw(state) {
    const scaleX = canvas.width / 800;
    const scaleY = canvas.height / 600;

    if (!ctx) {
      console.error("Canvas context is not available");
      return;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";

    // Draw ball
    ctx.fillRect(
      state.ball.x * scaleX,
      state.ball.y * scaleY,
      15 * scaleX,
      15 * scaleY
    );

    // Draw paddles
    ctx.fillRect(
      state.paddles.player1.x * scaleX,
      state.paddles.player1.y * scaleY,
      20 * scaleX,
      100 * scaleY
    );
    ctx.fillRect(
      state.paddles.player2.x * scaleX,
      state.paddles.player2.y * scaleY,
      20 * scaleX,
      100 * scaleY
    );

    // Update score display
    const scoreElement = document.getElementById("score");
    if (scoreElement) {
      scoreElement.textContent = `${state.score.player1} - ${state.score.player2}`;
    } else {
      console.error("Score element not found");
    }
  }

  // --- Event Listeners Tombol & Input ---
  createGameBtn.addEventListener("click", () => {
    lobbyError.textContent = "";
    websocket.send(JSON.stringify({ action: "create" }));
  });

  joinGameBtn.addEventListener("click", () => {
    const gameId = gameIdInput.value.trim().toUpperCase();
    if (gameId) {
      lobbyError.textContent = "";
      websocket.send(JSON.stringify({ action: "join", gameId: gameId }));
    } else {
      lobbyError.textContent = "Please enter a Game ID.";
    }
  });

  document.addEventListener("keydown", (event) => {
    let direction = null;
    if (
      event.key === "w" ||
      event.key === "W" ||
      event.key === "j" ||
      event.key === "J" ||
      event.key === "ArrowUp"
    )
      direction = "up";
    else if (
      event.key === "s" ||
      event.key === "S" ||
      event.key === "l" ||
      event.key === "L" ||
      event.key === "ArrowDown"
    )
      direction = "down";

    if (direction) {
      websocket.send(JSON.stringify({ action: "move", direction: direction }));
    }
  });

  let lastSent = 0;
  const throttleMs = 50; // Send updates every 50ms

  canvas.addEventListener("mousemove", (event) => {
    const now = Date.now();
    if (now - lastSent < throttleMs) return; // Skip if too soon
    lastSent = now;

    const rect = canvas.getBoundingClientRect();
    const mouseY = event.clientY - rect.top;
    const scaleY = canvas.height / 600;
    const gameY = mouseY / scaleY;
    const paddleHeight = 100;
    const paddleY = gameY - paddleHeight / 2;

    websocket.send(
      JSON.stringify({
        action: "move",
        y: paddleY,
      })
    );
  });

  gameIdDisplay.addEventListener("click", () => {
    navigator.clipboard
      .writeText(gameIdDisplay.textContent)
      .then(() => alert("Game ID copied to clipboard!"))
      .catch((err) => console.error("Failed to copy: ", err));
  });

  window.addEventListener("resize", resizeCanvas);

  // --- Inisialisasi ---
  connectWebSocket();
  showLobby();
});
