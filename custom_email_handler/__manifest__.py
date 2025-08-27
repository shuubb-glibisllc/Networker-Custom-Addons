{
    'name': 'Custom Email Handler',
    'version': '18.0.1.0.0',
    'category': 'Mail',
    'summary': 'SendGrid API integration for email sending and receiving',
    'description': """
        SendGrid connector that bypasses traditional SMTP and integrates
        directly with SendGrid's Web API for reliable email delivery.
        Supports webhooks for incoming emails and comprehensive logging.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/sendgrid_config_views.xml',
        'views/res_config_settings_views.xml',
        'data/sendgrid_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}