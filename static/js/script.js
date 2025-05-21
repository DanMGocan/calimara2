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

    // No longer need getCookie as login status is session-based (server-side)
    // Function to get cookie by name
    // function getCookie(name) {
    //     const value = `; ${document.cookie}`;
    //     const parts = value.split(`; ${name}=`);
    //     if (parts.length === 2) return parts.pop().split(';').shift();
    //     return null;
    // }

    // Function to check login status and update UI based on server-rendered data
    // This function will primarily hide/show elements based on initial page load
    function checkLoginStatus() {
        // We assume the server has rendered the correct UI state.
        // For dynamic updates, we'll rely on redirects or re-fetching page content.
        const navLoginRegister = document.getElementById('nav-login-register');
        const navLogout = document.getElementById('nav-logout');
        const navCreatePost = document.getElementById('nav-create-post');
        const navAdminDashboard = document.getElementById('nav-admin-dashboard');
        const navMainDomain = document.getElementById('nav-main-domain');

        // Check if current_user is available in the global scope (set by Jinja2 in base.html)
        // This is a simplified check. A more robust way would be to have a hidden input or data attribute.
        // For now, we'll rely on the presence of the logout button as an indicator.
        const isLoggedIn = logoutButton && logoutButton.style.display === 'block'; // If logout button is visible, user is logged in

        if (isLoggedIn) {
            navLoginRegister.style.display = 'none';
            navLogout.style.display = 'block';
            navCreatePost.style.display = 'block';
            navAdminDashboard.style.display = 'block';
            navMainDomain.style.display = 'block';

            // Username is now passed via template context or fetched from a /me API
            // For simplicity, we'll rely on the server to render the username in the logout button text
            // or fetch it via a new API endpoint if needed for dynamic display.
            // For now, the username will be set by the server in the logout button text.
        } else {
            navLoginRegister.style.display = 'block';
            navLogout.style.display = 'none';
            navCreatePost.style.display = 'none';
            navAdminDashboard.style.display = 'none';
            navMainDomain.style.display = 'block';
        }
    }

    // Initial check on page load (this will be less dynamic now)
    // The actual state will be determined by the server rendering the page.
    // This function is mostly for ensuring initial display correctness.
    // We will call it after login/logout/register to force a UI update.
    checkLoginStatus();


    // Login Form Submission
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            console.log('Attempting login with email:', email);

            try {
                const response = await fetch('/api/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password }),
                });

                console.log('Login API response status:', response.status);
                const data = await response.json(); // Expecting {"message": "Logged in successfully", "username": "..."}
                console.log('Login API response data:', data);

                if (response.ok) {
                    loginError.style.display = 'none';
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
                    if (loginModal) loginModal.hide();
                    
                    // Store username in localStorage for display in navbar (since session is httponly)
                    localStorage.setItem('username', data.username); 
                    
                    console.log('Login successful, reloading page to update UI.');
                    // Reload page to get server-rendered logged-in state
                    window.location.reload(); 
                } else {
                    loginError.textContent = data.detail || 'Login failed';
                    loginError.style.display = 'block';
                    console.error('Login failed:', data.detail);
                }
            } catch (error) {
                console.error('Error during login fetch:', error);
                loginError.textContent = 'An unexpected error occurred.';
                loginError.style.display = 'block';
            }
        });
    }

    // Logout Button
    if (logoutButton) {
        logoutButton.addEventListener('click', async (e) => {
            e.preventDefault();
            console.log('Attempting logout.');
            try {
                const response = await fetch('/api/logout', {
                    method: 'GET',
                });
                console.log('Logout API response status:', response.status);
                if (response.ok) {
                    localStorage.removeItem('username'); // Clear stored username
                    console.log('Logout successful, reloading page to update UI.');
                    window.location.reload(); // Reload page to get server-rendered logged-out state
                } else {
                    const data = await response.json();
                    console.error('Logout failed:', data.detail);
                }
            } catch (error) {
                console.error('Error during logout fetch:', error);
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
            console.log('Attempting registration with username:', username, 'email:', email);

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, email, password }),
                });

                console.log('Register API response status:', response.status);
                const data = await response.json();
                console.log('Register API response data:', data);

                if (response.ok) {
                    console.log('Registration successful. Attempting to log in automatically...');
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
                        localStorage.setItem('username', loginData.username); // Store username
                        registerSuccess.textContent = 'Registration successful! Logging you in...';
                        registerSuccess.style.display = 'block';
                        registerError.style.display = 'none';
                        registerForm.reset();
                        console.log('Auto-login successful, reloading page to update UI and redirect.');
                        // Redirect to user's subdomain after successful auto-login
                        window.location.href = `//${loginData.username}.calimara.ro`; 
                    } else {
                        registerError.textContent = loginData.detail || 'Auto-login failed. Please try logging in manually.';
                        registerError.style.display = 'block';
                        registerSuccess.style.display = 'none';
                        console.error('Auto-login failed:', loginData.detail);
                    }
                } else {
                    registerError.textContent = data.detail || 'Registration failed';
                    registerError.style.display = 'block';
                    registerSuccess.style.display = 'none';
                    console.error('Registration failed:', data.detail);
                }
            } catch (error) {
                console.error('Error during registration or auto-login fetch:', error);
                registerError.textContent = 'An unexpected error occurred during registration or auto-login.';
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
            // No longer getting token from cookie, rely on browser sending session cookie
            // const accessToken = getCookie('access_token'); 
            console.log('Attempting to create post with title:', title);

            try {
                const response = await fetch('/api/posts/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'Authorization': accessToken, // No longer sending Authorization header for session auth
                    },
                    body: JSON.stringify({ title, content }),
                });

                console.log('Create Post API response status:', response.status);
                const data = await response.json();
                console.log('Create Post API response data:', data);

                if (response.ok) {
                    postSuccess.textContent = 'Post created successfully!';
                    postSuccess.style.display = 'block';
                    postError.style.display = 'none';
                    createPostForm.reset();
                    console.log('Post created successfully, redirecting to dashboard.');
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
                } else {
                    postError.textContent = data.detail || 'Failed to create post';
                    postError.style.display = 'block';
                    postSuccess.style.display = 'none';
                    console.error('Failed to create post:', data.detail);
                }
            } catch (error) {
                console.error('Error during create post fetch:', error);
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
            // No longer getting token from cookie, rely on browser sending session cookie
            // const accessToken = getCookie('access_token'); 

            try {
                const response = await fetch(`/api/posts/${postId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'Authorization': accessToken, // No longer sending Authorization header for session auth
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
                // No longer getting token from cookie, rely on browser sending session cookie
                // const accessToken = getCookie('access_token'); 
                try {
                    const response = await fetch(`/api/posts/${postId}`, {
                        method: 'DELETE',
                        headers: {
                            // 'Authorization': accessToken, // No longer sending Authorization header for session auth
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
            // No longer getting token from cookie, rely on browser sending session cookie
            // const accessToken = getCookie('access_token'); // May be null if unlogged

            try {
                const response = await fetch(`/api/posts/${postId}/likes`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'Authorization': accessToken || '', // No longer sending Authorization header for session auth
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
            // No longer getting token from cookie, rely on browser sending session cookie
            // const accessToken = getCookie('access_token'); // May be null if unlogged
            const commentErrorDiv = form.querySelector('.comment-error');

            const commentData = { content };
            // If not logged in, include author details
            // We can't check accessToken directly anymore, so we'll assume if username is not in localStorage, they are unlogged
            if (!localStorage.getItem('username')) { 
                commentData.author_name = author_name;
                commentData.author_email = author_email;
            }

            try {
                const response = await fetch(`/api/posts/${postId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'Authorization': accessToken || '', // No longer sending Authorization header for session auth
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
            // No longer getting token from cookie, rely on browser sending session cookie
            // const accessToken = getCookie('access_token'); 
            try {
                const response = await fetch(`/api/comments/${commentId}/approve`, {
                    method: 'PUT',
                    headers: {
                        // 'Authorization': accessToken, // No longer sending Authorization header for session auth
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
                // No longer getting token from cookie, rely on browser sending session cookie
                // const accessToken = getCookie('access_token'); 
                try {
                    const response = await fetch(`/api/comments/${commentId}`, {
                        method: 'DELETE',
                        headers: {
                            // 'Authorization': accessToken, // No longer sending Authorization header for session auth
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
