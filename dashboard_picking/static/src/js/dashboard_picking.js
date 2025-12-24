/* @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillUnmount } from "@odoo/owl";

const batchSize = 28; // Número de registros por lote
const tiempo_refresh = 120000; // 10000 = 10 segundos
const dominio = [
                    ['picking_type_code', '=', 'outgoing'],
                    ['location_dest_id.id', '=', 5],
                    ['state', '!=', 'cancel'],
                    '|',
                    ['state', 'in', ['waiting', 'confirmed', 'assigned']],
                    ['x_estatus_paqueteria', 'in', ['En camino', 'En sucursal ocurre', 'Devolución', 'Revisión', false]],
                    ['x_almacen_confirmado', '=', true]
                ];

export class StockPickingDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            records: [],
            total: 0,
            currentOffset: 0,
        });

        this.intervalId = null; // Guardar el ID del intervalo

        // Cargar registros y configurar el intervalo
        this.loadRecords();
        this.intervalId = setInterval(() => {
            this.loadNextBatch();
        }, tiempo_refresh);

        // Limpia el intervalo al desmontar el componente
        onWillUnmount(() => {
            if (this.intervalId) {
                clearInterval(this.intervalId);
            }
        });
    }

    async loadRecords() {
        const total = await this.orm.call("stock.picking", "search_count", [dominio]);
        this.state.total = total;
        this.state.currentOffset = 0;
        this.state.records = [];
        await this.loadNextBatch();
    }

    async loadNextBatch() {
        const remaining = this.state.total - this.state.currentOffset;
        const limit = Math.min(batchSize, remaining);

        if (limit > 0) {
            const records = await this.orm.searchRead(
                "stock.picking",
                dominio,
                [
                    "id",
                    "x_fecha_pedido",
                    "x_numero_orden",
                    "x_warehouse_id",
                    "x_estatus_pedido",
                    "x_hora_status",
                    "x_paqueteria",
                    "x_numero_guia",
                    "x_estatus_paqueteria",
                ],
                {
                    offset: this.state.currentOffset,
                    limit: limit,
                    order: 'id desc',
                }
            );
            this.state.records = records;
            this.state.currentOffset += limit;
        } else {
            await this.loadRecords();
        }
    }

    _getStateClass(state) {
        switch (state) {
            case "Entregado":
                return "bg-success";
            case "Empacado":
                return "bg-info";
            case "Confirmado":
                return "bg-warning";
            default:
                return "bg-secondary";
        }
    }
}

StockPickingDashboard.template = "StockPickingDashboard";
registry.category("actions").add("stock_picking_dashboard", StockPickingDashboard);

export default StockPickingDashboard;
