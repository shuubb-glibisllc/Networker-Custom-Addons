from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class GoogleMeetMeeting(models.Model):
    _name = 'google.meet.meeting'
    _description = 'Google Meet Meeting'
    _order = 'create_date desc'

    name = fields.Char(string='Meeting Title', required=True)
    description = fields.Text(string='Description')
    start_datetime = fields.Datetime(string='Start Date', required=True)
    end_datetime = fields.Datetime(string='End Date', required=True)
    meet_url = fields.Char(string='Google Meet URL', readonly=True)
    meet_id = fields.Char(string='Google Meet ID', readonly=True)
    organizer_id = fields.Many2one('res.users', string='Organizer', default=lambda self: self.env.user)
    attendee_ids = fields.Many2many('res.partner', string='Attendees')
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('started', 'Started'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status')

    @api.model
    def create_google_meet(self, meeting_data):
        """Create a Google Meet meeting using Google Calendar API"""
        # This method will be implemented with Google API integration
        pass

    def action_schedule_meeting(self):
        """Schedule the Google Meet meeting"""
        if not self.meet_url:
            # Call Google API to create meeting
            self.create_google_meet({
                'summary': self.name,
                'description': self.description,
                'start': self.start_datetime,
                'end': self.end_datetime,
                'attendees': [{'email': attendee.email} for attendee in self.attendee_ids if attendee.email]
            })
        self.state = 'scheduled'

    def action_cancel_meeting(self):
        """Cancel the Google Meet meeting"""
        self.state = 'cancelled'

    def action_join_meeting(self):
        """Open Google Meet URL"""
        if self.meet_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.meet_url,
                'target': 'new',
            }
        else:
            raise UserError(_('No meeting URL available'))