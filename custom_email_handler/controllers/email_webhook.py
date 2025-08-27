import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class SendGridWebhook(http.Controller):
    
    @http.route('/webhook/sendgrid/incoming', type='http', auth='public', methods=['POST'], csrf=False)
    def handle_incoming_email(self, **kwargs):
        """Handle incoming email webhooks from SendGrid"""
        try:
            data = json.loads(request.httprequest.get_data())
            
            # Process the incoming email data
            self._process_webhook_email(data)
            
            return json.dumps({'status': 'success'})
            
        except Exception as e:
            _logger.error(f"Error processing SendGrid webhook: {str(e)}")
            return json.dumps({'status': 'error', 'message': str(e)})
    
    def _process_webhook_email(self, data):
        """Process incoming email from SendGrid webhook data"""
        # Extract email details from SendGrid webhook data
        
        sender = data.get('from', {}).get('email', '')
        subject = data.get('subject', '')
        body_html = data.get('html', '')
        body_text = data.get('text', '')
        
        # Create mail message in Odoo
        mail_message = request.env['mail.message'].sudo().create({
            'subject': subject,
            'body': body_html or body_text,
            'email_from': sender,
            'message_type': 'email',
        })
        
        # Process attachments if any
        attachments = data.get('attachments', [])
        for attachment in attachments:
            request.env['ir.attachment'].sudo().create({
                'name': attachment.get('name'),
                'datas': attachment.get('content'),
                'res_model': 'mail.message',
                'res_id': mail_message.id,
            })
        
        _logger.info(f"Processed SendGrid incoming email: {subject} from {sender}")