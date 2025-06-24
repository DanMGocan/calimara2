// ===================================
// CALIMARA - ENHANCED JAVASCRIPT
// ===================================

document.addEventListener('DOMContentLoaded', () => {
    // Set current year
    const currentYearElement = document.getElementById('currentYear');
    if (currentYearElement) {
        currentYearElement.textContent = new Date().getFullYear();
    }
    
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
    // Note: Login and registration now handled by Google OAuth

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

    // Comments are now auto-moderated by AI - no manual approval needed

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

// Login and registration now handled by Google OAuth - no local handlers needed

async function handleCreatePost(e) {
    e.preventDefault();
    const form = e.target;
    const title = document.getElementById('postTitle').value;
    const category = document.getElementById('postCategory').value;
    const tags = document.getElementById('postTags').value;
    const errorDiv = document.getElementById('postError');
    const successDiv = document.getElementById('postSuccess');

    // Get content from QuillJS editor if available, otherwise from textarea
    let content;
    if (window.quill) {
        content = window.quill.root.innerHTML;
    } else {
        content = document.getElementById('postContent').value;
    }

    showLoadingState(form);

    try {
        // Parse tags from space-separated string to array
        const tagsArray = tags ? tags.trim().split(/\s+/).filter(tag => tag.length > 0) : [];
        
        const response = await fetch('/api/posts/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                title, 
                content, 
                category: category || null,
                tags: tagsArray
            }),
        });

        const data = await response.json();

        if (response.ok) {
            showSuccess(successDiv, 'Postare creată cu succes!');
            hideError(errorDiv);
            form.reset();
            if (window.quill) {
                window.quill.setContents([]);
            }
            // Clear localStorage
            localStorage.removeItem('calimara_createPostForm');
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
    const avatar_seed = document.getElementById('newAvatarSeed').value;
    const errorDiv = document.getElementById('subtitleError');
    const successDiv = document.getElementById('subtitleSuccess');

    showLoadingState(form);

    try {
        const response = await fetch('/api/users/me', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subtitle, avatar_seed }),
        });

        const data = await response.json();

        if (response.ok) {
            showSuccess(successDiv, 'Setări actualizate cu succes!');
            hideError(errorDiv);
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showError(errorDiv, data.detail || 'Actualizarea setărilor a eșuat');
            hideSuccess(successDiv);
        }
    } catch (error) {
        console.error('Subtitle update error:', error);
        showError(errorDiv, 'A apărut o eroare neașteptată la actualizarea setărilor.');
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
        console.log('Submitting comment:', commentData);
        
        const response = await fetch(`/api/posts/${postId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(commentData),
        });

        console.log('Comment response status:', response.status);
        const data = await response.json();
        console.log('Comment response data:', data);

        if (response.ok) {
            console.log('Comment submitted successfully');
            
            // Check if the comment was flagged for moderation
            if (data.moderation_status === 'flagged') {
                showToast('Comentariul tău a fost trimis pentru revizuire. Va fi publicat după ce un moderator îl va aproba.', 'warning');
                
                // Clear the form
                form.reset();
                
                // Don't reload - the comment won't be visible anyway since it's flagged
                setTimeout(() => {
                    hideLoadingState(form);
                }, 1000);
            } else {
                // Comment was approved - show success and reload to display it
                showToast('Comentariu trimis cu succes!', 'success');
                
                // Small delay to ensure the toast is seen, then reload
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            }
        } else {
            console.error('Comment submission failed:', data);
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
    
    // Since logout endpoint now redirects, we can simply navigate to it
    showToast('Se deconectează...', 'info');
    
    // Navigate to logout endpoint which will clear session and redirect to main domain
    window.location.href = '/api/logout';
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

// Comment approval functions removed - comments are now auto-moderated by AI

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

// ===================================
// MESSAGES SYSTEM FUNCTIONALITY
// ===================================

// Messages page functionality
let conversations = [];
let currentUser = null;

function initializeMessagesPage() {
    // Get current user info for messages page
    fetch('/api/user/me')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                currentUser = data.user;
                loadConversations();
                loadUnreadCount();
            } else {
                window.location.href = '/login';
            }
        })
        .catch(error => {
            console.error('Error getting user info:', error);
        });
    
    // Setup messages event listeners
    setupMessagesEventListeners();
}

function setupMessagesEventListeners() {
    // Character counter for new message
    const messageContent = document.getElementById('messageContent');
    const charCount = document.getElementById('charCount');
    
    if (messageContent && charCount) {
        messageContent.addEventListener('input', function() {
            charCount.textContent = this.value.length;
        });
    }
    
    // Send new message button
    const sendNewMessageBtn = document.getElementById('sendNewMessage');
    if (sendNewMessageBtn) {
        sendNewMessageBtn.addEventListener('click', sendNewMessage);
    }
    
    // Search conversations
    const searchConversations = document.getElementById('searchConversations');
    if (searchConversations) {
        searchConversations.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length >= 2) {
                searchConversationsFunc(query);
            } else if (query.length === 0) {
                loadConversations();
            }
        });
    }
    
    // User suggestions for new message
    const recipientUsername = document.getElementById('recipientUsername');
    if (recipientUsername) {
        recipientUsername.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length >= 2) {
                searchUsers(query);
            } else {
                hideUserSuggestions();
            }
        });
    }
    
    // Hide suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#recipientUsername') && !e.target.closest('#userSuggestions')) {
            hideUserSuggestions();
        }
    });
}

function loadConversations() {
    fetch('/api/messages/conversations')
        .then(response => response.json())
        .then(data => {
            conversations = data.conversations;
            renderConversations(conversations);
            const loadingState = document.getElementById('loadingState');
            if (loadingState) {
                loadingState.classList.add('d-none');
            }
        })
        .catch(error => {
            console.error('Error loading conversations:', error);
            const loadingState = document.getElementById('loadingState');
            if (loadingState) {
                loadingState.innerHTML = `
                    <div class="text-center text-danger">
                        <i class="bi bi-exclamation-triangle fs-1 mb-3"></i>
                        <p>Eroare la încărcarea conversațiilor</p>
                    </div>
                `;
            }
        });
}

function loadUnreadCount() {
    fetch('/api/messages/unread-count')
        .then(response => response.json())
        .then(data => {
            const unreadCount = data.unread_count || 0;
            const unreadCountEl = document.getElementById('unreadCount');
            if (unreadCountEl) {
                unreadCountEl.textContent = 
                    unreadCount === 0 ? '0 necitite' : 
                    unreadCount === 1 ? '1 necitiit' : 
                    unreadCount + ' necitite';
            }
        })
        .catch(error => {
            console.error('Error loading unread count:', error);
        });
}

function renderConversations(conversationList) {
    const container = document.getElementById('conversationsList');
    if (!container) return;
    
    if (conversationList.length === 0) {
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            emptyState.classList.remove('d-none');
            container.innerHTML = emptyState.outerHTML;
        }
        return;
    }
    
    const emptyState = document.getElementById('emptyState');
    if (emptyState) {
        emptyState.classList.add('d-none');
    }
    
    const html = conversationList.map(conv => {
        const otherUser = conv.other_user;
        const latestMessage = conv.latest_message;
        const unreadBadge = conv.unread_count > 0 ? 
            `<span class="badge bg-danger ms-2">${conv.unread_count}</span>` : '';
        
        return `
            <div class="conversation-item border-bottom p-3 hover-bg-light" style="cursor: pointer;" 
                 onclick="openConversation(${conv.id})">
                <div class="d-flex align-items-start">
                    <img src="${getAvatarUrl(otherUser.avatar_seed || otherUser.username + '-shapes', 48)}" 
                         alt="Avatar ${otherUser.username}" 
                         class="rounded-circle me-3" 
                         style="width: 3rem; height: 3rem; object-fit: cover;">
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between align-items-start mb-1">
                            <h6 class="fw-bold mb-0">@${otherUser.username}${unreadBadge}</h6>
                            <small class="text-muted">
                                ${latestMessage ? formatTime(latestMessage.created_at) : ''}
                            </small>
                        </div>
                        ${otherUser.subtitle ? `<p class="text-muted small mb-1">${otherUser.subtitle}</p>` : ''}
                        ${latestMessage ? `
                            <p class="text-muted small mb-0">
                                <i class="bi bi-${latestMessage.sender_id === currentUser.id ? 'arrow-right' : 'arrow-left'} me-1"></i>
                                ${latestMessage.content}
                            </p>
                        ` : '<p class="text-muted small mb-0">Niciun mesaj încă</p>'}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

function openConversation(conversationId) {
    window.location.href = `/messages/${conversationId}`;
}

function searchConversationsFunc(query) {
    fetch(`/api/messages/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            renderConversations(data.conversations);
        })
        .catch(error => {
            console.error('Error searching conversations:', error);
        });
}

function searchUsers(query) {
    fetch(`/api/users/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            showUserSuggestions(data);
        })
        .catch(error => {
            console.error('Error searching users:', error);
        });
}

function showUserSuggestions(users) {
    const suggestionsContainer = document.getElementById('userSuggestions');
    if (!suggestionsContainer) return;
    
    if (users.length === 0) {
        suggestionsContainer.style.display = 'none';
        return;
    }
    
    const html = users.map(user => `
        <div class="user-suggestion p-2 hover-bg-light" style="cursor: pointer;" 
             onclick="selectUser('${user.username}')">
            <div class="d-flex align-items-center">
                <img src="${getAvatarUrl(user.username + '-shapes', 32)}" 
                     alt="Avatar ${user.username}" 
                     class="rounded-circle me-2" 
                     style="width: 2rem; height: 2rem; object-fit: cover;">
                <div>
                    <div class="fw-medium">@${user.username}</div>
                    ${user.subtitle ? `<small class="text-muted">${user.subtitle}</small>` : ''}
                </div>
            </div>
        </div>
    `).join('');
    
    suggestionsContainer.innerHTML = html;
    suggestionsContainer.style.display = 'block';
}

function hideUserSuggestions() {
    const suggestionsContainer = document.getElementById('userSuggestions');
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }
}

