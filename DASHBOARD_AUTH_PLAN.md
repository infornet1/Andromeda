# Dashboard Authentication & User Management - Implementation Plan

**Date:** 2025-10-20
**Status:** 📋 PLANNING (Awaiting User Approval)
**Priority:** HIGH (Security Enhancement)

---

## 📊 CURRENT ARCHITECTURE ANALYSIS

### Current Stack:
- **Backend:** Flask (Python 3)
- **Frontend:** Vanilla JavaScript (ES6+)
- **Data Exchange:** Yes, using AJAX/Fetch API
- **API Endpoints:** RESTful JSON APIs
- **Database:** SQLite (TradeDatabase)
- **No Authentication:** Dashboard is currently open/unprotected

### Current API Endpoints:
```
GET  /                    → Dashboard HTML page
GET  /api/status          → Bot status, account, positions (JSON)
GET  /api/adx             → ADX indicators (JSON)
GET  /api/trades          → Trade history (JSON)
GET  /api/performance     → Performance stats (JSON)
GET  /api/risk            → Risk management status (JSON)
GET  /health              → Health check (JSON)
```

### AJAX Usage: ✅ YES
- All data fetched via `fetch()` API (modern AJAX)
- Auto-refresh every 5 seconds
- Asynchronous parallel requests using `Promise.all()`
- JSON response format

---

## 🎯 PROPOSED SOLUTION

### Architecture: Session-Based Authentication with Role-Based Access Control (RBAC)

### Technology Stack:
```
Backend:
- Flask-Login (session management)
- Flask-Bcrypt (password hashing)
- Flask-WTF (form validation & CSRF protection)
- SQLite database (users table)

Frontend:
- Login/logout pages (HTML + CSS)
- Admin panel (HTML + JavaScript)
- Session token in cookies
- AJAX requests with credentials
```

---

## 🗄️ DATABASE SCHEMA

### New Table: `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'viewer',  -- 'admin' or 'viewer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,  -- admin user who created this user
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
```

### User Roles:
| Role | Permissions |
|------|-------------|
| **admin** | Full access: View dashboard + Manage users + Change settings |
| **viewer** | Read-only: View dashboard only (no user management) |

### Default Admin User (created on first run):
```
Username: admin
Password: (set during first setup via CLI command)
Role: admin
```

---

## 🔐 AUTHENTICATION FLOW

### 1. Login Process
```
User visits https://dev.ueipab.edu.ve:5900/
    ↓
Not authenticated? → Redirect to /login
    ↓
User enters credentials
    ↓
POST /api/auth/login
    ↓
Backend validates credentials
    ↓
