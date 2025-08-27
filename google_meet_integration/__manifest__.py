{
    'name': 'Google Meet Integration',
    "version": "18.0.2.0.2",
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
    'website': 'https://www.glibisllc.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'calendar',
        'contacts',
        'google_calendar',
    ],
    'data': [
        'views/calendar_event_views.xml',
        'views/google_meet_config.xml',
        'views/oauth_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}