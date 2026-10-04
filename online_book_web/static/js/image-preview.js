document.querySelectorAll('[data-image-preview]').forEach((input) => {
  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    const preview = document.querySelector(input.dataset.imagePreview);
    if (!file || !preview) return;
    if (!file.type.startsWith('image/') || file.size > 5 * 1024 * 1024) {
      input.value = '';
      return;
    }
    const reader = new FileReader();
    reader.addEventListener('load', () => { preview.src = reader.result; });
    reader.readAsDataURL(file);
  });
});
