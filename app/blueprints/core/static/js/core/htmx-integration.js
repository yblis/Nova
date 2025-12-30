/**
 * HTMX Integration
 * Handles path updates and integration with Alpine.js
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof htmx !== 'undefined') {
        htmx.on('htmx:afterSettle', function (evt) {
            // Update path state if needed for non-boosted HTMX requests (partials)
            if (!evt.detail.boosted) {
                // Optional: handle partial updates
            }
        });
    }
});
