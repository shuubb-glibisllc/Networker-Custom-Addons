from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    google_meet_enabled = fields.Boolean(
        string='Enable Google Meet Integration',
        config_parameter='google_meet.enabled',
        help='Enable Google Meet integration for calendar events'
    )
    
    google_meet_refresh_token = fields.Char(
        string='Google Meet Refresh Token',
        config_parameter='google_meet.refresh_token',
        help='Refresh token to automatically renew access tokens for Google Meet'
    )
    
    google_meet_access_token = fields.Char(
        string='Google Meet Access Token',
        config_parameter='google_meet.access_token',
        help='Access token with Calendar API permissions (auto-generated from refresh token)'
    )
    google_meet_redirect_uri = fields.Char(
        string="Google Meet Redirect URI",
        compute="_compute_google_meet_redirect_uri"
    )

    def _compute_google_meet_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.google_meet_redirect_uri = f"{base_url}/google_meet/oauth/callback"

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        res.update({
            'google_meet_enabled': ICPSudo.get_param('google_meet.enabled', False),
            'google_meet_refresh_token': ICPSudo.get_param('google_meet.refresh_token', ''),
            'google_meet_access_token': ICPSudo.get_param('google_meet.access_token', ''),
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        ICPSudo.set_param('google_meet.enabled', self.google_meet_enabled)
        ICPSudo.set_param('google_meet.refresh_token', self.google_meet_refresh_token or '')
        ICPSudo.set_param('google_meet.access_token', self.google_meet_access_token or '')