/** @odoo-module **/
import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";

class NetworkerCrmKanbanController extends KanbanController {
    static template = "networker_crm.CustomKanbanView";
    setup() {
        super.setup();
        this.actionService = this.env.services.action;
    }
    async openGenerateWizard() {
        await this.actionService.doAction("networker_crm.action_lead_from_contacts_wizard");
    }
}

registry.category("views").add("crm_generate_from_contacts_kanban", {
    ...kanbanView,
    Controller: NetworkerCrmKanbanController,
});
