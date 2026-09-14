const commandBar = document.querySelector("[data-copy]");

if (commandBar) {
  const copyLabel = commandBar.querySelector(".copy-label");
  const originalLabel = copyLabel.textContent;

  commandBar.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(commandBar.dataset.copy);
      copyLabel.textContent = "Copied";
      window.setTimeout(() => {
        copyLabel.textContent = originalLabel;
      }, 1800);
    } catch {
      copyLabel.textContent = "Select command";
      window.setTimeout(() => {
        copyLabel.textContent = originalLabel;
      }, 1800);
    }
  });
}
