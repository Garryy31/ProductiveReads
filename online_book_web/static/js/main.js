document.querySelectorAll('.flash').forEach((flash) => {
  window.setTimeout(() => flash.remove(), 4500);
});

document.querySelectorAll('form[data-loading], form[method="post"]:not([data-loading="false"])').forEach((form) => {
  form.addEventListener('submit', () => {
    const submitButton = form.querySelector('button[type="submit"]');
    if (!submitButton) return;
    submitButton.disabled = true;
    submitButton.classList.add('is-loading');
    submitButton.dataset.originalText = submitButton.innerHTML;
    submitButton.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Processing...';
  });
});

document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
