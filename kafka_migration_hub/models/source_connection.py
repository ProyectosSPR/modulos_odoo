# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class MigrationSourceConnection(models.Model):
    _name = 'migration.source.connection'
    _description = 'Conexión a Base de Datos Origen'
    _order = 'name'

    name = fields.Char(
        string='Nombre de la Conexión',
        required=True,
    )
    description = fields.Text(string='Descripción')

    # Tipo de base de datos
    db_type = fields.Selection([
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL / MariaDB'),
        ('mssql', 'Microsoft SQL Server'),
        ('oracle', 'Oracle'),
        ('odoo', 'Odoo (otra instancia)'),
        ('csv', 'Archivos CSV'),
        ('excel', 'Archivos Excel'),
        ('json', 'Archivos JSON'),
    ], string='Tipo de Base de Datos', required=True, default='postgresql')

    # Conexión para bases de datos
    host = fields.Char(string='Host / Servidor')
    port = fields.Integer(string='Puerto')
    database = fields.Char(string='Base de Datos')
    username = fields.Char(string='Usuario')
    password = fields.Char(string='Contraseña')

    # Opciones adicionales de conexión
    ssl_enabled = fields.Boolean(string='Usar SSL', default=False)
    connection_string = fields.Char(
        string='Cadena de Conexión',
        help='Cadena de conexión personalizada (sobrescribe los campos individuales)',
    )
    extra_params = fields.Text(
        string='Parámetros Extra',
        help='Parámetros adicionales en formato JSON',
    )

    # Para conexión a otro Odoo
    odoo_url = fields.Char(
        string='URL de Odoo',
        help='URL de la instancia de Odoo (ej: https://mi-odoo.com)',
    )
    odoo_version = fields.Selection([
        ('13.0', 'Odoo 13'),
        ('14.0', 'Odoo 14'),
        ('15.0', 'Odoo 15'),
        ('16.0', 'Odoo 16'),
        ('17.0', 'Odoo 17'),
        ('18.0', 'Odoo 18'),
        ('19.0', 'Odoo 19'),
    ], string='Versión de Odoo')

    # Para archivos
    file_path = fields.Char(
        string='Ruta del Archivo',
        help='Ruta al archivo o directorio de archivos',
    )
    file_ids = fields.Many2many(
        'ir.attachment',
        'migration_connection_attachment_rel',
        'connection_id',
        'attachment_id',
        string='Archivos Subidos',
    )

    # Estado de la conexión
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('testing', 'Probando'),
        ('connected', 'Conectado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')
    last_test_date = fields.Datetime(string='Última Prueba')
    last_test_message = fields.Text(string='Resultado Última Prueba')

    # Propietario
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        default=lambda self: self.env.user.partner_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # Proyectos que usan esta conexión
    project_ids = fields.One2many(
        'migration.project',
        'source_connection_id',
        string='Proyectos',
    )
    project_count = fields.Integer(
        string='Cantidad de Proyectos',
        compute='_compute_project_count',
    )

    @api.depends('project_ids')
    def _compute_project_count(self):
        for record in self:
            record.project_count = len(record.project_ids)

    @api.onchange('db_type')
    def _onchange_db_type(self):
        """Establecer puerto por defecto según el tipo de BD"""
        default_ports = {
            'postgresql': 5432,
            'mysql': 3306,
            'mssql': 1433,
            'oracle': 1521,
            'odoo': 8069,
        }
        if self.db_type in default_ports:
            self.port = default_ports[self.db_type]

    def _get_connection_params(self):
        """Obtener parámetros de conexión como diccionario"""
        self.ensure_one()

        params = {
            'db_type': self.db_type,
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'username': self.username,
            'password': self.password,
            'ssl': self.ssl_enabled,
        }

        if self.connection_string:
            params['connection_string'] = self.connection_string

        if self.extra_params:
            try:
                extra = json.loads(self.extra_params)
                params.update(extra)
            except json.JSONDecodeError:
                pass

        if self.db_type == 'odoo':
            params['url'] = self.odoo_url
            params['version'] = self.odoo_version

        return params

    def test_connection(self):
        """Probar la conexión a la base de datos"""
        self.ensure_one()
        self.state = 'testing'
        self.last_test_date = fields.Datetime.now()

        try:
            if self.db_type == 'postgresql':
                result = self._test_postgresql()
            elif self.db_type == 'mysql':
                result = self._test_mysql()
            elif self.db_type == 'mssql':
                result = self._test_mssql()
            elif self.db_type == 'oracle':
                result = self._test_oracle()
            elif self.db_type == 'odoo':
                result = self._test_odoo()
            elif self.db_type in ('csv', 'excel', 'json'):
                result = self._test_files()
            else:
                result = {'success': False, 'message': 'Tipo de BD no soportado'}

            if result.get('success'):
                self.state = 'connected'
                self.last_test_message = result.get('message', 'Conexión exitosa')
            else:
                self.state = 'error'
                self.last_test_message = result.get('message', 'Error desconocido')

            return result

        except Exception as e:
            self.state = 'error'
            self.last_test_message = str(e)
            _logger.error(f'Error probando conexión: {str(e)}')
            return {'success': False, 'message': str(e)}

    def _test_postgresql(self):
        """Probar conexión PostgreSQL"""
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
            )

            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """)
            table_count = cursor.fetchone()[0]

            conn.close()

            return {
                'success': True,
                'message': f'Conectado a PostgreSQL. Versión: {version}. Tablas: {table_count}',
                'version': version,
                'table_count': table_count,
            }

        except ImportError:
            return {'success': False, 'message': 'Módulo psycopg2 no instalado'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_mysql(self):
        """Probar conexión MySQL"""
        try:
            import pymysql

            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
            )

            cursor = conn.cursor()
            cursor.execute('SELECT VERSION();')
            version = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = '{self.database}'
            """)
            table_count = cursor.fetchone()[0]

            conn.close()

            return {
                'success': True,
                'message': f'Conectado a MySQL. Versión: {version}. Tablas: {table_count}',
                'version': version,
                'table_count': table_count,
            }

        except ImportError:
            return {'success': False, 'message': 'Módulo pymysql no instalado'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_mssql(self):
        """Probar conexión SQL Server"""
        try:
            import pyodbc

            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.host},{self.port};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password}'
            )

            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute('SELECT @@VERSION')
            version = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """)
            table_count = cursor.fetchone()[0]

            conn.close()

            return {
                'success': True,
                'message': f'Conectado a SQL Server. Tablas: {table_count}',
                'version': version,
                'table_count': table_count,
            }

        except ImportError:
            return {'success': False, 'message': 'Módulo pyodbc no instalado'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_oracle(self):
        """Probar conexión Oracle"""
        try:
            import cx_Oracle

            dsn = cx_Oracle.makedsn(self.host, self.port, service_name=self.database)
            conn = cx_Oracle.connect(self.username, self.password, dsn)

            cursor = conn.cursor()
            cursor.execute('SELECT * FROM V$VERSION WHERE ROWNUM = 1')
            version = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM USER_TABLES')
            table_count = cursor.fetchone()[0]

            conn.close()

            return {
                'success': True,
                'message': f'Conectado a Oracle. Versión: {version}. Tablas: {table_count}',
                'version': version,
                'table_count': table_count,
            }

        except ImportError:
            return {'success': False, 'message': 'Módulo cx_Oracle no instalado'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_odoo(self):
        """Probar conexión a otra instancia de Odoo"""
        try:
            import xmlrpc.client

            common = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/common')
            version = common.version()

            uid = common.authenticate(
                self.database,
                self.username,
                self.password,
                {}
            )

            if not uid:
                return {'success': False, 'message': 'Autenticación fallida'}

            models = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/object')
            model_count = models.execute_kw(
                self.database, uid, self.password,
                'ir.model', 'search_count', [[]]
            )

            return {
                'success': True,
                'message': f'Conectado a Odoo {version.get("server_version")}. Modelos: {model_count}',
                'version': version.get('server_version'),
                'table_count': model_count,
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_files(self):
        """Probar acceso a archivos"""
        if self.file_ids:
            return {
                'success': True,
                'message': f'{len(self.file_ids)} archivo(s) cargado(s)',
                'file_count': len(self.file_ids),
            }
        elif self.file_path:
            import os
            if os.path.exists(self.file_path):
                return {
                    'success': True,
                    'message': f'Ruta válida: {self.file_path}',
                }
            else:
                return {'success': False, 'message': 'Ruta no existe'}
        else:
            return {'success': False, 'message': 'No hay archivos configurados'}

    def get_connection(self):
        """Obtener objeto de conexión a la BD"""
        self.ensure_one()

        if self.db_type == 'postgresql':
            import psycopg2
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
            )
        elif self.db_type == 'mysql':
            import pymysql
            return pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
            )
        # ... otros tipos

        raise UserError(_('Tipo de conexión no implementado: %s') % self.db_type)

    def action_view_projects(self):
        """Ver proyectos que usan esta conexión"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Proyectos'),
            'res_model': 'migration.project',
            'view_mode': 'tree,form',
            'domain': [('source_connection_id', '=', self.id)],
            'context': {'default_source_connection_id': self.id},
        }
