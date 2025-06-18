# Instructions to Fix Admin 404 Errors on Calimara

## Quick Fix Steps

### 1. Connect to your Azure VM
```bash
ssh dangocan_1@[your-vm-ip]
```

### 2. Check your current Nginx configuration
```bash
# View current configuration
sudo cat /etc/nginx/sites-available/calimara

# Or if using sites-enabled
sudo cat /etc/nginx/sites-enabled/calimara
```

### 3. Backup current configuration
```bash
sudo cp /etc/nginx/sites-available/calimara /etc/nginx/sites-available/calimara.backup
```

### 4. Edit the Nginx configuration
```bash
sudo nano /etc/nginx/sites-available/calimara
```

### 5. Key Changes to Make

The most important change is to ensure you have proper location blocks in the CORRECT ORDER:

```nginx
# 1. Static files first
location /static { ... }

# 2. Admin API routes (MUST come before general /api)
location /api/admin {
    proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
    # ... proxy headers
}

# 3. General API routes
location /api {
    proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
    # ... proxy headers
}

# 4. Root location last
location / {
    proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
    # ... proxy headers
}
```

### 6. Test the configuration
```bash
sudo nginx -t
```

### 7. If test passes, reload Nginx
```bash
sudo systemctl reload nginx
```

### 8. Test the admin endpoint
```bash
# From the VM itself
curl -I http://localhost/api/admin/test-ai-moderation

# Or check the logs while accessing from browser
sudo tail -f /var/log/nginx/access.log
```

## Debugging Commands

### Check if FastAPI is receiving requests
```bash
# Watch Gunicorn logs
sudo journalctl -u calimara -f

# Or if using systemd
sudo systemctl status calimara
```

### Test directly against the socket (bypass Nginx)
```bash
curl --unix-socket /home/dangocan_1/calimara2/calimara.sock \
     http://localhost/api/admin/test-ai-moderation
```

### Check Nginx error logs
```bash
sudo tail -f /var/log/nginx/error.log
```

## Common Issues and Solutions

### Issue 1: Location blocks in wrong order
**Symptom**: `/api/admin/*` routes return 404 but other routes work
**Solution**: Ensure `/api/admin` location block comes BEFORE `/api` location block

### Issue 2: Missing proxy headers
**Symptom**: Routes work but authentication fails
**Solution**: Ensure all proxy headers are set, especially:
- `proxy_set_header Host $host;`
- `proxy_set_header X-Forwarded-Proto $scheme;`

### Issue 3: Socket permissions
**Symptom**: 502 Bad Gateway errors
**Solution**: Check socket permissions:
```bash
ls -la /home/dangocan_1/calimara2/calimara.sock
# Should be readable by nginx user (usually www-data)
```

### Issue 4: Gunicorn not running
**Symptom**: 502 Bad Gateway errors
**Solution**: Restart Gunicorn:
```bash
sudo systemctl restart calimara
```

## Complete Working Example

Here's a minimal working Nginx config that should fix the issue:

```nginx
server {
    listen 80;
    server_name calimara.ro *.calimara.ro;

    # Static files
    location /static {
        alias /home/dangocan_1/calimara2/static;
    }

    # Admin API - MUST be before /api
    location /api/admin {
        proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Other API routes
    location /api {
        proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Everything else
    location / {
        proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## After Applying the Fix

1. Clear your browser cache
2. Try accessing: `http://calimara.ro/api/admin/test-ai-moderation`
3. Check the admin dashboard at: `http://calimara.ro/admin/moderation`

The 404 errors should be resolved!
