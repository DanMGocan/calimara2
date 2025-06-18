document.addEventListener('DOMContentLoaded', function() {
    const titleInput = document.getElementById('postTitle');
    const contentInput = document.getElementById('postContent');
    const categoriesInput = document.getElementById('postCategories');
    const previewButton = document.getElementById('previewPost');
    const deleteButton = document.getElementById('deletePost');
    const revertButton = document.getElementById('revertChanges');
    const undoButton = document.getElementById('undoChanges');
    const autoSaveStatus = document.getElementById('autoSaveStatus');
    const changeStatus = document.getElementById('changeStatus');
    
    // Store original values
    const originalValues = {
        title: titleInput.value,
        content: contentInput.value,
        categories: categoriesInput.value
    };
    
    let hasUnsavedChanges = false;
    let lastSavedValues = { ...originalValues };

    // Character counters
    const titleMaxLength = titleInput.getAttribute('maxlength');
    if (titleMaxLength) {
        const titleCounter = document.createElement('small');
        titleCounter.className = 'text-muted character-counter float-end';
        titleCounter.textContent = `${titleInput.value.length}/${titleMaxLength}`;
        titleInput.parentNode.appendChild(titleCounter);
        
        titleInput.addEventListener('input', function() {
            const currentLength = this.value.length;
            titleCounter.textContent = `${currentLength}/${titleMaxLength}`;
            titleCounter.className = currentLength > titleMaxLength * 0.9 ? 'text-warning character-counter float-end' : 'text-muted character-counter float-end';
        });
    }

    // Content word counter
    const contentCounter = document.createElement('small');
    contentCounter.className = 'text-muted character-counter float-end';
    const initialWordCount = contentInput.value.trim().split(/\s+/).filter(word => word.length > 0).length;
    contentCounter.textContent = `${initialWordCount} cuvinte`;
    contentInput.parentNode.appendChild(contentCounter);
    
    contentInput.addEventListener('input', function() {
        const wordCount = this.value.trim().split(/\s+/).filter(word => word.length > 0).length;
        contentCounter.textContent = `${wordCount} cuvinte`;
    });

    // Track changes
    function checkForChanges() {
        const currentValues = {
            title: titleInput.value,
            content: contentInput.value,
            categories: categoriesInput.value
        };
        
        hasUnsavedChanges = JSON.stringify(currentValues) !== JSON.stringify(lastSavedValues);
        
        if (hasUnsavedChanges) {
            changeStatus.innerHTML = '<i class="bi bi-exclamation-circle me-1 text-warning"></i>Modificări nesalvate';
        } else {
            changeStatus.innerHTML = '<i class="bi bi-check-circle me-1 text-success"></i>Toate modificările sunt salvate';
        }
        
        return hasUnsavedChanges;
    }

    // Formatting buttons
    document.getElementById('formatBold').addEventListener('click', function() {
        insertFormatting('**', '**', 'text îngroșat');
    });
    
    document.getElementById('formatItalic').addEventListener('click', function() {
        insertFormatting('*', '*', 'text cursiv');
    });
    
    document.getElementById('insertLink').addEventListener('click', function() {
        const url = prompt('Introdu URL-ul:');
        if (url) {
            insertFormatting('[', `](${url})`, 'text link');
        }
    });

    function insertFormatting(before, after, placeholder) {
        const start = contentInput.selectionStart;
        const end = contentInput.selectionEnd;
        const selectedText = contentInput.value.substring(start, end);
        const replacement = selectedText || placeholder;
        
        contentInput.value = contentInput.value.substring(0, start) + 
                           before + replacement + after + 
                           contentInput.value.substring(end);
        
        contentInput.focus();
        contentInput.setSelectionRange(start + before.length, start + before.length + replacement.length);
        checkForChanges();
    }

    // Undo changes
    undoButton.addEventListener('click', function() {
        if (confirm('Anulezi ultima modificare?')) {
            // Simple undo - could be enhanced with proper history
            document.execCommand('undo');
            checkForChanges();
        }
    });

    // Revert to original
    revertButton.addEventListener('click', function() {
        if (confirm('Revii la versiunea originală? Toate modificările se vor pierde.')) {
            titleInput.value = originalValues.title;
            contentInput.value = originalValues.content;
            categoriesInput.value = originalValues.categories;
            checkForChanges();
            showToast('Postarea a fost revenită la versiunea originală', 'info');
        }
    });

    // Preview functionality
    previewButton.addEventListener('click', function() {
        const title = titleInput.value || 'Fără titlu';
        const content = contentInput.value || 'Fără conținut';
        const categories = categoriesInput.value;
        
        document.getElementById('previewTitle').textContent = title;
        
        if (categories) {
            document.getElementById('previewCategories').textContent = categories;
            document.getElementById('previewCategoriesContainer').style.display = 'inline';
            document.getElementById('previewCategoriesIcon').style.display = 'inline';
        } else {
            document.getElementById('previewCategoriesContainer').style.display = 'none';
            document.getElementById('previewCategoriesIcon').style.display = 'none';
        }
        
        // Simple markdown-like formatting
        let formattedContent = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
            .replace(/\n/g, '<br>');
        
        document.getElementById('previewBody').innerHTML = formattedContent;
        
        const modal = new bootstrap.Modal(document.getElementById('previewModal'));
        modal.show();
    });

    // Delete functionality
    deleteButton.addEventListener('click', function() {
        const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
        modal.show();
    });

    document.getElementById('confirmDelete').addEventListener('click', async function() {
        const postId = document.getElementById('editPostForm').dataset.postId;
        
        try {
            const response = await fetch(`/api/posts/${postId}`, {
                method: 'DELETE'
            });
            
            if (response.status === 204) {
                showToast('Postarea a fost ștearsă cu succes!', 'success');
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                const data = await response.json();
                showToast(data.detail || 'Ștergerea postării a eșuat', 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            showToast('A apărut o eroare neașteptată.', 'error');
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteModal'));
        modal.hide();
    });

    // Auto-save functionality
    let autoSaveTimeout;
    function autoSave() {
        if (!checkForChanges()) return;
        
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(() => {
            const formData = {
                title: titleInput.value,
                content: contentInput.value,
                categories: categoriesInput.value
            };
            localStorage.setItem(`calimara_editPost_${document.getElementById('editPostForm').dataset.postId}`, JSON.stringify(formData));
            autoSaveStatus.innerHTML = '<i class="bi bi-check-circle me-1 text-success"></i>Salvat automat local';
            
            setTimeout(() => {
                autoSaveStatus.innerHTML = '<i class="bi bi-cloud me-1"></i>Salvare automată activă';
            }, 2000);
        }, 1000);
    }

    // Attach change tracking and auto-save to inputs
    [titleInput, contentInput, categoriesInput].forEach(input => {
        input.addEventListener('input', () => {
            checkForChanges();
            autoSave();
        });
    });

    // Warn before leaving with unsaved changes
    window.addEventListener('beforeunload', function(e) {
        if (hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // Clear saved data on successful submission
    document.getElementById('editPostForm').addEventListener('submit', function() {
        localStorage.removeItem(`calimara_editPost_${this.dataset.postId}`);
        hasUnsavedChanges = false;
    });

    // Real-time validation
    const form = document.getElementById('editPostForm');
    const inputs = form.querySelectorAll('input[required], textarea[required]');
    
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

    // Keyboard shortcuts
    contentInput.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'b':
                    e.preventDefault();
                    document.getElementById('formatBold').click();
                    break;
                case 'i':
                    e.preventDefault();
                    document.getElementById('formatItalic').click();
                    break;
                case 'k':
                    e.preventDefault();
                    document.getElementById('insertLink').click();
                    break;
                case 's':
                    e.preventDefault();
                    document.getElementById('editPostForm').dispatchEvent(new Event('submit'));
                    break;
            }
        }
    });

    // Initial change check
    checkForChanges();
});