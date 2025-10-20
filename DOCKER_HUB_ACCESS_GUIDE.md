# Docker Hub Access Guide - Setup for Automation

**Date:** 2025-10-20
**Your Docker Hub:** https://hub.docker.com/repositories/infornet1
**Status:** 📋 SETUP GUIDE (No Implementation Yet)

---

## 🎯 WHAT YOU NEED

To allow automation (GitHub Actions, CI/CD, or Claude Code) to push Docker images to your Docker Hub account, you need:

1. ✅ Docker Hub account (you have: `infornet1`)
2. ✅ Access Token (we'll create this)
3. ✅ Repository permissions (we'll verify this)

**IMPORTANT:** We will NOT implement anything yet. This guide shows you how to set up access manually.

---

## 🔐 DOCKER HUB ACCESS TOKENS

### **Why Use Access Tokens?**

**DON'T use your Docker Hub password** for automation because:
- ❌ Less secure (exposes main password)
- ❌ Cannot be scoped (all-or-nothing access)
- ❌ Cannot be revoked individually
- ❌ No audit trail

**DO use Access Tokens** because:
- ✅ More secure (doesn't expose main password)
- ✅ Can be scoped (read-only, read-write)
- ✅ Can be revoked individually without affecting other access
- ✅ Audit trail (can see which token was used)
- ✅ Can have expiration dates

---

## 📋 STEP-BY-STEP: CREATE ACCESS TOKEN

### **Step 1: Login to Docker Hub**

1. Go to: https://hub.docker.com/
2. Login with your credentials:
   - Username: `infornet1`
   - Password: (your Docker Hub password)

### **Step 2: Navigate to Access Tokens**

```
After logging in:
1. Click your username (top-right corner) → "Account Settings"
2. Click "Security" in left sidebar
3. Click "New Access Token" button
```

**Direct link:** https://hub.docker.com/settings/security

### **Step 3: Create New Access Token**

**Fill in the form:**

```
Access Token Description:
└─> "GitHub Actions - ADX Trading Bot CI/CD"
    (This helps you remember what it's for)

Access permissions:
└─> Select: "Read, Write, Delete"
    (Needed to push/update images)
```

**Options explained:**
- **Read-only:** Can only pull images (not useful for CI/CD)
- **Read, Write, Delete:** Can push/update images ✅ (recommended)

### **Step 4: IMPORTANT - Save the Token**

After clicking "Generate":

```
⚠️ CRITICAL: Copy the token immediately!

The token looks like:
YOUR_DOCKER_HUB_TOKEN_HERE

You will NEVER see this token again after closing the dialog!
```

**Save it securely:**
- Option A: Password manager (1Password, LastPass, Bitwarden)
- Option B: Encrypted file on your computer
- Option C: GitHub Secrets (we'll add it there)

**DO NOT:**
- ❌ Save in plain text file
- ❌ Commit to Git
- ❌ Share publicly
- ❌ Email to yourself

---

## 🔑 WHERE TO USE THE TOKEN

### **Option A: Local Development (Manual)**

When building/pushing Docker images manually on your server:

```bash
# Login to Docker Hub using token
docker login -u infornet1

# When prompted for password, paste your ACCESS TOKEN (not your password)
Password: YOUR_DOCKER_HUB_TOKEN_HERE

# Result: Login Succeeded

# Now you can push images
docker push infornet1/adx-trading-bot:latest
```

**Store token on server securely:**
```bash
# Create secure directory
mkdir -p ~/.docker-tokens
chmod 700 ~/.docker-tokens

# Save token (encrypted)
echo "YOUR_DOCKER_HUB_TOKEN_HERE" | \
  gpg --symmetric --cipher-algo AES256 > ~/.docker-tokens/dockerhub.gpg

# Use token
gpg --decrypt ~/.docker-tokens/dockerhub.gpg | docker login -u infornet1 --password-stdin
```

### **Option B: GitHub Actions (Automated CI/CD)**

Add token to GitHub Secrets:

```
1. Go to your GitHub repository:
   https://github.com/infornet1/Andromeda

2. Click "Settings" → "Secrets and variables" → "Actions"

3. Click "New repository secret"

4. Add two secrets:

   Secret 1:
   Name:  DOCKER_USERNAME
   Value: infornet1

   Secret 2:
   Name:  DOCKER_PASSWORD
   Value: YOUR_DOCKER_HUB_TOKEN_HERE
          (Paste your Docker Hub access token here)

5. Click "Add secret"
```

**Then GitHub Actions can use it:**
```yaml
# .github/workflows/docker-publish.yml
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}
```

### **Option C: Docker Compose with .env File**

For local development with docker-compose:

```bash
# Create .env file (add to .gitignore!)
cat > .env << 'EOF'
DOCKER_USERNAME=infornet1
DOCKER_TOKEN=YOUR_DOCKER_HUB_TOKEN_HERE
EOF

# Secure permissions
chmod 600 .env

# Login script
echo "$DOCKER_TOKEN" | docker login -u "$DOCKER_USERNAME" --password-stdin
```

---

## 🗂️ DOCKER HUB REPOSITORIES

### **Current Repositories**

Check your existing repositories at: https://hub.docker.com/repositories/infornet1

You may already have some repositories. If not, they'll be created automatically when you first push.

### **Creating Repositories (Two Options)**

#### **Option A: Auto-Create on First Push (Easy)**

```bash
# Repositories are created automatically when you push
docker push infornet1/adx-trading-bot:latest

# If repository doesn't exist, Docker Hub creates it automatically
# Default: Private visibility
```

#### **Option B: Manual Creation (More Control)**

```
1. Go to: https://hub.docker.com/repositories/infornet1

2. Click "Create Repository" button

3. Fill in details:
   Name: adx-trading-bot
   Description: ADX Strategy Trading Bot - Multi-user cryptocurrency trading platform
   Visibility: Private (recommended for production code)

4. Click "Create"

5. Repeat for second repository:
   Name: adx-trading-dashboard
   Description: ADX Trading Dashboard - Web interface for multi-user trading bot
   Visibility: Private
```

### **Repository Visibility Options**

**Private (Recommended):**
- ✅ Only you can see/pull images
- ✅ Suitable for production code
- ✅ Free tier: Unlimited private repos (1 concurrent build)
- ⚠️ Others need your credentials to pull

**Public:**
- ✅ Anyone can see/pull images
- ✅ Good for open-source projects
- ✅ More bandwidth from Docker Hub
- ⚠️ Source code visible to world (via image inspection)

**Recommendation for your project:** Start with **Private**, make Public later if you want.

---

## 🧪 TEST YOUR ACCESS

### **Test 1: Command Line Login**

```bash
# Test login with access token
docker login -u infornet1
# Paste your token when prompted

# Expected output:
# Login Succeeded
```

### **Test 2: Push a Test Image**

```bash
# Pull a tiny test image
docker pull hello-world

# Tag it with your username
docker tag hello-world:latest infornet1/test-image:latest

# Try pushing
docker push infornet1/test-image:latest

# Expected output:
# The push refers to repository [docker.io/infornet1/test-image]
# latest: digest: sha256:xxx size: xxx
```

### **Test 3: Verify on Docker Hub**

```
1. Go to: https://hub.docker.com/repositories/infornet1
2. You should see "test-image" in the list
3. Click it to see details
4. Delete it if you want (it was just a test)
```

---

## 🔄 TOKEN MANAGEMENT

### **Rotating Tokens (Security Best Practice)**

It's good practice to rotate tokens every 6-12 months:

```
1. Create new token (Step 2-4 above)
2. Update GitHub Secrets with new token
3. Test new token works
4. Delete old token from Docker Hub
```

### **Multiple Tokens for Different Uses**

You can create multiple tokens:

```
Token 1: "GitHub Actions - ADX Trading Bot"
└─> Used by: GitHub CI/CD
└─> Permissions: Read, Write, Delete

Token 2: "Production Server - Manual Deploys"
└─> Used by: SSH manual deploys
└─> Permissions: Read, Write, Delete

Token 3: "Development Laptop"
└─> Used by: Local development
└─> Permissions: Read, Write, Delete
```

**Benefits:**
- If one token is compromised, revoke only that one
- Audit trail shows which token pushed which image
- Different expiration dates

### **Revoking a Token**

If a token is compromised:

```
1. Go to: https://hub.docker.com/settings/security
2. Find the token in the list
3. Click "Delete" next to it
4. Token immediately stops working
5. Create new token if needed
```

---

## 🚨 SECURITY BEST PRACTICES

### **DO:**

✅ **Use access tokens** instead of passwords
✅ **Store tokens securely** (password manager, GitHub Secrets)
✅ **Give descriptive names** to tokens ("GitHub Actions", "Production Server")
✅ **Rotate tokens periodically** (every 6-12 months)
✅ **Revoke unused tokens** immediately
✅ **Use private repositories** for production code
✅ **Scan images for vulnerabilities** (Docker Hub does this automatically)

### **DON'T:**

❌ **Use your password** for automation
❌ **Commit tokens to Git** (.env files must be in .gitignore)
❌ **Share tokens** via email or chat
❌ **Use one token everywhere** (create multiple for different uses)
❌ **Forget to delete test images** (they use storage quota)
❌ **Push images with secrets** inside them (API keys, passwords)

---

## 📊 DOCKER HUB ACCOUNT OVERVIEW

### **Free Plan Features:**

Your current plan (Free) includes:

```
✅ Unlimited public repositories
✅ Unlimited private repositories
✅ 1 concurrent build (can build one image at a time)
✅ Unlimited pulls
✅ Automatic image scanning (vulnerability detection)
✅ Webhooks (notify on push)
✅ Access tokens (unlimited)
```

**Limitations:**
- ⚠️ 1 concurrent build (if pushing 2 images, 2nd waits for 1st)
- ⚠️ Rate limiting on pulls (200 pulls/6 hours for free users)

**If you need more:**
- Pro Plan ($7/month): 5 concurrent builds, more pulls
- Team Plan ($9/user/month): Shared repos, better collaboration

**Recommendation:** Free plan is sufficient for your project initially.

---

## 🔍 VERIFYING YOUR SETUP

### **Checklist:**

```
Step 1: Access Token Created
- [ ] Created access token on Docker Hub
- [ ] Token description: "GitHub Actions - ADX Trading Bot"
- [ ] Permissions: Read, Write, Delete
- [ ] Token saved securely (password manager or GitHub Secrets)

Step 2: Repositories Prepared
- [ ] Decision made: Private or Public?
- [ ] Repositories will be auto-created on first push
      OR manually created on Docker Hub

Step 3: GitHub Secrets Added (for CI/CD)
- [ ] DOCKER_USERNAME secret added to GitHub
- [ ] DOCKER_PASSWORD secret added to GitHub (with token value)

Step 4: Local Login Tested
- [ ] Ran: docker login -u infornet1
- [ ] Entered access token (not password)
- [ ] Result: Login Succeeded

Step 5: Test Push Successful
- [ ] Pushed test image (hello-world)
- [ ] Verified image appears on Docker Hub
- [ ] Deleted test image (cleanup)
```

---

## 🎯 NEXT STEPS (AFTER YOU CREATE TOKEN)

### **Immediate (Setup Phase):**

1. **Create Docker Hub Access Token**
   - Follow Step 1-4 above
   - Save token securely

2. **Add to GitHub Secrets**
   - Go to: https://github.com/infornet1/Andromeda/settings/secrets/actions
   - Add DOCKER_USERNAME and DOCKER_PASSWORD

3. **Test Local Login**
   ```bash
   docker login -u infornet1
   # Paste token when prompted
   ```

4. **Decide Repository Visibility**
   - Private (recommended) or Public?

### **Future (When Ready to Implement):**

5. **First Manual Push**
   ```bash
   # Build image
   docker build -f Dockerfile.bot -t infornet1/adx-trading-bot:develop .

   # Push to Docker Hub
   docker push infornet1/adx-trading-bot:develop
   ```

6. **Set Up GitHub Actions** (optional, for automation)
   - Create `.github/workflows/docker-publish.yml`
   - Automatic builds on push/tag

---

## 📋 SUMMARY

### **What You Need to Do:**

1. **Login to Docker Hub:**
   - https://hub.docker.com/
   - Username: `infornet1`

2. **Create Access Token:**
   - Go to: Settings → Security → New Access Token
   - Description: "GitHub Actions - ADX Trading Bot CI/CD"
   - Permissions: Read, Write, Delete
   - **SAVE THE TOKEN IMMEDIATELY** (you won't see it again)

3. **Add Token to GitHub Secrets:**
   - Go to: https://github.com/infornet1/Andromeda/settings/secrets/actions
   - Add `DOCKER_USERNAME` = `infornet1`
   - Add `DOCKER_PASSWORD` = `YOUR_DOCKER_HUB_TOKEN_HERE` (your token)

4. **Test Login:**
   ```bash
   docker login -u infornet1
   # Paste token when prompted
   ```

5. **Ready for Implementation:**
   - Token works ✅
   - GitHub Secrets configured ✅
   - Can push images manually ✅
   - Can automate with GitHub Actions ✅

---

## ❓ COMMON QUESTIONS

### **Q: Can I use my Docker Hub password instead of a token?**
A: Yes, but **NOT recommended**. Tokens are more secure and can be revoked individually.

### **Q: How many access tokens can I create?**
A: Unlimited. Create multiple tokens for different purposes.

### **Q: What if I lose my token?**
A: Create a new one. You cannot retrieve a lost token.

### **Q: Are private repositories really free?**
A: Yes! Docker Hub offers unlimited private repos on the free plan.

### **Q: Can I delete images later?**
A: Yes, you can delete images/tags anytime from Docker Hub web interface.

### **Q: Do I need to create repositories manually?**
A: No, they're auto-created on first push. But manual creation gives you more control over description/visibility.

### **Q: Can Claude Code push images to my Docker Hub?**
A: Not directly. Claude Code can generate commands, but you run them manually or via GitHub Actions automation.

---

## 🔐 SECURITY REMINDER

**Your access token is like a password:**
- 🔒 Keep it secret
- 🔒 Don't commit to Git
- 🔒 Don't share publicly
- 🔒 Rotate periodically
- 🔒 Revoke if compromised

**If you ever see your token in a public place:**
1. Immediately revoke it on Docker Hub
2. Create a new token
3. Update GitHub Secrets with new token

---

## 📞 READY TO PROCEED?

**After you complete these steps:**
1. ✅ Access token created
2. ✅ Token saved securely
3. ✅ GitHub Secrets configured
4. ✅ Test login successful

**Then you'll be ready for:**
- Manual Docker image pushes
- Automated CI/CD with GitHub Actions
- Full Docker-based deployment workflow

**Let me know when you've:**
- Created your access token
- Added it to GitHub Secrets
- Tested `docker login` successfully

Then we can proceed with the Docker implementation plan!

---

**Status:** 📋 AWAITING USER ACTION (Create Access Token)
**No Implementation Yet:** Just a guide for you to follow
**Next:** You create token manually, then we can proceed

---

*Prepared by: Claude Code*
*Date: 2025-10-20*
*Action Required: Create Docker Hub Access Token (Manual)*
