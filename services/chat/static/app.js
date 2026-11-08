const form = document.getElementById("ask-form");
const button = document.getElementById("ask-button");
const input = document.getElementById("question");
const status = document.getElementById("status");
const answer = document.getElementById("answer");
const sources = document.getElementById("sources");

const ERRORS = { 502: "The language model is unavailable.", 503: "The search service is unavailable." };

form.addEventListener("submit", async (event) => {
  event.preventDefault();               // stop the page reloading
  button.disabled = true;               // no double clicks: each one would spend LLM quota
  status.textContent = "Searching...";
  answer.textContent = "";
  sources.replaceChildren();            // clear the old sources

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: input.value.trim() }),
    });
    if (!response.ok) throw new Error(ERRORS[response.status] || `Error ${response.status}`);

    const data = await response.json();
    status.textContent = "";
    answer.textContent = data.answer;   

    for (const c of data.citations) {
      const link = document.createElement("a");
      link.href = `${c.url}#page=${c.page}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `${c.title}, PDF page ${c.page}`;
      const item = document.createElement("li");
      item.append(link);
      sources.append(item);
    }
  } catch (err) {
    status.textContent = err.message;
  } finally {
    button.disabled = false;
  }
});