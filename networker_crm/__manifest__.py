{
    "name": "networker_crm",
    "version": "18.0.1.0.0",
    "depends": ["web", "crm"],
    "data": [
        "security/ir.model.access.csv",
        "views/lead_from_contacts_wizard_views.xml",
        "views/crm_lead_kanban_inherit.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "networker_crm/static/src/js/kanban_button.js",
            "networker_crm/static/src/xml/kanban_button.xml",
            "networker_crm/static/src/css/hide_iap.css",
        ],
    },
    "license": "LGPL-3",
}
