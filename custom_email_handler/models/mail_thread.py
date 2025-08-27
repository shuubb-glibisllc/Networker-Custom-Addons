from odoo import models, api
import logging
from odoo.exceptions import UserError
import re

_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    
    @api.model
    def message_process(self, model, message, custom_values=None, save_original=False, strip_attachments=False, thread_id=None):
        """Override to handle incoming emails through custom service"""
        # Process incoming email through custom ha
        self._process_incoming_email(message)
        return super(MailThread, self).message_process(
            model, message, custom_values, save_original, strip_attachments, thread_id
        )
    
    def _process_incoming_email(self, message):
        """Process incoming email message"""
        _logger.info("Processing incoming email through custom handler")
        # Add your custom incoming email processing logic here
        # This could involve parsing email content, extracting attachments,
        # updating records, etc.

class MailMail(models.Model):
    _inherit = 'mail.mail'
    
    def send(self, auto_commit=False, raise_exception=False):
        """Override send method to use custom email service"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        use_custom_service = IrConfigParam.get_param('custom_email_handler.use_custom_service', False)
        
        if use_custom_service:
            return self._send_via_custom_service(auto_commit, raise_exception)
        else:
            return super(MailMail, self).send(auto_commit, raise_exception)
   

            
    def _send_via_custom_service(self, auto_commit=False, raise_exception=False):
        sendgrid_config = self.env['sendgrid.config'].search([('active', '=', True)], limit=1)
        if not sendgrid_config:
            if raise_exception:
                raise UserError("No active SendGrid configuration found")
            return False
        
        def _sanitize_email(addr: str) -> str:
            """Remove hidden characters and whitespace from an email string."""
            if not addr:
                return ""
            # Remove zero-width + control chars
            clean = re.sub(r"[\u200B-\u200D\uFEFF\r\n\t ]+", "", addr)
            return clean.strip()

        for mail in self:
            try:
                # Collect recipients
                to_emails = []
                if mail.email_to:
                    _logger.debug("Raw email_to: %r", mail.email_to)
                    # Split, sanitize, and filter
                    to_emails += [_sanitize_email(e) for e in mail.email_to.split(",") if _sanitize_email(e)]

                # Add from related fields
                to_emails += [_sanitize_email(p.email) for p in mail.recipient_ids if p.email]
                to_emails += [_sanitize_email(p.email) for p in mail.partner_ids if p.email]

                # Deduplicate
                to_emails = list({e for e in to_emails if e})

                _logger.debug("Final sanitized recipient list: %s", to_emails)
                subject = mail.subject or ''
                body = mail.body_html or mail.body or ''

                # Collect attachments
                attachments = []
                for attachment in mail.attachment_ids:
                    attachments.append({
                        'filename': attachment.name,
                        'content': attachment.datas or '',
                        'type': attachment.mimetype or 'application/octet-stream'
                    })

                if not to_emails:
                    raise UserError("No recipients found for email")

                success = sendgrid_config.send_email(to_emails, subject, body, attachments)

                if success:
                    mail.write({
                        'state': 'sent',
                        'message_id': f"<custom-{mail.id}@{self.env.cr.dbname}>",
                    })
                    if auto_commit:
                        self.env.cr.commit()
                else:
                    mail.write({'state': 'exception'})

            except Exception as e:
                _logger.error(f"Failed to send email ID {mail.id}: {str(e)}")
                mail.write({'state': 'exception', 'failure_reason': str(e)})
                if raise_exception:
                    raise

        return True
