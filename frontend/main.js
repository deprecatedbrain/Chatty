document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("composer");
  const input = document.getElementById("input");
  const messages = document.getElementById("messages");

  function appendMessage(text, cls = "bot") {
    const li = document.createElement("li");
    li.className = `message ${cls}`;
    li.textContent = text;
    messages.appendChild(li);
    messages.scrollTop = messages.scrollHeight;
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const val = input.value.trim();
    if (!val) return;
    appendMessage(val, "user");
    input.value = "";

    setTimeout(() => {
      appendMessage("Echo: " + val, "bot");
    }, 400);
  });
});

// Small accessibility helper: focus input when page is clicked
document.addEventListener("click", (e) => {
  const input = document.getElementById("input");
  if (input && !document.activeElement.isSameNode(input)) input.focus();
});