Success: Create session → Redirect to /
Failure: Show error message
```

### 2. Session Management
```
- Session stored server-side (Flask session)
- Session ID in HTTP-only cookie (secure)
- Session timeout: 8 hours (configurable)
- Remember me option: 30 days
```

### 3. Protected Routes
```
All /api/* endpoints require authentication
All dashboard pages require authentication
Only /login, /api/auth/login, /health are public
```

### 4. Role-Based Access
```
Viewer Role:
  ✅ View dashboard (/)
  ✅ Access all /api/* endpoints
  ❌ Access /admin routes
  ❌ Manage users

Admin Role:
  ✅ Everything viewers can do
  ✅ Access /admin panel
  ✅ Create/edit/delete users
  ✅ View audit logs
  ✅ Change system settings
```

---

## 🎨 UI DESIGN

### 1. Login Page (`/login`)
```
┌─────────────────────────────────────┐
│                                     │
│   🤖 ADX STRATEGY v2.0              │
│      Live Trading Dashboard         │
│                                     │
│   ┌───────────────────────────┐   │
│   │ Username: [____________] │   │
│   │                           │   │
│   │ Password: [____________] │   │
│   │                           │   │
│   │ [ ] Remember me           │   │
│   │                           │   │
│   │      [  LOGIN  ]          │   │
│   └───────────────────────────┘   │
│                                     │
│   Forgot password? Contact admin   │
│                                     │
└─────────────────────────────────────┘
```

**Features:**
- Clean, modern dark theme (matching dashboard)
- Password field with show/hide toggle
- Remember me checkbox
- Input validation (client + server side)
- Error messages (invalid credentials, account locked, etc.)
- Rate limiting (prevent brute force)

### 2. Dashboard Header (Updated)
```
┌─────────────────────────────────────────────────────────┐
│ 🤖 ADX STRATEGY v2.0          [👤 john_doe ▼]  [LIVE] │
│    Live Trading Dashboard           └─────────┘         │
└─────────────────────────────────────────────────────────┘
                                           │
                                           ├─ Profile
                                           ├─ Admin Panel (admins only)
                                           ├─ Change Password
                                           └─ Logout
```

**Changes:**
- Add user dropdown menu in top-right corner
- Show current username
- Role indicator badge (👑 Admin / 👁️ Viewer)
- Quick access to admin panel (admins only)
- Logout button

### 3. Admin Panel (`/admin`)
```
┌─────────────────────────────────────────────────────────────┐
│ 🔧 ADMIN PANEL                              [Back to Dashboard] │
└─────────────────────────────────────────────────────────────┘

┌─── User Management ──────────────────────────────────────┐
│                                                           │
│  [+ Create New User]                         [Search: __] │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Username      Email              Role    Status     │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │ admin         admin@email.com    👑 ADMIN  Active   │ │
│  │   Created: 2025-10-20           [Edit] [Delete]    │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │ john_doe      john@email.com     👁️ VIEWER Active   │ │
│  │   Created: 2025-10-20           [Edit] [Delete]    │ │
│  │   Last login: 2 hours ago                          │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │ jane_trader   jane@email.com     👁️ VIEWER Inactive │ │
│  │   Created: 2025-10-19           [Edit] [Delete]    │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘

┌─── Audit Log ────────────────────────────────────────────┐
│                                                           │
│  Recent Activity (Last 50 actions):                      │
│                                                           │
│  • 2025-10-20 10:45:23 - admin logged in                │
│  • 2025-10-20 10:30:15 - admin created user 'john_doe'  │
│  • 2025-10-20 09:12:45 - jane_trader logged out         │
│  • 2025-10-19 18:23:11 - admin changed user role        │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### 4. Create/Edit User Modal
```
┌─────────────────────────────────────┐
│  Create New User              [×]   │
├─────────────────────────────────────┤
│                                     │
│  Username: *                        │
│  [_________________________]        │
│                                     │
│  Email:                             │
│  [_________________________]        │
│                                     │
│  Password: *                        │
│  [_________________________]        │
│                                     │
│  Confirm Password: *                │
│  [_________________________]        │
│                                     │
│  Role: *                            │
│  ( ) Admin  (•) Viewer              │
│                                     │
│  [ ] Send welcome email             │
│                                     │
│     [Cancel]      [Create User]     │
│                                     │
└─────────────────────────────────────┘
```

**Validation Rules:**
- Username: 3-20 chars, alphanumeric + underscore
- Password: Min 8 chars, must include uppercase, lowercase, number
- Email: Valid email format (optional)
- Role: Required selection

---

## 🔧 BACKEND IMPLEMENTATION

### New Files to Create:

#### 1. `src/auth/user_database.py`
```python
"""
User Database Management
Handles user CRUD operations, authentication
"""

class UserDatabase:
    def __init__(self, db_path='data/users.db'):
        # Initialize SQLite connection
        # Create users table if not exists

    def create_user(self, username, password, email, role, created_by):
        # Hash password with bcrypt
        # Insert into database
        # Return user object

    def authenticate(self, username, password):
        # Verify credentials
        # Update last_login
        # Return user object or None

    def get_user_by_id(self, user_id):
        # Fetch user by ID

    def get_user_by_username(self, username):
        # Fetch user by username

    def update_user(self, user_id, updates):
        # Update user fields

    def delete_user(self, user_id):
        # Soft delete (set is_active=0)

    def list_users(self, filters=None):
        # List all users with optional filters

    def change_password(self, user_id, new_password):
        # Hash and update password
```

#### 2. `src/auth/decorators.py`
```python
"""
Flask decorators for authentication and authorization
"""

from functools import wraps
from flask import session, redirect, url_for, jsonify
from flask_login import current_user

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function
```

#### 3. `src/auth/audit_log.py`
```python
"""
Audit logging for security events
"""

class AuditLog:
    def __init__(self, db_path='data/users.db'):
        # Initialize logging

    def log_login(self, user_id, ip_address, success):
        # Log login attempt

    def log_logout(self, user_id):
        # Log logout

    def log_user_action(self, admin_id, action, target_user_id, details):
        # Log admin actions (create, edit, delete user)

    def get_recent_logs(self, limit=50):
        # Fetch recent audit entries
```

### Modified Files:

#### `dashboard_web.py` - Add authentication
```python
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from src.auth.user_database import UserDatabase
from src.auth.decorators import admin_required
from src.auth.audit_log import AuditLog

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

user_db = UserDatabase()
audit_log = AuditLog()

@login_manager.user_loader
def load_user(user_id):
    return user_db.get_user_by_id(user_id)

# Update existing routes
@app.route('/')
@login_required
def index():
    return render_template('dashboard.html', user=current_user)

@app.route('/api/status')
@login_required
def api_status():
    # ... existing code ...

# New routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Login page and handler

@app.route('/logout')
@login_required
def logout():
    # Logout handler

@app.route('/admin')
@admin_required
def admin_panel():
    # Admin panel page

@app.route('/api/admin/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def manage_users():
    # User management API
```

---

## 🎨 FRONTEND IMPLEMENTATION

### New Files to Create:

#### 1. `templates/login.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Login - ADX Strategy v2.0</title>
    <link rel="stylesheet" href="/static/css/auth.css">
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <h1>🤖 ADX STRATEGY v2.0</h1>
            <h2>Live Trading Dashboard</h2>

            <form id="loginForm">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <label>
                    <input type="checkbox" name="remember"> Remember me
                </label>
                <button type="submit">Login</button>
            </form>

            <div id="errorMessage" class="error hidden"></div>
        </div>
    </div>

    <script src="/static/js/auth.js"></script>
</body>
</html>
```

#### 2. `templates/admin.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel - ADX Strategy v2.0</title>
    <link rel="stylesheet" href="/static/css/dashboard.css">
    <link rel="stylesheet" href="/static/css/admin.css">
</head>
<body>
    <!-- Admin panel UI with user management -->
    <script src="/static/js/admin.js"></script>
</body>
</html>
```

#### 3. `static/js/auth.js`
```javascript
// Login form handler
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const credentials = {
        username: formData.get('username'),
        password: formData.get('password'),
        remember: formData.get('remember') ? true : false
    };

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(credentials)
        });

        const result = await response.json();

        if (response.ok) {
            // Success - redirect to dashboard
            window.location.href = '/';
        } else {
            // Error - show message
            showError(result.error || 'Login failed');
        }
    } catch (error) {
        showError('Connection error. Please try again.');
    }
});
```

#### 4. `static/js/admin.js`
```javascript
// Admin panel functionality
// - Load users via AJAX
// - Create/edit/delete users via API
// - Display audit logs
// - Real-time updates

async function loadUsers() {
    const response = await fetch('/api/admin/users');
    const data = await response.json();
    renderUsersTable(data.users);
}

async function createUser(userData) {
    const response = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
    });
    return response.json();
}

// ... more functions
```

#### 5. `static/css/auth.css`
```css
/* Login page styling - dark theme */
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: var(--bg-primary);
}

