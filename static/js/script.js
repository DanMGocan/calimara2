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
    const loggedInUsernameSpan = document.getElementById('loggedInUsername');

    // Function to get cookie by name
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // Function to check login status and update UI
    function checkLoginStatus() {
        const accessToken = getCookie('access_token');
        const navLoginRegister = document.getElementById('nav-login-register');
        const navLogout = document.getElementById('nav-logout');
        const navCreatePost = document.getElementById('nav-create-post');
        const navAdminDashboard = document.getElementById('nav-admin-dashboard');
        const navMainDomain = document.getElementById('nav-main-domain');

        if (accessToken) {
            // User is logged in
            navLoginRegister.style.display = 'none';
            navLogout.style.display = 'block';
            navCreatePost.style.display = 'block';
            navAdminDashboard.style.display = 'block';
            navMainDomain.style.display = 'block'; // Always show main domain link

            // Decode JWT to get username (or store username in another cookie)
            // For simplicity, let's assume username is also stored in a cookie or returned by login API
            const username = localStorage.getItem('username'); // Assuming username is stored in localStorage on login
            if (loggedInUsernameSpan && username) {
                loggedInUsernameSpan.textContent = username;
            }
        } else {
            // User is not logged in
            navLoginRegister.style.display = 'block';
            navLogout.style.display = 'none';
            navCreatePost.style.display = 'none';
            navAdminDashboard.style.display = 'none';
            navMainDomain.style.display = 'block'; // Always show main domain link
        }
    }

    // Initial check on page load
    checkLoginStatus();

    // Login Form Submission
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;

            try {
                const response = await fetch('/api/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password }),
                });

                const data = await response.json();

                if (response.ok) {
                    localStorage.setItem('username', data.username); // Store username
                    loginError.style.display = 'none';
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
                    if (loginModal) loginModal.hide();
                    checkLoginStatus();
                    // Redirect to dashboard or user's blog
                    window.location.href = `/dashboard`; // Or `http://${data.username}.calimara.ro`
                } else {
                    loginError.textContent = data.detail || 'Login failed';
                    loginError.style.display = 'block';
                }
            } catch (error) {
                console.error('Error:', error);
                loginError.textContent = 'An unexpected error occurred.';
                loginError.style.display = 'block';
            }
        });
    }

    // Logout Button
    if (logoutButton) {
        logoutButton.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                const response = await fetch('/api/logout', {
                    method: 'GET',
                });
                if (response.ok) {
                    localStorage.removeItem('username'); // Clear stored username
                    checkLoginStatus();
                    window.location.href = '/'; // Redirect to main page
                } else {
                    console.error('Logout failed');
                }
            } catch (error) {
                console.error('Error:', error);
            }
        });
    }

    // Register Form Submission
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, email, password }),
                });

                const data = await response.json();

                if (response.ok) {
                    registerSuccess.textContent = 'Registration successful! You can now log in.';
                    registerSuccess.style.display = 'block';
                    registerError.style.display = 'none';
                    registerForm.reset();
                    // Optionally, auto-login or redirect to login modal
                    // setTimeout(() => { window.location.href = '/'; }, 2000);
                } else {
                    registerError.textContent = data.detail || 'Registration failed';
                    registerError.style.display = 'block';
                    registerSuccess.style.display = 'none';
                }
            } catch (error) {
                console.error('Error:', error);
                registerError.textContent = 'An unexpected error occurred.';
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
            const accessToken = getCookie('access_token');

            try {
                const response = await fetch('/api/posts/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': accessToken,
                    },
                    body: JSON.stringify({ title, content }),
                });

                const data = await response.json();

                if (response.ok) {
                    postSuccess.textContent = 'Post created successfully!';
                    postSuccess.style.display = 'block';
                    postError.style.display = 'none';
                    createPostForm.reset();
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
                } else {
                    postError.textContent = data.detail || 'Failed to create post';
                    postError.style.display = 'block';
                    postSuccess.style.display = 'none';
                }
            } catch (error) {
                console.error('Error:', error);
                postError.textContent = 'An unexpected error occurred.';
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
            const accessToken = getCookie('access_token');

            try {
                const response = await fetch(`/api/posts/${postId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': accessToken,
                    },
                    body: JSON.stringify({ title, content }),
                });

                const data = await response.json();

                if (response.ok) {
                    editPostSuccess.textContent = 'Post updated successfully!';
                    editPostSuccess.style.display = 'block';
                    editPostError.style.display = 'none';
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
                } else {
                    editPostError.textContent = data.detail || 'Failed to update post';
                    editPostError.style.display = 'block';
                    editPostSuccess.style.display = 'none';
                }
            } catch (error) {
                console.error('Error:', error);
                editPostError.textContent = 'An unexpected error occurred.';
                editPostError.style.display = 'block';
                editPostSuccess.style.display = 'none';
            }
        });
    }

    // Delete Post Button (on Admin Dashboard)
    document.querySelectorAll('.delete-post-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const postId = e.target.dataset.postId;
            if (confirm('Are you sure you want to delete this post?')) {
                const accessToken = getCookie('access_token');
                try {
                    const response = await fetch(`/api/posts/${postId}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': accessToken,
                        },
                    });
                    if (response.status === 204) {
                        e.target.closest('tr').remove(); // Remove row from table
                        alert('Post deleted successfully!');
                    } else {
                        const data = await response.json();
                        alert(data.detail || 'Failed to delete post');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('An unexpected error occurred.');
                }
            }
        });
    });

    // Like Button
    document.querySelectorAll('.like-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const postId = e.target.dataset.postId;
            const accessToken = getCookie('access_token'); // May be null if unlogged

            try {
                const response = await fetch(`/api/posts/${postId}/likes`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': accessToken || '', // Send empty if not logged in
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
                    alert('You have already liked this post!');
                } else {
                    const data = await response.json();
                    alert(data.detail || 'Failed to like post');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An unexpected error occurred.');
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
            const accessToken = getCookie('access_token'); // May be null if unlogged
            const commentErrorDiv = form.querySelector('.comment-error');

            const commentData = { content };
            if (!accessToken) { // Only include if unlogged
                commentData.author_name = author_name;
                commentData.author_email = author_email;
            }

            try {
                const response = await fetch(`/api/posts/${postId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': accessToken || '',
                    },
                    body: JSON.stringify(commentData),
                });

                const data = await response.json();

                if (response.ok) {
                    alert('Comment submitted successfully! It will appear after approval.');
                    form.reset();
                    commentErrorDiv.style.display = 'none';
                } else {
                    commentErrorDiv.textContent = data.detail || 'Failed to submit comment';
                    commentErrorDiv.style.display = 'block';
                }
            } catch (error) {
                console.error('Error:', error);
                commentErrorDiv.textContent = 'An unexpected error occurred.';
                commentErrorDiv.style.display = 'block';
            }
        });
    });

    // Approve Comment Button (on Admin Dashboard)
    document.querySelectorAll('.approve-comment-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const commentId = e.target.dataset.commentId;
            const accessToken = getCookie('access_token');
            try {
                const response = await fetch(`/api/comments/${commentId}/approve`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': accessToken,
                    },
                });
                if (response.ok) {
                    e.target.closest('tr').remove(); // Remove row from table
                    alert('Comment approved successfully!');
                } else {
                    const data = await response.json();
                    alert(data.detail || 'Failed to approve comment');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An unexpected error occurred.');
            }
        });
    });

    // Delete Comment Button (on Admin Dashboard)
    document.querySelectorAll('.delete-comment-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const commentId = e.target.dataset.commentId;
            if (confirm('Are you sure you want to delete this comment?')) {
                const accessToken = getCookie('access_token');
                try {
                    const response = await fetch(`/api/comments/${commentId}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': accessToken,
                        },
                    });
                    if (response.status === 204) {
                        e.target.closest('tr').remove(); // Remove row from table
                        alert('Comment deleted successfully!');
                    } else {
                        const data = await response.json();
                        alert(data.detail || 'Failed to delete comment');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('An unexpected error occurred.');
                }
            }
        });
    });
});
