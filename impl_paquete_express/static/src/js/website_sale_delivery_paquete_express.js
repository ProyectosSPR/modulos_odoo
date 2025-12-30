/** @odoo-module **/

import publicWidget from "web.public.widget";
import "website_sale_delivery.checkout";
import {qweb as QWeb} from "web.core";

import concurrency from "web.concurrency";
import core from "web.core";

var _t = core._t;

const WebsiteSaleDeliveryWidget = publicWidget.registry.websiteSaleDelivery;

// temporary for OnNoResultReturned bug
import {registry} from "@web/core/registry";
import {UncaughtCorsError} from "@web/core/errors/error_service";
const errorHandlerRegistry = registry.category("error_handlers");

function corsIgnoredErrorHandler(env, error) {
    if (error instanceof UncaughtCorsError) {
        return true;
    }
}

var dp = new concurrency.DropPrevious();

WebsiteSaleDeliveryWidget.include({
    events: _.extend({
        "click #btn_confirm_relay": "_onClickBtnConfirmRelay",
    }, WebsiteSaleDeliveryWidget.prototype.events),

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Loads Mondial Relay the first time, else show it.
     *
     * @override
     */
    _handleCarrierUpdateResult: function (result) {
        console.log('!!!!!!!!!!!!!!!!!!!!!! __handleCarrierUpdateResult');
        console.log('##### _handleCarrierUpdateResult result: ', result);
        this._super(...arguments);
        console.log('------ this.pxServiceSelected: ', this.pxServiceSelected);
        if (result.paquete_express && !this.pxServiceSelected) {
            var $payButton = $('button[name="o_payment_submit_button"]');
            $payButton.prop('disabled', true);

            if (!$('#modal_paquete_express').length) {
                this._loadPaqueteExpressModal(result);
            } 

            this.$modal_paquete_express.find('#btn_confirm_relay').toggleClass('disabled', true);
            this.$modal_paquete_express.modal('show');
            this.getServicesPaqueteExpress(result['paquete_express'])
        }

        this.pxServiceSelected = false;
    },
    getServicesPaqueteExpress: async function(paquete_express){
        try {
            // Obtener el elemento div por su id
            const div = document.getElementById('o_zone_widget_px');
            div.innerHTML = `
                <div class="d-flex justify-content-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;

            const self = this;
            console.log('!!!!!!!!!!!!!!!!!!!!!!!!!!!! CONSULTA API !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            // console.log('this.pxServiceSelected: ', this.pxServiceSelected);
            const { partner_zip, partner_state, amount_total, products } = paquete_express
            // const data = await this._rpc({
            //     model: 'stock.picking',
            //     method: 'px_api_quotation',
            //     args: [partner_zip, partner_street, amount_total, products],
            // });
            const data = await this._rpc({
                route: '/website_sale_delivery_paquete_express/api_quotation',
                params: {                    
                    partner_zip,
                    partner_state,
                    amount_total,
                    products
                },
            })

            // console.log(JSON.stringify(data, null, 4))

            
            // Crear un elemento ul
            const ul = document.createElement('ul');

            // Iterar sobre los quotations y agregar elementos li con radio buttons al ul
            data.body.response.data.quotations.forEach((quotation, index) => {
                const li = document.createElement('li');
            
                const label = document.createElement('label');
                label.textContent = `${quotation.serviceName} - ${quotation.serviceInfoDescr} - $ ${quotation.services.dlvyTypeAmt}`;

                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'quotation';
                radio.value = quotation.id;
                radio.id = `px-service-${quotation.id}`;

                // Event listener para cambiar el estilo al seleccionar
                radio.addEventListener('change', () => {
                    document.querySelectorAll('li').forEach(el => el.classList.remove('selected'));
                    li.classList.add('selected');
                    self.$modal_paquete_express.find('#btn_confirm_relay').removeClass('disabled');
                    
                    self.pxServiceSelected = true;
                    self.pxService = quotation;
                });

                label.prepend(radio);
                li.appendChild(label);
                ul.appendChild(li);
            });

            // Agregar el elemento ul al div
            div.innerHTML = "";
            div.appendChild(ul);
        } catch (error) {
            console.log(error);
        }
    },
    /**
     * This method render the modal, and inject it in dom with the Modial Relay Widgets script.
     * Once script loaded, it initialize the widget pre-configured with the information of result
     *
     * @private
     *
     * @param {Object} result: dict returned by call of _update_website_sale_delivery_return (python)
     */
    _loadPaqueteExpressModal: function (result) {
        console.log('!!!!!!!!!!!!!!!!!!!!!! __loadPaqueteExpressModal');
        console.log('_loadPaqueteExpressModal result: ', result);
        // add modal to body and bind 'save' button
        $(QWeb.render('website_sale_delivery_paquete_express', {})).appendTo('body');

        this.$modal_paquete_express = $('#modal_paquete_express');
        this.$modal_paquete_express.find('#btn_confirm_relay').on('click', this._onClickBtnConfirmRelay.bind(this, result.carrier_id));

        // this.getServicesPaqueteExpress(result['paquete_express'])
        // this.$modal_paquete_express.modal('show');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------


    /**
     * Update the shipping address on the order and refresh the UI.
     *
     * @private
     *
     */
    _onClickBtnConfirmRelay: function (carrier_id) {
        console.log('_onClickBtnConfirmRelay": carrier_id: ', carrier_id);
        console.log('!!!!!!!!!!!!!!!!!!!!!! __onClickBtnConfirmRelay');

        const self = this;

        if (!this.pxServiceSelected) {
            return;
        }

        this._rpc({
            route: '/website_sale_delivery_paquete_express/update_shipping',
            params: {
                px_service: self.pxService,
            },
        }).then((o) => {
            $('#address_on_payment').html(o.address);
            this.$modal_paquete_express.modal('hide');

            var $payButton = $('button[name="o_payment_submit_button"]');
            $payButton.prop('disabled', false);

            return self._rpc({
                route: '/shop/update_carrier',
                params: {
                    carrier_id: carrier_id,
                },
            })
        }).then(self._handleCarrierUpdateResult.bind(this));
    },
    /**
     * @private
     * @param {Object} result
     */
    _handleCarrierUpdateResultBadge: function (result) {
        var $carrierBadge = $('#delivery_carrier input[name="delivery_type"][value=' + result.carrier_id + '] ~ .o_wsale_delivery_badge_price');
        
        if (result.status === true) {
             // if free delivery (`free_over` field), show 'Free', not '$0'
            if (result.is_free_delivery) {
                 $carrierBadge.text(_t('Free'));
                 console.log('ENTRO FREE: ', result);
            } else if (result.is_paquete_express) {
                $carrierBadge.text('A estimar');
            }else {
                 $carrierBadge.html(result.new_amount_delivery);
             }
             $carrierBadge.removeClass('o_wsale_delivery_carrier_error');
        } else {
            $carrierBadge.addClass('o_wsale_delivery_carrier_error');
            $carrierBadge.text(result.error_message);
        }
    },
});
