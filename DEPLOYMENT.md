# Deployment Guide - Streamlit Cloud

This guide will help you deploy the Lead Generation Tool to Streamlit Cloud so you can access it from anywhere.

## Prerequisites

- GitHub account (free)
- Google Maps API Key
- Streamlit Cloud account (free)

## Step 1: Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click **New repository**
3. Name it `lead-generation-tool`
4. Add a description: "A Streamlit app for lead generation using Google Maps"
5. Choose **Public** (needed for free Streamlit Cloud tier)
6. Click **Create repository**

## Step 2: Push Your Code to GitHub

Open PowerShell/Terminal in your project folder and run:

```bash
git init
git add .
git commit -m "Initial commit: Lead Generation Tool with password protection"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/lead-generation-tool.git
git push -u origin main
```

## Step 3: Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **Sign up** (or sign in if you already have an account)
3. Sign up with your GitHub account or email
4. Once signed in, click **New app**
5. Fill in the form:
   - **Repository**: `YOUR_GITHUB_USERNAME/lead-generation-tool`
   - **Branch**: `main`
   - **Main file path**: `app.py`
6. Click **Deploy**

**Note**: The first deploy may take 2-3 minutes as Streamlit installs dependencies.

## Step 4: Add Secrets (API Key & Password)

1. Once deployed, click the **☰ menu** in the top right → **Settings**
2. Go to the **Secrets** tab
3. Add your secrets in TOML format:

```toml
GOOGLE_MAPS_API_KEY = "YOUR_ACTUAL_API_KEY_HERE"
APP_PASSWORD = "YOUR_PASSWORD_HERE"
```

4. Click **Save**
5. The app will automatically restart with your secrets

## Step 5: Share Your App

Your app is now live! The URL will be something like:
```
https://lead-generation-tool-{random-id}.streamlit.app
```

You can:
- Share this link with others
- Access it from any device with internet
- Bookmark it for quick access

## Accessing Your App

- **From anywhere**: Open the URL in any browser
- **From any device**: Works on phones, tablets, laptops, etc.
- **Always available**: Your app runs 24/7 (with community tier limits)
- **Secure**: Protected by your password

## Updating Your App

To push updates to your deployed app:

```bash
# Make your changes locally
git add .
git commit -m "Your changes description"
git push origin main
```

Streamlit Cloud automatically deploys your changes within seconds!

## Troubleshooting

### "App is sleeping"
- Streamlit Cloud's free tier puts apps to sleep after 7 days of inactivity
- Just visit your app again to wake it up

### "Secrets not working"
- Make sure secrets are in the correct TOML format
- Check that the secret names match exactly: `GOOGLE_MAPS_API_KEY` and `APP_PASSWORD`
- Click **Save** to apply changes

### "Error: No module named..."
- Make sure `requirements.txt` is in the root folder
- Commit and push your changes
- Streamlit Cloud will reinstall dependencies

## Community Tier Limits

Free tier includes:
- 1 app deployed
- 3 GB storage
- 15 daily active users
- Standard CPU/memory

Enough for personal or small team use!

## Upgrade Options

If you need more resources:
- **Streamlit+**: $20/month - More resources and priority support
- **Advanced Tier**: Custom resources for enterprise needs

---

**Enjoy! Your Lead Generation Tool is now accessible from anywhere! 🚀**
