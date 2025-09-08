# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an Odoo 18.0 custom addons repository containing four specialized modules for business networking and communication:

- **custom_email_handler**: SendGrid API integration for reliable email delivery
- **google_meet_integration**: Google Meet integration for calendar events  
- **networker_contact**: Contact management with Georgian registry integration
- **networker_crm**: CRM enhancements with contact-to-lead conversion

## Architecture

### Core Structure
Each addon follows standard Odoo module structure with:
- `__manifest__.py`: Module metadata and dependencies
- `models/`: Python business logic and data models
- `views/`: XML view definitions for UI
- `controllers/`: HTTP endpoints and webhooks
- `security/`: Access control definitions
- `data/`: Default data and configurations

### Key Dependencies
- **Base modules**: `base`, `mail`, `contacts`, `crm`, `calendar`
- **External integrations**: `google_calendar` module for Google services
- **Python packages**: `sendgrid` for email integration

### Integration Points
- **Email Flow**: `custom_email_handler` intercepts `mail.mail.send()` to route through SendGrid API
- **Calendar Events**: `google_meet_integration` overrides `calendar.event` to create Google Meet URLs  
- **Partner Extensions**: `networker_contact` extends `res.partner` with Georgian registry integration
- **CRM Workflow**: `networker_crm` adds kanban buttons and contact-to-lead conversion wizards

## Development Commands

### Odoo Server
```bash
# Start development server with auto-reload
python odoo-bin -c custom_addons/odoo.conf --addons-path=/home/shuubb/Desktop/networker_odoo/custom_addons --dev=reload

# Install specific addon
python odoo-bin -c custom_addons/odoo.conf -d database_name -i addon_name

# Update addon
python odoo-bin -c custom_addons/odoo.conf -d database_name -u addon_name

# Run tests for specific addon
python odoo-bin -c custom_addons/odoo.conf -d database_name -i addon_name --test-enable
```

### Database Management
```bash
# Create new database
python odoo-bin -c custom_addons/odoo.conf -d new_database --init=base --stop-after-init

# Drop database (be careful!)
dropdb database_name
```

### Development Configuration
The `odoo.conf` file is configured for development with:
- Debug logging enabled
- Database connection to localhost PostgreSQL
- Custom addons path pre-configured
- Admin password: `Sazamtro1!` (development only)

## Key Implementation Patterns

### Configuration Parameters
Critical system parameters that control addon behavior:
- `custom_email_handler.use_custom_service`: Enable/disable SendGrid routing
- `custom_email_handler.default_service_id`: Default SendGrid configuration
- `google_meet.enabled`: Enable/disable Google Meet integration
- `google_meet.access_token`: OAuth token for Google API access

### Model Inheritance
All addons extend existing Odoo models:
- `res.partner`: Extended with Georgian registry fetching
- `mail.mail`: Overridden for SendGrid email routing
- `calendar.event`: Enhanced with Google Meet URL generation
- `crm.lead`: Extended with contact conversion functionality

### Wizard Pattern
Multiple addons use transient wizards for complex operations:
- `partner.napr.fetch.wizard`: Georgian registry integration
- `partner.to.crm.wizard`: Contact-to-lead conversion
- `lead.from.contacts.wizard`: Bulk lead creation

### API Integration Security
- SendGrid API keys stored as password fields in UI
- Google OAuth tokens managed through system parameters
- External API calls wrapped with comprehensive error handling
- Webhook endpoints have CSRF disabled for third-party integration

## External Integrations

### SendGrid Email Service
- Direct Web API integration (no SMTP)
- EU data residency support via `https://api.eu.sendgrid.com`
- Webhook processing for incoming emails at `/webhook/sendgrid/incoming`
- Comprehensive attachment and email sanitization

### Google Services
- OAuth2 integration with Google Calendar API
- Google Meet URL generation for calendar events
- Refresh token management for long-term access

### Georgian Registry (NAPR)
- Legal name fetching for business partners
- VAT number validation and company data retrieval
- Integration through custom wizard interface

## JavaScript Assets
The `networker_crm` module includes frontend JavaScript:
- `static/src/js/kanban_button.js`: Custom kanban view buttons
- `static/src/xml/kanban_button.xml`: Button templates
- `static/src/css/hide_iap.css`: UI styling overrides

Assets are loaded through the `web.assets_backend` bundle in the manifest file.