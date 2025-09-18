from odoo import models, fields, api, _
import logging
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
                # Check for Google authentication first
                auth = self.env['google.user.auth'].get_user_google_auth()
                if auth and auth.access_token:
                    # User has Google auth, create Google Meet
                    event._set_discuss_videocall_location()
                else:
                    # No Google auth, fall back to original behavior or show message
                    super(CalendarEvent, event)._compute_videocall_location()
            else:
                # For other cases, use original computation
                super(CalendarEvent, event)._compute_videocall_location()

    def _set_discuss_videocall_location(self):
        """Override to create real Google Meet using user's Google account"""
        self.ensure_one()
        _logger.info("GOOGLE MEET: _set_discuss_videocall_location called for event %s", self.name)
        
        try:
            # Get the current user's Google authentication
            auth = self.env['google.user.auth'].get_user_google_auth()
            
            if not auth or not auth.access_token:
                _logger.warning("GOOGLE MEET: No Google authentication found for user %s", self.env.user.name)
                return super(CalendarEvent, self)._set_discuss_videocall_location()
            
            # Format datetime for Google API
            start_time = self.start.strftime('%Y-%m-%dT%H:%M:%S')
            end_time = self.stop.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Prepare attendees list
            attendees = []
            if self.partner_ids:
                attendees = [{'email': partner.email} for partner in self.partner_ids if partner.email]
            
            # Create calendar event with Google Meet
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
            
            # Create event using user's authentication
            google_event = auth.create_google_event(event_data)
            
            if google_event and 'conferenceData' in google_event and 'entryPoints' in google_event['conferenceData']:
                for entry in google_event['conferenceData']['entryPoints']:
                    if entry['entryPointType'] == 'video':
                        # Set the real Google Meet URL
                        self.google_meet_url = entry['uri']
                        self.videocall_location = entry['uri']
                        self.google_event_id = google_event.get('id')
                        _logger.info("GOOGLE MEET: Created Google Meet for user %s: %s", auth.user_id.name, entry['uri'])
                        return True
            
            # If Google Meet creation fails, fall back to original
            _logger.warning("GOOGLE MEET: Failed to create Google Meet, falling back to default")
            return super(CalendarEvent, self)._set_discuss_videocall_location()
            
        except Exception as e:
            _logger.error("GOOGLE MEET: Error creating Google Meet: %s", str(e))
            # Fall back to original behavior on error
            return super(CalendarEvent, self)._set_discuss_videocall_location()
    
    def set_discuss_videocall_location(self):
        """Override to create real Google Meet instead of Odoo meeting"""
        self.ensure_one()
        
        # Check if user has Google authentication
        auth = self.env['google.user.auth'].get_user_google_auth()
        if not auth or not auth.access_token:
            # No Google auth, redirect directly to OAuth
            return {
                'type': 'ir.actions.act_url',
                'url': '/google_meet/oauth/connect',
                'target': 'new',
            }
        
        # User has auth, proceed with Google Meet creation
        return self._set_discuss_videocall_location()
    
    @api.model
    def get_discuss_videocall_location(self):
        """Override to create and return a real Google Meet URL using user's account"""
        _logger.info("GOOGLE MEET: get_discuss_videocall_location called")
        
        try:
            # Get the current user's Google authentication
            auth = self.env['google.user.auth'].get_user_google_auth()
            
            if not auth or not auth.access_token:
                _logger.warning("GOOGLE MEET: No Google authentication found for user %s", self.env.user.name)
                return super(CalendarEvent, self).get_discuss_videocall_location()
            
            _logger.info("GOOGLE MEET: Creating Google Meet with user %s's account", auth.user_id.name)
            
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
            
            # Create event using user's authentication
            google_event = auth.create_google_event(event_data)
            
            if google_event and 'conferenceData' in google_event and 'entryPoints' in google_event['conferenceData']:
                for entry in google_event['conferenceData']['entryPoints']:
                    if entry['entryPointType'] == 'video':
                        _logger.info("GOOGLE MEET: Created real Google Meet URL for user %s: %s", auth.user_id.name, entry['uri'])
                        return entry['uri']
            
            _logger.error("GOOGLE MEET: Failed to create Google Meet for user %s", auth.user_id.name)
            
        except Exception as e:
            _logger.error("GOOGLE MEET: Error creating Google Meet: %s", str(e))
        
        # Fall back to original behavior
        _logger.info("GOOGLE MEET: Using original behavior")
        return super(CalendarEvent, self).get_discuss_videocall_location()


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

