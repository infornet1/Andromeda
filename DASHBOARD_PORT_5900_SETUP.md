# Dashboard Direct Port 5900 Access - Setup Complete

**Date**: 2025-10-24
**Status**: ✅ OPERATIONAL

## Configuration Summary

The dashboard is now accessible directly at:
```
https://dev.ueipab.edu.ve:5900/
```

## Architecture

```
Internet
   ↓
Port 5900 (HTTPS)
   ↓
Nginx SSL Proxy
   ↓
Port 5901 (HTTP)
   ↓
Flask Dashboard App
```

### Components:

1. **Nginx** listens on port 5900 with SSL/TLS
   - Uses Let's Encrypt certificates
   - Handles HTTPS encryption
   - Proxies to Flask app on port 5901

2. **Flask App** runs on port 5901 (HTTP only)
   - No SSL overhead
   - Faster startup
   - Simpler configuration

## Files Modified

### 1. Nginx Configuration
**File**: `/etc/nginx/sites-available/dashboard-5900`
```nginx
server {
    listen 5900 ssl;
    server_name dev.ueipab.edu.ve;

    ssl_certificate /etc/letsencrypt/live/dev.ueipab.edu.ve/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dev.ueipab.edu.ve/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5901/;
        ...
    }
}
```

### 2. Flask Application
**File**: `/var/www/dev/trading/adx_strategy_v2/dashboard_web.py`

Changed from:
- Port 5900 with SSL context
- Flask handling SSL directly (was causing hangs)

To:
- Port 5901 HTTP only
- Nginx handles SSL termination

## Access URLs

| URL | Description |
|-----|-------------|
| https://dev.ueipab.edu.ve:5900/ | Primary dashboard access (HTTPS) |
| https://dev.ueipab.edu.ve:5900/health | Health check endpoint |
| https://dev.ueipab.edu.ve/trading/ | Alternative path (still works) |
| http://localhost:5901 | Local direct access to Flask |

## Port Status

```bash
$ netstat -tlnp | grep -E ':(5900|5901)'
tcp  0  0  0.0.0.0:5900  0.0.0.0:*  LISTEN  nginx
tcp  0  0  0.0.0.0:5901  0.0.0.0:*  LISTEN  python3 (dashboard)
```

## Service Management

```bash
# Restart dashboard
sudo systemctl restart adx-dashboard.service

# Reload nginx (after config changes)
sudo systemctl reload nginx

# Check status
systemctl status adx-dashboard.service
curl -sk https://dev.ueipab.edu.ve:5900/health
```

## Benefits of This Setup

1. **Proper SSL handling**: Nginx is production-ready for SSL
2. **No Flask SSL issues**: Flask development server no longer hangs
3. **Better performance**: Nginx handles SSL termination efficiently
4. **Standard practice**: Nginx reverse proxy is industry standard
5. **Easy to debug**: Flask runs simple HTTP, easier to troubleshoot

## Troubleshooting

### Dashboard not accessible
```bash
# Check both services
systemctl status adx-dashboard.service
systemctl status nginx

# Check ports
netstat -tlnp | grep -E ':(5900|5901)'

# Test locally
curl http://localhost:5901/health
curl -sk https://localhost:5900/health
```

### SSL certificate issues
```bash
# Check cert validity
sudo openssl x509 -in /etc/letsencrypt/live/dev.ueipab.edu.ve/fullchain.pem -noout -dates

# Renew if needed
sudo certbot renew
sudo systemctl reload nginx
```

## Previous Issue (Resolved)

**Problem**: Flask was trying to handle SSL directly on port 5900
- Flask's development server doesn't handle SSL well
- Connections were timing out
- SSL handshake was hanging

**Solution**: 
- Nginx handles SSL on port 5900
- Flask runs simple HTTP on port 5901
- Nginx proxies requests between them

---

**Configuration tested and verified working: 2025-10-24 03:26 UTC**