function selectUser(username) {
    const recipientUsername = document.getElementById('recipientUsername');
    if (recipientUsername) {
        recipientUsername.value = username;
    }
    hideUserSuggestions();
}

function sendNewMessage() {
    const form = document.getElementById('newMessageForm');
    if (!form) return;
    
    const formData = new FormData(form);
    
    const messageData = {
        recipient_username: formData.get('recipient_username'),
        content: formData.get('content')
    };
    
    if (!messageData.recipient_username || !messageData.content) {
        showToast('Te rog completează toate câmpurile', 'danger');
        return;
    }
    
    fetch('/api/messages/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(messageData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.conversation_id) {
                showToast('Mesaj trimis cu succes!', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('newMessageModal'));
                if (modal) modal.hide();
                form.reset();
                const charCount = document.getElementById('charCount');
                if (charCount) charCount.textContent = '0';
                
                // Redirect to the conversation
                setTimeout(() => {
                    window.location.href = `/messages/${data.conversation_id}`;
                }, 1000);
            } else {
                showToast(data.detail || 'Eroare la trimiterea mesajului', 'danger');
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            showToast('Eroare la trimiterea mesajului', 'danger');
        });
}

// ===================================
// CONVERSATION PAGE FUNCTIONALITY
// ===================================

let conversationId = null;
let conversation = null;
let messages = [];
let isLoadingMessages = false;

