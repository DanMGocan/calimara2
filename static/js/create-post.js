document.addEventListener('DOMContentLoaded', function() {
    const titleInput = document.getElementById('postTitle');
    const contentInput = document.getElementById('postContent');
    const categorySelect = document.getElementById('postCategory');
    const previewButton = document.getElementById('previewPost');
    const clearButton = document.getElementById('clearForm');
    const autoSaveStatus = document.getElementById('autoSaveStatus');
    
    // Initialize QuillJS Editor
    window.quill = new Quill('#quillEditor', {
        theme: 'snow',
        placeholder: 'Scrie-ți aici gândurile, poemele, povestirile...\n\nLasă-ți creativitatea să curgă liber!',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, 3, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'color': [] }, { 'background': [] }],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                [{ 'indent': '-1'}, { 'indent': '+1' }],
                [{ 'align': [] }],
                ['blockquote', 'code-block'],
                ['link'],
                ['clean']
            ]
        }
    });
    
    // Sync QuillJS content with hidden textarea
    window.quill.on('text-change', function() {
        const html = window.quill.root.innerHTML;
        contentInput.value = html;
        
        // Trigger validation check
        if (window.quill.getText().trim().length > 0) {
            contentInput.setCustomValidity('');
        } else {
            contentInput.setCustomValidity('Te rugăm să adaugi conținut pentru postarea ta.');
        }
    });
    
    // Toast notification function
    function showToast(message, type = 'info') {
        // Simple alert fallback - could be enhanced with proper toast UI later
        console.log(`${type.toUpperCase()}: ${message}`);
    }
    
    // Tags functionality
    const tagsInput = document.getElementById('postTags');
    const tagsList = document.getElementById('tagsList');
    let currentTags = [];
    
    function renderTags() {
        tagsList.innerHTML = '';
        currentTags.forEach((tag, index) => {
            const tagElement = document.createElement('span');
            tagElement.className = 'badge bg-primary me-1 mb-1';
            tagElement.innerHTML = `${tag} <button type="button" class="btn-close btn-close-white ms-1" onclick="removeTag(${index})" style="font-size: 0.6em;"></button>`;
            tagsList.appendChild(tagElement);
        });
    }
    
    window.removeTag = function(index) {
        currentTags.splice(index, 1);
        renderTags();
        updateTagsInput();
    };
    
    function updateTagsInput() {
        tagsInput.value = currentTags.join(' ');
    }
    
    function addTag(tagText) {
        const tag = tagText.trim();
        if (tag && tag.length <= 12 && currentTags.length < 6 && !currentTags.includes(tag)) {
            currentTags.push(tag);
            renderTags();
            updateTagsInput();
            return true;
        }
        return false;
    }
    
    tagsInput.addEventListener('keydown', function(e) {
        if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            const words = this.value.trim().split(/\s+/);
            const newTag = words[words.length - 1];
            
            if (newTag) {
                if (addTag(newTag)) {
                    this.value = '';
                } else {
                    // Show validation error
                    if (newTag.length > 12) {
                        this.setCustomValidity('Eticheta poate avea maximum 12 caractere');
                    } else if (currentTags.length >= 6) {
                        this.setCustomValidity('Poți adăuga maximum 6 etichete');
                    } else if (currentTags.includes(newTag)) {
                        this.setCustomValidity('Această etichetă există deja');
                    }
                    this.reportValidity();
                    setTimeout(() => this.setCustomValidity(''), 3000);
                }
            }
        }
    });
    
    tagsInput.addEventListener('input', function() {
        this.setCustomValidity('');
    });
    
    // Character counters
    const titleMaxLength = titleInput.getAttribute('maxlength');
    if (titleMaxLength) {
        const titleCounter = document.createElement('small');
        titleCounter.className = 'text-muted character-counter float-end';
        titleCounter.textContent = `0/${titleMaxLength}`;
        titleInput.parentNode.appendChild(titleCounter);
        
        titleInput.addEventListener('input', function() {
            const currentLength = this.value.length;
            titleCounter.textContent = `${currentLength}/${titleMaxLength}`;
            titleCounter.className = currentLength > titleMaxLength * 0.9 ? 'text-warning character-counter float-end' : 'text-muted character-counter float-end';
        });
    }

    // Content word counter for QuillJS
    const contentCounter = document.createElement('small');
    contentCounter.className = 'text-muted character-counter float-end mt-2';
    contentCounter.textContent = '0 cuvinte';
    document.getElementById('quillEditor').parentNode.appendChild(contentCounter);
    
    // Update word count when QuillJS content changes
    window.quill.on('text-change', function() {
        const text = window.quill.getText().trim();
        const wordCount = text ? text.split(/\s+/).filter(word => word.length > 0).length : 0;
        contentCounter.textContent = `${wordCount} cuvinte`;
    });

    // Note: Formatting is now handled by QuillJS toolbar, so removing old formatting buttons

    // Preview functionality
    previewButton.addEventListener('click', function() {
        const title = titleInput.value || 'Fără titlu';
        const content = window.quill.root.innerHTML || '<p>Fără conținut</p>';
        const category = categorySelect.options[categorySelect.selectedIndex]?.text || '';
        const tags = currentTags.join(', ');
        
        document.getElementById('previewTitle').textContent = title;
        document.getElementById('previewDate').textContent = new Date().toLocaleDateString('ro-RO');
        
        let categoryText = '';
        if (category && category !== 'Selectează o categorie...') {
            categoryText = category;
            if (tags) {
                categoryText += ` • ${tags}`;
            }
        } else if (tags) {
            categoryText = tags;
        }
        
        if (categoryText) {
            document.getElementById('previewCategories').textContent = categoryText;
            document.getElementById('previewCategoriesContainer').style.display = 'inline';
            document.getElementById('previewCategoriesIcon').style.display = 'inline';
        } else {
            document.getElementById('previewCategoriesContainer').style.display = 'none';
            document.getElementById('previewCategoriesIcon').style.display = 'none';
        }
        
        // QuillJS already provides HTML content, so use it directly
        document.getElementById('previewBody').innerHTML = content;
        
        const modal = new bootstrap.Modal(document.getElementById('previewModal'));
        modal.show();
    });

    // Clear form
    clearButton.addEventListener('click', function() {
        if (confirm('Ești sigur că vrei să resetezi formularul? Toate modificările nesalvate se vor pierde.')) {
            document.getElementById('createPostForm').reset();
            window.quill.setContents([]);
            currentTags = [];
            renderTags();
            updateTagsInput();
            localStorage.removeItem('calimara_createPostForm');
            showToast('Formularul a fost resetat', 'info');
        }
    });

    // Auto-save functionality
    let autoSaveTimeout;
    function autoSave() {
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(() => {
            const formData = {
                title: titleInput.value,
                content: window.quill.root.innerHTML,
                category: categorySelect.value,
                tags: currentTags
            };
            localStorage.setItem('calimara_createPostForm', JSON.stringify(formData));
            autoSaveStatus.innerHTML = '<i class="bi bi-check-circle me-1 text-success"></i>Salvat automat';
            
            setTimeout(() => {
                autoSaveStatus.innerHTML = '<i class="bi bi-cloud me-1"></i>Salvare automată activă';
            }, 2000);
        }, 1000);
    }

    // Load saved data
    const savedData = localStorage.getItem('calimara_createPostForm');
    if (savedData) {
        const data = JSON.parse(savedData);
        titleInput.value = data.title || '';
        
        if (data.content) {
            try {
                window.quill.root.innerHTML = data.content;
                contentInput.value = data.content;
            } catch (e) {
                console.error('Error loading saved content:', e);
            }
        }
        
        if (data.category) {
            categorySelect.value = data.category;
        }
        
        if (data.tags && Array.isArray(data.tags)) {
            currentTags = data.tags;
            renderTags();
            updateTagsInput();
        }
        
        if (data.title || data.content || data.category) {
            showToast('Date salvate automat au fost restaurate', 'info');
        }
    }

    // Attach auto-save to inputs
    [titleInput, categorySelect, tagsInput].forEach(input => {
        input.addEventListener('input', autoSave);
        input.addEventListener('change', autoSave);
    });
    
    // Add auto-save to QuillJS editor
    window.quill.on('text-change', autoSave);

    // Clear saved data on successful submission and trigger animation
    document.getElementById('createPostForm').addEventListener('submit', function(e) {
        const submitButton = this.querySelector('button[type="submit"]');
        
        // Add animation class
        submitButton.classList.add('create-animation');
        
        // Remove animation class after animation completes
        setTimeout(() => {
            submitButton.classList.remove('create-animation');
        }, 600);
        
        localStorage.removeItem('calimara_createPostForm');
    });

    // Real-time validation
    const form = document.getElementById('createPostForm');
    const inputs = form.querySelectorAll('input[required], select[required]');
    
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
    
    // Note: Form submission is handled by script.js handleCreatePost function

    // Note: QuillJS handles keyboard shortcuts automatically (Ctrl+B for bold, Ctrl+I for italic, etc.)
});