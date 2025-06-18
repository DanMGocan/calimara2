document.addEventListener('DOMContentLoaded', function() {
    loadModerationStats();
    loadPendingContent();
    
    // Content type filter change
    const contentTypeFilter = document.getElementById('contentTypeFilter');
    if (contentTypeFilter) {
        contentTypeFilter.addEventListener('change', loadPendingContent);
    }
    
    // Test AI button
    const testAIButton = document.getElementById('testAIButton');
    if (testAIButton) {
        testAIButton.addEventListener('click', testAIModeration);
    }
    
    // Tab switching
    const tabs = document.querySelectorAll('#moderationTabs button[data-bs-toggle="tab"]');
    tabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const target = e.target.getAttribute('data-bs-target');
            switch(target) {
                case '#pending-pane':
                    loadPendingContent();
                    break;
                case '#flagged-pane':
                    loadFlaggedContent();
                    break;
                case '#ai-queue-pane':
                    loadAIQueue();
                    break;
                case '#ai-logs-pane':
                    loadAILogs('all');
                    break;
                case '#users-pane':
                    loadUsers();
                    break;
                case '#analytics-pane':
                    loadAnalytics();
                    break;
            }
        });
    });
});

function loadModerationStats() {
    fetch('/api/admin/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('pendingCount').innerHTML = `<i class="bi bi-clock-history"></i> ${data.pending_count}`;
            document.getElementById('flaggedCount').innerHTML = `<i class="bi bi-flag"></i> ${data.flagged_count}`;
            document.getElementById('suspendedCount').innerHTML = `<i class="bi bi-person-x"></i> ${data.suspended_count}`;
            document.getElementById('todayActions').innerHTML = `<i class="bi bi-check-circle"></i> ${data.today_actions}`;
        })
        .catch(error => console.error('Error loading stats:', error));
}

function loadPendingContent() {
    const contentType = document.getElementById('contentTypeFilter')?.value || 'all';
    fetch(`/api/admin/content/pending?content_type=${contentType}`)
        .then(response => response.json())
        .then(data => {
            renderContentQueue(data.content, 'pendingContent');
        })
        .catch(error => console.error('Error loading pending content:', error));
}

function loadFlaggedContent() {
    fetch('/api/admin/content/flagged')
        .then(response => response.json())
        .then(data => {
            renderContentQueue(data.content, 'flaggedContent');
        })
        .catch(error => console.error('Error loading flagged content:', error));
}

function renderContentQueue(content, containerId) {
    const container = document.getElementById(containerId);
    if (!content || content.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="bi bi-check-circle text-success display-1"></i>
                <h5 class="mt-3">All Clear!</h5>
                <p class="text-muted">No content needs review at the moment.</p>
            </div>
        `;
        return;
    }
    
    const html = content.map(item => {
        const toxicityColor = item.toxicity_score > 0.7 ? 'danger' : item.toxicity_score > 0.4 ? 'warning' : 'success';
        const statusColor = item.moderation_status === 'flagged' ? 'danger' : item.moderation_status === 'pending' ? 'warning' : 'info';
        
        return `
        <div class="card mb-3 ${item.toxicity_score > 0.7 ? 'border-danger' : item.toxicity_score > 0.4 ? 'border-warning' : ''}">
            <div class="card-header d-flex justify-content-between align-items-center">
                <div>
                    <span class="badge bg-${item.type === 'post' ? 'primary' : 'secondary'}">${item.type.toUpperCase()}</span>
                    <span class="text-muted ms-2">by @${item.author}</span>
                    <span class="badge bg-${statusColor} ms-2">${item.moderation_status.toUpperCase()}</span>
                    ${item.toxicity_score !== null ? `<span class="badge bg-${toxicityColor} ms-2">AI Score: ${(item.toxicity_score * 100).toFixed(1)}%</span>` : ''}
                </div>
                <div class="btn-group">
                    <button class="btn btn-success btn-sm" onclick="moderateContent(${item.id}, '${item.type}', 'approve')" title="Approve Content">
                        <i class="bi bi-check"></i> Approve
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="moderateContent(${item.id}, '${item.type}', 'reject')" title="Reject Content">
                        <i class="bi bi-x"></i> Reject
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="moderateContent(${item.id}, '${item.type}', 'delete')" title="Delete Content">
                        <i class="bi bi-trash"></i>
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="viewContent(${item.id}, '${item.type}')" title="View Full Content">
                        <i class="bi bi-eye"></i>
                    </button>
                </div>
            </div>
            <div class="card-body">
                ${item.title ? `<h6 class="card-title">${item.title}</h6>` : ''}
                <p class="card-text">${item.content.substring(0, 200)}${item.content.length > 200 ? '...' : ''}</p>
                ${item.moderation_reason ? `<div class="alert alert-light p-2 mt-2"><small><strong>AI Reason:</strong> ${item.moderation_reason}</small></div>` : ''}
                <small class="text-muted">
                    <i class="bi bi-clock"></i> ${new Date(item.created_at).toLocaleString()}
                </small>
            </div>
        </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

function moderateContent(id, type, action) {
    const reason = prompt(`Enter reason for ${action} (optional):`);
    
    fetch(`/api/admin/moderate/${type}/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reason })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Content ${action}ed successfully`, 'success');
            loadPendingContent();
            loadFlaggedContent();
            loadModerationStats();
        } else {
            showToast(data.message || 'Action failed', 'danger');
        }
    })
    .catch(error => {
        console.error('Error moderating content:', error);
        showToast('Error performing action', 'danger');
    });
}