function initializeConversationPage(convId) {
    conversationId = convId || window.conversationId;
    
    // Get current user info
    fetch('/api/user/me')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                currentUser = data.user;
                loadConversation();
            } else {
                window.location.href = '/login';
            }
        })
        .catch(error => {
            console.error('Error getting user info:', error);
        });
    
    setupConversationEventListeners();
}

function setupConversationEventListeners() {
    // Character counter
    const messageInput = document.getElementById('messageInput');
    const charCount = document.getElementById('charCount');
    
    if (messageInput && charCount) {
        messageInput.addEventListener('input', function() {
            charCount.textContent = this.value.length;
        });
        
        // Auto-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // Send message on Ctrl+Enter
        messageInput.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Send message on form submit
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }
}

function loadConversation() {
    isLoadingMessages = true;
    
    fetch(`/api/messages/conversations/${conversationId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Conversation not found');
            }
            return response.json();
        })
        .then(data => {
            conversation = data.conversation;
            messages = data.messages;
            
            renderConversationHeader();
            renderMessages();
            scrollToBottom();
            
            const loadingMessages = document.getElementById('loadingMessages');
            if (loadingMessages) {
                loadingMessages.classList.add('d-none');
            }
            isLoadingMessages = false;
        })
        .catch(error => {
            console.error('Error loading conversation:', error);
            const loadingMessages = document.getElementById('loadingMessages');
            if (loadingMessages) {
                loadingMessages.innerHTML = `
                    <div class="text-center text-danger">
                        <i class="bi bi-exclamation-triangle fs-1 mb-3"></i>
                        <p>Conversația nu a fost găsită sau nu ai acces la ea</p>
                        <a href="/messages" class="btn btn-primary-custom">
                            <i class="bi bi-arrow-left me-1"></i>Înapoi la mesaje
                        </a>
                    </div>
                `;
            }
        });
}

function renderConversationHeader() {
    if (!conversation) return;
    
    const otherUser = conversation.other_user;
    const headerHtml = `
        <div class="d-flex align-items-center">
            <img src="${getAvatarUrl(otherUser.avatar_seed || otherUser.username + '-shapes', 48)}" 
                 alt="Avatar ${otherUser.username}" 
                 class="rounded-circle me-3" 
                 style="width: 3rem; height: 3rem; object-fit: cover;">
            <div>
                <h5 class="fw-bold mb-0">@${otherUser.username}</h5>
                ${otherUser.subtitle ? `<small class="text-muted">${otherUser.subtitle}</small>` : ''}
            </div>
        </div>
    `;
    
    const conversationHeader = document.getElementById('conversationHeader');
    if (conversationHeader) {
        conversationHeader.innerHTML = headerHtml;
    }
}

function renderMessages() {
    const container = document.getElementById('messagesList');
    if (!container) return;
    
    if (messages.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-chat-dots display-4 mb-3"></i>
                <p>Niciun mesaj încă. Începe conversația!</p>
            </div>
        `;
        return;
    }
    
    const html = messages.map(message => {
        const isMyMessage = message.is_mine;
        const messageClass = isMyMessage ? 'message-mine' : 'message-theirs';
        const alignClass = isMyMessage ? 'ms-auto' : 'me-auto';
        
        return `
            <div class="message-item mb-3 d-flex ${isMyMessage ? 'justify-content-end' : 'justify-content-start'}">
                <div class="message-bubble ${messageClass} ${alignClass}" style="max-width: 70%;">
                    <div class="message-content p-3 rounded-3">
                        <p class="mb-1">${escapeHtml(message.content)}</p>
                        <small class="text-muted">
                            ${formatTime(message.created_at)}
                            ${isMyMessage && message.is_read ? '<i class="bi bi-check2-all ms-1"></i>' : ''}
                        </small>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    if (!messageInput) return;
    
    const content = messageInput.value.trim();
    
    if (!content) {
        return;
    }
    
    const messageData = {
        content: content
    };
    
    // Disable input while sending
    messageInput.disabled = true;
    
    fetch(`/api/messages/conversations/${conversationId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(messageData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.id) {
                // Add message to local array
                messages.push(data);
                renderMessages();
                scrollToBottom();
                
                // Clear input
                messageInput.value = '';
                messageInput.style.height = 'auto';
                const charCount = document.getElementById('charCount');
                if (charCount) charCount.textContent = '0';
                
                showToast('Mesaj trimis!', 'success');
            } else {
                showToast(data.detail || 'Eroare la trimiterea mesajului', 'danger');
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            showToast('Eroare la trimiterea mesajului', 'danger');
        })
        .finally(() => {
            messageInput.disabled = false;
            messageInput.focus();
        });
}

function deleteConversation() {
    if (!confirm('Ești sigur că vrei să ștergi această conversație? Această acțiune nu poate fi anulată.')) {
        return;
    }
    
    fetch(`/api/messages/conversations/${conversationId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            showToast('Conversație ștearsă', 'success');
            setTimeout(() => {
                window.location.href = '/messages';
            }, 1000);
        })
        .catch(error => {
            console.error('Error deleting conversation:', error);
            showToast('Eroare la ștergerea conversației', 'danger');
        });
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// ===================================
// BLOG PAGE FUNCTIONALITY
// ===================================

function initializeBlogPage() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Setup send message functionality
    setupSendMessage();
    
    // Handle logout buttons
    const logoutButtonBlog = document.getElementById('logoutButtonBlog');
    if (logoutButtonBlog) {
        logoutButtonBlog.addEventListener('click', function(e) {
            e.preventDefault();
            showToast('Se deconectează...', 'info');
            window.location.href = '/api/logout';
        });
    }
    
    const logoutButtonPost = document.getElementById('logoutButtonPost');
    if (logoutButtonPost) {
        logoutButtonPost.addEventListener('click', function(e) {
            e.preventDefault();
            showToast('Se deconectează...', 'info');
            window.location.href = '/api/logout';
        });
    }
    
    // Handle month/year filter
    const monthYearFilter = document.getElementById('monthYearFilter');
    if (monthYearFilter) {
        monthYearFilter.addEventListener('change', function() {
            const filterValue = this.value;
            if (!filterValue) {
                // Show all posts - reload page without params
                const url = new URL(window.location);
                url.searchParams.delete('month');
                url.searchParams.delete('year');
                window.location.href = url.toString();
            } else {
                // Filter by month/year
                const [month, year] = filterValue.split('-');
                const url = new URL(window.location);
                url.searchParams.set('month', month);
                url.searchParams.set('year', year);
                window.location.href = url.toString();
            }
        });
    }
}

function setupSendMessage() {
    const messageContent = document.getElementById('messageContent');
    const charCount = document.getElementById('charCount');
    const sendBtn = document.getElementById('sendMessageBtn');
    
    if (!messageContent || !charCount || !sendBtn) {
        return; // Elements not found, probably not on a blog with send message capability
    }
    
    // Character counter
    messageContent.addEventListener('input', function() {
        charCount.textContent = this.value.length;
    });
    
    // Send message
    sendBtn.addEventListener('click', function() {
        const recipientUsername = document.getElementById('recipientUsername').value;
        const content = messageContent.value.trim();
        
        if (!content) {
            showToast('Te rog scrie un mesaj', 'danger');
            return;
        }
        
        const messageData = {
            recipient_username: recipientUsername,
            content: content
        };
        
        // Disable button while sending
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Se trimite...';
        
        fetch('/api/messages/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(messageData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.conversation_id) {
                    showToast('Mesaj trimis cu succes!', 'success');
                    const modal = bootstrap.Modal.getInstance(document.getElementById('sendMessageModal'));
                    if (modal) modal.hide();
                    messageContent.value = '';
                    charCount.textContent = '0';
                    
                    // Offer to go to conversation
                    setTimeout(() => {
                        if (confirm('Vrei să vezi conversația cu ' + recipientUsername + '?')) {
                            window.location.href = `/messages/${data.conversation_id}`;
                        }
                    }, 1500);
                } else {
                    showToast(data.detail || 'Eroare la trimiterea mesajului', 'danger');
                }
            })
            .catch(error => {
                console.error('Error sending message:', error);
                showToast('Eroare la trimiterea mesajului', 'danger');
            })
            .finally(() => {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="bi bi-send me-1"></i>Trimite mesaj';
            });
    });
}

// Copy to clipboard function
function copyToClipboard(text = window.location.href) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Link copiat în clipboard!', 'success');
    });
}

// ===================================
// UTILITY FUNCTIONS FOR MESSAGES
// ===================================

function getAvatarUrl(seed, size = 48) {
    return `https://api.dicebear.com/7.x/shapes/svg?seed=${seed}&backgroundColor=f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff&size=${size}`;
}

function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'acum';
    if (diffInMinutes < 60) return `${diffInMinutes}m`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h`;
    if (diffInMinutes < 10080) return `${Math.floor(diffInMinutes / 1440)}z`;
    
    return date.toLocaleDateString('ro-RO', { 
        day: 'numeric', 
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===================================
// UNREAD MESSAGES FUNCTIONALITY
// ===================================

// Load unread message count for logged-in users
function loadUnreadMessageCount() {
    fetch('/api/messages/unread-count')
        .then(response => response.json())
        .then(data => {
            const unreadCount = data.unread_count || 0;
            const badge = document.getElementById('unreadBadge');
            
            if (badge) {
                if (unreadCount > 0) {
                    badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            }
        })
        .catch(error => {
            console.error('Error loading unread count:', error);
        });
}

// ===================================
// PAGE-SPECIFIC INITIALIZATION
// ===================================

// Initialize different page functionality based on current page
document.addEventListener('DOMContentLoaded', function() {
    // Check what page we're on and initialize accordingly
    const path = window.location.pathname;
    
    if (path === '/messages') {
        initializeMessagesPage();
    } else if (path.startsWith('/messages/') && window.conversationId) {
        initializeConversationPage(window.conversationId);
    } else if (window.location.hostname.includes('.calimara.ro') && window.location.hostname !== 'calimara.ro') {
        // On a subdomain blog page
        initializeBlogPage();
    }
    
    // Initialize unread message count ONLY for logged-in users on their OWN pages
    // This prevents cross-user data exposure when visiting other subdomains
    const currentUserElement = document.querySelector('[data-current-user]');
    const unreadBadge = document.getElementById('unreadBadge');
    
    // Only load unread count if user is logged in AND either:
    // 1. On main domain (calimara.ro), OR
    // 2. On their own subdomain (current user's username matches subdomain)
    if (unreadBadge && window.CALIMARA_CONFIG) {
        const currentDomain = window.location.hostname;
        const isMainDomain = currentDomain === window.CALIMARA_CONFIG.MAIN_DOMAIN;
        const isOwnSubdomain = currentDomain.includes(window.CALIMARA_CONFIG.SUBDOMAIN_SUFFIX) && 
                               currentDomain !== window.CALIMARA_CONFIG.MAIN_DOMAIN;
        
        // Only load messages on main domain or check if this is the user's own subdomain
        if (isMainDomain) {
            loadUnreadMessageCount();
            setInterval(loadUnreadMessageCount, 30000);
        } else if (isOwnSubdomain) {
            // For subdomains, we need to verify this is the user's own subdomain
            // We'll check this via an API call to prevent unauthorized access
            fetch('/api/user/me')
                .then(response => response.json())
                .then(data => {
                    if (data.authenticated) {
                        const subdomain = currentDomain.replace(window.CALIMARA_CONFIG.SUBDOMAIN_SUFFIX, '');
                        if (data.user.username === subdomain) {
                            loadUnreadMessageCount();
                            setInterval(loadUnreadMessageCount, 30000);
                        }
                        // If not their own subdomain, don't load any message data
                    }
                })
                .catch(error => {
                    console.error('Error verifying user subdomain access:', error);
                    // On error, don't load message data for security
                });
        }
    }
    
    // Set current year in footer
    const currentYearElement = document.getElementById('currentYear');
    if (currentYearElement) {
        currentYearElement.textContent = new Date().getFullYear();
    }
});

// Global functions that need to be accessible from HTML onclick attributes
window.openConversation = openConversation;
window.selectUser = selectUser;
window.deleteConversation = deleteConversation;
window.copyToClipboard = copyToClipboard;
