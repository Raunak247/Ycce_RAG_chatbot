const chatWindow = document.getElementById("chat-window");
const form = document.getElementById("composer-form");
const input = document.getElementById("composer-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat");
const statusPill = document.getElementById("status-pill");
const tpl = document.getElementById("message-template");

const STORAGE_KEY = "ycce-chat-history-v1";
let isBusy = false;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderBubbleText(text) {
  const escaped = escapeHtml(text || "");
  const withLinks = escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
  return withLinks.replace(/\n/g, "<br>");
}

function saveHistory() {
  const history = [...chatWindow.querySelectorAll(".message")].map((node) => ({
    role: node.classList.contains("user") ? "user" : "assistant",
    text: node.querySelector(".bubble")?.textContent || "",
    meta: node.querySelector(".meta")?.textContent || "",
  }));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

function loadHistory() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    addMessage(
      "assistant",
      "Hi, I am your YCCE Smart Assistant. Ask me anything about YCCE and I will answer from your indexed knowledge base.",
      "Assistant"
    );
    saveHistory();
    return;
  }

  try {
    const history = JSON.parse(raw);
    history.forEach((m) => addMessage(m.role, m.text, m.meta || (m.role === "user" ? "You" : "Assistant")));
    scrollToBottom();
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function addMessage(role, text, metaLabel) {
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.classList.add(role);

  const avatar = node.querySelector(".avatar");
  avatar.textContent = role === "user" ? "YOU" : "AI";

  const meta = node.querySelector(".meta");
  meta.textContent = metaLabel || (role === "user" ? "You" : "Assistant");

  const bubble = node.querySelector(".bubble");
  bubble.innerHTML = renderBubbleText(text);

  chatWindow.appendChild(node);
  return node;
}

function addTypingIndicator() {
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.classList.add("assistant");
  node.querySelector(".avatar").textContent = "AI";
  node.querySelector(".meta").textContent = "Assistant";
  node.querySelector(".bubble").innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
  chatWindow.appendChild(node);
  return node;
}

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function autoresize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 200)}px`;
}

async function sendMessage(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }

  return data;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isBusy) return;

  const message = input.value.trim();
  if (!message) return;

  isBusy = true;
  statusPill.textContent = "Thinking";
  statusPill.style.background = "#fff7ed";
  statusPill.style.borderColor = "#fed7aa";
  statusPill.style.color = "#9a3412";

  addMessage("user", message, "You");
  saveHistory();
  input.value = "";
  autoresize();
  scrollToBottom();

  const typingNode = addTypingIndicator();
  scrollToBottom();

  sendBtn.disabled = true;

  try {
    const data = await sendMessage(message);
    typingNode.remove();
    const confidence = typeof data.confidence === "number" ? ` | confidence ${data.confidence.toFixed(2)}` : "";
    addMessage("assistant", data.answer || "No answer generated.", `Assistant${confidence}`);
    saveHistory();
  } catch (err) {
    typingNode.remove();
    addMessage("assistant", `I hit an error: ${err.message}`, "Assistant");
    saveHistory();
  } finally {
    sendBtn.disabled = false;
    isBusy = false;
    statusPill.textContent = "Ready";
    statusPill.style.background = "#ecfdf5";
    statusPill.style.borderColor = "#b7f2db";
    statusPill.style.color = "#047857";
    scrollToBottom();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", autoresize);

newChatBtn.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  chatWindow.innerHTML = "";
  addMessage(
    "assistant",
    "New chat started. Ask your next YCCE question.",
    "Assistant"
  );
  saveHistory();
  scrollToBottom();
});

loadHistory();
autoresize();
scrollToBottom();
