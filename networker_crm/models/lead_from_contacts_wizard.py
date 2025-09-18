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
    has_mobile = fields.Boolean("Has Mobile Number")
    contact_usage_filter = fields.Selection([
        ('all', 'All Contacts'),
        ('used', 'Used Contacts'),
        ('never_used', 'Never Used Contacts')
    ], string="Contact Usage", default='never_used')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        try:
            legal_statuses = self.env['x_legal_status'].sudo().search([])
            _logger.info("Found %d legal statuses: %s", len(legal_statuses), legal_statuses.mapped('x_name'))
        except Exception as e:
            _logger.error("Cannot access x_legal_status: %s", e)

        try:
            legal_forms = self.env['x_legal_forms'].sudo().search([])
            _logger.info("Found %d legal forms: %s", len(legal_forms), legal_forms.mapped('x_name'))
        except Exception as e:
            _logger.error("Cannot access x_legal_forms: %s", e)

        return res

    def _build_partner_domain(self):
        dom = [("is_company", "=", True)]
        if self.industry_ids:
            partner_model = self.env["res.partner"]
            field_name = "x_studio_industries" if "x_studio_industries" in partner_model._fields else "industry_id"
            dom.append((field_name, "in", self.industry_ids.ids))

        if self.legal_form_ids:
            partner_model = self.env["res.partner"]
            if "x_legal_forms_id" in partner_model._fields:
                dom.append(("x_legal_forms_id", "in", self.legal_form_ids.ids))
            elif "x_studio_legal_form" in partner_model._fields:
                dom.append(("x_studio_legal_form", "in", [form.x_name for form in self.legal_form_ids]))
        if self.has_mobile:
            dom.append(("mobile", "!=", False))

        return dom

    def _filter_partners_with_fetchable_names(self, partners):
        """Filter partners and fetch data from enreg.reestri.gov.ge and companyinfo.ge"""
        valid_partners = []
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        })

        for partner in partners:
            if not partner.vat:
                _logger.info("Partner %s has no VAT, skipping", partner.name)
                continue

            legal_name_napr = None
            try:
                SEARCH_URL_NAPR = "https://enreg.reestri.gov.ge/main.php"
                params_napr = {"c": "search", "m": "find_legal_persons", "s_legal_person_idnumber": partner.vat.strip()}
                r_napr = session.get(SEARCH_URL_NAPR, params=params_napr, timeout=30)
                r_napr.raise_for_status()
                r_napr.encoding = r_napr.apparent_encoding or "utf-8"
                html_napr = r_napr.text
                legal_name_napr = self._extract_legal_name_from_html(html_napr)

                if legal_name_napr:
                    updates = {"name": legal_name_napr}
                    if hasattr(partner, 'x_studio_legal_status'):
                        legal_status_record = self._get_or_create_legal_status('ფუნქციონირებადი')
                        if legal_status_record:
                            updates["x_studio_legal_status"] = legal_status_record.id
                    if hasattr(partner, 'x_studio_legal_name'):
                        updates["x_studio_legal_name"] = legal_name_napr
                    partner.write(updates)
                    _logger.info("Partner %s: successfully fetched legal name '%s' from NAPR", partner.vat, legal_name_napr)
                else:
                    updates = {}
                    if hasattr(partner, 'x_studio_legal_status'):
                        legal_status_record = self._get_or_create_legal_status('შეჩერებული')
                        if legal_status_record:
                            updates["x_studio_legal_status"] = legal_status_record.id
                    if updates:
                        partner.write(updates)
                    _logger.info("Partner %s: could not fetch legal name from NAPR, set status to 'შეჩერებული'", partner.vat)

            except Exception as e:
                updates = {}
                if hasattr(partner, 'x_studio_legal_status'):
                    legal_status_record = self._get_or_create_legal_status('შეჩერებული')
                    if legal_status_record:
                        updates["x_studio_legal_status"] = legal_status_record.id
                if updates:
                    partner.write(updates)
                _logger.warning("Error fetching legal name for partner %s from NAPR: %s", partner.vat, e)

            try:
                search_url_api = "https://api.companyinfo.ge/api/corporations/search"
                params_api = {"idCode": partner.vat.strip()}
                r_search_api = session.get(search_url_api, params=params_api, timeout=30)
                r_search_api.raise_for_status()
                search_data = r_search_api.json()

                if search_data.get("items"):
                    corp_info = search_data["items"][0]
                    corp_id = corp_info.get("id")
                    legal_name_api = corp_info.get("name")

                    if not legal_name_napr and legal_name_api:
                        partner.name = legal_name_api

                    if corp_id and hasattr(partner, 'x_studio_director') and not partner.x_studio_director:
                        details_url_api = f"https://api.companyinfo.ge/api/company-info/{corp_id}"
                        r_details_api = session.get(details_url_api, timeout=30)
                        r_details_api.raise_for_status()
                        details_data = r_details_api.json()

                        if details_data.get("persons"):
                            for person in details_data["persons"]:
                                if person.get("personRole") == "დირექტორი":
                                    director_name = person.get("personName")
                                    if director_name:
                                        partner.x_studio_director = director_name
                                        _logger.info("Found director '%s' for partner %s", director_name, partner.name)
                                        break
                else:
                    _logger.info("Partner %s: could not find corporation info on companyinfo.ge API", partner.vat)

            except Exception as e:
                _logger.warning("Error fetching data for partner %s from companyinfo.ge: %s", partner.vat, e)

            if partner.name:
                 valid_partners.append(partner)

        return self.env['res.partner'].browse([p.id for p in valid_partners])

    def _get_or_create_legal_status(self, status_name):
        """Get or create a legal status record with the given name"""
        try:
            legal_status_record = self.env['x_legal_status'].search([('x_name', '=', status_name)], limit=1)
            if legal_status_record:
                return legal_status_record
            legal_status_record = self.env['x_legal_status'].create({'x_name': status_name})
            return legal_status_record
        except Exception as e:
            _logger.error("Error getting or creating x_legal_status record for '%s': %s", status_name, e)
            return None

    def _extract_legal_name_from_html(self, html):
        """Extract legal name from the NAPR search results"""
        name_pattern = r'<td valign="top">\s*([^\d<][^<]*?)\s*</td>'
        matches = re.findall(name_pattern, html or "", re.DOTALL | re.MULTILINE)
        for match in matches:
            cleaned = match.strip()
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

        if self.contact_usage_filter != 'all':
            existing_lead_partners_query = self.env["crm.lead"].read_group(
                domain=[("partner_id", "in", partners.ids), ("active", "=", True)],
                fields=["partner_id"], groupby=["partner_id"]
            )
            existing_lead_partner_ids = {res["partner_id"][0] for res in existing_lead_partners_query if res.get("partner_id")}

            if self.contact_usage_filter == 'never_used':
                partners = partners.filtered(lambda p: p.id not in existing_lead_partner_ids)
            elif self.contact_usage_filter == 'used':
                partners = partners.filtered(lambda p: p.id in existing_lead_partner_ids)

        if not partners:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No New Leads to Generate"),
                    "message": _("All matching partners have been filtered out based on the contact usage filter."),
                    "type": "info",
                    "sticky": True
                }
            }

        partners_to_process = partners[:limit]

        valid_partners = self._filter_partners_with_fetchable_names(partners_to_process)
        
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

        partners_to_create = valid_partners
        
        to_create = [
            {
                "name": f"Lead: {p.name}",
                "partner_id": p.id,
                "user_id": self.user_id.id or False,
                "type": "opportunity",
            }
            for p in partners_to_create
        ]
        
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