function loadUsers() {
    fetch('/api/admin/users/search?q=')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('usersList');
            if (!data.users || data.users.length === 0) {
                container.innerHTML = '<p class="text-muted">No users found.</p>';
                return;
            }
            
            const html = data.users.slice(0, 20).map(user => `
                <div class="card mb-2">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-title mb-1">${user.username}</h6>
                                <small class="text-muted">${user.email}</small>
                                ${user.is_admin ? '<span class="badge bg-danger ms-2">Admin</span>' : ''}
                                ${user.is_moderator ? '<span class="badge bg-warning ms-2">Moderator</span>' : ''}
                                ${user.is_suspended ? '<span class="badge bg-secondary ms-2">Suspended</span>' : ''}
                            </div>
                            <div>
                                <small class="text-muted">Joined: ${new Date(user.created_at).toLocaleDateString()}</small>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = html;
        })
        .catch(error => console.error('Error loading users:', error));
}

function loadAnalytics() {
    const container = document.getElementById('recentActions');
    container.innerHTML = `
        <div class="alert alert-info">
            <i class="bi bi-info-circle me-2"></i>
            Analytics and charts will be implemented in a future version.
            <br><br>
            For now, you can see moderation statistics in the overview cards above.
        </div>
    `;
}

function viewContent(id, type) {
    // Simple content viewer - could be enhanced with a modal
    alert(`Viewing ${type} ID: ${id}. Full content viewer coming soon.`);
}

function loadAIQueue() {
    fetch('/api/admin/moderation/queue')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('aiQueue');
            if (!data.queue || data.queue.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-success text-center">
                        <i class="bi bi-check-circle-fill me-2"></i>
                        <strong>Nu există conținut marcat pentru revizuire!</strong>
                        <br><small>Toate postările și comentariile au fost procesate.</small>
                    </div>
                `;
                return;
            }

            const html = data.queue.map(item => {
                const content = item.content;
                const analysis = item.ai_analysis;
                
                return `
                <div class="card mb-3 border-warning">
                    <div class="card-header bg-warning bg-opacity-10">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <span class="badge bg-warning text-dark">${item.content_type.toUpperCase()}</span>
                                <strong>${content.title || (content.post_title ? 'Comment on: ' + content.post_title : 'Comment')}</strong>
                            </div>
                            <div>
                                <span class="badge bg-danger">Toxicitate: ${(analysis.toxicity_score || 0).toFixed(2)}</span>
                                <button class="btn btn-success btn-sm me-1" onclick="reviewContent(${item.log_id}, 'approved')">
                                    <i class="bi bi-check"></i> Aprobă
                                </button>
                                <button class="btn btn-danger btn-sm" onclick="reviewContent(${item.log_id}, 'rejected')">
                                    <i class="bi bi-x"></i> Respinge
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="card-text">${content.content}</p>
                        <div class="row mt-3">
                            <div class="col-md-6">
                                <small class="text-muted">
                                    <strong>Autor:</strong> ${content.author}<br>
                                    <strong>Data:</strong> ${new Date(content.created_at).toLocaleString()}
                                </small>
                            </div>
                            <div class="col-md-6">
                                <div class="ai-scores">
                                    <small><strong>AI Analiză:</strong></small><br>
                                    <small>Toxicitate: ${(analysis.toxicity_score || 0).toFixed(2)}</small><br>
                                    <small>Hărțuire: ${(analysis.harassment_score || 0).toFixed(2)}</small><br>
                                    <small>Discurs de ură: ${(analysis.hate_speech_score || 0).toFixed(2)}</small><br>
                                    <small>Conținut explicit: ${(analysis.sexually_explicit_score || 0).toFixed(2)}</small><br>
                                    <small>Înjurături românești: ${(analysis.romanian_profanity_score || 0).toFixed(2)}</small>
                                </div>
                            </div>
                        </div>
                        ${analysis.reason ? `<div class="alert alert-warning p-2 mt-2"><small><strong>Motiv AI:</strong> ${analysis.reason}</small></div>` : ''}
                    </div>
                </div>
                `;
            }).join('');
            
            container.innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading AI queue:', error);
            document.getElementById('aiQueue').innerHTML = '<div class="alert alert-danger">Error loading AI review queue</div>';
        });
}

