function copyBlogUrl() {
    const url = `https://${window.location.hostname.replace('calimara.ro', '{{ current_user.username }}.calimara.ro')}`;
    navigator.clipboard.writeText(url).then(() => {
        showToast('Link-ul blogului a fost copiat în clipboard!', 'success');
    }).catch(() => {
        showToast('Nu s-a putut copia link-ul', 'error');
    });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Dashboard Avatar Selection Logic
    const dashboardAvatarOptions = document.getElementById('dashboardAvatarOptions');
    const currentAvatarPreview = document.getElementById('currentAvatarPreview');
    const newAvatarSeedInput = document.getElementById('newAvatarSeed');
    const generateNewDashboardAvatarsBtn = document.getElementById('generateNewDashboardAvatars');
    
    function generateAvatarSeed() {
        const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < 10; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }
    
    function getDiceBearUrl(seed) {
        return `https://api.dicebear.com/7.x/shapes/svg?seed=${seed}&backgroundColor=f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff&size=80`;
    }
    
    function createDashboardAvatarOption(seed) {
        const option = document.createElement('div');
        option.className = 'dashboard-avatar-option position-relative cursor-pointer';
        option.style.cssText = 'cursor: pointer; transition: transform 0.2s;';
        
        const img = document.createElement('img');
        img.src = getDiceBearUrl(seed);
        img.alt = 'Avatar option';
        img.className = 'rounded-circle border';
        img.width = 50;
        img.height = 50;
        img.style.cssText = 'border: 2px solid transparent;';
        
        option.appendChild(img);
        
        option.addEventListener('click', function() {
            // Remove selected state from all options
            document.querySelectorAll('.dashboard-avatar-option img').forEach(img => {
                img.style.border = '2px solid transparent';
            });
            
            // Add selected state to clicked option
            img.style.border = '2px solid #0d6efd';
            
            // Update preview and hidden input
            currentAvatarPreview.src = getDiceBearUrl(seed);
            newAvatarSeedInput.value = seed;
        });
        
        option.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
        });
        
        option.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
        
        return option;
    }
    
    function generateDashboardAvatarOptions() {
        dashboardAvatarOptions.innerHTML = '';
        const seeds = [];
        
        // Generate 6 different avatar options for dashboard
        for (let i = 0; i < 6; i++) {
            const seed = generateAvatarSeed();
            seeds.push(seed);
            const option = createDashboardAvatarOption(seed);
            dashboardAvatarOptions.appendChild(option);
        }
    }
    
    // Generate new avatars button for dashboard
    generateNewDashboardAvatarsBtn.addEventListener('click', generateDashboardAvatarOptions);
    
    // Generate initial set of avatars for dashboard
    generateDashboardAvatarOptions();

    // URL validation function
    function validateUrl(url, platform) {
        if (!url || url.trim() === '') return true; // Empty URLs are valid
        
        const platformDomains = {
            'facebook': ['facebook.com', 'fb.com'],
            'instagram': ['instagram.com'],
            'tiktok': ['tiktok.com'],
            'x': ['x.com', 'twitter.com'],
            'bluesky': ['bsky.app'],
            'patreon': ['patreon.com'],
            'paypal': ['paypal.me', 'paypal.com'],
            'buymeacoffee': ['buymeacoffee.com']
        };
        
        try {
            const urlObj = new URL(url.toLowerCase());
            const domain = urlObj.hostname.replace('www.', '');
            return platformDomains[platform]?.some(validDomain => domain.includes(validDomain)) || false;
        } catch {
            return false;
        }
    }
    
    // Clear validation states
    function clearValidationStates(form) {
        form.querySelectorAll('.form-control').forEach(input => {
            input.classList.remove('is-invalid', 'is-valid');
        });
        form.querySelectorAll('.invalid-feedback').forEach(feedback => {
            feedback.textContent = '';
        });
    }
    
    // Social Links Form Handling
    const socialLinksForm = document.getElementById("socialLinksForm");
    if (socialLinksForm) {
        socialLinksForm.addEventListener("submit", async function(e) {
            e.preventDefault();
            clearValidationStates(socialLinksForm);
            
            const formData = new FormData(socialLinksForm);
            const socialData = {
                facebook_url: formData.get("facebook_url"),
                tiktok_url: formData.get("tiktok_url"),
                instagram_url: formData.get("instagram_url"),
                x_url: formData.get("x_url"),
                bluesky_url: formData.get("bluesky_url")
            };
            
            // Client-side validation
            let hasErrors = false;
            for (const [field, url] of Object.entries(socialData)) {
                const platform = field.replace('_url', '');
                const input = document.getElementById(field);
                const errorDiv = document.getElementById(field + '_error');
                
                if (url && !validateUrl(url, platform)) {
                    input.classList.add('is-invalid');
                    errorDiv.textContent = `URL-ul trebuie să conțină ${platform === 'x' ? 'x.com sau twitter.com' : platform + '.com'}`;
                    hasErrors = true;
                } else if (url) {
                    input.classList.add('is-valid');
                }
            }
            
            if (hasErrors) {
                showSocialLinksMessage("Te rog corectează erorile de mai sus.", "error");
                return;
            }
            
            try {
                const response = await fetch("/api/user/social-links", {
                    method: "PUT",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(socialData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showSocialLinksMessage("Link-urile sociale au fost salvate cu succes!", "success");
                } else {
                    showSocialLinksMessage(result.detail || "A apărut o eroare la salvarea link-urilor.", "error");
                }
            } catch (error) {
                console.error("Error:", error);
                showSocialLinksMessage("A apărut o eroare la salvarea link-urilor.", "error");
            }
        });
    }
    
    // Donation Links Form Handling
    const donationLinksForm = document.getElementById("donationLinksForm");
    if (donationLinksForm) {
        donationLinksForm.addEventListener("submit", async function(e) {
            e.preventDefault();
            clearValidationStates(donationLinksForm);
            
            const formData = new FormData(donationLinksForm);
            const donationData = {
                buymeacoffee_url: formData.get("buymeacoffee_url")
            };
            
            // Client-side validation
            let hasErrors = false;
            for (const [field, url] of Object.entries(donationData)) {
                const platform = field.replace('_url', '');
                const input = document.getElementById(field);
                const errorDiv = document.getElementById(field + '_error');
                
                if (url && !validateUrl(url, platform)) {
                    input.classList.add('is-invalid');
                    errorDiv.textContent = `URL-ul trebuie să conțină ${platform}.com`;
                    hasErrors = true;
                } else if (url) {
                    input.classList.add('is-valid');
                }
            }
            
            if (hasErrors) {
                showDonationLinksMessage("Te rog corectează erorile de mai sus.", "error");
                return;
            }
            
            try {
                const response = await fetch("/api/user/social-links", {
                    method: "PUT",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(donationData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showDonationLinksMessage("Link-ul de sprijin a fost salvat cu succes!", "success");
                } else {
                    showDonationLinksMessage(result.detail || "A apărut o eroare la salvarea link-ului.", "error");
                }
            } catch (error) {
                console.error("Error:", error);
                showDonationLinksMessage("A apărut o eroare la salvarea link-ului.", "error");
            }
        });
    }
});

function showSocialLinksMessage(message, type) {
    const errorDiv = document.getElementById("socialLinksError");
    const successDiv = document.getElementById("socialLinksSuccess");
    
    // Hide both divs first
    errorDiv.classList.add("d-none");
    successDiv.classList.add("d-none");
    
    if (type === "success") {
        successDiv.querySelector(".success-message").textContent = message;
        successDiv.classList.remove("d-none");
        setTimeout(() => successDiv.classList.add("d-none"), 5000);
    } else {
        errorDiv.querySelector(".error-message").textContent = message;
        errorDiv.classList.remove("d-none");
        setTimeout(() => errorDiv.classList.add("d-none"), 8000);
    }
}

function showDonationLinksMessage(message, type) {
    const errorDiv = document.getElementById("donationLinksError");
    const successDiv = document.getElementById("donationLinksSuccess");
    
    // Hide both divs first
    errorDiv.classList.add("d-none");
    successDiv.classList.add("d-none");
    
    if (type === "success") {
        successDiv.querySelector(".success-message").textContent = message;
        successDiv.classList.remove("d-none");
        setTimeout(() => successDiv.classList.add("d-none"), 5000);
    } else {
        errorDiv.querySelector(".error-message").textContent = message;
        errorDiv.classList.remove("d-none");
        setTimeout(() => errorDiv.classList.add("d-none"), 8000);
    }
}

// Best Friends functionality
document.addEventListener('DOMContentLoaded', function() {
    // Load current best friends
    loadCurrentBestFriends();
    
    // Handle friend search inputs
    document.querySelectorAll('.friend-search').forEach(input => {
        let searchTimeout;
        input.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            const resultsDiv = document.getElementById('results' + this.id.slice(-1));
            
            if (query.length < 2) {
                resultsDiv.innerHTML = '';
                return;
            }
            
            searchTimeout = setTimeout(() => {
                searchFriends(query, resultsDiv, this);
            }, 300);
        });
    });
    
    // Handle best friends form submission
    document.getElementById('bestFriendsForm').addEventListener('submit', saveBestFriends);
});

