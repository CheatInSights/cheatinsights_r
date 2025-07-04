# Email System Configuration Guide

## Current Issue
The application is failing with SMTP authentication errors because the email credentials are not properly configured in the production environment.

## Email System Architecture

### 1. Configuration (mysite/settings.py)
The email system automatically detects the environment and configures itself:

- **Development/Testing**: Uses console backend (emails print to console)
- **Production**: Uses SMTP backend with Zoho Mail

### 2. Environment Variables Required
To enable email functionality in production, set these environment variables in Railway:

```
EMAIL_HOST_USER=contact@cheatinsights.com
EMAIL_HOST_PASSWORD=your_zoho_app_password
DEFAULT_FROM_EMAIL=contact@cheatinsights.com
CONTACT_EMAIL=contact@cheatinsights.com
```

### 3. Zoho Mail Setup
1. **Create Zoho Mail Account**: Sign up at zoho.com/mail
2. **Generate App Password**: 
   - Go to Zoho Mail settings
   - Navigate to "Security" → "App Passwords"
   - Generate a new app password for "Django"
3. **Configure Domain**: Ensure your domain is properly configured with Zoho

### 4. Current Fallback Behavior
- If `EMAIL_HOST_PASSWORD` is not set, the system automatically switches to console backend
- This prevents crashes but emails won't be sent in production
- Contact form submissions will still work but emails will only appear in logs

### 5. Error Handling
The system now includes robust error handling:
- Email failures don't crash the application
- Errors are logged for debugging
- Users still get a success message (to prevent confusion)

## Quick Fix Options

### Option 1: Use Console Backend (Temporary)
If you want to deploy immediately without email functionality:
- The system will automatically use console backend
- Emails will appear in Railway logs
- Contact form will work but emails won't be sent

### Option 2: Configure Zoho Mail (Recommended)
1. Set up Zoho Mail account
2. Add environment variables in Railway dashboard
3. Redeploy the application

### Option 3: Use Alternative Email Service
You can easily switch to Gmail, SendGrid, or other providers by updating the SMTP settings in `mysite/settings.py`.

## Testing Email Configuration
To test if email is working:
1. Submit a contact form
2. Check Railway logs for email output
3. If using SMTP, check your email inbox

## Troubleshooting
- **Authentication Failed**: Check EMAIL_HOST_PASSWORD environment variable
- **Connection Refused**: Check EMAIL_HOST and EMAIL_PORT settings
- **No emails received**: Check spam folder and email configuration 