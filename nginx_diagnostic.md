# Nginx Configuration Diagnostic for Calimara Admin 404 Issues

## Problem Summary
FastAPI admin endpoints return 404 errors when accessed via browser, despite being properly defined in the application.

## Likely Root Cause
The Nginx reverse proxy configuration is not correctly forwarding `/api/admin/*` requests to the FastAPI application socket.

## Diagnostic Steps

### 1. Check Current Nginx Configuration
On your Azure VM, run:
```bash
sudo cat /etc/nginx/sites-available/calimara
# or
sudo cat /etc/nginx/sites-enabled/calimara
```

### 2. Common Nginx Configuration Issues

#### Issue A: Missing or Incorrect Location Block
Your Nginx config might be missing a proper location block for API routes. Ensure you have:

```nginx
server {
    listen 80;
    server_name calimara.ro *.calimara.ro;
    
    # This location block should handle ALL /api/* routes
    location /api {
        proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Root location for everything else
    location / {
        proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Static files
    location /static {
        alias /home/dangocan_1/calimara2/static;
    }
}
```

#### Issue B: Order of Location Blocks
If you have multiple location blocks, ensure `/api` comes before more general patterns:

```nginx
# CORRECT ORDER
location /api { ... }
location /static { ... }
location / { ... }

# WRONG ORDER (/ would catch everything first)
location / { ... }
location /api { ... }
```

#### Issue C: Regex Location Blocks Interfering
Check if you have any regex location blocks that might be catching `/api/*` requests:

```nginx
# This would catch /api routes before they reach the /api location block
location ~ \.(js|css|png|jpg|gif|ico)$ {
    # ...
}
```

### 3. Quick Fix Solution

Add this specific location block for admin routes if missing:

```nginx
# Add this BEFORE the general /api location block
location /api/admin {
    proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    
    # Add these for debugging
    proxy_redirect off;
    proxy_buffering off;
}
```

### 4. Testing After Changes

After modifying Nginx configuration:

```bash
# Test configuration
sudo nginx -t

# If test passes, reload Nginx
sudo systemctl reload nginx

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Check access logs while making a request
sudo tail -f /var/log/nginx/access.log
```

### 5. Alternative: Using Upstream Block

For better organization, you can use an upstream block:

```nginx
upstream calimara_app {
    server unix:/home/dangocan_1/calimara2/calimara.sock;
}

server {
    listen 80;
    server_name calimara.ro *.calimara.ro;
    
    location /api {
        proxy_pass http://calimara_app;
        include proxy_params;  # If you have a proxy_params file
    }
    
    location / {
        proxy_pass http://calimara_app;
        include proxy_params;
    }
}
```

### 6. Debug Headers

Add these headers temporarily to debug:

```nginx
location /api/admin {
    add_header X-Debug-Message "Admin API route matched" always;
    add_header X-Upstream-Status $upstream_status always;
    
    proxy_pass http://unix:/home/dangocan_1/calimara2/calimara.sock;
    # ... rest of proxy settings
}
```

## Common Pitfalls

1. **Trailing slashes**: Ensure consistency in trailing slashes
   - `location /api` vs `location /api/`
   - `proxy_pass http://unix:/path/to/sock` vs `proxy_pass http://unix:/path/to/sock/`

2. **SSL/HTTPS**: If using HTTPS, ensure proper SSL configuration and that FastAPI knows it's behind HTTPS proxy

3. **Permissions**: Verify Nginx user can access the socket file:
   ```bash
   ls -la /home/dangocan_1/calimara2/calimara.sock
   ```

4. **Firewall**: Check if any firewall rules might be blocking internal communication

## Verification Commands

```bash
# Check if FastAPI is actually receiving requests
sudo journalctl -u calimara -f

# Test directly against the socket (bypass Nginx)
curl --unix-socket /home/dangocan_1/calimara2/calimara.sock http://localhost/api/admin/test-ai-moderation

# Check Nginx is running
sudo systemctl status nginx

# Check all listening ports/sockets
sudo ss -tlnp
```

## Expected Solution

Most likely, your Nginx configuration is missing proper location blocks for `/api/*` routes or they're in the wrong order. Adding the location blocks shown above should resolve the 404 errors.
