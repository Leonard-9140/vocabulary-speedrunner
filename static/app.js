document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".answer-form");
  if (!form) return;

  form.addEventListener("submit", () => {
    const button = form.querySelector(".submit-button");
    const status = form.querySelector(".grading-status");
    if (button) {
      button.disabled = true;
      button.textContent = "AI 正在批改…";
    }
    if (status) status.hidden = false;
  });
});
