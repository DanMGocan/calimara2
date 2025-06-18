document.addEventListener('DOMContentLoaded', function() {
    const setupForm = document.getElementById('setupForm');
    const usernameInput = document.getElementById('username');
    
    // Form submission
    setupForm.addEventListener('submit', handleSetupSubmit);
    
    // Real-time validation
    const inputs = setupForm.querySelectorAll('input[required]');
    inputs.forEach(input => {
        let hasBeenTouched = false;
        
        input.addEventListener('input', function() {
            hasBeenTouched = true;
        });
        
        input.addEventListener('blur', function() {
            if (hasBeenTouched) {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            }
        });
    });

    // Username validation and preview
    usernameInput.addEventListener('input', function() {
        const username = this.value.toLowerCase();
        const preview = document.querySelector('.input-group-text');
        
        if (username && /^[a-zA-Z0-9]+$/.test(username)) {
            preview.textContent = '.calimara.ro';
            preview.classList.remove('text-danger');
            preview.classList.add('text-success');
        } else {
            preview.textContent = '.calimara.ro';
            preview.classList.remove('text-success');
            if (username) {
                preview.classList.add('text-danger');
            }
        }
    });

    // Character counter for subtitle
    const subtitleInput = document.getElementById('subtitle');
    const maxLength = subtitleInput.getAttribute('maxlength');
    
    if (maxLength) {
        const counter = document.createElement('small');
        counter.className = 'text-muted character-counter';
        counter.textContent = `0/${maxLength}`;
        subtitleInput.parentNode.appendChild(counter);
        
        subtitleInput.addEventListener('input', function() {
            const currentLength = this.value.length;
            counter.textContent = `${currentLength}/${maxLength}`;
            counter.className = currentLength > maxLength * 0.9 ? 'text-warning character-counter' : 'text-muted character-counter';
        });
    }

    // Avatar Selection Logic (same as register page)
    initializeAvatarSelection();
});

async function handleSetupSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const errorDiv = document.getElementById('setupError');
    const successDiv = document.getElementById('setupSuccess');

    // Hide previous messages
    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');

    // Show loading state
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Se finalizează...';

    try {
        const setupData = {
            username: formData.get('username'),
            subtitle: formData.get('subtitle') || null,
            avatar_seed: formData.get('avatar_seed')
        };

        const response = await fetch('/api/auth/complete-setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(setupData),
        });

        const data = await response.json();

        if (response.ok) {
            successDiv.querySelector('.success-message').textContent = 'Călimara ta a fost creată cu succes!';
            successDiv.classList.remove('d-none');
            
            setTimeout(() => {
                window.location.href = `https://${data.username}.calimara.ro/dashboard`;
            }, 1500);
        } else {
            errorDiv.querySelector('.error-message').textContent = data.detail || 'Finalizarea contului a eșuat';
            errorDiv.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Setup error:', error);
        errorDiv.querySelector('.error-message').textContent = 'A apărut o eroare neașteptată.';
        errorDiv.classList.remove('d-none');
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = originalText;
    }
}

function initializeAvatarSelection() {
    const avatarOptions = document.getElementById('avatarOptions');
    const selectedAvatarPreview = document.getElementById('selectedAvatarPreview');
    const avatarSeedInput = document.getElementById('avatarSeed');
    const generateNewAvatarsBtn = document.getElementById('generateNewAvatars');
    const usernameForAvatar = document.getElementById('username');
    
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
    
    function createAvatarOption(seed) {
        const option = document.createElement('div');
        option.className = 'avatar-option position-relative cursor-pointer';
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
            document.querySelectorAll('.avatar-option img').forEach(img => {
                img.style.border = '2px solid transparent';
            });
            
            // Add selected state to clicked option
            img.style.border = '2px solid #0d6efd';
            
            // Update preview and hidden input
            selectedAvatarPreview.src = getDiceBearUrl(seed);
            avatarSeedInput.value = seed;
        });
        
        option.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
        });
        
        option.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
        
        return option;
    }
    
    function generateAvatarOptions() {
        avatarOptions.innerHTML = '';
        const seeds = [];
        
        // Generate 8 different avatar options
        for (let i = 0; i < 8; i++) {
            const seed = generateAvatarSeed();
            seeds.push(seed);
            const option = createAvatarOption(seed);
            avatarOptions.appendChild(option);
        }
        
        // Auto-select the first avatar
        if (seeds.length > 0) {
            const firstOption = avatarOptions.firstChild.querySelector('img');
            firstOption.style.border = '2px solid #0d6efd';
            selectedAvatarPreview.src = getDiceBearUrl(seeds[0]);
            avatarSeedInput.value = seeds[0];
        }
    }
    
    // Generate initial set of avatars
    generateAvatarOptions();
    
    // Generate new random avatars button
    generateNewAvatarsBtn.addEventListener('click', generateAvatarOptions);
}