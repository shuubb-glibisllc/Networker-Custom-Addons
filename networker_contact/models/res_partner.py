# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    has_crm_opportunity = fields.Boolean(
        string="Has CRM Opportunity",
        compute="_compute_has_crm_opportunity",
        store=True,
        help="Indicates if this contact is linked to any CRM opportunity."
    )

    @api.depends('opportunity_ids')
    def _compute_has_crm_opportunity(self):
        for partner in self:
            partner.has_crm_opportunity = bool(partner.opportunity_ids)

    def action_napr_fetch(self):
        self.ensure_one()
        wiz = self.env["partner.napr.fetch.wizard"].create({
            "partner_id": self.id,
            "vat": self.vat or "",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "partner.napr.fetch.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_fetch_legal_name(self):
        """Fetch legal name from Georgian registry"""
        self.ensure_one()
        wiz = self.env["partner.napr.fetch.wizard"].create({
            "partner_id": self.id,
            "vat": self.vat or "",
        })
        result = wiz.action_fetch_legal_name()
        
        # After successful fetch, save legal name to x_studio_legal_name field
        if hasattr(self, 'x_studio_legal_name') and self.name:
            self.write({'x_studio_legal_name': self.name})
            
        return result
