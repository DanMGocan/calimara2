# Troubleshooting Cache Issues - Complete Guide

## Changes Made to Fix Caching Issues

### 1. **Deployment Script Updates** (`deploy_vm.py`)
- Added Python cache clearing (`__pycache__` and `*.pyc` files)
- Added Nginx cache clearing
- Added deployment timestamp tracking
- Enhanced verification steps

### 2. **Service Worker Fix**
- Created minimal `static/sw.js` to prevent registration errors
- This stops the "SW registration failed" console error

### 3. **Cache Control Headers**
- Added no-cache headers to moderation API endpoints
- Prevents browser/proxy caching of dynamic API responses

## Steps to Clear All Caches

### On Your Local Machine:
1. **Browser Cache (Most Important!)**
   - Chrome/Edge: Press `Ctrl+Shift+Delete` → Clear browsing data → Cached images and files
   - OR: Open DevTools (F12) → Network tab → Check "Disable cache" → Hard refresh (Ctrl+Shift+R)
   - OR: Test in Incognito/Private mode

2. **Service Worker Cache**
   - Open DevTools → Application tab → Storage → Clear site data
   - OR: Application tab → Service Workers → Unregister

3. **DNS Cache (if needed)**
   ```bash
   # Windows
   ipconfig /flushdns
   
   # Linux/Mac
   sudo systemctl restart systemd-resolved
   # or
   sudo dscacheutil -flushcache
   ```

### On the VM (during deployment):
The updated `deploy_vm.py` now automatically:
- Clears Python bytecode cache
- Clears Nginx cache
- Restarts all services properly

## Manual Cache Clearing on VM

If you need to manually clear caches on the VM:

```bash
# 1. Clear Python cache
find /home/dangocan_1/calimara2 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /home/dangocan_1/calimara2 -name "*.pyc" -delete

# 2. Clear Nginx cache
sudo rm -rf /var/cache/nginx/*

# 3. Restart services
sudo systemctl restart calimara
sudo systemctl restart nginx

# 4. Verify endpoints exist
curl -s http://localhost:8000/api/moderation/test-simple
```

## Verification Steps

After deployment and cache clearing:

1. **Check deployment timestamp**:
   ```bash
   cat /home/dangocan_1/calimara2/last_deployment.txt
   ```

2. **Test moderation endpoint directly**:
   ```bash
   curl -H "Cache-Control: no-cache" https://calimara.ro/api/moderation/test-simple
   ```

3. **Check browser console** for any remaining 404s

## Common Issues and Solutions

### Still getting 404s?
1. Ensure you ran BOTH deployment scripts:
   - Local: `python deploy_local.py`
   - VM: `python deploy_vm.py`

2. Check if behind CDN/WAF:
   - Cloudflare: Purge cache from dashboard
   - Azure CDN: Purge endpoints

3. Try a different browser or device

### Service Worker issues?
- The new `sw.js` file should prevent errors
- Clear browser storage completely

### API calls still cached?
- Check browser DevTools Network tab
- Look for `Cache-Control` headers in response
- Ensure "Disable cache" is checked in DevTools

## Testing the Fix

1. Open browser in Incognito mode
2. Visit `/admin/moderation`
3. Open DevTools Console
4. Should see NO 404 errors
5. Moderation queue should load properly