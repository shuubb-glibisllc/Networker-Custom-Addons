# Project Overview

This project is an Odoo addon named "networker_contact". It extends the functionality of the Contacts and CRM modules in Odoo.

The main features of this addon are:
- **NAPR Integration:** It allows users to fetch documents and legal names from the Georgian National Agency of Public Registry (NAPR) directly from a contact's form view. This is useful for verifying contact information and retrieving official documents.
- **Partner to CRM Conversion:** It provides a wizard to convert one or more contacts (res.partner) into CRM leads. This helps streamline the process of creating leads from existing contacts.

## Key Technologies

- **Odoo 18.0:** The addon is developed for Odoo version 18.0.
- **Python:** The backend logic is written in Python.
- **XML:** The views and wizards are defined using XML.

## Architecture

The addon follows the standard Odoo module structure:
- `models/`: Contains the Python models that define the data structure and business logic.
  - `res_partner.py`: Extends the `res.partner` model to add the NAPR integration actions.
  - `partner_napr_wizard.py`: Implements the wizard for fetching data from NAPR.
  - `partner_to_crm_wizard.py`: Implements the wizard for converting partners to CRM leads.
- `views/`: Contains the XML files that define the user interface.
  - `res_partner_view.xml`: Modifies the contact form view to add the NAPR integration buttons.
  - `napr_fetch_wizard_views.xml`: Defines the form view for the NAPR fetch wizard.
  - `partner_to_crm_wizard_views.xml`: Defines the form view for the partner to CRM conversion wizard.
- `security/`: Contains the access control list (ACL) settings.
- `__manifest__.py`: The module manifest file, which declares the module's metadata and dependencies.

# Building and Running

This is an Odoo addon and should be installed in an Odoo environment.

1.  **Place the addon:** Copy the `networker_contact` directory into the `addons` path of your Odoo instance.
2.  **Install dependencies:** This addon depends on the `base`, `contacts`, and `crm` modules. Make sure these are installed in your Odoo database.
3.  **Install Python packages:** The NAPR integration requires the `requests` python package. It also uses the `ddjvu` command-line tool to convert DJVU files to PDF. You may need to install these on your server.
    ```bash
    pip install requests
    sudo apt-get install djvulibre-bin
    ```
4.  **Start Odoo server:** Run your Odoo server.
5.  **Install the addon:** In your Odoo database, go to the "Apps" menu, search for "networker_contact", and click "Install".

# Development Conventions

- The code follows the standard Odoo development guidelines.
- The NAPR integration feature includes detailed logging to help with debugging.
- The code is written for Odoo 18.0 and uses new features like the simplified `attrs` and `states` syntax in XML views.
