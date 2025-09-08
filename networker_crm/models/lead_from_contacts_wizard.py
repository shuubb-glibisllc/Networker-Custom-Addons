from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import requests
import re

_logger = logging.getLogger(__name__)

class LeadFromContactsWizard(models.TransientModel):
    _name = "lead.from.contacts.wizard"
    _description = "Generate Leads from Own Contacts"

    number_leads = fields.Integer("How many leads", default=10)
    industry_ids = fields.Many2many("res.partner.industry", string="Industries")
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda s: s.env.user)
    legal_form_ids = fields.Many2many("x_legal_forms", string="Legal Form", context={'active_test': False})
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Debug: Check if we can access the models
        try:
            legal_statuses = self.env['x_legal_status'].sudo().search([])
            _logger.info("Found %d legal statuses: %s", len(legal_statuses), legal_statuses.mapped('name'))
        except Exception as e:
            _logger.error("Cannot access x_legal_status: %s", e)
            
        try:
            legal_forms = self.env['x_legal_forms'].sudo().search([])
            _logger.info("Found %d legal forms: %s", len(legal_forms), legal_forms.mapped('name'))
        except Exception as e:
            _logger.error("Cannot access x_legal_forms: %s", e)
            
        return res
    
    def test_models_access(self):
        """Test method to debug model access"""
        self.ensure_one()
        # Check if models exist in registry
        if 'x_legal_status' in self.env:
            _logger.info("x_legal_status model exists in registry")
            try:
                records = self.env['x_legal_status'].sudo().search([])
                _logger.info("Found %d legal status records", len(records))
                for record in records[:5]:  # Show first 5
                    _logger.info("Legal Status: ID=%s, Name=%s", record.id, record.display_name)
            except Exception as e:
                _logger.error("Error accessing legal status: %s", e)
        else:
            _logger.error("x_legal_status model NOT in registry")
            
        if 'x_legal_forms' in self.env:
            _logger.info("x_legal_forms model exists in registry")
            try:
                records = self.env['x_legal_forms'].sudo().search([])
                _logger.info("Found %d legal form records", len(records))
                for record in records[:5]:  # Show first 5
                    _logger.info("Legal Form: ID=%s, Name=%s", record.id, record.display_name)
            except Exception as e:
                _logger.error("Error accessing legal forms: %s", e)
        else:
            _logger.error("x_legal_forms model NOT in registry")

    def _build_partner_domain(self):
        dom = [("is_company", "=", True)]
        if self.industry_ids:
            partner_model = self.env["res.partner"]
            field_name = "x_studio_industries" if "x_studio_industries" in partner_model._fields else "industry_id"
            dom.append((field_name, "in", self.industry_ids.ids))
        
        # Note: Legal status filtering removed - we'll fetch and update status for all partners
        
        # Add legal form filter if specified  
        if self.legal_form_ids:
            # Use the actual field that exists on res.partner for legal forms
            partner_model = self.env["res.partner"]
            if "x_legal_forms_id" in partner_model._fields:
                dom.append(("x_legal_forms_id", "in", self.legal_form_ids.ids))
            elif "x_studio_legal_form" in partner_model._fields:
                dom.append(("x_studio_legal_form", "in", [form.x_name for form in self.legal_form_ids]))
            
        return dom

    def _filter_partners_with_fetchable_names(self, partners):
        """Filter partners to only include those where legal names can be fetched from NAPR"""
        SEARCH_URL = "https://enreg.reestri.gov.ge/main.php"
        valid_partners = []
        
        for partner in partners:
            if not partner.vat:
                _logger.info("Partner %s has no VAT, skipping", partner.name)
                continue
                
            try:
                # Use NAPR wizard's legal name fetching logic
                session = requests.Session()
                session.headers.update({
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
                    "Referer": "https://enreg.reestri.gov.ge/main.php?m=new_index",
                })
                
                # Search for the company using VAT
                params = {"c": "search", "m": "find_legal_persons", "s_legal_person_idnumber": partner.vat.strip()}
                r = session.get(SEARCH_URL, params=params, timeout=30)
                r.raise_for_status()
                
                # Decode response
                r.encoding = r.apparent_encoding or "utf-8"
                html = r.text
                
                # Extract legal name from the response
                legal_name = self._extract_legal_name_from_html(html)
                
                if legal_name:
                    # Successfully fetched legal name - update the partner name and status
                    updates = {"name": legal_name}
                    
                    # Update legal status field to "ფუნქციონირებადი" (Active)
                    if hasattr(partner, 'x_studio_legal_status'):
                        legal_status_record = self._get_or_create_legal_status('ფუნქციონირებადი')
                        if legal_status_record:
                            updates["x_studio_legal_status"] = legal_status_record.id
                            _logger.info("Setting x_studio_legal_status to 'ფუნქციონირებადი' for partner %s", partner.vat)
                    
                    # Update legal name field if it exists
                    if hasattr(partner, 'x_studio_legal_name'):
                        updates["x_studio_legal_name"] = legal_name
                    
                    partner.write(updates)
                    valid_partners.append(partner)
                    _logger.info("Partner %s: successfully fetched legal name '%s'", partner.vat, legal_name)
                else:
                    # Could not fetch legal name - set status to "შეჩერებული" (Stopped)
                    updates = {}
                    if hasattr(partner, 'x_studio_legal_status'):
                        legal_status_record = self._get_or_create_legal_status('შეჩერებული')
                        if legal_status_record:
                            updates["x_studio_legal_status"] = legal_status_record.id
                            _logger.info("Setting x_studio_legal_status to 'შეჩერებული' for partner %s", partner.vat)
                    
                    if updates:
                        partner.write(updates)
                    
                    _logger.info("Partner %s: could not fetch legal name, set status to 'შეჩერებული', excluding from lead generation", partner.vat)
                    
            except Exception as e:
                # Error occurred - set status to "შეჩერებული" (Stopped)
                updates = {}
                if hasattr(partner, 'x_studio_legal_status'):
                    legal_status_record = self._get_or_create_legal_status('შეჩერებული')
                    if legal_status_record:
                        updates["x_studio_legal_status"] = legal_status_record.id
                        _logger.info("Setting x_studio_legal_status to 'შეჩერებული' for partner %s due to error", partner.vat)
                
                if updates:
                    partner.write(updates)
                
                _logger.warning("Error fetching legal name for partner %s (%s): %s, set status to 'შეჩერებული', excluding from lead generation", 
                              partner.vat, partner.name, e)
        
        return self.env['res.partner'].browse([p.id for p in valid_partners])

    def _get_or_create_legal_status(self, status_name):
        """Get or create a legal status record with the given name"""
        try:
            # First try to find existing record
            legal_status_record = self.env['x_legal_status'].search([('x_name', '=', status_name)], limit=1)
            if legal_status_record:
                _logger.info("Found existing x_legal_status record: ID=%s, x_name='%s'", legal_status_record.id, status_name)
                return legal_status_record
            
            # If not found, check what records exist
            all_records = self.env['x_legal_status'].search([])
            _logger.info("Available x_legal_status records: %s", [(r.id, getattr(r, 'x_name', 'NO_X_NAME'), getattr(r, 'name', 'NO_NAME')) for r in all_records])
            
            # Try to create new record
            legal_status_record = self.env['x_legal_status'].create({'x_name': status_name})
            _logger.info("Created new x_legal_status record: ID=%s, x_name='%s'", legal_status_record.id, status_name)
            return legal_status_record
            
        except Exception as e:
            _logger.error("Error getting or creating x_legal_status record for '%s': %s", status_name, e)
            return None

    def _extract_legal_name_from_html(self, html):
        """Extract legal name from the NAPR search results"""
        # Based on NAPR wizard logic - look for company name in table cells
        name_pattern = r'<td valign="top">\s*([^\d<][^<]*?)\s*</td>'
        matches = re.findall(name_pattern, html or "", re.DOTALL | re.MULTILINE)
        
        for match in matches:
            cleaned = match.strip()
            # Valid company name criteria
            if (cleaned and 
                not re.match(r'^\d+$', cleaned) and
                cleaned not in ['', '&nbsp;'] and
                'აქტიური' not in cleaned and
                'შეზღუდული პასუხისმგებლობის საზოგადოება' not in cleaned and
                ('შპს' in cleaned or 'ოოო' in cleaned or 'სს' in cleaned or
                 any('ა' <= c <= 'ჰ' for c in cleaned))):
                return cleaned
                
        return ""

    def action_generate(self):
        self.ensure_one()
        limit = max(self.number_leads or 0, 0)
        if not limit:
            return {"type": "ir.actions.act_window_close"}

        partners = self.env["res.partner"].search(self._build_partner_domain())

        # Check if no partners found with current filters
        if not partners:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Partners Found"),
                    "message": _("No partners match the current filter criteria. Please adjust your filters and try again."),
                    "type": "warning",
                    "sticky": True
                }
            }

        # Filter partners to only include those with fetchable legal names
        valid_partners = self._filter_partners_with_fetchable_names(partners)
        
        # Check if no valid partners after name fetching
        if not valid_partners:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Valid Companies Found"),
                    "message": _("No companies have fetchable legal names from the Georgian registry. Cannot generate leads."),
                    "type": "warning",
                    "sticky": True
                }
            }

        # Use the filtered partners for lead generation
        partners = valid_partners

        existing = self.env["crm.lead"].read_group(
            domain=[("partner_id", "in", partners.ids), ("active", "=", True)],
            fields=["partner_id"], groupby=["partner_id"]
        )
        skip_ids = {r["partner_id"][0] for r in existing if r.get("partner_id")}
        partners_without_leads = [p for p in partners if p.id not in skip_ids]
        
        # Apply the limit after filtering out partners with existing leads
        partners_to_create = partners_without_leads[:limit]
        
        to_create = [
            {
                "name": f"Lead: {p.name}",
                "partner_id": p.id,
                "user_id": self.user_id.id or False,
                "type": "opportunity",
            }
            for p in partners_to_create
        ]
        
        # Check if no new leads can be created (all partners already have leads)
        if not to_create:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No New Leads to Generate"),
                    "message": _("All matching partners already have active leads. No new leads were created."),
                    "type": "info",
                    "sticky": True
                }
            }
        
        if to_create:
            self.env["crm.lead"].create(to_create)

        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "name": "Pipeline",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
