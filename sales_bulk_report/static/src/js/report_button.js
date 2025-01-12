odoo.define('sales_bulk_report.tree_button', function (require) {
"use strict";
var ListController = require('web.ListController');
var ListView = require('web.ListView');
var viewRegistry = require('web.view_registry');
var po_status_result = false;
var framework = require('web.framework');
var ajax = require('web.ajax');
var core = require('web.core');
var _t = core._t;

var TreeButton = ListController.extend({
   buttons_template: 'button_near_create.buttons',
   events: _.extend({}, ListController.prototype.events, {
       'click .button_clicks': '_OpenDropDown',
       'click #download-po-report': 'download_report',
       'change #po_time_period': 'selection_change',
       'click #close-selection': 'Close',
   }),
   _OpenDropDown: function () {
       var self = this;
       var context = this.model.get(this.handle).getContext();
       document.getElementById('dropdown_view').style.display = 'block';
       document.getElementById('po_time_period').style.display = 'block';
       document.getElementById('button_clicks').style.display = 'none';
       document.getElementById('download-close').style.display = 'block';
       document.querySelector('.o_list_export_xlsx').style.display = 'none';
       document.querySelector('.o_list_button_add').style.display = 'none';
   },

   Close: function(){
       document.getElementById('dropdown_view').style.display = 'none';
       document.getElementById('download-close').style.display = 'none';
       document.getElementById('button_clicks').style.display = 'block';
       document.querySelector('.o_list_export_xlsx').style.display = 'block';
       document.querySelector('.o_list_button_add').style.display = 'block';
       document.getElementById('custom_date_selection').style.display = 'none';
       document.getElementById('custom_date_to_selection').style.display = 'none';
       $("#po_time_period").val('last_month');
   },

   selection_change : function(ev){
        var selected = $(ev.currentTarget).val().trim();
        if (selected === 'custom_date') {
            document.getElementById('po_time_period').style.display = 'none';
            document.getElementById('custom_date_selection').style.display = 'block';
            document.getElementById('custom_date_to_selection').style.display = 'block';
        } else {
            document.getElementById('dropdown_view').style.display = 'block';
            document.getElementById('po_time_period').style.display = 'block';
            document.getElementById('custom_date_selection').style.display = 'none';
            document.getElementById('custom_date_to_selection').style.display = 'none';
        }
   },

   download_report: function(){
        var filter = $("#po_time_period").val().trim();
        if(filter === 'custom_date') {
            var date_from = $("#date_from").val().trim();
            var date_to = $("#date_to").val().trim();
            var data = { 'date_from':date_from, 'date_to': date_to }
        } else {
            var data = {'time_period': filter}
        }
        this.GetPoStatusReport(data)
   },

   GetPoStatusReport: function(data) {
            var self = this;
            self._rpc({
                model: 'sale.order',
                method: 'get_po_sales_report',
                args: [data]
            }).then(function(result) {
                if (result.sales_list && result.sales_list.length === 0) {
                    self.displayNotification({ type: 'warning', title: _t('Warning'),
                        message: "There is No Records from Selected Date Ranges", sticky: false
                    });
                } else {
                    po_status_result = result.sales_list;
                    console.log('statusss', po_status_result)
                    self._generate_xlsx_data(po_status_result)
                }
            });
    },

     _generate_xlsx_data: function(data){
		    var self = this;
		    var action = {
                  'data': {
                            'model': 'sale.order',
                            'output_format': 'xlsx',
                            'report_data': JSON.stringify(data),
                            'report_name': 'Sales PO Report',
                        },
                  };
            self.downloadXlsx(action);
		},

		downloadXlsx: function (action){
            framework.blockUI();
                session.get_file({
                    url: '/sale_po_xlsx_reports',
                    data: action.data,
                    complete: framework.unblockUI,
                    error: (error) => this.call('crash_manager', 'rpc_error', error),
                });
        },

});
var SaleOrderListView = ListView.extend({
   config: _.extend({}, ListView.prototype.config, {
       Controller: TreeButton,
   }),
});

var session = require('web.session');
session.user_has_group('sales_bulk_report.group_download_reports').then(function (hasGroup) {
    if (hasGroup) {
        console.log("User has access to download reports.");
        viewRegistry.add('button_in_tree', SaleOrderListView);
    } else {
        console.log("User does not have access to download reports.");
    }
});

});