.login-card {
    background: var(--bg-secondary);
    padding: 2rem;
    border-radius: var(--radius-lg);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    width: 400px;
}

/* ... more styles */
```

#### 6. `static/css/admin.css`
```css
/* Admin panel styling */
.admin-container {
    /* Layout and styling for admin panel */
}

.users-table {
    /* User list table styling */
}

/* ... more styles */
```

### Modified Files:

#### `templates/dashboard.html` - Add user menu
```html
<div class="header-right">
    <!-- Existing status indicator -->
    <div class="status-indicator" id="botStatus">...</div>

    <!-- NEW: User menu -->
    <div class="user-menu">
        <button class="user-button" id="userMenuButton">
            <span class="user-icon">👤</span>
            <span class="username">{{ user.username }}</span>
            <span class="role-badge">{{ user.role }}</span>
            <span class="dropdown-arrow">▼</span>
        </button>

        <div class="user-dropdown" id="userDropdown">
            {% if user.role == 'admin' %}
            <a href="/admin">🔧 Admin Panel</a>
            {% endif %}
            <a href="/profile">⚙️ Profile</a>
            <a href="/change-password">🔑 Change Password</a>
            <hr>
            <a href="/logout">🚪 Logout</a>
        </div>
    </div>
</div>
```

#### `static/js/dashboard.js` - Add session handling
```javascript
// Add session check on page load
async function checkSession() {
    try {
        const response = await fetch('/api/auth/session');
        if (!response.ok) {
            // Session expired - redirect to login
            window.location.href = '/login';
        }
    } catch (error) {
        console.error('Session check failed:', error);
    }
}

