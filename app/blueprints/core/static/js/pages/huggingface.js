/**
 * HuggingFace Search Integration
 * Handles filter interactions for the HuggingFace GGUF model search page
 */
document.addEventListener('DOMContentLoaded', function () {
    const filters = document.querySelectorAll('#hf-search-form select');
    const parameterSizeSelect = document.getElementById('parameter_size');
    const minParamsSelect = document.getElementById('min_params');
    const maxParamsSelect = document.getElementById('max_params');

    // Function to clear exact parameter size when range is selected
    function clearExactParameterSize() {
        if (parameterSizeSelect) {
            parameterSizeSelect.value = '';
        }
    }

    // Function to clear range when exact parameter size is selected
    function clearParameterRange() {
        if (minParamsSelect) minParamsSelect.value = '';
        if (maxParamsSelect) maxParamsSelect.value = '';
    }

    // Add event listeners for mutual exclusion
    if (minParamsSelect) {
        minParamsSelect.addEventListener('change', clearExactParameterSize);
    }
    if (maxParamsSelect) {
        maxParamsSelect.addEventListener('change', clearExactParameterSize);
    }
    if (parameterSizeSelect) {
        parameterSizeSelect.addEventListener('change', clearParameterRange);
    }

    // Auto-submit on filter change
    filters.forEach(filter => {
        filter.addEventListener('change', function () {
            const form = document.getElementById('hf-search-form');
            const queryInput = document.getElementById('q');
            if (queryInput && queryInput.value.trim()) {
                htmx.trigger(form, 'submit');
            }
        });
    });
});
