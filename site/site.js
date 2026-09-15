const copyButtons = document.querySelectorAll("[data-copy]");

const setCopyLabel = (button, label) => {
  const labelNode = button.querySelector("[data-copy-label]");
  if (labelNode) {
    labelNode.textContent = label;
  }
};

const copyText = async (value) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const helper = document.createElement("textarea");
  helper.value = value;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.opacity = "0";
  document.body.appendChild(helper);
  helper.select();
  const copied = document.execCommand("copy");
  helper.remove();

  if (!copied) {
    throw new Error("Copy was not available");
  }
};

copyButtons.forEach((button) => {
  const originalLabel = button.querySelector("[data-copy-label]")?.textContent || "Copy";

  button.addEventListener("click", async () => {
    try {
      await copyText(button.dataset.copy || "");
      setCopyLabel(button, "Copied");
    } catch {
      setCopyLabel(button, "Select text");
    }

    window.setTimeout(() => setCopyLabel(button, originalLabel), 1800);
  });
});
