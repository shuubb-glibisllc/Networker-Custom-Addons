from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GoogleConnectWizard(models.TransientModel):
    _name = 'google.connect.wizard'
    _description = 'Google Account Connection Wizard'

    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, readonly=True)
    google_auth_status = fields.Selection(related='user_id.google_auth_status', readonly=True)
    google_auth_email = fields.Char(related='user_id.google_auth_email', readonly=True)
    
    def action_connect_google(self):
        """Redirect to Google OAuth"""
        return {
            'type': 'ir.actions.act_url',
            'url': '/google_meet/oauth/connect',
            'target': 'new',
        }
    
    def action_disconnect_google(self):
        """Disconnect Google account"""
        return self.user_id.action_disconnect_google()
    
    def action_open_user_preferences(self):
        """Open user preferences"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.env.user.id,
            'view_mode': 'form',
            'target': 'current',
        }