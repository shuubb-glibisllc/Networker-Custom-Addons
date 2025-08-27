from odoo import api, fields, models

class LeadFromContactsWizard(models.TransientModel):
    _name = "lead.from.contacts.wizard"
    _description = "Generate Leads from Own Contacts"

    number_leads = fields.Integer("How many leads", default=10)
    companies_only = fields.Boolean("Companies", default=True)
    industry_ids = fields.Many2many("res.partner.industry", string="Industries")
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda s: s.env.user)
    tag_ids = fields.Many2many("crm.tag", string="Default Tags")

    def _build_partner_domain(self):
        dom = []
        if self.companies_only:
            dom.append(("is_company", "=", True))
        if self.industry_ids:
            partner_model = self.env["res.partner"]
            field_name = "x_studio_industries" if "x_studio_industries" in partner_model._fields else "industry_id"
            dom.append((field_name, "in", self.industry_ids.ids))
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
                "tag_ids": [(6, 0, self.tag_ids.ids)],
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
