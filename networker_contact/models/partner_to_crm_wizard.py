# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class PartnerToCrmWizard(models.TransientModel):
    _name = "partner.to.crm.wizard"
    _description = "Convert Partners to CRM Leads"

    partner_ids = fields.Many2many("res.partner", string="Selected Contacts")
    team_id = fields.Many2one("crm.team", string="Sales Team", required=True)
    stage_id = fields.Many2one("crm.stage", string="Stage", required=True)
    user_id = fields.Many2one("res.users", string="Salesperson")
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string="Priority", default='1')
    source_id = fields.Many2one("utm.source", string="Source")
    medium_id = fields.Many2one("utm.medium", string="Medium")
    campaign_id = fields.Many2one("utm.campaign", string="Campaign")
    description = fields.Text(string="Internal Notes")

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            # Set default stage for the selected team
            stages = self.env['crm.stage'].search([('team_id', '=', self.team_id.id)], limit=1)
            if stages:
                self.stage_id = stages[0]
            # Set default salesperson from team
            if self.team_id.user_id:
                self.user_id = self.team_id.user_id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Get selected partners from context
        partner_ids = self.env.context.get('active_ids', [])
        if partner_ids:
            res['partner_ids'] = [(6, 0, partner_ids)]
        # Set default team
        default_team = self.env['crm.team'].search([], limit=1)
        if default_team:
            res['team_id'] = default_team.id
        return res

    def action_convert_to_crm(self):
        """Convert selected partners to CRM leads"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_("No contacts selected for conversion."))
        
        # Check if any partners can be converted (don't have any existing leads)
        Lead = self.env['crm.lead']
        convertible_partners = []
        
        for partner in self.partner_ids:
            existing_leads = Lead.search([
                ('partner_id', '=', partner.id)
            ], limit=1)
            if not existing_leads:
                convertible_partners.append(partner)
        
        if not convertible_partners:
            raise UserError(_("All selected contacts already have linked leads and cannot be converted."))
        
        leads_created = []
        
        for partner in convertible_partners:
            # Create new lead (we already filtered out partners with existing leads)
            vals = self._prepare_lead_values(partner)
            lead = Lead.create(vals)
            leads_created.append(lead)
        
        # Return action to view created leads
        if len(leads_created) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('CRM Lead'),
                'res_model': 'crm.lead',
                'res_id': leads_created[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('CRM Leads'),
                'res_model': 'crm.lead',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', [lead.id for lead in leads_created])],
                'target': 'current',
            }

    def _prepare_lead_values(self, partner):
        """Prepare values for lead creation"""
        vals = {
            'name': f"Lead from {partner.name or partner.email or 'Contact'}",
            'partner_id': partner.id,
            'contact_name': partner.name,
            'email_from': partner.email,
            'phone': partner.phone or partner.mobile,
            'street': partner.street,
            'street2': partner.street2,
            'city': partner.city,
            'state_id': partner.state_id.id if partner.state_id else False,
            'zip': partner.zip,
            'country_id': partner.country_id.id if partner.country_id else False,
            'website': partner.website,
            'team_id': self.team_id.id,
            'stage_id': self.stage_id.id,
            'user_id': self.user_id.id if self.user_id else False,
            'priority': self.priority,
            'source_id': self.source_id.id if self.source_id else False,
            'medium_id': self.medium_id.id if self.medium_id else False,
            'campaign_id': self.campaign_id.id if self.campaign_id else False,
            'type': 'lead',
        }
        
        if self.description:
            vals['description'] = self.description
            
        return vals