from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import json
from datetime import datetime

_logger = logging.getLogger(__name__)

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    google_meet_url = fields.Char(string='Google Meet URL', help='Direct URL to join the Google Meet')
    google_event_id = fields.Char(string='Google Calendar Event ID', help='ID of the event in Google Calendar')
    
    @api.depends('videocall_source', 'access_token', 'google_meet_url')
    def _compute_videocall_location(self):
        """Override to use Google Meet instead of local videocall"""
        for event in self:
            if event.google_meet_url:
                # Use existing Google Meet URL
                event.videocall_location = event.google_meet_url
            elif event.videocall_source == 'discuss':
                # This will trigger our _set_discuss_videocall_location override
                event._set_discuss_videocall_location()
            # For other cases, videocall_location remains as is

    def _set_discuss_videocall_location(self):
        """Override to create real Google Meet instead of Odoo meeting"""
        self.ensure_one()
        _logger.info("GOOGLE MEET: _set_discuss_videocall_location called for event %s", self.name)
        
        # Check if Google Meet is enabled
        google_meet_enabled = self.env['ir.config_parameter'].sudo().get_param('google_meet.enabled', False)
        _logger.info("GOOGLE MEET: Google Meet enabled = %s", google_meet_enabled)
        
        if google_meet_enabled:
            try:
                # Get Google API credentials from Google Calendar module
                google_client_id = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
                google_client_secret = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_secret')
                google_access_token = self.env['ir.config_parameter'].sudo().get_param('google_meet.access_token')
                google_refresh_token = self.env['ir.config_parameter'].sudo().get_param('google_meet.refresh_token')
                
                if not all([google_client_id, google_client_secret]):
                    # Fall back to original behavior if credentials missing
                    return super(CalendarEvent, self)._set_discuss_videocall_location()
                
                # Get or refresh access token
                if not google_access_token and google_refresh_token:
                    _logger.info("GOOGLE MEET: Getting new access token from refresh token")
                    google_access_token = self._refresh_google_access_token(google_client_id, google_client_secret, google_refresh_token)
                    if not google_access_token:
                        _logger.error("GOOGLE MEET: Failed to get access token")
                        return super(CalendarEvent, self)._set_discuss_videocall_location()
                elif not google_access_token:
                    _logger.warning("GOOGLE MEET: No access token or refresh token available")
                    return super(CalendarEvent, self)._set_discuss_videocall_location()
                
                # Format datetime for Google API
                start_time = self.start.strftime('%Y-%m-%dT%H:%M:%S')
                end_time = self.stop.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Prepare attendees list
                attendees = []
                if self.partner_ids:
                    attendees = [{'email': partner.email} for partner in self.partner_ids if partner.email]
                
                # Create calendar event with Google Meet (copied from google_meet.py)
                event_data = {
                    'summary': self.name or 'Meeting',
                    'description': self.description or '',
                    'start': {
                        'dateTime': start_time,
                        'timeZone': 'UTC',
                    },
                    'end': {
                        'dateTime': end_time,
                        'timeZone': 'UTC',
                    },
                    'attendees': attendees,
                    'conferenceData': {
                        'createRequest': {
                            'requestId': f"meet-{self.id or 'new'}-{int(datetime.now().timestamp())}",
                            'conferenceSolutionKey': {
                                'type': 'hangoutsMeet'
                            }
                        }
                    }
                }
                
                headers = {
                    'Authorization': f'Bearer {google_access_token}',
                    'Content-Type': 'application/json',
                }
                
                # Create event with Google Meet
                url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1'
                response = requests.post(url, headers=headers, json=event_data)
                
                if response.status_code == 200:
                    event = response.json()
                    if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                        for entry in event['conferenceData']['entryPoints']:
                            if entry['entryPointType'] == 'video':
                                # Set the real Google Meet URL
                                self.google_meet_url = entry['uri']
                                self.videocall_location = entry['uri']
                                return True
                
                # If Google Meet creation fails, fall back to original
                return super(CalendarEvent, self)._set_discuss_videocall_location()
                
            except Exception as e:
                _logger.error(f"Error creating Google Meet: {str(e)}")
                # Fall back to original behavior on error
                return super(CalendarEvent, self)._set_discuss_videocall_location()
        else:
            # Fall back to original behavior
            return super(CalendarEvent, self)._set_discuss_videocall_location()
    
    def set_discuss_videocall_location(self):
        """Override to create real Google Meet instead of Odoo meeting"""
        self.ensure_one()
        return self._set_discuss_videocall_location()
    
    @api.model
    def get_discuss_videocall_location(self):
        """Override to create and return a real Google Meet URL"""
        _logger.info("GOOGLE MEET: get_discuss_videocall_location called")
        
        # Check if Google Meet is enabled
        google_meet_enabled = self.env['ir.config_parameter'].sudo().get_param('google_meet.enabled', False)
        _logger.info("GOOGLE MEET: Google Meet enabled = %s", google_meet_enabled)
        
        if google_meet_enabled:
            try:
                _logger.info("GOOGLE MEET: Creating Google Meet directly")
                
                # Get Google API credentials from Google Calendar module
                google_client_id = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_id')
                google_client_secret = self.env['ir.config_parameter'].sudo().get_param('google_calendar_client_secret')
                google_access_token = self.env['ir.config_parameter'].sudo().get_param('google_meet.access_token')
                google_refresh_token = self.env['ir.config_parameter'].sudo().get_param('google_meet.refresh_token')
                
                if not all([google_client_id, google_client_secret]):
                    _logger.warning("GOOGLE MEET: Missing Client ID or Client Secret")
                    return super(CalendarEvent, self).get_discuss_videocall_location()
                
                # Get or refresh access token
                if not google_access_token and google_refresh_token:
                    _logger.info("GOOGLE MEET: Getting new access token from refresh token")
                    google_access_token = self._refresh_google_access_token(google_client_id, google_client_secret, google_refresh_token)
                    if not google_access_token:
                        _logger.error("GOOGLE MEET: Failed to get access token")
                        return super(CalendarEvent, self).get_discuss_videocall_location()
                elif not google_access_token:
                    _logger.warning("GOOGLE MEET: No access token or refresh token available")
                    return super(CalendarEvent, self).get_discuss_videocall_location()
                
                # Create a basic Google Meet event
                from datetime import datetime, timedelta
                now = datetime.now()
                start_time = now.strftime('%Y-%m-%dT%H:%M:%S')
                end_time = (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S')
                
                event_data = {
                    'summary': 'Meeting',
                    'start': {
                        'dateTime': start_time,
                        'timeZone': 'UTC',
                    },
                    'end': {
                        'dateTime': end_time,
                        'timeZone': 'UTC',
                    },
                    'conferenceData': {
                        'createRequest': {
                            'requestId': f"meet-{int(datetime.now().timestamp())}",
                            'conferenceSolutionKey': {
                                'type': 'hangoutsMeet'
                            }
                        }
                    }
                }
                
                headers = {
                    'Authorization': f'Bearer {google_access_token}',
                    'Content-Type': 'application/json',
                }
                
                # Create event with Google Meet
                import requests
                url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1'
                response = requests.post(url, headers=headers, json=event_data)
                
                if response.status_code == 200:
                    event = response.json()
                    if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                        for entry in event['conferenceData']['entryPoints']:
                            if entry['entryPointType'] == 'video':
                                _logger.info("GOOGLE MEET: Created real Google Meet URL: %s", entry['uri'])
                                return entry['uri']
                
                _logger.error("GOOGLE MEET: Failed to create Google Meet, response: %s", response.text)
                
            except Exception as e:
                _logger.error("GOOGLE MEET: Error creating Google Meet: %s", str(e))
        
        # Fall back to original behavior
        _logger.info("GOOGLE MEET: Using original behavior")
        return super(CalendarEvent, self).get_discuss_videocall_location()

    def _refresh_google_access_token(self, client_id, client_secret, refresh_token):
        """Refresh Google access token using refresh token"""
        try:
            refresh_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post('https://oauth2.googleapis.com/token', data=refresh_data)
            
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data.get('access_token')
                
                if new_access_token:
                    # Save the new access token
                    self.env['ir.config_parameter'].sudo().set_param('google_meet.access_token', new_access_token)
                    _logger.info("GOOGLE MEET: Successfully refreshed access token")
                    return new_access_token
            
            _logger.error("GOOGLE MEET: Failed to refresh token, response: %s", response.text)
            return None
            
        except Exception as e:
            _logger.error("GOOGLE MEET: Error refreshing token: %s", str(e))
            return None

    def action_join_google_meet(self):
        """Join the Google Meet associated with this event"""
        if self.google_meet_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.google_meet_url,
                'target': 'new',
            }
        else:
            # Create Google Meet if it doesn't exist
            return self._set_discuss_videocall_location()