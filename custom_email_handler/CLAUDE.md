# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an Odoo 18.0 SendGrid Connector addon that provides direct integration with SendGrid's Web API for reliable email delivery, bypassing traditional SMTP. The addon intercepts Odoo's standard mail sending process and routes emails through SendGrid.

## Architecture

### Core Components

- **SendGridConfig Model** (`models/email_service.py`): Configuration model for SendGrid API settings (API key, sender details, EU data residency)
- **MailThread Override** (`models/mail_thread.py`): Intercepts Odoo's `mail.mail.send()` method to route through SendGrid API
- **SendGrid Webhook Controller** (`controllers/email_webhook.py`): HTTP endpoint for processing incoming email webhooks from SendGrid
- **Settings Integration** (`models/res_config_settings.py`): System settings to enable/disable SendGrid integration

### Email Flow

1. **Outgoing**: When Odoo sends emails, `MailMail.send()` checks if SendGrid service is enabled via config parameter `custom_email_handler.use_custom_service`
2. **If enabled**: Emails are routed through `SendGridConfig.send_email()` which handles SendGrid API integration
3. **Incoming**: Webhook endpoint `/webhook/sendgrid/incoming` processes incoming emails from SendGrid

### Data Models

- `sendgrid.config`: Stores SendGrid configurations (API keys, sender details, EU data residency settings)
- Extends `mail.mail` and `mail.thread` for custom email processing
- Integrates with `res.config.settings` for global configuration

## Development Commands

This is an Odoo addon, so standard Odoo development practices apply:

### Installation
```bash
# Install addon in Odoo instance
# Add this addon path to --addons-path parameter
# Install via Odoo Apps interface or CLI
```

### Testing
```bash
# Run Odoo tests for this module
python odoo-bin -c odoo.conf -d database_name -i custom_email_handler --test-enable
```

### Development Server
```bash
# Start Odoo with this addon
python odoo-bin -c odoo.conf --addons-path=/path/to/custom_addons --dev=reload
```

## Key Implementation Details

### SendGrid Integration
- Direct API integration with comprehensive logging
- Handles EU data residency via API URL configuration (`https://api.eu.sendgrid.com`)
- Comprehensive attachment support with base64 encoding
- Email address sanitization to remove hidden characters

### Security Model
- Regular users have read-only access to SendGrid configurations
- System administrators have full CRUD access
- API keys are stored as password fields in the UI

### Configuration Parameters
- `custom_email_handler.use_custom_service`: Boolean to enable/disable SendGrid routing
- `custom_email_handler.default_service_id`: Default SendGrid configuration

### SendGrid Webhook Processing
- Public endpoint with CSRF disabled for SendGrid integration
- JSON payload processing for incoming emails
- Automatic mail.message creation from webhook data
- Attachment handling for incoming emails

## File Structure
```
custom_email_handler/
├── __manifest__.py          # Addon metadata and dependencies
├── models/
│   ├── email_service.py     # Core SendGrid configuration model and API integration
│   ├── mail_thread.py       # Odoo mail system overrides
│   └── res_config_settings.py # System settings extension
├── controllers/
│   └── email_webhook.py     # SendGrid webhook handler
├── views/                   # XML view definitions for UI
├── security/                # Access control definitions
└── data/                    # Default data records
```

This addon requires the `sendgrid` Python package for SendGrid API integration.