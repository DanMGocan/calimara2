// ===================================
// CALIMARA - ENHANCED JAVASCRIPT
// ===================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize all components
    initializeComponents();
    initializeAnimations();
    initializeFormHandlers();
    initializeInteractiveFeatures();
});

// ===================================
// COMPONENT INITIALIZATION
// ===================================

function initializeComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Initialize loading overlay functionality
    initializeLoadingOverlay();
}

// ===================================
// ANIMATION SYSTEM
// ===================================

function initializeAnimations() {
    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate__animated', 'animate__fadeInUp');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe elements for animation
    document.querySelectorAll('.card, .post-card, .sidebar-card, .blog-card').forEach(el => {
        observer.observe(el);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// ===================================
// FORM HANDLERS
// ===================================

function initializeFormHandlers() {
    // Login Form
    const loginForm = document.getElementById('loginForm');
    console.log('Login form found:', !!loginForm);
    if (loginForm) {
        console.log('Adding login event listener');
        loginForm.addEventListener('submit', handleLogin);
    } else {
        console.error('Login form not found!');
    }

    // Register Form
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }

    // Create Post Form
    const createPostForm = document.getElementById('createPostForm');
    if (createPostForm) {
        createPostForm.addEventListener('submit', handleCreatePost);
    }

    // Edit Post Form
    const editPostForm = document.getElementById('editPostForm');
    if (editPostForm) {
        editPostForm.addEventListener('submit', handleEditPost);
    }

    // Subtitle Update Form
    const subtitleForm = document.getElementById('subtitleForm');
    if (subtitleForm) {
        subtitleForm.addEventListener('submit', handleSubtitleUpdate);
    }

    // Comment Forms
    document.querySelectorAll('.comment-form').forEach(form => {
        form.addEventListener('submit', handleCommentSubmission);
    });

    // Logout Button
    const logoutButton = document.getElementById('logoutButton');
    console.log('Logout button found:', !!logoutButton);
    if (logoutButton) {
        console.log('Adding logout event listener');
        logoutButton.addEventListener('click', handleLogout);
    } else {
        console.log('Logout button not found (normal if not logged in)');
    }
}

// ===================================
// INTERACTIVE FEATURES
// ===================================

function initializeInteractiveFeatures() {
    // Like buttons
    document.querySelectorAll('.like-button').forEach(button => {
        button.addEventListener('click', handleLike);
    });

    // Delete post buttons
    document.querySelectorAll('.delete-post-button').forEach(button => {
        button.addEventListener('click', handleDeletePost);
    });

    // Comment management buttons
    document.querySelectorAll('.approve-comment-button').forEach(button => {
        button.addEventListener('click', handleApproveComment);
    });

    document.querySelectorAll('.delete-comment-button').forEach(button => {
        button.addEventListener('click', handleDeleteComment);
    });

    // Auto-save functionality for forms
    initializeAutoSave();

    // Real-time character counters
    initializeCharacterCounters();

    // Enhanced form validation
    initializeFormValidation();
}

// ===================================
// API HANDLERS
// ===================================

async function handleLogin(e) {
    e.preventDefault();
    console.log('=== JavaScript Login Started ===');
    const form = e.target;
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    console.log('Email:', email);
    console.log('Password length:', password ? password.length : 0);

    showLoadingState(form);

    try {
        console.log('Sending login request...');
        const response = await fetch('/api/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
            credentials: 'include' // Ensure cookies are included
        });

        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers);
        
        const data = await response.json();
        console.log('Response data:', data);

        if (response.ok) {
            hideError(errorDiv);
            showToast('Autentificare reușită! Te redirecționăm...', 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
            if (modal) modal.hide();
            
            // Debug: Check session before redirect
            console.log('Login successful, checking session...');
            
            // Verify session is set before redirect
            setTimeout(async () => {
                try {
                    const sessionCheck = await fetch('/api/debug/session', {
                        credentials: 'include'
                    });
                    const sessionData = await sessionCheck.json();
                    console.log('Session data after login:', sessionData);
                    
                    if (sessionData.user_found) {
                        // Session is valid, redirect
                        window.location.replace(`//${data.username}.calimara.ro/dashboard`);
                    } else {
                        console.error('Session not found after login');
                        showError(errorDiv, 'Sesiune invalidă după autentificare. Te rugăm să încerci din nou.');
                    }
                } catch (e) {
                    console.error('Session check failed:', e);
                    // Fallback: try redirect anyway
                    window.location.replace(`//${data.username}.calimara.ro/dashboard`);
                }
            }, 1000);
        } else {
            showError(errorDiv, data.detail || 'Autentificare eșuată');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată.');
    } finally {
        hideLoadingState(form);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const form = e.target;
    const username = document.getElementById('username').value;
    const subtitle = document.getElementById('subtitle').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('registerError');

    showLoadingState(form);

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, subtitle, email, password }),
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Înregistrare reușită! Te redirecționăm...', 'success');
            
            // Verify authentication before redirecting
            setTimeout(async () => {
                try {
                    const authCheck = await fetch('/api/user/me');
                    const authData = await authCheck.json();
                    
                    if (authData.authenticated) {
                        // User is authenticated, redirect to dashboard
                        window.location.replace(`//${username.toLowerCase()}.calimara.ro/dashboard`);
                    } else {
                        // Authentication failed, show error
                        showError(errorDiv, 'Autentificare automată eșuată. Te rugăm să te conectezi manual.');
                        setTimeout(() => {
                            window.location.href = '/';
                        }, 2000);
                    }
                } catch (error) {
                    console.error('Auth verification error:', error);
                    // Fallback: try to redirect anyway
                    window.location.replace(`//${username.toLowerCase()}.calimara.ro/dashboard`);
                }
            }, 1500);
        } else {
            showError(errorDiv, data.detail || 'Înregistrare eșuată');
        }
    } catch (error) {
        console.error('Register error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată în timpul înregistrării.');
    } finally {
        hideLoadingState(form);
    }
}

