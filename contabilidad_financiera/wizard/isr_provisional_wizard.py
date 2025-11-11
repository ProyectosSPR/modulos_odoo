from odoo import api, fields, models, _
import base64
import io
from odoo.tools.misc import xlwt
from xlwt import easyxf


class IsrProvisionalWizard(models.TransientModel):
    _name = "isr.provisional.wizard"
    _description = "ISR Provisional Wizard"

    file_data = fields.Binary('File')

    ano = fields.Selection([
        ('2021', '2021'),
        ('2022', '2022'),
        ('2023', '2023'),
    ], string="Año")

    coeficiente = fields.Float(string="Coeficiente")

    def action_print_isr_provisional_report(self):
        months = [
            ('Enero', 1),
            ('Febrero', 2),
            ('Marzo', 3),
            ('Abril', 4),
            ('Mayo', 5),
            ('Junio', 6),
            ('Julio', 7),
            ('Agosto', 8),
            ('Septiembre', 9),
            ('Octubre', 10),
            ('Noviembre', 11),
            ('Diciembre', 12),
        ]
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Listado de nomina')
        header_style = easyxf(
            'font:height 200; align: horiz center; font:bold True;' "borders: top thin,left thin,right thin,bottom thin")
        worksheet.write(0, 0, 'Concepto', header_style)
        for mon, key in months:
            worksheet.write(0, key, mon, header_style)
        worksheet.write(1, 0, 'Ingreso acumulado')
        worksheet.write(2, 0, 'Coeficiente')
        worksheet.write(3, 0, 'Utilidad fiscal')
        worksheet.write(5, 0, 'Base de pago provisional')
        worksheet.write(6, 0, '30% de ISR')
        worksheet.write(7, 0, 'ISR acumulado')
        worksheet.write(9, 0, 'Pagos provisionales')
        worksheet.write(10, 0, 'Pago provisional del mes')

        a = self.env['account.move'].search([('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]).filtered(
            lambda x: x.date.year == int(self.ano))
        c = self.env['account.move'].search([('state', '=', 'posted'), ('move_type', '=', 'out_refund')]).filtered(
            lambda x: x.date.year == int(self.ano))
        b = {}
        d = {}
        for i in a:
            month = i.date.month
            b[month] = b.get(month, 0) + i.amount_untaxed
        for i in c:
            month = i.date.month
            d[month] = d.get(month, 0) + i.amount_untaxed

        acum_pago_provisional = 0
        for mon, j in months:
            total = sum([val for key, val in b.items() if j >= key])
            total_nc = sum([val for key, val in d.items() if j >= key])
            isr = 0.3
            utilidad_fiscal = (total -total_nc) * self.coeficiente
            isr_acumulado = utilidad_fiscal * isr
            pagos_provisionale = isr_acumulado if j == 1 else acum_pago_provisional
            acum_pago_provisional += (isr_acumulado - pagos_provisionale)
            worksheet.write(1, j, total - total_nc)
            worksheet.write(2, j, self.coeficiente)
            worksheet.write(3, j, utilidad_fiscal)
            worksheet.write(5, j, utilidad_fiscal)
            worksheet.write(6, j, isr)
            worksheet.write(7, j, isr_acumulado)
            worksheet.write(9, j, pagos_provisionale)
            worksheet.write(10, j, isr_acumulado -pagos_provisionale)

        fp = io.BytesIO()
        workbook.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        self.write({'file_data': base64.b64encode(data)})
        action = {
            'name': 'ISR Provisional',
            'type': 'ir.actions.act_url',
            'url': "/web/content/?model=isr.provisional.wizard&id=" + str(
                self.id) + "&field=file_data&download=true&filename=ISR Provisional.xls",
            'target': 'self',
        }
        return action
