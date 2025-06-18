document.addEventListener('DOMContentLoaded', function() {
    // Contact form handling
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', handleContactForm);
    }

    // Form validation
    const inputs = contactForm.querySelectorAll('input[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.checkValidity()) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    });

    // Initialize AJAX category filtering
    initializeCategoryFiltering();
});

async function handleContactForm(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const errorDiv = document.getElementById('contactError');
    const successDiv = document.getElementById('contactSuccess');
    const submitButton = form.querySelector('button[type="submit"]');

    // Show loading state
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Se trimite...';

    // Hide previous messages
    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');

    try {
        // Simulate sending email (you would implement actual email sending here)
        const contactData = {
            name: formData.get('name'),
            email: formData.get('email'),
            subject: formData.get('subject'),
            message: formData.get('message'),
            to: 'contact@calimara.ro'
        };

        // For now, just show success message
        // In a real implementation, you would send this to your backend
        await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call

        successDiv.classList.remove('d-none');
        form.reset();
        form.classList.remove('was-validated');
        
        // Clear validation classes
        inputs.forEach(input => {
            input.classList.remove('is-valid', 'is-invalid');
        });

        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('contactModal'));
            modal.hide();
        }, 2000);

    } catch (error) {
        console.error('Contact form error:', error);
        errorDiv.querySelector('.error-message').textContent = 'A apărut o eroare la trimiterea mesajului. Te rugăm să încerci din nou.';
        errorDiv.classList.remove('d-none');
    } finally {
        // Restore button state
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="bi bi-send me-2"></i>Trimite Mesajul';
    }
}

// Animate elements on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0rem 0rem -3.125rem 0rem'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate__animated', 'animate__fadeInUp');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe cards for animation
document.querySelectorAll('.blog-card').forEach(card => {
    observer.observe(card);
});

// Category hover functionality
document.querySelectorAll('.category-item').forEach(categoryItem => {
    const genreDropdown = categoryItem.querySelector('.genre-dropdown');
    let hoverTimeout;

    categoryItem.addEventListener('mouseenter', () => {
        clearTimeout(hoverTimeout);
        genreDropdown.classList.remove('d-none');
    });

    categoryItem.addEventListener('mouseleave', () => {
        hoverTimeout = setTimeout(() => {
            genreDropdown.classList.add('d-none');
        }, 150); // Small delay to allow moving cursor to dropdown
    });
});

// AJAX Category filtering functions

function initializeCategoryFiltering() {
    console.log('Initializing category filtering...');
    const categoryButtons = document.querySelectorAll('.category-filter-btn');
    const postsContainer = document.getElementById('postsContainer');
    
    console.log('Found category buttons:', categoryButtons.length);
    console.log('Found posts container:', !!postsContainer);
    
    if (!postsContainer) {
        console.error('Posts container not found!');
        return;
    }
    
    categoryButtons.forEach((button, index) => {
        console.log(`Adding listener to button ${index}:`, button.dataset.category);
        button.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Category button clicked:', this.dataset.category);
            
            const category = this.dataset.category;
            
            // Update active button
            categoryButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Add loading state
            postsContainer.style.opacity = '0.5';
            postsContainer.style.transition = 'opacity 0.3s ease';
            
            // Fetch filtered posts
            fetchFilteredPosts(category);
        });
    });
}

async function fetchFilteredPosts(category) {
    console.log('Fetching posts for category:', category);
    const postsContainer = document.getElementById('postsContainer');
    
    try {
        const url = `/api/posts/random?category=${encodeURIComponent(category)}&limit=10`;
        console.log('Fetching from URL:', url);
        
        const response = await fetch(url);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: Failed to fetch posts`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        // Animate out current content
        postsContainer.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            // Update content
            renderPosts(data.posts);
            
            // Animate in new content
            postsContainer.style.opacity = '1';
            postsContainer.style.transform = 'translateY(0)';
        }, 300);
        
    } catch (error) {
        console.error('Error fetching filtered posts:', error);
        // Restore opacity on error
        postsContainer.style.opacity = '1';
        postsContainer.style.transform = 'translateY(0)';
    }
}

function renderPosts(posts) {
    const postsContainer = document.getElementById('postsContainer');
    
    if (posts.length === 0) {
        postsContainer.innerHTML = `
            <div class="text-center py-4">
                <i class="bi bi-file-text-x display-4 text-muted mb-3"></i>
                <p class="text-muted">Nu există postări pentru această categorie.</p>
                <a href="/register" class="btn btn-primary-custom">
                    <i class="bi bi-pencil-square me-2"></i>Scrie prima postare
                </a>
            </div>
        `;
        return;
    }
    
    const postsHtml = posts.map(post => `
        <a href="//${post.owner.username}.calimara.ro/${post.slug}" 
           class="list-group-item list-group-item-action border-0 px-0 py-3 hover-lift text-decoration-none">
            <div class="d-flex align-items-start">
                <img src="https://api.dicebear.com/7.x/shapes/svg?seed=${post.owner.avatar_seed}&backgroundColor=f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff&size=45" 
                     alt="Avatar ${post.owner.username}" 
                     class="rounded-circle me-3 flex-shrink-0" 
                     style="width: 2.8125rem; height: 2.8125rem; object-fit: cover;">
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="fw-semibold mb-0 text-dark flex-grow-1 me-2">${escapeHtml(post.title)}</h6>
                        ${post.likes_count > 0 ? `
                            <span class="badge bg-danger rounded-pill">
                                <i class="bi bi-heart-fill me-1"></i>${post.likes_count}
                            </span>
                        ` : ''}
                    </div>
                    <p class="text-muted small mb-2 lh-sm">
                        ${escapeHtml(post.content)}
                    </p>
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center text-muted small">
                            <i class="bi bi-person me-1"></i>
                            <span class="me-3 fw-medium">${escapeHtml(post.owner.username)}</span>
                            <i class="bi bi-clock me-1"></i>
                            <span>${post.created_at}</span>
                        </div>
                        ${post.category_name ? `
                            <div class="d-flex gap-1">
                                <span class="badge bg-accent rounded-pill text-white small">
                                    ${escapeHtml(post.category_name)}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        </a>
    `).join('');
    
    postsContainer.innerHTML = `<div class="list-group list-group-flush">${postsHtml}</div>`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}