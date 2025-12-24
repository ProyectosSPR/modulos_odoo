/** @odoo-module **/


import session  from 'web.session';
import SystrayMenu from 'web.SystrayMenu';
import Widget from 'web.Widget';


const { Component } = owl;
import core from 'web.core';
//var QWeb = core.qweb;
var _t = core._t;
// const _lt = core._lt;

/**
 * Menu item appended in the systray part of the navbar, enable or disable dark mode
 */
var lyon_backend_theme_dark_mode_menu = Widget.extend({
    name: 'lyon_backend_theme_dark_mode_menu',
    template:'mail.systray.lyon_backend_theme_dark_mode_menu',
    events: {
        'click .js_cls_lyon_backend_theme_toggle_dark_mode_btn': '_on_click_js_cls_lyon_backend_theme_toggle_dark_mode_btn',
    },
    start: function () {
        this._update_dark_mode_preview();
        return this._super();
    },
    //--------------------------------------------------
    // Private
    //--------------------------------------------------
    /**
     * Make RPC and get current user's dark mode details
     * @private
     */
    _get_or_set_lyon_backend_theme_has_dark_mode: function (toggle_dark_mode) {
        var self = this;
        return self._rpc({
            model: 'res.users',
            method: 'get_or_set_lyon_backend_theme_has_dark_mode',
            args: [toggle_dark_mode],
            kwargs: {context: session.user_context},
        }).then(function (has_dark_mode) {
			self.has_dark_mode = has_dark_mode;
        });
    },

	/*
     * Update(render) dark mode system tray view on page load or refresh.
     * @private
     */
    _update_dark_mode_preview: function () {
        var self = this;
        self._get_or_set_lyon_backend_theme_has_dark_mode(false).then(function (){	
			if (self.has_dark_mode){
				self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn > i').removeClass('fa-spin fa-circle-o-notch fa-moon-o').addClass('fa-sun-o');		
		 		self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn').attr('title',_t("Day Mode"));	
						
			}else{
				self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn > i').removeClass('fa-spin fa-circle-o-notch fa-sun-o').addClass('fa-moon-o');	
				self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn').attr('title',_t("Night Mode"));			
			}
        });
    },


    //------------------------------------------------------------
    // Handlers
    //------------------------------------------------------------

    /**
     * On click dark mode systray icon enable or disable dark mode
     *
     * @private
     * @param {MouseEvent} ev
     */
    _on_click_js_cls_lyon_backend_theme_toggle_dark_mode_btn: function (ev) {
		ev.preventDefault();        
		ev.stopPropagation();		
        var self = this;
        self._get_or_set_lyon_backend_theme_has_dark_mode(true).then(function (){
			if (self.has_dark_mode){
				self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn > i').removeClass('fa-spin fa-circle-o-notch fa-moon-o').addClass('fa-sun-o');		
		 		$(ev.currentTarget).attr('title', _t("Day Mode"));	
						
			}else{
				self.$('.js_cls_lyon_backend_theme_toggle_dark_mode_btn > i').removeClass('fa-spin fa-circle-o-notch fa-sun-o').addClass('fa-moon-o');	
				$(ev.currentTarget).attr('title', _t("Night Mode"));			
			}
			 //self.trigger_up('reload');
			location.reload();
        });		

    },

});

SystrayMenu.Items.push(lyon_backend_theme_dark_mode_menu);

export default lyon_backend_theme_dark_mode_menu;
