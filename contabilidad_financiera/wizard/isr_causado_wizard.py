from odoo import api, fields, models, _
import base64
import io
from odoo.tools.misc import xlwt
from xlwt import easyxf
from odoo.exceptions import UserError

class IsrProvisionalWizard(models.TransientModel):
    _name = "isr.causado.wizard"
    _description = "ISR Causado Wizard"

    file_data = fields.Binary('File')

    ano = fields.Selection([
        ('2021', '2021'),
        ('2022', '2022'),
    ], string="Año")

    mes = fields.Selection([
        ('01', 'Enero'),
        ('02', 'Febrero'),
        ('03', 'Marzo'),
        ('04', 'Abril'),
        ('05', 'Mayo'),
        ('06', 'Junio'),
        ('07', 'Julio'),
        ('08', 'Agosto'),
        ('09', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre'),
    ], string="Mes")

    def action_print_isr_causado_report(self):
        module = self.env['ir.module.module'].sudo().search([('name','=','nomina_cfdi')])
        if module and module.state == 'installed':

           workbook = xlwt.Workbook()
           worksheet = workbook.add_sheet('ISR Nomina', cell_overwrite_ok=True)
           header_style = easyxf(
               'font:height 200; align: horiz center; font:bold True;' "borders: top thin,left thin,right thin,bottom thin")
           worksheet.write(1, 0, 'ISR Nomina', header_style)

           a = self.env['hr.payslip.line'].search([('code', '=', 'ISR2')]).filtered(
               lambda x: x.date_from.year == int(self.ano) and x.date_from.month == int(self.mes))

           worksheet.write(1, 1, sum(a.mapped('total')))
           # for i in a:
           #     worksheet.write(1, 1, i.total)

           fp = io.BytesIO()
           workbook.save(fp)
           fp.seek(0)
           data = fp.read()
           fp.close()
           self.write({'file_data': base64.b64encode(data)})
           action = {
               'name': 'Isr Causado',
               'type': 'ir.actions.act_url',
               'url': "/web/content/?model=isr.causado.wizard&id=" + str(
                   self.id) + "&field=file_data&download=true&filename=ISR_nomina.xls",
               'target': 'self',
           }
           return action
        else:
          raise UserError(_("No tiene instalado el módulo de nóminas."))
