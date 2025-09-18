from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class GoogleUserAuth(models.Model):
    _name = 'google.user.auth'
    _description = 'Google Authentication per User'
    _rec_name = 'user_email'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    user_email = fields.Char(related='user_id.email', string='User Email', store=True)
    google_email = fields.Char(string='Google Account Email', help='The Google account email used for authentication')
    access_token = fields.Char(string='Access Token', help='Google API access token')
    refresh_token = fields.Char(string='Refresh Token', help='Google API refresh token for token renewal')
    token_expires_at = fields.Datetime(string='Token Expires At', help='When the access token expires')
    is_active = fields.Boolean(string='Active', default=True, help='Whether this Google connection is active')
    last_sync = fields.Datetime(string='Last Sync', help='Last time the tokens were refreshed')
    
    _sql_constraints = [
        ('unique_user_google', 'UNIQUE(user_id, google_email)', 'Each user can only have one connection per Google account.'),
    ]

    @api.model
    def _get_token_expiry(self, expires_in):
        """Helper method to get token expiry timedelta"""
        return timedelta(seconds=expires_in)

    @api.model
    def get_user_google_auth(self, user_id=None):
        """Get the active Google authentication for a user"""
        if not user_id:
            user_id = self.env.user.id
        
        auth = self.search([
            ('user_id', '=', user_id),
            ('is_active', '=', True)
        ], limit=1)
        
        if auth and auth.is_token_expired():
            auth._refresh_access_token_internal()
        
        return auth

    def is_token_expired(self):
        """Check if the access token is expired"""
        self.ensure_one()
        if not self.token_expires_at:
            return True
        return datetime.now() > self.token_expires_at

    def refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        self.ensure_one()
        if not self.refresh_token:
            _logger.error("No refresh token available for user %s", self.user_id.name)
            raise UserError(_("No refresh token available. Please reconnect your Google account."))

        try:
            client_id = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
            client_secret = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_secret')
            
            if not all([client_id, client_secret]):
                _logger.error("Google credentials not configured")
                raise UserError(_("Google credentials not configured. Please contact your administrator."))

            refresh_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post('https://oauth2.googleapis.com/token', data=refresh_data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                self.write({
                    'access_token': token_data.get('access_token'),
                    'token_expires_at': datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                    'last_sync': datetime.now()
                })
                
                _logger.info("Successfully refreshed access token for user %s", self.user_id.name)
                raise UserError(_("✅ Access token refreshed successfully!"))
            else:
                _logger.error("Failed to refresh token for user %s: %s", self.user_id.name, response.text)
                raise UserError(_("❌ Failed to refresh access token. You may need to reconnect your Google account."))
                
        except UserError:
            raise
        except Exception as e:
            _logger.error("Error refreshing token for user %s: %s", self.user_id.name, str(e))
            raise UserError(_("❌ Error refreshing token. Please try again or reconnect your account."))

    def _refresh_access_token_internal(self):
        """Internal method to refresh access token without user feedback"""
        self.ensure_one()
        if not self.refresh_token:
            _logger.error("No refresh token available for user %s", self.user_id.name)
            return False

        try:
            client_id = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
            client_secret = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_secret')
            
            if not all([client_id, client_secret]):
                _logger.error("Google credentials not configured")
                return False

            refresh_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post('https://oauth2.googleapis.com/token', data=refresh_data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                self.write({
                    'access_token': token_data.get('access_token'),
                    'token_expires_at': datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                    'last_sync': datetime.now()
                })
                
                _logger.info("Successfully refreshed access token for user %s", self.user_id.name)
                return True
            else:
                _logger.error("Failed to refresh token for user %s: %s", self.user_id.name, response.text)
                return False
                
        except Exception as e:
            _logger.error("Error refreshing token for user %s: %s", self.user_id.name, str(e))
            return False

    def revoke_access(self):
        """Revoke Google access for this user"""
        self.ensure_one()
        try:
            if self.access_token:
                # Revoke the token with Google
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={self.access_token}"
                requests.post(revoke_url)
            
            # Mark as inactive
            self.write({
                'is_active': False,
                'access_token': False,
                'refresh_token': False,
                'token_expires_at': False
            })
            
            _logger.info("Revoked Google access for user %s", self.user_id.name)
            raise UserError(_("✅ Google access has been revoked successfully. You can reconnect anytime from the Calendar menu."))
            
        except UserError:
            raise
        except Exception as e:
            _logger.error("Error revoking access for user %s: %s", self.user_id.name, str(e))
            raise UserError(_("❌ Error revoking access. Please try again."))

    def test_connection(self):
        """Test the Google API connection"""
        self.ensure_one()
        if not self.access_token:
            raise UserError(_("No access token available. Please refresh or reconnect your Google account."))
            
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
            }
            
            # Test with a simple calendar list request
            response = requests.get('https://www.googleapis.com/calendar/v3/users/me/calendarList', headers=headers)
            
            if response.status_code == 200:
                raise UserError(_("✅ Connection test successful! Your Google account is properly connected."))
            else:
                raise UserError(_("❌ Connection test failed. Please refresh your token or reconnect your account."))
                
        except requests.RequestException as e:
            _logger.error("Error testing connection for user %s: %s", self.user_id.name, str(e))
            raise UserError(_("❌ Connection test failed due to network error. Please try again."))
        except UserError:
            raise
        except Exception as e:
            _logger.error("Error testing connection for user %s: %s", self.user_id.name, str(e))
            raise UserError(_("❌ Connection test failed due to unexpected error."))

    @api.model
    def create_google_event(self, event_data, user_id=None):
        """Create a Google Calendar event with Meet link using user's authentication"""
        auth = self.get_user_google_auth(user_id)
        if not auth or not auth.access_token:
            raise UserError(_("No active Google authentication found. Please connect your Google account first."))

        try:
            headers = {
                'Authorization': f'Bearer {auth.access_token}',
                'Content-Type': 'application/json',
            }
            
            url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1'
            response = requests.post(url, headers=headers, json=event_data)
            
            if response.status_code == 200:
                return response.json()
            else:
                _logger.error("Failed to create Google event for user %s: %s", auth.user_id.name, response.text)
                return None
                
        except Exception as e:
            _logger.error("Error creating Google event for user %s: %s", auth.user_id.name, str(e))
            return None