// ===================================
// NOTIFICATIONS - DROPDOWN AND PAGE
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    const notifBadge = document.getElementById('notifBadge');
    const notifDropdownMenu = document.getElementById('notifDropdownMenu');
    const notifItemsContainer = document.getElementById('notifItemsContainer');
    const markAllReadBtn = document.getElementById('markAllReadBtn');
    const notifDropdown = document.getElementById('notificationDropdown');

    // Fetch unread count and update badge
    async function fetchUnreadCount() {
        try {
            const response = await fetch('/api/notifications/unread-count');
            if (response.ok) {
                const data = await response.json();
                if (notifBadge) {
                    if (data.unread_count > 0) {
                        notifBadge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                        notifBadge.classList.remove('d-none');
                    } else {
                        notifBadge.classList.add('d-none');
                    }
                }
            }
        } catch (error) {
            console.error('Error fetching notification count:', error);
        }
    }

    // Load notifications into dropdown
    async function loadNotifications() {
        if (!notifItemsContainer) return;
        notifItemsContainer.innerHTML = '<li class="text-center p-3"><small>Se incarca...</small></li>';

        try {
            const response = await fetch('/api/notifications?limit=10');
            if (response.ok) {
                const data = await response.json();
                if (data.notifications.length === 0) {
                    notifItemsContainer.innerHTML = '<li class="text-center p-3"><small class="text-muted">Nicio notificare</small></li>';
                    return;
                }

                notifItemsContainer.innerHTML = data.notifications.map(n => {
                    const icon = n.type.includes('drama') ? 'bi-mask' : n.type.includes('message') ? 'bi-envelope' : 'bi-bell';
                    const readClass = n.is_read ? 'text-muted' : 'fw-semibold';
                    const bgClass = n.is_read ? '' : 'bg-light';
                    const timeAgo = formatTimeAgo(n.created_at);

                    return `<li>
                        <a class="dropdown-item ${bgClass} py-2 notification-item"
                           href="${n.link || '#'}"
                           data-notification-id="${n.id}"
                           ${!n.is_read ? 'data-unread="true"' : ''}>
                            <div class="d-flex align-items-start">
                                <i class="bi ${icon} me-2 mt-1"></i>
                                <div>
                                    <div class="${readClass}" style="font-size: 0.875rem;">${n.title}</div>
                                    ${n.message ? `<small class="text-muted">${n.message}</small>` : ''}
                                    <div><small class="text-muted">${timeAgo}</small></div>
                                </div>
                            </div>
                        </a>
                    </li>`;
                }).join('');

                // Add click handlers to mark as read
                notifItemsContainer.querySelectorAll('.notification-item[data-unread]').forEach(item => {
                    item.addEventListener('click', async (e) => {
                        const notifId = item.dataset.notificationId;
                        await markAsRead(notifId);
                    });
                });
            }
        } catch (error) {
            console.error('Error loading notifications:', error);
            notifItemsContainer.innerHTML = '<li class="text-center p-3"><small class="text-danger">Eroare la incarcarea notificarilor</small></li>';
        }
    }

    // Mark single notification as read
    async function markAsRead(notificationId) {
        try {
            await fetch(`/api/notifications/${notificationId}/read`, { method: 'PUT' });
            fetchUnreadCount();
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    // Mark all as read
    async function markAllRead() {
        try {
            const response = await fetch('/api/notifications/read-all', { method: 'PUT' });
            if (response.ok) {
                fetchUnreadCount();
                loadNotifications();
                if (typeof showToast === 'function') {
                    showToast('Toate notificarile au fost marcate ca citite', 'success');
                }
            }
        } catch (error) {
            console.error('Error marking all as read:', error);
        }
    }

    // Format relative time
    function formatTimeAgo(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return 'Acum';
        if (seconds < 3600) return `Acum ${Math.floor(seconds / 60)} min`;
        if (seconds < 86400) return `Acum ${Math.floor(seconds / 3600)} ore`;
        if (seconds < 604800) return `Acum ${Math.floor(seconds / 86400)} zile`;
        return date.toLocaleDateString('ro-RO');
    }

    // Event handlers
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            markAllRead();
        });
    }

    // Load notifications when dropdown opens
    if (notifDropdown) {
        notifDropdown.addEventListener('click', () => {
            loadNotifications();
        });
    }

    // Notifications full page
    const notificationsPageList = document.getElementById('notificationsPageList');
    const markAllReadPageBtn = document.getElementById('markAllReadPageBtn');

    if (notificationsPageList) {
        loadNotificationsPage();
    }

    async function loadNotificationsPage() {
        if (!notificationsPageList) return;

        try {
            const response = await fetch('/api/notifications?limit=50');
            if (response.ok) {
                const data = await response.json();
                if (data.notifications.length === 0) {
                    notificationsPageList.innerHTML = '<div class="text-center p-5"><p class="text-muted">Nicio notificare</p></div>';
                    return;
                }

                notificationsPageList.innerHTML = data.notifications.map(n => {
                    const icon = n.type.includes('drama') ? 'bi-mask' : n.type.includes('message') ? 'bi-envelope' : 'bi-bell';
                    const readClass = n.is_read ? 'border-start-0' : 'border-start border-primary border-3';
                    const bgClass = n.is_read ? '' : 'bg-light';
                    const timeAgo = formatTimeAgo(n.created_at);

                    return `<a href="${n.link || '#'}" class="list-group-item list-group-item-action ${bgClass} ${readClass} notification-page-item"
                              data-notification-id="${n.id}" ${!n.is_read ? 'data-unread="true"' : ''}>
                        <div class="d-flex align-items-start">
                            <i class="bi ${icon} me-3 mt-1 fs-5"></i>
                            <div class="flex-grow-1">
                                <div class="d-flex justify-content-between">
                                    <strong>${n.title}</strong>
                                    <small class="text-muted">${timeAgo}</small>
                                </div>
                                ${n.message ? `<p class="mb-0 text-muted">${n.message}</p>` : ''}
                            </div>
                        </div>
                    </a>`;
                }).join('');

                notificationsPageList.querySelectorAll('.notification-page-item[data-unread]').forEach(item => {
                    item.addEventListener('click', async () => {
                        await markAsRead(item.dataset.notificationId);
                    });
                });
            }
        } catch (error) {
            notificationsPageList.innerHTML = '<div class="text-center p-5"><p class="text-danger">Eroare la incarcarea notificarilor</p></div>';
        }
    }

    if (markAllReadPageBtn) {
        markAllReadPageBtn.addEventListener('click', async () => {
            await markAllRead();
            loadNotificationsPage();
        });
    }

    // Poll for unread count every 30 seconds
    fetchUnreadCount();
    setInterval(fetchUnreadCount, 30000);
});
