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
        """Redirect user to Google OAuth consent page for per-user authentication"""
        client_id = request.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
        if not client_id:
            raise UserError(_('Google Calendar Client ID not configured. Please configure Google Calendar first.'))

        redirect_uri = f"{request.httprequest.url_root}google_meet/oauth/callback"
        
        # Store user ID in session for callback
        request.session['google_oauth_user_id'] = request.env.user.id
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email',
            'access_type': 'offline',
            'prompt': 'consent',
            'include_granted_scopes': 'true',
        }
        auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

        # Use absolute redirect to Google (avoid Odoo rewriting to /o/oauth2/auth)
        return Response("", status=302, headers=[("Location", auth_url)])

    @http.route('/google_meet/oauth/callback', type='http', auth='user')
    def google_meet_oauth_callback(self, code=None, error=None, **kwargs):
        """Handle OAuth callback from Google for per-user authentication"""
        if error:
            _logger.error("Google OAuth error: %s", error)
            return request.render('google_meet_integration.oauth_error', {'error': error})

        if not code:
            return request.render('google_meet_integration.oauth_error', {'error': 'No authorization code received'})

        try:
            # Get user ID from session
            user_id = request.session.get('google_oauth_user_id')
            if not user_id:
                user_id = request.env.user.id

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
                
                # Get user info to get Google email
                google_email = None
                if 'access_token' in tokens:
                    user_info_response = requests.get(
                        'https://www.googleapis.com/oauth2/v2/userinfo',
                        headers={'Authorization': f"Bearer {tokens['access_token']}"}
                    )
                    if user_info_response.status_code == 200:
                        user_info = user_info_response.json()
                        google_email = user_info.get('email')

                # Create or update user authentication record
                from datetime import datetime, timedelta
                auth_vals = {
                    'user_id': user_id,
                    'google_email': google_email,
                    'access_token': tokens.get('access_token'),
                    'refresh_token': tokens.get('refresh_token'),
                    'token_expires_at': datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600)),
                    'is_active': True,
                    'last_sync': datetime.now()
                }

                # Check if user already has auth record
                existing_auth = request.env['google.user.auth'].sudo().search([
                    ('user_id', '=', user_id),
                    ('google_email', '=', google_email)
                ], limit=1)

                if existing_auth:
                    existing_auth.sudo().write(auth_vals)
                    auth = existing_auth
                else:
                    auth = request.env['google.user.auth'].sudo().create(auth_vals)

                # Clean up session
                if 'google_oauth_user_id' in request.session:
                    del request.session['google_oauth_user_id']

                return request.render('google_meet_integration.oauth_success', {
                    'has_refresh_token': 'refresh_token' in tokens,
                    'google_email': google_email,
                    'user_specific': True
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
