from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    use_sendgrid_service = fields.Boolean(
        'Use SendGrid Service',
        config_parameter='custom_email_handler.use_custom_service'
    )
    
    sendgrid_config_id = fields.Many2one(
        'sendgrid.config',
        'SendGrid Configuration',
        config_parameter='custom_email_handler.default_service_id'
    )