// Check session on page load
checkSession();

// Add credentials to all fetch requests
async function fetchStatus() {
    const response = await fetch('/api/status', {
        credentials: 'same-origin'  // Include session cookie
    });
    // ... rest of code
}
```

---

## 🔒 SECURITY FEATURES

### 1. Password Security
- ✅ Bcrypt hashing (work factor: 12)
- ✅ Minimum password strength requirements
- ✅ Password history (prevent reuse of last 3 passwords)
- ✅ Force password change on first login (optional)

### 2. Session Security
- ✅ HTTP-only cookies (prevent XSS attacks)
- ✅ Secure flag (HTTPS only)
- ✅ SameSite flag (prevent CSRF)
- ✅ Session timeout (8 hours default)
- ✅ Automatic logout on inactivity

### 3. Brute Force Protection
- ✅ Rate limiting on login endpoint (5 attempts per minute)
- ✅ Account lockout after 5 failed attempts
- ✅ Progressive delay between login attempts
- ✅ CAPTCHA after multiple failures (optional)

### 4. CSRF Protection
- ✅ Flask-WTF CSRF tokens on all forms
- ✅ Validate token on all POST/PUT/DELETE requests
- ✅ Token rotation on each request

### 5. Audit Logging
- ✅ Log all authentication events
- ✅ Log all admin actions
- ✅ Store IP addresses
- ✅ Retention: 90 days

### 6. Input Validation
- ✅ Server-side validation on all inputs
- ✅ SQL injection prevention (parameterized queries)
- ✅ XSS prevention (escape HTML)
- ✅ Path traversal prevention

---

## 📦 REQUIRED DEPENDENCIES

### Python Packages (add to requirements.txt):
```
Flask-Login==0.6.3
Flask-Bcrypt==1.0.1
Flask-WTF==1.2.1
WTForms==3.1.1
```

### Installation:
```bash
pip install Flask-Login Flask-Bcrypt Flask-WTF
```

---

## 🚀 IMPLEMENTATION PHASES

### Phase 1: Core Authentication (Week 1)
**Priority: HIGH**
- [ ] Create user database schema
- [ ] Implement UserDatabase class
- [ ] Create login/logout pages
- [ ] Add Flask-Login integration
- [ ] Protect existing API endpoints
- [ ] Add session management
- [ ] Create default admin user
- [ ] Test authentication flow

**Deliverables:**
- Users can log in/out
- Dashboard requires authentication
- All APIs protected
- Sessions working correctly

### Phase 2: Admin Panel (Week 2)
**Priority: HIGH**
- [ ] Create admin panel UI
- [ ] Implement user management API
- [ ] Add create/edit/delete user functionality
- [ ] Add role-based access control
- [ ] Create admin decorators
- [ ] Add user listing and search
- [ ] Test admin operations

**Deliverables:**
- Admins can create users
- Admins can edit/delete users
- Role permissions enforced
- Admin panel fully functional

### Phase 3: Security Hardening (Week 3)
**Priority: MEDIUM**
- [ ] Implement rate limiting
- [ ] Add account lockout
- [ ] Add audit logging
- [ ] Implement CSRF protection
- [ ] Add password strength validation
- [ ] Add session timeout
- [ ] Security testing

**Deliverables:**
- Brute force protection active
- All actions logged
- CSRF tokens implemented
- Password policies enforced

### Phase 4: UI Polish & Features (Week 4)
**Priority: LOW**
- [ ] Add profile page
- [ ] Add change password feature
- [ ] Add password reset (email-based)
- [ ] Improve error messages
- [ ] Add loading states
- [ ] Add success notifications
- [ ] Mobile responsiveness

**Deliverables:**
- Complete user experience
- All features polished
- Mobile-friendly UI
- Production-ready

---

## 📋 TESTING CHECKLIST

### Authentication Tests:
- [ ] Login with valid credentials → Success
- [ ] Login with invalid credentials → Error message
- [ ] Login without credentials → Validation error
- [ ] Logout → Session cleared, redirected to login
- [ ] Session timeout → Auto-logout after 8 hours
- [ ] Remember me → Session persists 30 days

### Authorization Tests:
- [ ] Viewer accesses dashboard → Allowed
- [ ] Viewer accesses admin panel → Denied (403)
- [ ] Admin accesses admin panel → Allowed
- [ ] Unauthenticated user accesses dashboard → Redirect to login
- [ ] Unauthenticated user accesses API → 401 error

### User Management Tests:
- [ ] Admin creates new user → User created
- [ ] Admin edits user → Changes saved
- [ ] Admin deletes user → User soft-deleted
- [ ] Viewer tries to create user → Denied (403)
- [ ] Admin creates duplicate username → Error
- [ ] Admin creates user with weak password → Error

### Security Tests:
- [ ] 5 failed login attempts → Account locked
- [ ] SQL injection in login → Prevented
- [ ] XSS in username field → Escaped
- [ ] CSRF attack → Token validation fails
- [ ] Session hijacking → Session validation fails

---

## 🔄 MIGRATION PLAN

### Step 1: Backup Current System
```bash
# Backup database
cp data/trades.db data/trades.db.backup

