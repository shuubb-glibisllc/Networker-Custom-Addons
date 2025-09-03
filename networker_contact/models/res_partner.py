# -*- coding: utf-8 -*-
from odoo import models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

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
        return wiz.action_fetch_legal_name()
