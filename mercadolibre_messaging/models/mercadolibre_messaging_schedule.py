# -*- coding: utf-8 -*-

import logging
from datetime import datetime
import pytz
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibreMessagingSchedule(models.Model):
    _name = 'mercadolibre.messaging.schedule'
    _description = 'Horario de Atención para Mensajería ML'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Ej: Horario Laboral, Horario Extendido'
    )
    active = fields.Boolean(default=True)

    account_ids = fields.Many2many(
        'mercadolibre.account',
        'ml_messaging_schedule_account_rel',
        'schedule_id',
        'account_id',
        string='Cuentas ML',
        help='Cuentas a las que aplica este horario. Vacío = Todas'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )

    # Zona horaria
    timezone = fields.Selection(
        '_tz_get',
        string='Zona Horaria',
        default='America/Mexico_City',
        required=True
    )

    @api.model
    def _tz_get(self):
        return [(x, x) for x in pytz.common_timezones]

    # Horarios por día
    monday_active = fields.Boolean(string='Lunes', default=True)
    monday_start = fields.Float(string='Inicio Lunes', default=9.0)
    monday_end = fields.Float(string='Fin Lunes', default=18.0)

    tuesday_active = fields.Boolean(string='Martes', default=True)
    tuesday_start = fields.Float(string='Inicio Martes', default=9.0)
    tuesday_end = fields.Float(string='Fin Martes', default=18.0)

    wednesday_active = fields.Boolean(string='Miércoles', default=True)
    wednesday_start = fields.Float(string='Inicio Miércoles', default=9.0)
    wednesday_end = fields.Float(string='Fin Miércoles', default=18.0)

    thursday_active = fields.Boolean(string='Jueves', default=True)
    thursday_start = fields.Float(string='Inicio Jueves', default=9.0)
    thursday_end = fields.Float(string='Fin Jueves', default=18.0)

    friday_active = fields.Boolean(string='Viernes', default=True)
    friday_start = fields.Float(string='Inicio Viernes', default=9.0)
    friday_end = fields.Float(string='Fin Viernes', default=18.0)

    saturday_active = fields.Boolean(string='Sábado', default=True)
    saturday_start = fields.Float(string='Inicio Sábado', default=9.0)
    saturday_end = fields.Float(string='Fin Sábado', default=14.0)

    sunday_active = fields.Boolean(string='Domingo', default=False)
    sunday_start = fields.Float(string='Inicio Domingo', default=0.0)
    sunday_end = fields.Float(string='Fin Domingo', default=0.0)

    # Mensaje fuera de horario
    out_of_hours_enabled = fields.Boolean(
        string='Enviar Mensaje Fuera de Horario',
        default=True,
        help='Si está activo, envía un mensaje automático cuando se recibe un mensaje fuera de horario'
    )
    out_of_hours_template_id = fields.Many2one(
        'mercadolibre.message.template',
        string='Plantilla Fuera de Horario',
        help='Mensaje a enviar cuando se contacta fuera de horario'
    )

    # Resumen visual
    schedule_summary = fields.Text(
        string='Resumen de Horario',
        compute='_compute_schedule_summary'
    )

    @api.depends(
        'monday_active', 'monday_start', 'monday_end',
        'tuesday_active', 'tuesday_start', 'tuesday_end',
        'wednesday_active', 'wednesday_start', 'wednesday_end',
        'thursday_active', 'thursday_start', 'thursday_end',
        'friday_active', 'friday_start', 'friday_end',
        'saturday_active', 'saturday_start', 'saturday_end',
        'sunday_active', 'sunday_start', 'sunday_end',
    )
    def _compute_schedule_summary(self):
        days = [
            ('monday', 'Lunes'),
            ('tuesday', 'Martes'),
            ('wednesday', 'Miércoles'),
            ('thursday', 'Jueves'),
            ('friday', 'Viernes'),
            ('saturday', 'Sábado'),
            ('sunday', 'Domingo'),
        ]
        for record in self:
            lines = []
            for day_code, day_name in days:
                active = getattr(record, f'{day_code}_active')
                if active:
                    start = getattr(record, f'{day_code}_start')
                    end = getattr(record, f'{day_code}_end')
                    start_str = self._float_to_time_str(start)
                    end_str = self._float_to_time_str(end)
                    lines.append(f'{day_name}: {start_str} - {end_str}')
                else:
                    lines.append(f'{day_name}: Cerrado')
            record.schedule_summary = '\n'.join(lines)

    @staticmethod
    def _float_to_time_str(float_time):
        """Convierte float (ej: 9.5) a string (ej: '09:30')"""
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f'{hours:02d}:{minutes:02d}'

    @staticmethod
    def _time_str_to_float(time_str):
        """Convierte string (ej: '09:30') a float (ej: 9.5)"""
        parts = time_str.split(':')
        return int(parts[0]) + int(parts[1]) / 60

    def is_within_schedule(self, dt=None):
        """
        Verifica si una fecha/hora está dentro del horario de atención.

        Args:
            dt: datetime a verificar. Si es None, usa la hora actual.

        Returns:
            bool: True si está dentro del horario
        """
        self.ensure_one()

        if dt is None:
            dt = datetime.now(pytz.UTC)

        # Convertir a la zona horaria del horario
        tz = pytz.timezone(self.timezone)
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        local_dt = dt.astimezone(tz)

        # Obtener día de la semana (0=Lunes, 6=Domingo)
        weekday = local_dt.weekday()
        day_map = {
            0: 'monday',
            1: 'tuesday',
            2: 'wednesday',
            3: 'thursday',
            4: 'friday',
            5: 'saturday',
            6: 'sunday',
        }
        day_code = day_map[weekday]

        # Verificar si el día está activo
        if not getattr(self, f'{day_code}_active'):
            return False

        # Verificar hora
        current_hour = local_dt.hour + local_dt.minute / 60
        start_hour = getattr(self, f'{day_code}_start')
        end_hour = getattr(self, f'{day_code}_end')

        return start_hour <= current_hour < end_hour

    def get_schedule_status(self, dt=None):
        """
        Obtiene el estado del horario con información detallada.

        Returns:
            dict: {
                'is_open': bool,
                'current_day': str,
                'current_time': str,
                'next_open': str (si está cerrado),
                'closes_at': str (si está abierto),
            }
        """
        self.ensure_one()

        if dt is None:
            dt = datetime.now(pytz.UTC)

        tz = pytz.timezone(self.timezone)
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        local_dt = dt.astimezone(tz)

        weekday = local_dt.weekday()
        day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        day_codes = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        current_day = day_names[weekday]
        current_time = local_dt.strftime('%H:%M')

        is_open = self.is_within_schedule(dt)

        result = {
            'is_open': is_open,
            'current_day': current_day,
            'current_time': current_time,
            'timezone': self.timezone,
        }

        day_code = day_codes[weekday]

        if is_open:
            end_hour = getattr(self, f'{day_code}_end')
            result['closes_at'] = self._float_to_time_str(end_hour)
        else:
            # Buscar próxima apertura
            for i in range(7):
                check_day = (weekday + i) % 7
                check_code = day_codes[check_day]
                if getattr(self, f'{check_code}_active'):
                    start_hour = getattr(self, f'{check_code}_start')
                    if i == 0:
                        # Mismo día
                        current_hour = local_dt.hour + local_dt.minute / 60
                        if current_hour < start_hour:
                            result['next_open'] = f'Hoy a las {self._float_to_time_str(start_hour)}'
                            break
                    else:
                        result['next_open'] = f'{day_names[check_day]} a las {self._float_to_time_str(start_hour)}'
                        break

        return result

    @api.model
    def get_schedule_for_account(self, account):
        """
        Obtiene el horario aplicable para una cuenta.

        Args:
            account: mercadolibre.account record

        Returns:
            mercadolibre.messaging.schedule record o False
        """
        # Buscar horario específico para la cuenta
        schedule = self.search([
            ('active', '=', True),
            ('account_ids', 'in', account.id),
        ], limit=1)

        if schedule:
            return schedule

        # Buscar horario sin cuentas específicas (global)
        schedule = self.search([
            ('active', '=', True),
            ('account_ids', '=', False),
            '|',
            ('company_id', '=', account.company_id.id),
            ('company_id', '=', False),
        ], limit=1)

        return schedule or False
