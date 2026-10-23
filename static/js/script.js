/**
 * CHEREMO EGG DEPOT | MANAGEMENT SYSTEM
 * Client-Side Interactivity, Live Pricing Preview, and Mobile Navigation
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Mobile Sidebar Navigation Toggle
  const sidebar = document.getElementById('sidebar');
  const toggleBtn = document.getElementById('sidebarToggle');
  const overlay = document.getElementById('sidebarOverlay');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('active');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', function () {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }

  // 2. Prevent Double Form Submissions
  const forms = document.querySelectorAll('form:not([data-no-disable])');
  forms.forEach(form => {
    form.addEventListener('submit', function (e) {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.disabled) {
        // Allow brief delay so browser registers submit event
        setTimeout(() => {
          submitBtn.disabled = true;
          const origText = submitBtn.innerHTML;
          submitBtn.innerHTML = '<span>⏳ Processing...</span>';
          // Re-enable after 8 seconds just in case of validation stop
          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = origText;
          }, 8000);
        }, 50);
      }
    });
  });

  // 3. Live Pricing Preview on Sales Form
  const quantityInput = document.getElementById('id_quantity');
  const previewBox = document.getElementById('pricePreviewBox');
  const previewTotal = document.getElementById('previewTotal');
  const previewBreakdown = document.getElementById('previewBreakdown');
  const stockWarning = document.getElementById('stockWarning');

  let debounceTimer = null;

  function fetchPricePreview(qty) {
    if (!qty || qty <= 0) {
      if (previewBox) previewBox.style.display = 'none';
      return;
    }

    fetch(`/api/price-preview/?quantity=${qty}`)
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        if (data.success) {
          if (previewBox) previewBox.style.display = 'block';
          if (previewTotal) previewTotal.textContent = data.formatted_price;
          if (previewBreakdown) {
            let itemsHtml = '';
            data.breakdown_items.forEach(item => {
              itemsHtml += `<div style="display:flex; justify-content:space-between; margin-bottom:4px; padding:4px 0; border-bottom:1px dashed #eee;">
                <span><strong>${item.units}x</strong> ${item.name}</span>
                <span>KSh ${item.subtotal.toFixed(2)}</span>
              </div>`;
            });
            previewBreakdown.innerHTML = itemsHtml || data.breakdown_text;
          }

          if (stockWarning) {
            if (!data.sufficient_stock) {
              stockWarning.style.display = 'block';
              stockWarning.innerHTML = `⚠️ <strong>Insufficient Stock!</strong> You only have <strong>${data.available_stock}</strong> eggs in stock.`;
            } else {
              stockWarning.style.display = 'none';
            }
          }
        }
      })
      .catch(err => {
        console.error('Pricing preview error:', err);
      });
  }

  if (quantityInput) {
    quantityInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      const val = parseInt(this.value, 10);
      debounceTimer = setTimeout(() => {
        fetchPricePreview(val);
      }, 250);
    });

    // Initial trigger if input has default value
    if (quantityInput.value) {
      fetchPricePreview(parseInt(quantityInput.value, 10));
    }
  }

  // 4. Auto-dismiss alerts after 6 seconds
  const autoAlerts = document.querySelectorAll('.alert-auto-dismiss');
  autoAlerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease, max-height 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });
});
