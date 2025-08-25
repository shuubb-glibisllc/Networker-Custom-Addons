import base64
import json
import logging
import re
import time

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_sanitize

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Email, Attachment, FileContent, FileName, FileType, Disposition, ReplyTo
)
from sendgrid.helpers.mail.header import Header

_logger = logging.getLogger(__name__)


class SendGridConfig(models.Model):
    _name = "sendgrid.config"
    _description = "SendGrid Configuration"
    _order = "name"

    name = fields.Char(required=True)
    api_key = fields.Char(string="SendGrid API Key", required=True)
    api_url = fields.Char(string="API URL", help="Use https://api.eu.sendgrid.com for EU data residency")
    sender_email = fields.Char(string="Default Sender Email", required=True)
    sender_name = fields.Char(string="Default Sender Name")
    active = fields.Boolean(default=True)

    def send_email(self, to_emails, subject, body_html, attachments=None, cc=None, bcc=None, reply_to=None):
        self.ensure_one()
        _logger.debug(
            "[SendGrid] send_email called | to=%s | cc=%s | bcc=%s | subject_len=%s | body_len=%s | atts=%s | reply_to=%s",
            self._peek_list(to_emails),
            self._peek_list(cc),
            self._peek_list(bcc),
            len(subject or "") if subject is not None else 0,
            len(body_html or "") if body_html is not None else 0,
            len(attachments or []),
            str(reply_to) if reply_to else None,
        )
        return self._send_via_sendgrid(to_emails, subject, body_html, attachments, cc, bcc, reply_to)

    def _peek_list(self, value):
        if not value:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

    def _norm_list(self, value):
        if not value:
            _logger.debug("[SendGrid] _norm_list -> []")
            return []
        if isinstance(value, (list, tuple, set)):
            out = [str(v).strip() for v in value if v]
            _logger.debug("[SendGrid] _norm_list from iterable -> %s", out)
            return out
        out = [str(value).strip()]
        _logger.debug("[SendGrid] _norm_list from scalar -> %s", out)
        return out

    def _clean_email_body(self, body_html):
        """Clean email body content to improve deliverability and avoid promotions folder"""
        if not body_html:
            return ""
        
        # Convert to string if not already
        body = str(body_html)
        
        # Remove or convert problematic ** symbols that might interfere with email delivery
        # Convert **text** to <strong>text</strong> for proper HTML formatting
        body = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', body)
        
        # Remove any remaining lone ** symbols
        body = re.sub(r'\*\*', '', body)
        
        # Replace promotional language with more neutral alternatives
        promotional_replacements = {
            r'\b(CLICK HERE|CLICK NOW)\b': 'View Details',
            r'\b(BUY NOW|PURCHASE NOW)\b': 'View Product',
            r'\b(LIMITED TIME|ACT NOW)\b': 'Available Now',
            r'\b(URGENT|HURRY)\b': 'Important',
            r'\b(FREE|100% FREE)\b': 'Complimentary',
            r'\b(GUARANTEE|GUARANTEED)\b': 'Assured',
            r'\b(AMAZING|INCREDIBLE)\b': 'Notable',
        }
        
        for pattern, replacement in promotional_replacements.items():
            body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)
        
        # Sanitize HTML to ensure safe content
        try:
            body = html_sanitize(body, silent=True)
        except Exception as e:
            _logger.warning("[SendGrid] HTML sanitization failed: %s", e)
        
        _logger.debug("[SendGrid] Body cleaned, length: %d", len(body))
        return body

    def _clean_subject_line(self, subject):
        """Clean subject line to avoid promotional flags"""
        if not subject:
            return ""
        
        # Remove excessive punctuation and symbols
        subject = re.sub(r'[!]{2,}', '!', subject)  # Multiple exclamation marks
        subject = re.sub(r'[?]{2,}', '?', subject)  # Multiple question marks
        subject = re.sub(r'[$]{2,}', '$', subject)  # Multiple dollar signs
        
        # Remove promotional phrases from subject
        promotional_patterns = [
            r'\b(FREE|100% FREE)\b',
            r'\b(URGENT|HURRY)\b', 
            r'\b(ACT NOW|CLICK NOW)\b',
            r'\b(LIMITED TIME|OFFER EXPIRES)\b',
            r'\b(SALE|DISCOUNT)\b',
            r'\b(WIN|WINNER)\b',
            r'\b(GUARANTEE|GUARANTEED)\b'
        ]
        
        for pattern in promotional_patterns:
            subject = re.sub(pattern, '', subject, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        subject = re.sub(r'\s+', ' ', subject).strip()
        
        _logger.debug("[SendGrid] Subject cleaned: %s", subject)
        return subject

    def _html_to_plain_text(self, html_content):
        """Convert HTML content to plain text for better deliverability"""
        if not html_content:
            return ""
        
        try:
            # Remove HTML tags and convert to plain text
            import html
            
            # Decode HTML entities
            text = html.unescape(html_content)
            
            # Replace common HTML tags with appropriate formatting
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<p\b[^>]*>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<div\b[^>]*>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
            
            # Remove all remaining HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            # Clean up whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Remove excessive newlines
            text = re.sub(r'[ \t]+', ' ', text)      # Normalize spaces
            text = text.strip()
            
            return text
            
        except Exception as e:
            _logger.warning("[SendGrid] HTML to plain text conversion failed: %s", e)
            return ""

    def _send_via_sendgrid(self, to_emails, subject, body_html, attachments=None, cc=None, bcc=None, reply_to=None):
        t0 = time.time()
        key = (self.api_key or "").strip()
        if not key:
            _logger.error("[SendGrid] Missing SendGrid API key")
            raise UserError(_("SendGrid API key is required"))
        _logger.debug("[SendGrid] Using API key=%s", key)

        tos = self._norm_list(to_emails)
        if not tos:
            _logger.error("[SendGrid] No recipients after normalization")
            raise UserError(_("At least one recipient is required"))
        _logger.debug("[SendGrid] To list normalized: %s", tos)

        # Clean subject line to avoid promotional flags
        cleaned_subject = self._clean_subject_line(subject) or "(no subject)"
        _logger.debug("[SendGrid] Subject resolved: %r", cleaned_subject)

        # Clean the email body to remove problematic ** symbols and promotional content
        cleaned_body = self._clean_email_body(body_html)

        from_email = Email(self.sender_email, self.sender_name or None)
        _logger.debug("[SendGrid] From: %s (%s)", self.sender_email, self.sender_name or "")

        msg = Mail(
            from_email=from_email,
            to_emails=tos,
            subject=cleaned_subject,
            html_content=cleaned_body,
        )
        
        # Add headers to improve deliverability and avoid promotions folder
        msg.add_header(Header("X-Priority", "1"))  # High priority
        msg.add_header(Header("X-MSMail-Priority", "High"))  # Outlook priority
        msg.add_header(Header("Importance", "high"))  # General importance header
        msg.add_header(Header("X-Mailer", "Odoo SendGrid Connector"))  # Identify as transactional
        msg.add_header(Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"))  # RFC 8058 compliance
        msg.add_header(Header("X-Auto-Response-Suppress", "OOF, DR, RN, NRN"))  # Suppress auto-responses
        
        # Add transactional email indicators to avoid promotions folder
        msg.add_category("transactional")  # SendGrid category for transactional emails
        msg.add_category("business")       # Business communication category
        
        # Set mail settings for better deliverability
        try:
            # Add plain text version to improve deliverability
            plain_content = self._html_to_plain_text(cleaned_body)
            if plain_content:
                from sendgrid.helpers.mail import Content
                msg.add_content(Content("text/plain", plain_content))
                _logger.debug("[SendGrid] Plain text content added, length: %d", len(plain_content))
            
            # Add tracking settings (helps with sender reputation)
            mail_settings = msg.mail_settings
            if mail_settings:
                # Disable click tracking for transactional emails (reduces promotional flags)
                click_tracking = mail_settings.click_tracking
                if click_tracking:
                    click_tracking.enable = False
                    
                # Enable open tracking for engagement metrics
                open_tracking = mail_settings.open_tracking  
                if open_tracking:
                    open_tracking.enable = True
                    
        except Exception as e:
            _logger.warning("[SendGrid] Failed to set mail settings: %s", e)
        
        _logger.debug("[SendGrid] HTML content length: %d (original: %d)", len(cleaned_body), len(body_html or ""))

        cc_list = self._norm_list(cc)
        for e in cc_list:
            msg.add_cc(e)
        if cc_list:
            _logger.debug("[SendGrid] CC: %s", cc_list)

        bcc_list = self._norm_list(bcc)
        for e in bcc_list:
            msg.add_bcc(e)
        if bcc_list:
            _logger.debug("[SendGrid] BCC: %s", bcc_list)

        if reply_to:
            msg.reply_to = ReplyTo(str(reply_to).strip())
            _logger.debug("[SendGrid] Reply-To: %s", str(reply_to).strip())

        att_count = 0
        if attachments:
            for idx, a in enumerate(attachments, 1):
                if not isinstance(a, dict):
                    _logger.warning("[SendGrid] Attachment %d skipped (not dict)", idx)
                    continue
                name = a.get("filename") or a.get("name") or "attachment"
                ctype = a.get("type") or a.get("mimetype") or "application/octet-stream"
                raw = a.get("content") or a.get("datas") or b""
                orig_len = (len(raw) if isinstance(raw, (bytes, bytearray)) else len(str(raw)))
                if isinstance(raw, bytes):
                    b64 = base64.b64encode(raw).decode()
                else:
                    s = str(raw)
                    try:
                        base64.b64decode(s.encode(), validate=True)
                        b64 = s
                        _logger.debug("[SendGrid] Attachment %d appears base64 already", idx)
                    except Exception:
                        b64 = base64.b64encode(s.encode()).decode()
                att = Attachment()
                att.file_content = FileContent(b64)
                att.file_type = FileType(ctype)
                att.file_name = FileName(name)
                att.disposition = Disposition("attachment")
                msg.add_attachment(att)
                att_count += 1
                _logger.debug(
                    "[EmailService] Attachment %d added | name=%s | type=%s | raw_len=%d | b64_len=%d",
                    idx, name, ctype, orig_len, len(b64)
                )
        _logger.debug("[SendGrid] Total attachments added: %d", att_count)

        try:
            payload = msg.get()
            _logger.debug("[SendGrid] SendGrid payload preview: %s", json.dumps(payload, ensure_ascii=False)[:2000])
        except Exception as plerr:
            _logger.debug("[SendGrid] Payload preview failed: %s", plerr)

        try:
            sg = SendGridAPIClient(key)
            eu_mode = False
            if self.api_url and "api.eu.sendgrid.com" in self.api_url:
                try:
                    sg.set_sendgrid_data_residency("eu")
                    eu_mode = True
                except Exception:
                    sg.host = "https://api.eu.sendgrid.com"
                    eu_mode = True
            _logger.debug("[SendGrid] Client ready | host=%s | eu_mode=%s",
                          getattr(sg, "host", "https://api.sendgrid.com"), eu_mode)

            t_send = time.time()
            resp = sg.send(msg)
            dt = time.time() - t_send
            _logger.debug("[SendGrid] Send attempted | status=%s | duration_ms=%d",
                          getattr(resp, "status_code", "n/a"), int(dt * 1000))

            if resp.status_code in (200, 202):
                _logger.info("SendGrid accepted mail: %s", resp.status_code)
                _logger.debug("[SendGrid] Response headers keys: %s", list(getattr(resp, "headers", {}).keys()))
                _logger.debug("[SendGrid] Total time ms: %d", int((time.time() - t0) * 1000))
                return True

            body_txt = ""
            try:
                body_txt = resp.body.decode() if getattr(resp, "body", None) else ""
                if body_txt:
                    j = json.loads(body_txt)
                    body_txt = json.dumps(j.get("errors", j), ensure_ascii=False)
            except Exception:
                body_txt = body_txt or ""

            _logger.error("SendGrid error %s: %s", resp.status_code, body_txt[:2000])
            _logger.debug("[SendGrid] Response headers keys: %s", list(getattr(resp, "headers", {}).keys()))
            _logger.debug("[SendGrid] Total time ms: %d", int((time.time() - t0) * 1000))
            raise UserError(_("SendGrid error %s: %s") % (resp.status_code, body_txt or _("see logs")))
        except Exception as e:
            body_txt = ""
            try:
                body = getattr(e, "body", None)
                if body:
                    body_txt = json.dumps(json.loads(body), ensure_ascii=False)
            except Exception:
                pass
            _logger.exception("Failed to send via SendGrid%s", f" ({body_txt})" if body_txt else "")
            _logger.debug("[SendGrid] Total time ms: %d", int((time.time() - t0) * 1000))
            raise UserError(_("Failed to send email: %s%s") % (str(e), f" | {body_txt}" if body_txt else ""))
