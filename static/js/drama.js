// ===================================
// CALIMARA - DRAMA PAGE JAVASCRIPT
// ===================================

document.addEventListener('DOMContentLoaded', () => {

    // ===================================
    // 1. Drama Creation Form
    // ===================================
    const createForm = document.getElementById('createDramaForm');
    if (createForm) {
        createForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('dramaTitle')?.value?.trim();
            const description = document.getElementById('dramaDescription')?.value?.trim();
            const characterName = document.getElementById('characterName')?.value?.trim();
            const characterDescription = document.getElementById('characterDescription')?.value?.trim();

            try {
                const response = await fetch('/api/dramas/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, description, character_name: characterName, character_description: characterDescription }),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.href = `/piese/${data.slug}/gestioneaza`;
                } else {
                    showToast(data.detail || 'Eroare la crearea piesei.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 2. Reply Submission
    // ===================================
    const replyForm = document.getElementById('replyForm');
    if (replyForm) {
        replyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = replyForm.dataset.slug;
            const actNumber = replyForm.dataset.act;
            const content = document.getElementById('replyContent')?.value?.trim();
            const stageDirection = document.getElementById('replyStageDirection')?.value?.trim();

            const body = { content };
            if (stageDirection) body.stage_direction = stageDirection;

            try {
                const response = await fetch(`/api/dramas/${slug}/acts/${actNumber}/replies`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la adăugarea replicii.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 3. Invitation Form
    // ===================================
    const inviteForm = document.getElementById('inviteForm');
    if (inviteForm) {
        inviteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = inviteForm.dataset.slug;
            const toUsername = document.getElementById('inviteUsername')?.value?.trim();
            const characterName = document.getElementById('inviteCharacterName')?.value?.trim();
            const message = document.getElementById('inviteMessage')?.value?.trim();

            try {
                const response = await fetch(`/api/dramas/${slug}/invite`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ to_username: toUsername, character_name: characterName, message }),
                });
                const data = await response.json();
                if (response.ok) {
                    showToast('Invitație trimisă cu succes!', 'success');
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la trimiterea invitației.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 4. Application Form
    // ===================================
    const applyForm = document.getElementById('applyForm');
    if (applyForm) {
        applyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = applyForm.dataset.slug;
            const characterName = document.getElementById('applyCharacterName')?.value?.trim();
            const characterDescription = document.getElementById('applyCharacterDescription')?.value?.trim();
            const message = document.getElementById('applyMessage')?.value?.trim();

            try {
                const response = await fetch(`/api/dramas/${slug}/apply`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ character_name: characterName, character_description: characterDescription, message }),
                });
                const data = await response.json();
                if (response.ok) {
                    showToast('Candidatura a fost trimisă cu succes!', 'success');
                    const modal = bootstrap.Modal.getInstance(document.getElementById('applyModal'));
                    if (modal) modal.hide();
                } else {
                    showToast(data.detail || 'Eroare la trimiterea candidaturii.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 5. Invitation Response (Accept / Reject)
    // ===================================
    document.querySelectorAll('.invitation-respond-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const slug = btn.dataset.slug;
            const invitationId = btn.dataset.invitationId;
            const status = btn.dataset.status;

            try {
                const response = await fetch(`/api/dramas/${slug}/invitations/${invitationId}/respond`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status }),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la răspunsul invitației.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    });

    // ===================================
    // 6. Act Management
    // ===================================

    // Create act form
    const createActForm = document.getElementById('createActForm');
    if (createActForm) {
        createActForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = createActForm.dataset.slug;
            const title = document.getElementById('actTitle')?.value?.trim();
            const description = document.getElementById('actDescription')?.value?.trim();

            const body = {};
            if (title) body.title = title;
            if (description) body.description = description;

            try {
                const response = await fetch(`/api/dramas/${slug}/acts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la crearea actului.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // Complete act buttons
    document.querySelectorAll('.complete-act-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Sigur doriți să marcați acest act ca finalizat?')) return;
            const slug = btn.dataset.slug;
            const actNumber = btn.dataset.actNumber;

            try {
                const response = await fetch(`/api/dramas/${slug}/acts/${actNumber}/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la finalizarea actului.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    });

    // ===================================
    // 7. Reply Delete
    // ===================================
    document.querySelectorAll('.delete-reply-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Sigur doriți să ștergeți această replică?')) return;
            const slug = btn.dataset.slug;
            const replyId = btn.dataset.replyId;

            try {
                const response = await fetch(`/api/dramas/${slug}/replies/${replyId}`, {
                    method: 'DELETE',
                });
                if (response.ok || response.status === 204) {
                    const replyEl = btn.closest('[data-reply-id]') || btn.closest('.reply-item');
                    if (replyEl) {
                        replyEl.remove();
                    } else {
                        window.location.reload();
                    }
                    showToast('Replica a fost ștearsă.', 'success');
                } else {
                    const data = await response.json().catch(() => ({}));
                    showToast(data.detail || 'Eroare la ștergerea replicii.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    });

    // ===================================
    // 8. Reply Reorder (HTML5 Drag API)
    // ===================================
    const replyList = document.getElementById('replyReorderList');
    if (replyList) {
        let dragSrcEl = null;

        function handleDragStart(e) {
            dragSrcEl = this;
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', this.dataset.replyId);
        }

        function handleDragOver(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const target = e.currentTarget;
            if (target !== dragSrcEl) {
                const bounding = target.getBoundingClientRect();
                const offset = bounding.y + bounding.height / 2;
                if (e.clientY - offset > 0) {
                    target.after(dragSrcEl);
                } else {
                    target.before(dragSrcEl);
                }
            }
            return false;
        }

        function handleDrop(e) {
            e.stopPropagation();
            return false;
        }

        async function handleDragEnd() {
            this.classList.remove('dragging');
            dragSrcEl = null;

            const slug = replyList.dataset.slug;
            const actNumber = replyList.dataset.act;
            const replyIds = [...replyList.querySelectorAll('.reply-drag-item')].map(el => parseInt(el.dataset.replyId, 10));

            try {
                const url = actNumber
                    ? `/api/dramas/${slug}/replies/reorder?act_number=${actNumber}`
                    : `/api/dramas/${slug}/replies/reorder`;
                const response = await fetch(url, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reply_ids: replyIds }),
                });
                const data = await response.json();
                if (!response.ok) {
                    showToast(data.detail || 'Eroare la reordonarea replicilor.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        }

        replyList.querySelectorAll('.reply-drag-item').forEach(item => {
            item.setAttribute('draggable', 'true');
            item.addEventListener('dragstart', handleDragStart);
            item.addEventListener('dragover', handleDragOver);
            item.addEventListener('drop', handleDrop);
            item.addEventListener('dragend', handleDragEnd);
        });
    }

    // ===================================
    // 9. Complete Drama
    // ===================================
    const completeDramaBtn = document.getElementById('completeDramaBtn');
    if (completeDramaBtn) {
        completeDramaBtn.addEventListener('click', async () => {
            const slug = completeDramaBtn.dataset.slug;

            try {
                const response = await fetch(`/api/dramas/${slug}/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.href = `/piese/${slug}`;
                } else {
                    showToast(data.detail || 'Eroare la finalizarea piesei.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 10. Like Handler
    // ===================================
    const likeBtn = document.getElementById('dramaLikeBtn');
    if (likeBtn) {
        likeBtn.addEventListener('click', async () => {
            const slug = likeBtn.dataset.slug;

            likeBtn.disabled = true;

            try {
                const response = await fetch(`/api/dramas/${slug}/likes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const data = await response.json();
                if (response.ok) {
                    const countEl = document.getElementById('dramaLikeCount');
                    if (countEl && data.likes_count !== undefined) {
                        countEl.textContent = data.likes_count;
                    }
                    likeBtn.classList.add('liked');
                } else {
                    showToast(data.detail || 'Eroare la aprecierea piesei.', 'danger');
                    likeBtn.disabled = false;
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
                likeBtn.disabled = false;
            }
        });
    }

    // ===================================
    // 11. Comment Handler
    // ===================================
    const commentForm = document.getElementById('dramaCommentForm');
    if (commentForm) {
        commentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = commentForm.dataset.slug;
            const content = document.getElementById('commentContent')?.value?.trim();
            const authorName = document.getElementById('commentAuthorName')?.value?.trim();

            const body = { content };
            if (authorName) body.author_name = authorName;

            try {
                const response = await fetch(`/api/dramas/${slug}/comments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await response.json();
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast(data.detail || 'Eroare la adăugarea comentariului.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 12. Drama Edit Form
    // ===================================
    const editForm = document.getElementById('editDramaForm');
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const slug = editForm.dataset.slug;
            const title = document.getElementById('editDramaTitle')?.value?.trim();
            const description = document.getElementById('editDramaDescription')?.value?.trim();
            const isOpenEl = document.getElementById('editDramaIsOpen');
            const isOpenForApplications = isOpenEl ? isOpenEl.checked : undefined;

            const body = { title, description };
            if (isOpenForApplications !== undefined) body.is_open_for_applications = isOpenForApplications;

            try {
                const response = await fetch(`/api/dramas/${slug}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await response.json();
                if (response.ok) {
                    showToast('Piesa a fost actualizată cu succes!', 'success');
                } else {
                    showToast(data.detail || 'Eroare la actualizarea piesei.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    }

    // ===================================
    // 13. Remove Character
    // ===================================
    document.querySelectorAll('.remove-character-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Sigur doriți să eliminați acest personaj?')) return;
            const slug = btn.dataset.slug;
            const characterId = btn.dataset.characterId;

            try {
                const response = await fetch(`/api/dramas/${slug}/characters/${characterId}`, {
                    method: 'DELETE',
                });
                if (response.ok || response.status === 204) {
                    window.location.reload();
                } else {
                    const data = await response.json().catch(() => ({}));
                    showToast(data.detail || 'Eroare la eliminarea personajului.', 'danger');
                }
            } catch (err) {
                showToast('Eroare de rețea. Încearcă din nou.', 'danger');
            }
        });
    });

});
