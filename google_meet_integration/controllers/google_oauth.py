import logging
import requests
from urllib.parse import urlencode

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class GoogleMeetOAuth(http.Controller):

    @http.route('/google_meet/oauth/connect', type='http', auth='user')
    def google_meet_oauth_connect(self):
        """Redirect user to Google OAuth consent page"""
        client_id = request.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
        if not client_id:
            raise UserError(_('Google Calendar Client ID not configured. Please configure Google Calendar first.'))

        redirect_uri = f"{request.httprequest.url_root}google_meet/oauth/callback"
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/calendar.events',
            'access_type': 'offline',
            'prompt': 'consent',
            'include_granted_scopes': 'true',
        }
        auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

        # Use absolute redirect to Google (avoid Odoo rewriting to /o/oauth2/auth)
        return Response("", status=302, headers=[("Location", auth_url)])

    @http.route('/google_meet/oauth/callback', type='http', auth='user')
    def google_meet_oauth_callback(self, code=None, error=None, **kwargs):
        """Handle OAuth callback from Google"""
        if error:
            _logger.error("Google OAuth error: %s", error)
            return request.render('google_meet_integration.oauth_error', {'error': error})

        if not code:
            return request.render('google_meet_integration.oauth_error', {'error': 'No authorization code received'})

        try:
            client_id = request.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
            client_secret = request.env['ir.config_parameter'].sudo().get_param('google_calendar_client_secret')
            if not all([client_id, client_secret]):
                raise UserError(_('Google Calendar credentials not configured'))

            redirect_uri = f"{request.httprequest.url_root}google_meet/oauth/callback"
            token_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
            }

            response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            if response.status_code == 200:
                tokens = response.json()
                ICPSudo = request.env['ir.config_parameter'].sudo()

                if 'access_token' in tokens:
                    ICPSudo.set_param('google_meet.access_token', tokens['access_token'])
                if 'refresh_token' in tokens:
                    ICPSudo.set_param('google_meet.refresh_token', tokens['refresh_token'])
                    _logger.info("Google Meet OAuth: refresh token saved")
                else:
                    _logger.warning("Google Meet OAuth: no refresh token received")

                ICPSudo.set_param('google_meet.enabled', True)

                return request.render('google_meet_integration.oauth_success', {
                    'has_refresh_token': 'refresh_token' in tokens
                })
            else:
                _logger.error("Google OAuth token exchange failed: %s", response.text)
                return request.render('google_meet_integration.oauth_error', {
                    'error': 'Failed to exchange authorization code for tokens'
                })

        except Exception as e:
            _logger.error("Google Meet OAuth error: %s", str(e))
            return request.render('google_meet_integration.oauth_error', {'error': str(e)})

    @http.route('/google_meet/oauth/revoke', type='http', auth='user')
    def google_meet_oauth_revoke(self):
        """Revoke Google Meet OAuth tokens"""
        try:
            ICPSudo = request.env['ir.config_parameter'].sudo()
            ICPSudo.set_param('google_meet.access_token', '')
            ICPSudo.set_param('google_meet.refresh_token', '')
            ICPSudo.set_param('google_meet.enabled', False)

            return request.render('google_meet_integration.oauth_revoked')

        except Exception as e:
            _logger.error("Google Meet OAuth revoke error: %s", str(e))
            return request.render('google_meet_integration.oauth_error', {'error': str(e)})
