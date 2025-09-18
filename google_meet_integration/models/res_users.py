from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    google_auth_status = fields.Selection([
        ('not_connected', 'Not Connected'),
        ('connected', 'Connected'),
        ('expired', 'Token Expired')
    ], string='Google Account Status', compute='_compute_google_auth_status')
    
    google_auth_email = fields.Char(
        string='Connected Google Account', 
        compute='_compute_google_auth_status'
    )

    @api.depends()
    def _compute_google_auth_status(self):
        """Compute the Google authentication status for each user"""
        for user in self:
            auth = self.env['google.user.auth'].search([
                ('user_id', '=', user.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if auth:
                if auth.is_token_expired():
                    user.google_auth_status = 'expired'
                else:
                    user.google_auth_status = 'connected'
                user.google_auth_email = auth.google_email or ''
            else:
                user.google_auth_status = 'not_connected'
                user.google_auth_email = ''

    def action_connect_google(self):
        """Redirect user to Google OAuth connection"""
        self.ensure_one()
        if self.id != self.env.user.id:
            raise UserError(_("You can only connect your own Google account."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': '/google_meet/oauth/connect',
            'target': 'self',
        }

    def action_disconnect_google(self):
        """Disconnect user's Google account"""
        self.ensure_one()
        if self.id != self.env.user.id:
            raise UserError(_("You can only disconnect your own Google account."))
            
        auth = self.env['google.user.auth'].search([
            ('user_id', '=', self.id),
            ('is_active', '=', True)
        ], limit=1)
        
        if auth:
            auth.revoke_access()
        else:
            raise UserError(_("No Google account connection found to disconnect."))

    def action_open_my_google_auth(self):
        """Open the user's Google authentication records"""
        self.ensure_one()
        return {
            'name': _('My Google Account'),
            'type': 'ir.actions.act_window',
            'res_model': 'google.user.auth',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }