import json
import xlsxwriter
from odoo import models, fields, api, _
import time
import calendar
from datetime import datetime, timedelta
from odoo.tools import date_utils, format_amount
import io

def get_last_yearly_dates():
    start_date = f"{datetime.now().year - 1}-01-01"
    end_date = f"{datetime.now().year - 1}-12-31"
    return start_date, end_date

def get_yearly_dates():
    start_date = f"{datetime.now().year}-01-01"
    end_date = f"{datetime.now().year}-12-31"
    return start_date, end_date

def get_this_week_date():
        today = datetime.now()
        start_of_week = today - timedelta(days=(today.weekday() + 1) % 7)
        end_of_week = start_of_week + timedelta(days=6)
        start_date = start_of_week.strftime('%Y-%m-%d')
        end_date = end_of_week.strftime('%Y-%m-%d')
        return start_date, end_date

def get_last_week_date():
        today = datetime.now()
        start_of_this_week = today - timedelta(days=(today.weekday() + 1) % 7)
        start_date = (start_of_this_week - timedelta(weeks=1)).strftime('%Y-%m-%d')
        end_date = (start_of_this_week - timedelta(days=1)).strftime('%Y-%m-%d')
        return start_date, end_date

def get_this_month():
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
        end_date = f"{now.year}-{now.month:02d}-{calendar.monthrange(now.year, now.month)[1]}"
        return start_date, end_date

def get_last_month():
        today = fields.date.today()
        previous_month = date_utils.subtract(today, months=1)
        start_date = date_utils.start_of(previous_month, "month")
        end_date = date_utils.end_of(previous_month, "month")
        return start_date, end_date

def get_last_n_date_range(data):
        today = datetime.today()
        start_date = today - timedelta(days=int(data))
        end_date = today
        return start_date, end_date


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def get_date_query(self, data):
        if data == 'this_year':
            start_date, end_date = get_yearly_dates()
        elif data == 'last_year':
            start_date, end_date = get_last_yearly_dates()
        elif data == 'this_month':
            start_date, end_date = get_this_month()
        elif data == 'last_month':
            start_date, end_date = get_last_month()
        elif data == 'last_week':
            start_date, end_date = get_last_week_date()
        elif data == 'this_week':
            start_date, end_date = get_this_week_date()
        elif data in ('30','60','90','120','180', '365'):
            start_date, end_date = get_last_n_date_range(data)
        else:
            start_date = f"{datetime.now().year}-01-01"
            end_date = f"{datetime.now().year }-12-31"
        return start_date, end_date

    def get_sales_domain(self, data):

        domain_conditions = []
        if data and 'date_from' in data and 'date_to' in data:
            start_date, end_date = data['date_from'], data['date_to']
            domain_conditions.append(
                f"DATE(so.date_order) BETWEEN '{start_date}' AND '{end_date}' AND so.state != 'cancel'")

        elif data and 'last_n_days' in data and data['last_n_days'] != '':
            start_date, end_date = self.get_date_query(data['last_n_days'])
            domain_conditions.append(
                f"DATE(so.date_order) BETWEEN '{start_date}' AND '{end_date}' AND so.state != 'cancel'")

        elif data and 'time_period' in data and data['time_period'] != '':
            start_date, end_date = self.get_date_query(data['time_period'])
            domain_conditions.append(
                f"DATE(so.date_order) BETWEEN '{start_date}' AND '{end_date}' AND so.state != 'cancel'")

        elif data and 'domain' in data:
            for condition in data['domain']:
                field, operator, value = condition
                if operator == '=':
                    domain_conditions.append(f"so.{field} = '{value}'")
                elif operator == '!=':
                    domain_conditions.append(f"so.{field} != '{value}'")
                elif operator == 'ilike':
                    domain_conditions.append(f"so.{field} ILIKE '%{value}%'")
                elif operator == '>':
                    domain_conditions.append(f"so.{field} > '%{value}%'")
                elif operator == '>=':
                    domain_conditions.append(f"so.{field} >= '%{value}%'")
                elif operator == '<':
                    domain_conditions.append(f"so.{field} < '%{value}%'")
                elif operator == '<=':
                    domain_conditions.append(f"so.{field} <= '%{value}%'")
                elif operator == 'between':
                    domain_conditions.append(f"DATE(so.{field}) BETWEEN '%{value[0]}%' AND  '%{value[1]}%'")

        if not domain_conditions:
            domain_conditions.append("so.state != 'cancel'")
        domain = " AND ".join(domain_conditions)
        return domain

    @api.model
    def get_po_sales_report(self, data):
        domain = self.get_sales_domain(data)
        query = f"""
                WITH manufacturing_status_cte AS (
                    SELECT 
                        mp.product_id,
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM mrp_production mp_sub
                                WHERE mp_sub.product_id = mp.product_id AND mp_sub.state IN ('progress', 'confirmed')
                            ) THEN 'In Production'
                            WHEN EXISTS (
                                SELECT 1
                                FROM mrp_production mp_sub
                                WHERE mp_sub.product_id = mp.product_id AND mp_sub.state = 'done'
                            ) THEN 'Manufactured'
                            WHEN EXISTS (
                                SELECT 1
                                FROM mrp_production mp_sub
                                WHERE mp_sub.product_id = mp.product_id
                            ) THEN 'Pending Production'
                            ELSE 'Not Applicable'
                        END AS manufacturing_status
                    FROM 
                        mrp_production mp
                    GROUP BY 
                        mp.product_id
                )
                SELECT 
                    so.name AS order_name,
                    rp.name AS partner_name,
                    so.date_order AS create_date,
                    so.commitment_date AS delivery_date,
                   TRIM(
                         COALESCE(dp.street, '') || ' ' ||
                         COALESCE(dp.street2, '') || ' ' ||
                         COALESCE(dp.city, '') || ' ' ||
                         COALESCE(d_cs.name, '') || ' ' ||
                         COALESCE(d_rc.name, '')
                     ) AS delivery_address,
                    so.state AS status,
                    so.client_order_ref AS order_type,
                    ru_rp.name AS salesperson,
                    so.amount_total AS amount_total,
                    line.id AS order_line_id,
                    pt.default_code AS default_code,
                    pt.name AS product_name,
                    line.product_uom_qty AS quantity,
                    line.price_unit AS unit_price,
                    um.name AS uom,
                    line.product_uom_qty AS ordered_qty,
                    line.qty_delivered AS qty_delivered,
                    (line.qty_delivered * line.price_unit) AS delivered_amt,
                    (line.product_uom_qty - line.qty_delivered) AS balance_qty_to_deliver,
                    line.price_subtotal - (line.qty_delivered * line.price_unit) AS balance_amt_to_deliver,
                    line.qty_invoiced AS qty_invoiced,
                    (line.qty_invoiced * line.price_unit) AS invoiced_amt,
                    (line.product_uom_qty - line.qty_invoiced) AS balance_qty_to_invoice,
                    line.price_subtotal - (line.qty_invoiced * line.price_unit) AS balance_amt_to_invoice,
                    line.price_subtotal AS subtotal,
                    line.price_total AS line_total,
                    cu.full_name AS currency_name,
                    STRING_AGG(DISTINCT sm.reference, ', ') AS picking_names,
                        CASE  so.invoice_status
                        WHEN 'upselling' THEN 'Upselling Opportunity'
                        WHEN 'invoiced' THEN 'Fully Invoiced'
                        WHEN 'to invoice' THEN 'To Invoice'
                        WHEN 'no' THEN 'Nothing to Invoice'
                        ELSE so.invoice_status
                    END AS invoice_status,
                    pt.description_sale AS description_sale,
                    ms_cte.manufacturing_status,
                    STRING_AGG(DISTINCT crm.name, ', ') AS tags,
                    JSON_AGG(
                        DISTINCT (JSON_BUILD_OBJECT( 
                            'name', sp.name,
                            'quantity_demand', sm.product_uom_qty,
                            'done_qty', COALESCE((
                                SELECT SUM(sml.qty_done)
                                FROM stock_move_line sml
                                WHERE sml.move_id = sm.id
                            ), 0),
                            'remaining_qty_to_done', (
                                sm.product_uom_qty - COALESCE((
                                    SELECT SUM(sml.qty_done)
                                    FROM stock_move_line sml
                                    WHERE sml.move_id = sm.id
                                ), 0)
                            ),
                            'state', sp.state,
                            'scheduled_date', sp.scheduled_date,
                            'effective_date', sp.date_done
                        ))::text 
                    )::json AS picking_details
                FROM 
                    sale_order so
                LEFT JOIN 
                    res_partner rp ON rp.id = so.partner_id
                LEFT JOIN 
                    res_partner dp ON dp.id = so.partner_shipping_id
                LEFT JOIN 
                    sale_order_line line ON line.order_id = so.id
                LEFT JOIN 
                    product_product pp ON pp.id = line.product_id
                LEFT JOIN 
                    product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN 
                    uom_uom um ON um.id = line.product_uom
                LEFT JOIN 
                    res_currency cu ON cu.id = so.currency_id
                LEFT JOIN 
                    res_country_state d_cs ON d_cs.id = dp.state_id
                LEFT JOIN
    	            res_country d_rc on d_rc.id = dp.country_id
                LEFT JOIN 
                    res_users ru ON ru.id = so.user_id
                LEFT JOIN 
                    res_partner ru_rp ON ru_rp.id = ru.partner_id
                LEFT JOIN 
                    stock_move sm ON sm.sale_line_id = line.id
                LEFT JOIN 
                    stock_picking sp ON sp.id = sm.picking_id
                LEFT JOIN 
                    manufacturing_status_cte ms_cte ON ms_cte.product_id = line.product_id
                LEFT JOIN 
                    sale_order_tag_rel rel ON rel.order_id = so.id 
                LEFT JOIN 
                    crm_tag crm ON crm.id = rel.tag_id
                WHERE 
                    {domain}
                GROUP BY 
                    so.name, rp.name, line.id, so.date_order, pt.description_sale,delivery_address, so.state,
                     so.client_order_ref, so.commitment_date,
                    ru_rp.name, so.amount_total,
                    pt.default_code, pt.name, line.product_uom_qty, line.price_unit, um.name, cu.full_name, so.invoice_status, ms_cte.manufacturing_status
                ORDER BY 
                    so.name DESC;
            """

        self._cr.execute(query)
        sales_details = self.env.cr.dictfetchall()

        count_query = f"""
                SELECT COUNT(*) FROM sale_order so
                WHERE {domain}
            """
        self._cr.execute(count_query)
        total_count = self._cr.fetchone()[0]

        return {'sales_list': sales_details, 'total_count': total_count}

    def get_sale_po_xlsx_report(self, response, report_data):
        data = json.loads(report_data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        generated_by = "Generated by: {}".format(self.env.user.name)  # User name
        from pytz import timezone
        user_tz = self.env.user.tz or 'UTC'
        local_tz = timezone(user_tz)
        formatted_datetime = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
        generated_on = f"Generated on: {formatted_datetime}"
        bold = workbook.add_format({'bold': True})

        worksheet.write(0, 0, generated_by, bold)
        worksheet.write(1, 0, generated_on, bold)

        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 20)
        worksheet.set_column('G:G', 20)
        worksheet.set_column('H:H', 20)
        worksheet.set_column('I:I', 20)
        worksheet.set_column('J:J', 20)
        worksheet.set_column('K:K', 20)
        worksheet.set_column('L:L', 20)
        worksheet.set_column('M:M', 20)
        worksheet.set_column('N:N', 20)
        worksheet.set_column('O:O', 20)
        worksheet.set_column('P:P', 20)
        worksheet.set_column('Q:Q', 20)
        worksheet.set_column('R:R', 20)
        worksheet.set_column('S:S', 20)
        worksheet.set_column('T:T', 20)
        worksheet.set_column('U:U', 20)
        worksheet.set_column('V:V', 20)
        worksheet.set_column('W:W', 20)
        worksheet.set_column('X:X', 20)
        worksheet.set_column('Y:Y', 20)
        worksheet.set_column('Z:Z', 20)
        worksheet.set_column('AA:AA', 20)
        worksheet.set_column('AB:AB', 20)
        worksheet.set_column('AC:AC', 20)
        worksheet.set_column('AD:AD', 20)
        worksheet.set_column('AE:AE', 20)
        worksheet.set_column('AF:AF', 20)
        worksheet.set_column('AG:AG', 20)
        worksheet.set_column('AH:AH', 20)
        worksheet.set_column('AI:AI', 20)
        worksheet.set_column('AJ:AJ', 20)
        worksheet.set_column('AK:AK', 20)

        headers = ['Order Reference NO.',
                   'Customer Reference NO',
                   'Create Date',
                   'Customer Name',
                   'Delivery Address',
                   'Status',
                   'SalesPerson',
                   'PO Delivery Date',
                   'Tags',
                   'Sale Description',
                   'Item CODE#',
                   'Item Name',
                   'UOM',
                   'Unit Price',
                   'Total Item QTY',
                   'Total Item Amt',
                   'QTY Delivered',
                   'Delivered Amt',
                   'Balance Qty To Deliver',
                   'Balance Amt To Deliver',
                   'Qty Invoiced',
                   'Amt Invoiced',
                   'Balanace Qty To Invoice',
                   'Balance Amt To Invoice',
                   'Currency',
                   'WH/Out No.#',
                   'Production Status',
                   'Invoice Status',
                   'Picking Name',
                   'Qty Demand',
                   'Done Qty',
                   'Qty To Done',
                   'Scheduled Date',
                   'Effective Date',
                   'State',
                   ]
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, bold)

        row = 4
        for order in data:

            worksheet.write(row, 0, order['order_name'])
            worksheet.write(row, 1, order['order_type'])
            worksheet.write(row, 2, order['create_date'])
            worksheet.write(row, 3, order['partner_name'])
            worksheet.write(row, 4, order['delivery_address'])
            worksheet.write(row, 5, order['status'])
            worksheet.write(row, 6, order['salesperson'])
            worksheet.write(row, 7, order['delivery_date'])
            worksheet.write(row, 8, order['tags'])
            worksheet.write(row, 9, order['description_sale'])
            worksheet.write(row, 10, order['default_code'])
            worksheet.write(row, 11, order['product_name'])
            worksheet.write(row, 12, order['uom'])
            worksheet.write(row, 13, order['unit_price'])
            worksheet.write(row, 14, order['ordered_qty'])
            worksheet.write(row, 15, order['subtotal'])
            worksheet.write(row, 16, order['qty_delivered'])
            worksheet.write(row, 17, order['delivered_amt'])
            worksheet.write(row, 18, order['balance_qty_to_deliver'])
            worksheet.write(row, 19, order['balance_amt_to_deliver'])
            worksheet.write(row, 20, order['qty_invoiced'])
            worksheet.write(row, 21, order['invoiced_amt'])
            worksheet.write(row, 22, order['balance_qty_to_invoice'])
            worksheet.write(row, 23, order['balance_amt_to_invoice'])
            worksheet.write(row, 24, order['currency_name'])
            worksheet.write(row, 25, order['picking_names'])
            worksheet.write(row, 26, order['manufacturing_status'])
            worksheet.write(row, 27, order['invoice_status'])
            if 'picking_details' in order and order['picking_details']:
                for picking in order['picking_details']:
                    picking_data = json.loads(picking)
                    worksheet.write(row, 28, picking_data['name'])
                    worksheet.write(row, 29, picking_data['quantity_demand'])
                    worksheet.write(row, 30, picking_data['done_qty'])
                    worksheet.write(row, 31, picking_data['remaining_qty_to_done'])
                    worksheet.write(row, 32, picking_data.get('scheduled_date', ''))
                    worksheet.write(row, 33, picking_data.get('effective_date', ''))
                    worksheet.write(row, 34, picking_data['state'])
                    row += 1
            else:
                row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()