# Backup dashboard code
tar -czf dashboard_backup_$(date +%Y%m%d).tar.gz dashboard_web.py templates/ static/
```

### Step 2: Install Dependencies
```bash
pip install Flask-Login Flask-Bcrypt Flask-WTF
```

### Step 3: Create Default Admin
```bash
# CLI command to create first admin user
python3 setup_admin.py
# Prompts for username and password
```

### Step 4: Deploy Authentication
```bash
# Update dashboard_web.py
# Add auth templates
# Add auth static files
systemctl restart dashboard-web.service
```

### Step 5: Test in Staging
```bash
# Test on staging URL first
# Verify all functionality
# Run security tests
```

### Step 6: Deploy to Production
```bash
# Deploy to production
# Monitor logs
# Verify access control
```

---

## 💰 EFFORT ESTIMATION

### Development Time:
| Phase | Tasks | Estimated Hours |
|-------|-------|-----------------|
| Phase 1: Core Auth | Database, login, sessions | 12-16 hours |
| Phase 2: Admin Panel | User CRUD, UI | 10-14 hours |
| Phase 3: Security | Rate limiting, audit log | 8-10 hours |
| Phase 4: Polish | UX improvements | 6-8 hours |
| **Total** | | **36-48 hours** |

### Complexity: MEDIUM
- Straightforward implementation
- Well-documented libraries (Flask-Login)
- Standard patterns (session auth)
- No external dependencies (no OAuth)

---

## 🎓 ALTERNATIVE APPROACHES CONSIDERED

### Option 1: JWT Token-Based Auth
**Pros:** Stateless, scalable, mobile-friendly
**Cons:** More complex, requires token storage/refresh, harder to revoke
**Verdict:** ❌ Overkill for single-server dashboard

### Option 2: OAuth2 (Google/GitHub)
**Pros:** No password management, SSO convenience
**Cons:** Requires internet, external dependency, complexity
**Verdict:** ❌ Not suitable for internal trading dashboard

### Option 3: Basic HTTP Auth
**Pros:** Simple, built-in browser support
**Cons:** No logout, no role management, poor UX
**Verdict:** ❌ Too basic, lacks features

### ✅ **Selected: Session-Based Auth with Flask-Login**
**Why:** Perfect balance of security, features, and simplicity for this use case.

---

## 📞 QUESTIONS FOR USER REVIEW

1. **User Roles:** Is "admin" and "viewer" sufficient, or do you need more granular roles?

2. **Password Policy:** Minimum 8 characters with complexity rules - acceptable?

3. **Session Timeout:** 8 hours default, 30 days with "remember me" - good?

4. **Email Features:** Do you want:
   - Welcome emails for new users?
   - Password reset via email?
   - Login notifications?

5. **Multi-Factor Authentication (MFA):** Required? (TOTP/SMS)

6. **IP Whitelisting:** Restrict access to specific IPs?

7. **Audit Retention:** 90 days - sufficient?

8. **Brute Force Protection:** 5 failed attempts = lock account - acceptable?

9. **Default Admin:** Create during first setup or hardcode?

10. **Migration:** Deploy immediately or test in parallel environment first?

---

## ✅ APPROVAL CHECKLIST

Before implementation, please confirm:

- [ ] Overall architecture approved
- [ ] UI design mockups approved
- [ ] Security features are sufficient
- [ ] Timeline and effort estimation acceptable
- [ ] Migration plan approved
- [ ] Any additional requirements documented

---

**Status:** 📋 AWAITING USER APPROVAL
**Next Step:** User reviews plan and provides feedback
**Implementation Start:** After approval

---

*Prepared by: Claude Code*
*Date: 2025-10-20*