function loadAILogs(decision = 'all') {
    const url = decision === 'all' ? '/api/admin/moderation/logs' : `/api/admin/moderation/logs?decision=${decision}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('aiLogs');
            if (!data.logs || data.logs.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-info text-center">
                        <i class="bi bi-info-circle me-2"></i>
                        Nu există jurnale pentru filtrul selectat.
                    </div>
                `;
                return;
            }

            const html = data.logs.map(log => {
                let badgeClass = 'secondary';
                let icon = 'question-circle';
                
                switch(log.ai_decision) {
                    case 'approved':
                        badgeClass = 'success';
                        icon = 'check-circle';
                        break;
                    case 'flagged':
                        badgeClass = 'warning';
                        icon = 'flag';
                        break;
                    case 'rejected':
                        badgeClass = 'danger';
                        icon = 'x-circle';
                        break;
                }

                return `
                <div class="card mb-2 border-${badgeClass} border-opacity-25">
                    <div class="card-body py-2">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <div class="d-flex align-items-center mb-1">
                                    <span class="badge bg-${badgeClass} me-2">
                                        <i class="bi bi-${icon}"></i> ${log.ai_decision.toUpperCase()}
                                    </span>
                                    <span class="badge bg-secondary me-2">${log.content_type.toUpperCase()}</span>
                                    <strong class="me-2">${log.content_title}</strong>
                                    ${log.human_decision ? `<span class="badge bg-info">Human: ${log.human_decision}</span>` : ''}
                                </div>
                                <p class="mb-1 text-muted small">${log.content_preview}</p>
                                <div class="row">
                                    <div class="col-md-8">
                                        <small class="text-muted">
                                            <strong>Autor:</strong> ${log.content_author} | 
                                            <strong>Data:</strong> ${new Date(log.created_at).toLocaleString()}
                                            ${log.moderator ? ` | <strong>Moderat de:</strong> ${log.moderator}` : ''}
                                        </small>
                                    </div>
                                    <div class="col-md-4 text-end">
                                        <small class="text-muted">
                                            Toxicitate: <strong>${(log.toxicity_score || 0).toFixed(2)}</strong>
                                        </small>
                                    </div>
                                </div>
                                ${log.ai_reason ? `<div class="mt-1"><small class="text-info"><strong>AI:</strong> ${log.ai_reason}</small></div>` : ''}
                                ${log.human_reason ? `<div class="mt-1"><small class="text-primary"><strong>Human:</strong> ${log.human_reason}</small></div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
            
            container.innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading AI logs:', error);
            document.getElementById('aiLogs').innerHTML = '<div class="alert alert-danger">Error loading AI logs</div>';
        });
}

function reviewContent(logId, decision) {
    const reason = prompt(`Motiv pentru ${decision === 'approved' ? 'aprobare' : 'respingere'}:`);
    if (reason === null) return; // User cancelled
    
    fetch(`/api/admin/moderation/review/${logId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, reason })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Conținut ${decision === 'approved' ? 'aprobat' : 'respins'} cu succes`, 'success');
            loadAIQueue(); // Refresh queue
            loadModerationStats(); // Refresh stats
        } else {
            showToast(data.message || 'Acțiunea a eșuat', 'danger');
        }
    })
    .catch(error => {
        console.error('Error reviewing content:', error);
        showToast('Eroare la procesarea acțiunii', 'danger');
    });
}

function testAIModeration() {
    const testButton = document.getElementById('testAIButton');
    testButton.disabled = true;
    testButton.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Testing...';
    
    fetch('/api/admin/test-ai-moderation')
        .then(response => response.json())
        .then(data => {
            if (data.ai_working) {
                showToast('AI Moderation is working! Check console for details.', 'success');
                console.log('AI Moderation Test Results:', data);
            } else {
                showToast(`AI Moderation failed: ${data.error}`, 'danger');
                console.error('AI Moderation Test Failed:', data);
            }
        })
        .catch(error => {
            console.error('Test failed:', error);
            showToast('Test request failed. Check if you have admin access.', 'danger');
        })
        .finally(() => {
            testButton.disabled = false;
            testButton.innerHTML = '<i class="bi bi-cpu me-1"></i>Test AI';
        });
}

function showToast(message, type) {
    // Simple toast implementation
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}