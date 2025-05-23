document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const loginError = document.getElementById('loginError');
    const registerForm = document.getElementById('registerForm');
    const registerError = document.getElementById('registerError');
    const registerSuccess = document.getElementById('registerSuccess');
    const createPostForm = document.getElementById('createPostForm');
    const postError = document.getElementById('postError');
    const postSuccess = document.getElementById('postSuccess');
    const editPostForm = document.getElementById('editPostForm');
    const editPostError = document.getElementById('editPostError');
    const editPostSuccess = document.getElementById('editPostSuccess');
    const logoutButton = document.getElementById('logoutButton');
    // Removed loggedInUsernameSpan as it's populated by Jinja2

    // Removed checkLoginStatus function as UI visibility is now controlled by Jinja2
    // Removed localStorage usage for login status

    // Login Form Submission
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            console.log('Se încearcă autentificarea cu email:', email);

            try {
                const response = await fetch('/api/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password }),
                });

                console.log('Status răspuns API autentificare:', response.status);
                const data = await response.json();
                console.log('Date răspuns API autentificare:', data);

                if (response.ok) {
                    loginError.style.display = 'none';
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
                    if (loginModal) loginModal.hide();
                    
                    // No localStorage usage for username
                    
                    console.log('Autentificare reușită, se reîncarcă pagina pentru a actualiza interfața.');
                    window.location.reload(); // Reload page to get server-rendered logged-in state
                } else {
                    loginError.textContent = data.detail || 'Autentificare eșuată';
                    loginError.style.display = 'block';
                    console.error('Autentificare eșuată:', data.detail);
                }
            } catch (error) {
                console.error('Eroare la solicitarea de autentificare:', error);
                loginError.textContent = 'A apărut o eroare neașteptată.';
                loginError.style.display = 'block';
            }
        });
    }

    // Logout Button
    if (logoutButton) {
        logoutButton.addEventListener('click', async (e) => {
            e.preventDefault();
            console.log('Se încearcă deconectarea.');
            try {
                const response = await fetch('/api/logout', {
                    method: 'GET',
                });
                console.log('Status răspuns API deconectare:', response.status);
                if (response.ok) {
                    // No localStorage usage for username
                    console.log('Deconectare reușită, se reîncarcă pagina pentru a actualiza interfața.');
                    window.location.reload(); // Reload page to get server-rendered logged-out state
                } else {
                    const data = await response.json();
                    console.error('Deconectare eșuată:', data.detail);
                }
            } catch (error) {
                console.error('Eroare la solicitarea de deconectare:', error);
            }
        });
    }

    // Register Form Submission
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const subtitle = document.getElementById('subtitle').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            console.log('Se încearcă înregistrarea cu nume de utilizator:', username, 'email:', email, 'motto:', subtitle);

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, subtitle, email, password }),
                });

                console.log('Status răspuns API înregistrare:', response.status);
                const data = await response.json();
                console.log('Date răspuns API înregistrare:', data);

                if (response.ok) {
                    console.log('Înregistrare reușită. Se reîncarcă pagina pentru a actualiza interfața și a redirecționa.');
                    // No auto-login via JS, rely on server redirect after successful registration
                    window.location.href = `//${username.toLowerCase()}.calimara.ro/dashboard`; // Redirect to dashboard
                } else {
                    registerError.textContent = data.detail || 'Înregistrare eșuată';
                    registerError.style.display = 'block';
                    registerSuccess.style.display = 'none';
                    console.error('Înregistrare eșuată:', data.detail);
                }
            } catch (error) {
                console.error('Eroare la solicitarea de înregistrare:', error);
                registerError.textContent = 'A apărut o eroare neașteptată în timpul înregistrării.';
                registerError.style.display = 'block';
                registerSuccess.style.display = 'none';
            }
        });
    }

    // Create Post Form Submission
    if (createPostForm) {
        createPostForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('postTitle').value;
            const content = document.getElementById('postContent').value;
            const categories = document.getElementById('postCategories').value;
            console.log('Se încearcă crearea postării cu titlul:', title, 'categorii:', categories);

            try {
                const response = await fetch('/api/posts/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ title, content, categories }),
                });

                console.log('Status răspuns API creare postare:', response.status);
                const data = await response.json();
                console.log('Date răspuns API creare postare:', data);

                if (response.ok) {
                    postSuccess.textContent = 'Postare creată cu succes!';
                    postSuccess.style.display = 'block';
                    postError.style.display = 'none';
                    createPostForm.reset();
                    console.log('Postare creată cu succes, se redirecționează către panoul de administrare.');
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
                } else {
                    postError.textContent = data.detail || 'Crearea postării a eșuat';
                    postError.style.display = 'block';
                    postSuccess.style.display = 'none';
                    console.error('Crearea postării a eșuat:', data.detail);
                }
            } catch (error) {
                console.error('Eroare la solicitarea de creare postare:', error);
                postError.textContent = 'A apărut o eroare neașteptată.';
                postError.style.display = 'block';
                postSuccess.style.display = 'none';
            }
        });
    }

    // Edit Post Form Submission
    if (editPostForm) {
        editPostForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const postId = editPostForm.dataset.postId;
            const title = document.getElementById('postTitle').value;
            const content = document.getElementById('postContent').value;
            const categories = document.getElementById('postCategories').value;

            try {
                const response = await fetch(`/api/posts/${postId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ title, content, categories }),
                });

                const data = await response.json();

                if (response.ok) {
                    editPostSuccess.textContent = 'Postare actualizată cu succes!';
                    editPostSuccess.style.display = 'block';
                    editPostError.style.display = 'none';
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
                } else {
                    editPostError.textContent = data.detail || 'Actualizarea postării a eșuat';
                    editPostError.style.display = 'block';
                    editPostSuccess.style.display = 'none';
                }
            } catch (error) {
                console.error('Eroare la solicitarea de actualizare postare:', error);
                editPostError.textContent = 'A apărut o eroare neașteptată.';
                editPostError.style.display = 'block';
                editPostSuccess.style.display = 'none';
            }
        });
    }

    // Delete Post Button (on Admin Dashboard)
    document.querySelectorAll('.delete-post-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const postId = e.target.dataset.postId;
            if (confirm('Ești sigur că vrei să ștergi această postare?')) {
                try {
                    const response = await fetch(`/api/posts/${postId}`, {
                        method: 'DELETE',
                        headers: {},
                    });
                    if (response.status === 204) {
                        e.target.closest('tr').remove(); // Remove row from table
                        alert('Postare ștearsă cu succes!');
                    } else {
                        const data = await response.json();
                        alert(data.detail || 'Ștergerea postării a eșuat');
                    }
                } catch (error) {
                    console.error('Eroare la solicitarea de ștergere postare:', error);
                    alert('A apărut o eroare neașteptată.');
                }
            }
        });
    });

    // Like Button
    document.querySelectorAll('.like-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const postId = e.target.dataset.postId;

            try {
                const response = await fetch(`/api/posts/${postId}/likes`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({}),
                });

                if (response.ok) {
                    const data = await response.json();
                    // Update like count on the UI
                    const likesCountSpan = document.getElementById(`likes-count-${postId}`);
                    if (likesCountSpan) {
                        const currentCount = parseInt(likesCountSpan.textContent);
                        likesCountSpan.textContent = currentCount + 1;
                    }
                } else if (response.status === 409) {
                    alert('Ai apreciat deja această postare!');
                } else {
                    const data = await response.json();
                    alert(data.detail || 'Aprecierea postării a eșuat');
                }
            } catch (error) {
                console.error('Eroare la solicitarea de apreciere postare:', error);
                alert('A apărut o eroare neașteptată.');
            }
        });
    });

    // Comment Form Submission
    document.querySelectorAll('.comment-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const postId = form.dataset.postId;
            const content = form.querySelector('textarea[name="content"]').value;
            const author_name = form.querySelector('input[name="author_name"]').value;
            const author_email = form.querySelector('input[name="author_email"]').value;
            const commentErrorDiv = form.querySelector('.comment-error');

            const commentData = { content };
            // If not logged in, include author details
            // No localStorage check needed here, server will validate
            commentData.author_name = author_name;
            commentData.author_email = author_email;

            try {
                const response = await fetch(`/api/posts/${postId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(commentData),
                });

                const data = await response.json();

                if (response.ok) {
                    alert('Comentariu trimis cu succes! Va apărea după aprobare.');
                    form.reset();
                    commentErrorDiv.style.display = 'none';
                } else {
                    commentErrorDiv.textContent = data.detail || 'Trimiterea comentariului a eșuat';
                    commentErrorDiv.style.display = 'block';
                }
            } catch (error) {
                console.error('Eroare la solicitarea de trimitere comentariu:', error);
                commentErrorDiv.textContent = 'A apărut o eroare neașteptată.';
                commentErrorDiv.style.display = 'block';
            }
        });
    });

    // Approve Comment Button (on Admin Dashboard)
    document.querySelectorAll('.approve-comment-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const commentId = e.target.dataset.commentId;
            if (confirm('Are you sure you want to approve this comment?')) {
                try {
                    const response = await fetch(`/api/comments/${commentId}/approve`, {
                        method: 'PUT',
                        headers: {},
                    });
                    if (response.ok) {
                        e.target.closest('tr').remove(); // Remove row from table
                        alert('Comentariu aprobat cu succes!');
                    } else {
                        const data = await response.json();
                        alert(data.detail || 'Aprobarea comentariului a eșuat');
                    }
                } catch (error) {
                    console.error('Eroare la solicitarea de aprobare comentariu:', error);
                    alert('A apărut o eroare neașteptată.');
                }
            }
        });
    });

    // Delete Comment Button (on Admin Dashboard)
    document.querySelectorAll('.delete-comment-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const commentId = e.target.dataset.commentId;
            if (confirm('Ești sigur că vrei să ștergi acest comentariu?')) {
                try {
                    const response = await fetch(`/api/comments/${commentId}`, {
                        method: 'DELETE',
                        headers: {},
                    });
                    if (response.status === 204) {
                        e.target.closest('tr').remove(); // Remove row from table
                        alert('Comentariu șters cu succes!');
                    } else {
                        const data = await response.json();
                        alert(data.detail || 'Ștergerea comentariului a eșuat');
                    }
                } catch (error) {
                    console.error('Eroare la solicitarea de ștergere comentariu:', error);
                    alert('A apărut o eroare neașteptată.');
                }
            }
        });
    });

    // Subtitle Update Form (on Admin Dashboard)
    const subtitleForm = document.getElementById('subtitleForm');
    if (subtitleForm) {
        subtitleForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const subtitle = document.getElementById('subtitle').value;
            const subtitleError = document.getElementById('subtitleError');
            const subtitleSuccess = document.getElementById('subtitleSuccess');

            try {
                const response = await fetch('/api/users/me', {
                    method: 'PUT', // Use PUT for update
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ subtitle }),
                });

                const data = await response.json();

                if (response.ok) {
                    subtitleSuccess.textContent = 'Motto actualizat cu succes!';
                    subtitleSuccess.style.display = 'block';
                    subtitleError.style.display = 'none';
                    // For now, a page reload will reflect the change
                    setTimeout(() => { window.location.reload(); }, 1500);
                } else {
                    subtitleError.textContent = data.detail || 'Actualizarea motto-ului a eșuat';
                    subtitleError.style.display = 'block';
                    subtitleSuccess.style.display = 'none';
                }
            } catch (error) {
                console.error('Error updating subtitle:', error);
                subtitleError.textContent = 'A apărut o eroare neașteptată la actualizarea motto-ului.';
                subtitleError.style.display = 'block';
                subtitleSuccess.style.display = 'none';
            }
        });
    }

    // Mobile Navbar Toggler (Tailwind specific)
    const navbarToggler = document.getElementById('navbar-toggler');
    const navbarNav = document.getElementById('navbarNav');

    if (navbarToggler && navbarNav) {
        navbarToggler.addEventListener('click', () => {
            navbarNav.classList.toggle('hidden');
        });
    }
});
