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
The `odoo.conf` file includes multiple addon paths. Use the full path for development:

```bash
# Start development server with auto-reload (from project root)
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf --dev=reload

# Install specific addon
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf -d database_name -i addon_name

# Update addon (recommended for development)
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf -d database_name -u addon_name

# Update all custom addons
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf -d database_name -u custom_email_handler,google_meet_integration,networker_contact,networker_crm

# Run tests for specific addon
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf -d database_name -i addon_name --test-enable --stop-after-init
```

### Database Management
```bash
# Create new database with custom addons
python3 /usr/lib/python3/dist-packages/odoo/odoo-bin -c /home/shuubb/Desktop/networker_odoo/custom_addons/odoo.conf -d new_database --init=base --stop-after-init

# Drop database (PostgreSQL command)
dropdb -h localhost -U odoo database_name
```

### Development Configuration
The `odoo.conf` file is configured for development with:
- Debug logging enabled for email handlers
- Multiple addon paths including central Odoo installation
- Database connection to localhost PostgreSQL (user: odoo)
- Admin password: `Sazamtro1!` (development only)
- Database list enabled for development

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

## Development Tools

### Odoo RAG Helper
The `odoo_helper.py` script links to a central RAG installation for Odoo documentation:
- Location: `/home/shuubb/Desktop/Odoo AI`
- Functions: `quick_search()`, `search_models()`, `search_views()`, `search_security()`, `search_api()`
- Use for quick documentation lookup during development

### Module Dependencies
Module dependency chain for proper installation order:
1. `custom_email_handler` → depends on: `base`, `mail`
2. `google_meet_integration` → depends on: `base`, `calendar`, `contacts`, `google_calendar`
3. `networker_contact` → depends on: `base`, `contacts`, `crm`
4. `networker_crm` → depends on: `web`, `crm`

Install in order or use `--init=all` for automatic dependency resolution.