async function loadCurrentBestFriends() {
    try {
        const response = await fetch('/api/user/me');
        const user = await response.json();
        
        // Note: You'll need to add best friends to the user endpoint response
        // For now, we'll leave the fields empty as this requires backend changes
    } catch (error) {
        console.error('Error loading best friends:', error);
    }
}

async function searchFriends(query, resultsDiv, inputElement) {
    try {
        const response = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
        const users = await response.json();
        
        if (users.length === 0) {
            resultsDiv.innerHTML = '<div class="search-result-item text-muted small">Nu s-au găsit utilizatori</div>';
            return;
        }
        
        resultsDiv.innerHTML = users.map(user => `
            <div class="search-result-item" onclick="selectFriend('${user.username}', '${inputElement.id}')">
                <strong>@${user.username}</strong>
                ${user.subtitle ? `<br><small class="text-muted">${user.subtitle}</small>` : ''}
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error searching friends:', error);
        resultsDiv.innerHTML = '<div class="search-result-item text-danger small">Eroare la căutare</div>';
    }
}

function selectFriend(username, inputId) {
    document.getElementById(inputId).value = username;
    document.getElementById('results' + inputId.slice(-1)).innerHTML = '';
}

async function saveBestFriends(e) {
    e.preventDefault();
    
    const friend1 = document.getElementById('friend1').value.trim();
    const friend2 = document.getElementById('friend2').value.trim();
    const friend3 = document.getElementById('friend3').value.trim();
    
    const friends = [friend1, friend2, friend3].filter(f => f !== '');
    
    try {
        const response = await fetch('/api/user/best-friends', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ friends: friends })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showMessage(true, 'Prietenii au fost salvați cu succes!');
        } else {
            showMessage(false, result.detail || 'Eroare la salvarea prietenilor');
        }
    } catch (error) {
        console.error('Error saving best friends:', error);
        showMessage(false, 'Eroare la salvarea prietenilor');
    }
}

// Featured Posts functionality
document.addEventListener('DOMContentLoaded', function() {
    // Load user's posts and current featured posts
    loadUserPostsAndFeatured();
    
    // Handle featured posts form submission
    document.getElementById('featuredPostsForm').addEventListener('submit', saveFeaturedPosts);
});

async function loadUserPostsAndFeatured() {
    try {
        // Load user's posts for selection
        const response = await fetch('/api/posts/archive');
        const data = await response.json();
        
        const posts = data.posts || [];
        
        // Populate select options
        ['featured1', 'featured2', 'featured3'].forEach(selectId => {
            const select = document.getElementById(selectId);
            
            // Clear existing options except first
            select.innerHTML = '<option value="">Selectează o postare...</option>';
            
            // Add posts as options
            posts.forEach(post => {
                const option = document.createElement('option');
                option.value = post.id;
                option.textContent = `${post.title} (${post.created_at})`;
                select.appendChild(option);
            });
        });
        
        // TODO: Load current featured posts and set selected values
        // This would require adding featured posts to the user data endpoint
        
    } catch (error) {
        console.error('Error loading posts:', error);
        showMessage(false, 'Eroare la încărcarea postărilor');
    }
}

async function saveFeaturedPosts(e) {
    e.preventDefault();
    
    const featured1 = document.getElementById('featured1').value;
    const featured2 = document.getElementById('featured2').value;
    const featured3 = document.getElementById('featured3').value;
    
    const posts = [featured1, featured2, featured3].filter(p => p !== '').map(p => parseInt(p));
    
    // Check for duplicates
    const uniquePosts = [...new Set(posts)];
    if (posts.length !== uniquePosts.length) {
        showMessage(false, 'Nu poți selecta aceeași postare de mai multe ori');
        return;
    }
    
    try {
        const response = await fetch('/api/user/featured-posts', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ posts: posts })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showMessage(true, 'Postările în evidență au fost salvate cu succes!');
        } else {
            showMessage(false, result.detail || 'Eroare la salvarea postărilor în evidență');
        }
    } catch (error) {
        console.error('Error saving featured posts:', error);
        showMessage(false, 'Eroare la salvarea postărilor în evidență');
    }
}