from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class LeadFromContactsWizard(models.TransientModel):
    _name = "lead.from.contacts.wizard"
    _description = "Generate Leads from Own Contacts"

    number_leads = fields.Integer("How many leads", default=10)
    companies_only = fields.Boolean("Companies", default=True)
    industry_ids = fields.Many2many("res.partner.industry", string="Industries")
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda s: s.env.user)
    tag_ids = fields.Many2many("res.partner.category", "wizard_tag_rel", "wizard_id", "category_id", string="Tags")
    legal_status_ids = fields.Many2many("x_legal_status", string="Legal Status", context={'active_test': False})  
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
        dom = []
        if self.companies_only:
            dom.append(("is_company", "=", True))
        if self.industry_ids:
            partner_model = self.env["res.partner"]
            field_name = "x_studio_industries" if "x_studio_industries" in partner_model._fields else "industry_id"
            dom.append((field_name, "in", self.industry_ids.ids))
        
        # Filter by legal status if specified
        if self.legal_status_ids:
            # Use the actual field that exists on res.partner for legal status
            partner_model = self.env["res.partner"]
            if "x_studio_legal_status" in partner_model._fields:
                dom.append(("x_studio_legal_status", "in", [status.x_name for status in self.legal_status_ids]))
            elif "x_legal_status_id" in partner_model._fields:
                dom.append(("x_legal_status_id", "in", self.legal_status_ids.ids))
        
        # Add legal form filter if specified  
        if self.legal_form_ids:
            # Use the actual field that exists on res.partner for legal forms
            partner_model = self.env["res.partner"]
            if "x_legal_forms_id" in partner_model._fields:
                dom.append(("x_legal_forms_id", "in", self.legal_form_ids.ids))
            elif "x_studio_legal_form" in partner_model._fields:
                dom.append(("x_studio_legal_form", "in", [form.x_name for form in self.legal_form_ids]))
            
        return dom

    def action_generate(self):
        self.ensure_one()
        limit = max(self.number_leads or 0, 0)
        if not limit:
            return {"type": "ir.actions.act_window_close"}

        partners = self.env["res.partner"].search(self._build_partner_domain(), limit=limit)

        existing = self.env["crm.lead"].read_group(
            domain=[("partner_id", "in", partners.ids), ("active", "=", True)],
            fields=["partner_id"], groupby=["partner_id"]
        )
        skip_ids = {r["partner_id"][0] for r in existing if r.get("partner_id")}
        to_create = [
            {
                "name": f"Lead: {p.name}",
                "partner_id": p.id,
                "user_id": self.user_id.id or False,
                "tag_ids": [(6, 0, self.tag_ids.ids)] if self.tag_ids else [],
                "type": "opportunity",
            }
            for p in partners if p.id not in skip_ids
        ]
        if to_create:
            self.env["crm.lead"].create(to_create)

        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "name": "Pipeline",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
