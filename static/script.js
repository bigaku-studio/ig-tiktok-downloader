const form = document.getElementById("download-form");
const urlInput = document.getElementById("url-input");
const button = document.getElementById("download-btn");
const btnLabel = button.querySelector(".btn-label");
const spinner = button.querySelector(".spinner");
const status = document.getElementById("status");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;

  setLoading(true);
  setStatus("", "");

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Unbekannter Fehler beim Download.");
    }

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "download";

    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);

    setStatus("success", "Download abgeschlossen ✔");
    urlInput.value = "";
  } catch (err) {
    setStatus("error", err.message);
  } finally {
    setLoading(false);
  }
});

function setLoading(loading) {
  button.disabled = loading;
  btnLabel.textContent = loading ? "Lädt..." : "Herunterladen";
  spinner.hidden = !loading;
}

function setStatus(type, message) {
  status.className = type ? `status ${type}` : "status";
  status.textContent = message;
}