async function handleCreatePost(e) {
    e.preventDefault();
    const form = e.target;
    const title = document.getElementById('postTitle').value;
    const content = document.getElementById('postContent').value;
    const categories = document.getElementById('postCategories').value;
    const errorDiv = document.getElementById('postError');
    const successDiv = document.getElementById('postSuccess');

    showLoadingState(form);

    try {
        const response = await fetch('/api/posts/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, categories }),
        });

        const data = await response.json();

        if (response.ok) {
            showSuccess(successDiv, 'Postare creată cu succes!');
            hideError(errorDiv);
            form.reset();
            setTimeout(() => window.location.href = '/dashboard', 1500);
        } else {
            showError(errorDiv, data.detail || 'Crearea postării a eșuat');
            hideSuccess(successDiv);
        }
    } catch (error) {
        console.error('Create post error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată.');
        hideSuccess(successDiv);
    } finally {
        hideLoadingState(form);
    }
}

async function handleEditPost(e) {
    e.preventDefault();
    const form = e.target;
    const postId = form.dataset.postId;
    const title = document.getElementById('postTitle').value;
    const content = document.getElementById('postContent').value;
    const categories = document.getElementById('postCategories').value;
    const errorDiv = document.getElementById('editPostError');
    const successDiv = document.getElementById('editPostSuccess');

    showLoadingState(form);

    try {
        const response = await fetch(`/api/posts/${postId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, categories }),
        });

        const data = await response.json();

        if (response.ok) {
            showSuccess(successDiv, 'Postare actualizată cu succes!');
            hideError(errorDiv);
            setTimeout(() => window.location.href = '/dashboard', 1500);
        } else {
            showError(errorDiv, data.detail || 'Actualizarea postării a eșuat');
            hideSuccess(successDiv);
        }
    } catch (error) {
        console.error('Edit post error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată.');
        hideSuccess(successDiv);
    } finally {
        hideLoadingState(form);
    }
}

async function handleSubtitleUpdate(e) {
    e.preventDefault();
    const form = e.target;
    const subtitle = document.getElementById('subtitle').value;
    const errorDiv = document.getElementById('subtitleError');
    const successDiv = document.getElementById('subtitleSuccess');

    showLoadingState(form);

    try {
        const response = await fetch('/api/users/me', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subtitle }),
        });

        const data = await response.json();

        if (response.ok) {
            showSuccess(successDiv, 'Motto actualizat cu succes!');
            hideError(errorDiv);
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showError(errorDiv, data.detail || 'Actualizarea motto-ului a eșuat');
            hideSuccess(successDiv);
        }
    } catch (error) {
        console.error('Subtitle update error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată la actualizarea motto-ului.');
        hideSuccess(successDiv);
    } finally {
        hideLoadingState(form);
    }
}

async function handleCommentSubmission(e) {
    e.preventDefault();
    const form = e.target;
    const postId = form.dataset.postId;
    const content = form.querySelector('textarea[name="content"]').value;
    const authorName = form.querySelector('input[name="author_name"]')?.value || '';
    const authorEmail = form.querySelector('input[name="author_email"]')?.value || '';
    const errorDiv = form.querySelector('.comment-error');

    showLoadingState(form);

    const commentData = { content };
    if (authorName) commentData.author_name = authorName;
    if (authorEmail) commentData.author_email = authorEmail;

    try {
        const response = await fetch(`/api/posts/${postId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(commentData),
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Comentariu trimis cu succes! Va apărea după aprobare.', 'success');
            form.reset();
            hideError(errorDiv);
        } else {
            showError(errorDiv, data.detail || 'Trimiterea comentariului a eșuat');
        }
    } catch (error) {
        console.error('Comment submission error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată.');
    } finally {
        hideLoadingState(form);
    }
}

async function handleLike(e) {
    const button = e.target.closest('.like-button');
    const postId = button.dataset.postId;
    const likesCountSpan = document.getElementById(`likes-count-${postId}`);

    // Add visual feedback
    button.classList.add('liked');
    button.disabled = true;

    try {
        const response = await fetch(`/api/posts/${postId}/likes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });

        if (response.ok) {
            if (likesCountSpan) {
                const currentCount = parseInt(likesCountSpan.textContent);
                likesCountSpan.textContent = currentCount + 1;
                
                // Animate the counter
                likesCountSpan.classList.add('animate__animated', 'animate__pulse');
            }
            showToast('Postare apreciată!', 'success');
        } else if (response.status === 409) {
            showToast('Ai apreciat deja această postare!', 'warning');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Aprecierea postării a eșuat', 'error');
        }
    } catch (error) {
        console.error('Like error:', error);
        showToast('A apărut o eroare neașteptată.', 'error');
    } finally {
        setTimeout(() => {
            button.classList.remove('liked');
            button.disabled = false;
        }, 1000);
    }
}

async function handleLogout(e) {
    e.preventDefault();
    console.log('=== JavaScript Logout Started ===');
    
    try {
        console.log('Sending logout request...');
        const response = await fetch('/api/logout', { 
            method: 'GET',
            credentials: 'include'
        });
        
        console.log('Logout response status:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('Logout response data:', data);
            showToast('Deconectare reușită!', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            const data = await response.json();
            console.log('Logout error data:', data);
            showToast(data.detail || 'Deconectare eșuată', 'error');
        }
    } catch (error) {
        console.error('Logout error:', error);
        showToast('A apărut o eroare neașteptată.', 'error');
    }
}

async function handleDeletePost(e) {
    const postId = e.target.dataset.postId;
    
    if (!confirm('Ești sigur că vrei să ștergi această postare?')) return;

    try {
        const response = await fetch(`/api/posts/${postId}`, { method: 'DELETE' });
        
        if (response.status === 204) {
            e.target.closest('tr').remove();
            showToast('Postare ștearsă cu succes!', 'success');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Ștergerea postării a eșuat', 'error');
        }
    } catch (error) {
        console.error('Delete post error:', error);
        showToast('A apărut o eroare neașteptată.', 'error');
    }
}

async function handleApproveComment(e) {
    const commentId = e.target.dataset.commentId;
    
    if (!confirm('Ești sigur că vrei să aprobi acest comentariu?')) return;

    try {
        const response = await fetch(`/api/comments/${commentId}/approve`, { method: 'PUT' });
        
        if (response.ok) {
            e.target.closest('tr').remove();
            showToast('Comentariu aprobat cu succes!', 'success');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Aprobarea comentariului a eșuat', 'error');
        }
    } catch (error) {
        console.error('Approve comment error:', error);
        showToast('A apărut o eroare neașteptată.', 'error');
    }
}

async function handleDeleteComment(e) {
    const commentId = e.target.dataset.commentId;
    
    if (!confirm('Ești sigur că vrei să ștergi acest comentariu?')) return;

    try {
        const response = await fetch(`/api/comments/${commentId}`, { method: 'DELETE' });
        
        if (response.status === 204) {
            e.target.closest('tr').remove();
            showToast('Comentariu șters cu succes!', 'success');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Ștergerea comentariului a eșuat', 'error');
        }
    } catch (error) {
        console.error('Delete comment error:', error);
        showToast('A apărut o eroare neașteptată.', 'error');
    }
}

// ===================================
// UTILITY FUNCTIONS
// ===================================

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'success' ? 'bg-success' : 
                   type === 'warning' ? 'bg-warning' : 
                   type === 'error' ? 'bg-danger' : 'bg-primary';
    
    const iconClass = type === 'success' ? 'bi-check-circle' : 
                     type === 'warning' ? 'bi-exclamation-triangle' : 
                     type === 'error' ? 'bi-x-circle' : 'bi-info-circle';

    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white ${bgClass} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${iconClass} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
    bsToast.show();

    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function showError(errorDiv, message) {
    if (!errorDiv) return;
    const messageSpan = errorDiv.querySelector('.error-message');
    if (messageSpan) {
        messageSpan.textContent = message;
    } else {
        errorDiv.textContent = message;
    }
    errorDiv.classList.remove('d-none');
    errorDiv.style.display = 'block';
}

function hideError(errorDiv) {
    if (!errorDiv) return;
    errorDiv.classList.add('d-none');
    errorDiv.style.display = 'none';
}

function showSuccess(successDiv, message) {
    if (!successDiv) return;
    successDiv.textContent = message;
    successDiv.classList.remove('d-none');
    successDiv.style.display = 'block';
}

function hideSuccess(successDiv) {
    if (!successDiv) return;
    successDiv.classList.add('d-none');
    successDiv.style.display = 'none';
}

function showLoadingState(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Se încarcă...';
    }
}

function hideLoadingState(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = false;
        // Restore original button text based on form type
        const originalTexts = {
            'loginForm': '<i class="bi bi-box-arrow-in-right me-2"></i>Autentificare',
            'registerForm': '<i class="bi bi-person-plus me-2"></i>Înregistrează-te',
            'createPostForm': '<i class="bi bi-plus-circle me-2"></i>Creează Postare',
            'editPostForm': '<i class="bi bi-save me-2"></i>Actualizează Postare',
            'subtitleForm': '<i class="bi bi-save me-2"></i>Salvează Motto'
        };
        
        const formId = form.id;
        submitButton.innerHTML = originalTexts[formId] || 'Trimite';
    }
}

function initializeLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;

    // Show loading overlay for page transitions
    window.addEventListener('beforeunload', () => {
        overlay.classList.remove('d-none');
    });
}

function initializeAutoSave() {
    // Auto-save for post creation/editing
    const postForms = document.querySelectorAll('#createPostForm, #editPostForm');
    
    postForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', debounce(() => {
                saveFormData(form);
            }, 1000));
        });
        
        // Load saved data on page load
        loadFormData(form);
    });
}

function saveFormData(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    localStorage.setItem(`calimara_${form.id}`, JSON.stringify(data));
}

function loadFormData(form) {
    const savedData = localStorage.getItem(`calimara_${form.id}`);
    if (savedData) {
        const data = JSON.parse(savedData);
        Object.keys(data).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input && !input.value) {
                input.value = data[key];
            }
        });
    }
}

function clearFormData(form) {
    localStorage.removeItem(`calimara_${form.id}`);
}

function initializeCharacterCounters() {
    // Add character counters to textareas
    document.querySelectorAll('textarea').forEach(textarea => {
        const maxLength = textarea.getAttribute('maxlength');
        if (maxLength) {
            const counter = document.createElement('small');
            counter.className = 'text-muted character-counter';
            counter.textContent = `0/${maxLength}`;
            textarea.parentNode.appendChild(counter);
            
            textarea.addEventListener('input', () => {
                const currentLength = textarea.value.length;
                counter.textContent = `${currentLength}/${maxLength}`;
                counter.className = currentLength > maxLength * 0.9 ? 'text-warning character-counter' : 'text-muted character-counter';
            });
        }
    });
}

function initializeFormValidation() {
    // Enhanced form validation
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===================================
// KEYBOARD SHORTCUTS
// ===================================

document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to submit forms
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const activeElement = document.activeElement;
        if (activeElement.tagName === 'TEXTAREA') {
            const form = activeElement.closest('form');
            if (form) {
                form.dispatchEvent(new Event('submit'));
            }
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modal = bootstrap.Modal.getInstance(openModal);
            if (modal) modal.hide();
        }
    }
});

// ===================================
// PERFORMANCE OPTIMIZATIONS
// ===================================

// Lazy loading for images
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });

    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}

// Service Worker registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => console.log('SW registered'))
            .catch(registrationError => console.log('SW registration failed'));
    });
}
