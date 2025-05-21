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
    // Removed logoutButton and loggedInUsernameSpan as their visibility is now server-side controlled

    // No longer need getCookie or checkLoginStatus as UI is server-side rendered
    // function getCookie(name) { ... }
    // function checkLoginStatus() { ... }

    // Initial check on page load is no longer needed here, as server renders initial state.
    // checkLoginStatus();


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
                    
                    // No longer storing username in localStorage
                    // localStorage.setItem('username', data.username); 
                    
                    console.log('Autentificare reușită, se reîncarcă pagina pentru a actualiza interfața.');
                    // Reload page to get server-rendered logged-in state
                    window.location.reload(); 
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

    // Logout Button (now a direct link to /api/logout, handled by server-side redirect)
    // The logout button is now a simple <a> tag in base.html, so this JS is no longer needed for it.
    // if (logoutButton) {
    //     logoutButton.addEventListener('click', async (e) => {
    //         e.preventDefault();
    //         console.log('Se încearcă deconectarea.');
    //         try {
    //             const response = await fetch('/api/logout', {
    //                 method: 'GET',
    //             });
    //             console.log('Status răspuns API deconectare:', response.status);
    //             if (response.ok) {
    //                 localStorage.removeItem('username'); // Clear stored username
    //                 console.log('Deconectare reușită, se reîncarcă pagina pentru a actualiza interfața.');
    //                 window.location.reload(); // Reload page to get server-rendered logged-out state
    //             } else {
    //                 const data = await response.json();
    //                 console.error('Deconectare eșuată:', data.detail);
    //             }
    //         } catch (error) {
    //             console.error('Eroare la solicitarea de deconectare:', error);
    //         }
    //     });
    // }

    // Register Form Submission
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            console.log('Se încearcă înregistrarea cu nume de utilizator:', username, 'email:', email);

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, email, password }),
                });

                console.log('Status răspuns API înregistrare:', response.status);
                const data = await response.json();
                console.log('Date răspuns API înregistrare:', data);

                if (response.ok) {
                    console.log('Înregistrare reușită. Se încearcă autentificarea automată...');
                    // Attempt to auto-login the user
                    const loginResponse = await fetch('/api/token', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ email, password }),
                    });

                    const loginData = await loginResponse.json();

                    if (loginResponse.ok) {
                        // No longer storing username in localStorage
                        // localStorage.setItem('username', loginData.username); 
                        registerSuccess.textContent = 'Înregistrare reușită! Te autentificăm...';
                        registerSuccess.style.display = 'block';
                        registerError.style.display = 'none';
                        registerForm.reset();
                        console.log('Autentificare automată reușită, se reîncarcă pagina pentru a actualiza interfața și a redirecționa.');
                        // Redirect to user's subdomain after successful auto-login
                        window.location.href = `//${loginData.username}.calimara.ro`; 
                    } else {
                        registerError.textContent = loginData.detail || 'Autentificare automată eșuată. Te rugăm să încerci să te autentifici manual.';
                        registerError.style.display = 'block';
                        registerSuccess.style.display = 'none';
                        console.error('Autentificare automată eșuată:', loginData.detail);
                    }
                } else {
                    registerError.textContent = data.detail || 'Înregistrare eșuată';
                    registerError.style.display = 'block';
                    registerSuccess.style.display = 'none';
                    console.error('Înregistrare eșuată:', data.detail);
                }
            } catch (error) {
                console.error('Eroare la solicitarea de înregistrare sau autentificare automată:', error);
                registerError.textContent = 'A apărut o eroare neașteptată în timpul înregistrării sau autentificării automate.';
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
            if (!localStorage.getItem('username')) { 
                commentData.author_name = author_name;
                commentData.author_email = author_email;
            }

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
});
