# Gemini Code Assistant Context: `networker_crm` Odoo Addon

## Project Overview

This project is a custom Odoo addon named `networker_crm`. It extends the functionality of the standard Odoo CRM module by providing tools to generate new leads from existing contact data.

The core features of this addon are:

1.  **Lead Generation Wizard:** It adds a "Generate from Contacts" button to the CRM pipeline's Kanban view. This button launches a wizard that allows users to:
    *   Specify the number of leads to generate.
    *   Filter contacts by Industry and Legal Form.
    *   Assign a salesperson to the newly created leads.

2.  **External Data Integration:** The wizard interacts with the Georgian National Agency of Public Registry (NAPR) to:
    *   Fetch the official legal name of a company based on its VAT number.
    *   Update the contact's name in Odoo with the fetched legal name.
    *   Update the contact's legal status (e.g., "Active", "Stopped") based on the lookup result.

3.  **Lead Creation Logic:**
    *   It identifies partners (companies) that do not already have an active lead.
    *   It creates new `crm.lead` records for these partners.

4.  **Mass Deletion:** A server action is included to allow for the bulk deletion of selected leads from the list view.

## Key Technologies and Architecture

*   **Backend:** Python, Odoo Framework
*   **Frontend:** JavaScript (ES6 Modules), XML (Odoo View Templates)
*   **Database:** PostgreSQL (managed by Odoo)
*   **External Services:** `requests` library is used to query `enreg.reestri.gov.ge`.

The addon follows the standard Odoo module structure:
*   `models/`: Contains the Python models, including the `lead.from.contacts.wizard` which holds the main business logic.
*   `views/`: Contains XML definitions for views, including the wizard form and the modification to the CRM Kanban view.
*   `data/`: Contains data files, such as the `ir.actions.server` for the mass delete action.
*   `static/`: Contains frontend assets, including the JavaScript for the custom Kanban button and its corresponding XML template.
*   `security/`: Defines access control rules in `ir.model.access.csv`.
*   `__manifest__.py`: The module descriptor file.

## Building and Running

This is a standard Odoo addon and does not have a separate build process.

**To run this addon:**

1.  Make sure the `networker_crm` directory is located in the `addons_path` of your Odoo server configuration.
2.  Start the Odoo server.
3.  Navigate to the **Apps** menu in the Odoo web interface.
4.  Search for "networker_crm" and click the **Install** button.

## Development Conventions

*   The addon is built for Odoo version 18.0.
*   It relies on custom fields on the `res.partner` model (e.g., `x_studio_industries`, `x_legal_forms_id`, `x_studio_legal_status`). These fields appear to be created using Odoo Studio. Any development on this module must account for the presence of these fields.
*   The frontend JavaScript uses the modern Odoo `owl` component system (via `odoo-module`) to extend the `KanbanController`.
*   The lead generation logic is heavily dependent on the structure and response of the external Georgian registry website. Changes to that site may break the lead generation functionality.
*   Logging (`_logger`) is used to provide debug information, especially for the external API calls.
