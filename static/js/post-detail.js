function copyPostUrl() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        showToast('Link-ul postării a fost copiat în clipboard!', 'success');
    }).catch(() => {
        showToast('Nu s-a putut copia link-ul', 'error');
    });
}

function copyToClipboard(text = window.location.href) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Link copiat în clipboard!', 'success');
    }).catch(() => {
        showToast('Nu s-a putut copia link-ul', 'error');
    });
}

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'primary'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-${type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle logout button in post detail header
    const logoutButtonPost = document.getElementById('logoutButtonPost');
    if (logoutButtonPost) {
        logoutButtonPost.addEventListener('click', function(e) {
            e.preventDefault();
            showToast('Se deconectează...', 'info');
            window.location.href = '/api/logout';
        });
    }
});