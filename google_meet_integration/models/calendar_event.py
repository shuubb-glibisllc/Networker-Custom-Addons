from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    google_meet_id = fields.Many2one('google.meet.meeting', string='Google Meet')
    has_google_meet = fields.Boolean(string='Has Google Meet', compute='_compute_has_google_meet', store=True)
    google_event_id = fields.Char(string='Google Calendar Event ID', help='ID of the event in Google Calendar')
    google_meet_url = fields.Char(string='Google Meet URL', help='Direct URL to join the Google Meet')

    @api.depends('google_meet_id', 'google_meet_url')
    def _compute_has_google_meet(self):
        for event in self:
            event.has_google_meet = bool(event.google_meet_id or event.google_meet_url)

    def set_discuss_videocall_location(self):
        """Override to use Google Meet instead of Odoo meeting"""
        self.ensure_one()
        # Use Odoo's built-in Google Meet functionality
        # Set videocall_location to 'google_meet' to trigger Odoo's Google Meet integration
        self.videocall_location = 'google_meet'
        return True

    def action_create_google_meet(self):
        """Create a Google Meet for this calendar event"""
        if self.google_meet_id:
            return self.google_meet_id.action_join_meeting()
        
        google_meet = self.env['google.meet.meeting'].create({
            'name': self.name,
            'description': self.description,
            'start_datetime': self.start,
            'end_datetime': self.stop,
            'organizer_id': self.user_id.id,
            'attendee_ids': [(6, 0, self.partner_ids.ids)],
            'calendar_event_id': self.id,
        })
        self.google_meet_id = google_meet.id
        return google_meet.action_schedule_meeting()

    def action_join_google_meet(self):
        """Join the Google Meet associated with this event"""
        if self.google_meet_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.google_meet_url,
                'target': 'new',
            }
        elif self.google_meet_id:
            return self.google_meet_id.action_join_meeting()
        else:
            return self.action_create_google_meet()