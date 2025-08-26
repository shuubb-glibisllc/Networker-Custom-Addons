{
    'name': 'Google Meet Integration',
    'version': '16.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Integration with Google Meet for creating and managing meetings',
    'description': """
Google Meet Integration
=======================
This module provides integration with Google Meet API to:
* Create Google Meet meetings from Odoo
* Schedule meetings with calendar integration
* Manage meeting participants
* Track meeting history
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'calendar',
        'contacts',
        'google_calendar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/google_meet_views.xml',
        'views/calendar_event_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}