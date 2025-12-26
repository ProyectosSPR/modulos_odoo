# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ConnectionTestWizard(models.TransientModel):
    """Wizard para probar conexiones de base de datos"""
    _name = 'migration.connection.test.wizard'
    _description = 'Wizard de Prueba de Conexión'

    connection_id = fields.Many2one(
        'migration.source.connection',
        string='Conexión',
        required=True,
        ondelete='cascade'
    )

    # Resultado de la prueba
    test_result = fields.Selection([
        ('pending', 'Pendiente'),
        ('success', 'Exitosa'),
        ('failed', 'Fallida')
    ], default='pending', string='Resultado')

    test_message = fields.Text(string='Mensaje')
    test_details = fields.Html(string='Detalles')

    # Información del esquema detectado
    table_count = fields.Integer(string='Tablas Encontradas')
    sample_tables = fields.Text(string='Tablas de Ejemplo')
    database_version = fields.Char(string='Versión de Base de Datos')
    database_size = fields.Char(string='Tamaño de Base de Datos')

    def action_test_connection(self):
        """Ejecutar prueba de conexión"""
        self.ensure_one()

        try:
            # Probar conexión
            result = self.connection_id.test_connection()

            if self.connection_id.state == 'connected':
                self.test_result = 'success'
                self.test_message = _('Conexión establecida exitosamente')

                # Obtener información adicional
                self._get_connection_details()
            else:
                self.test_result = 'failed'
                self.test_message = self.connection_id.last_test_message

        except Exception as e:
            self.test_result = 'failed'
            self.test_message = str(e)
            _logger.exception("Error en prueba de conexión")

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_connection_details(self):
        """Obtener detalles de la conexión"""
        conn = self.connection_id
        details_html = "<div class='o_connection_details'>"

        try:
            if conn.db_type == 'postgresql':
                self._get_postgresql_details(details_html)
            elif conn.db_type == 'mysql':
                self._get_mysql_details(details_html)
            elif conn.db_type == 'odoo':
                self._get_odoo_details(details_html)
            elif conn.db_type in ('csv', 'excel', 'json'):
                self._get_file_details(details_html)
            else:
                self._get_generic_details(details_html)

        except Exception as e:
            details_html += f"<p class='text-warning'>No se pudieron obtener detalles: {e}</p>"

        details_html += "</div>"
        self.test_details = details_html

    def _get_postgresql_details(self, details_html):
        """Obtener detalles de PostgreSQL"""
        import psycopg2

        conn = self.connection_id
        connection = psycopg2.connect(
            host=conn.host,
            port=conn.port,
            database=conn.database,
            user=conn.username,
            password=conn.password
        )

        try:
            cursor = connection.cursor()

            # Versión
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            self.database_version = version.split(',')[0] if version else 'Desconocida'

            # Tamaño
            cursor.execute(f"SELECT pg_size_pretty(pg_database_size('{conn.database}'))")
            self.database_size = cursor.fetchone()[0]

            # Contar tablas
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            self.table_count = cursor.fetchone()[0]

            # Tablas de ejemplo
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name LIMIT 10
            """)
            tables = [row[0] for row in cursor.fetchall()]
            self.sample_tables = '\n'.join(tables)

            self.test_details = f"""
            <div class='o_connection_details'>
                <h4>PostgreSQL</h4>
                <table class='table table-sm'>
                    <tr><td><strong>Versión:</strong></td><td>{self.database_version}</td></tr>
                    <tr><td><strong>Tamaño:</strong></td><td>{self.database_size}</td></tr>
                    <tr><td><strong>Tablas:</strong></td><td>{self.table_count}</td></tr>
                </table>
                <h5>Tablas de Ejemplo:</h5>
                <ul>{''.join(f'<li>{t}</li>' for t in tables)}</ul>
            </div>
            """
        finally:
            connection.close()

    def _get_mysql_details(self, details_html):
        """Obtener detalles de MySQL"""
        import pymysql

        conn = self.connection_id
        connection = pymysql.connect(
            host=conn.host,
            port=conn.port,
            database=conn.database,
            user=conn.username,
            password=conn.password
        )

        try:
            cursor = connection.cursor()

            # Versión
            cursor.execute("SELECT VERSION()")
            self.database_version = cursor.fetchone()[0]

            # Tamaño
            cursor.execute(f"""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2)
                FROM information_schema.tables
                WHERE table_schema = '{conn.database}'
            """)
            size = cursor.fetchone()[0]
            self.database_size = f"{size} MB" if size else 'Desconocido'

            # Contar tablas
            cursor.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = '{conn.database}'
            """)
            self.table_count = cursor.fetchone()[0]

            # Tablas de ejemplo
            cursor.execute(f"""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = '{conn.database}'
                ORDER BY table_name LIMIT 10
            """)
            tables = [row[0] for row in cursor.fetchall()]
            self.sample_tables = '\n'.join(tables)

            self.test_details = f"""
            <div class='o_connection_details'>
                <h4>MySQL</h4>
                <table class='table table-sm'>
                    <tr><td><strong>Versión:</strong></td><td>{self.database_version}</td></tr>
                    <tr><td><strong>Tamaño:</strong></td><td>{self.database_size}</td></tr>
                    <tr><td><strong>Tablas:</strong></td><td>{self.table_count}</td></tr>
                </table>
                <h5>Tablas de Ejemplo:</h5>
                <ul>{''.join(f'<li>{t}</li>' for t in tables)}</ul>
            </div>
            """
        finally:
            connection.close()

    def _get_odoo_details(self, details_html):
        """Obtener detalles de Odoo"""
        import xmlrpc.client

        conn = self.connection_id
        url = conn.odoo_url or f"http://{conn.host}:{conn.port}"

        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        version_info = common.version()

        self.database_version = f"Odoo {version_info.get('server_version', 'Desconocida')}"

        # Autenticar y contar modelos
        uid = common.authenticate(conn.database, conn.username, conn.password, {})
        if uid:
            models_proxy = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
            model_count = models_proxy.execute_kw(
                conn.database, uid, conn.password,
                'ir.model', 'search_count', [[]]
            )
            self.table_count = model_count

            # Modelos de ejemplo
            model_ids = models_proxy.execute_kw(
                conn.database, uid, conn.password,
                'ir.model', 'search', [[]], {'limit': 10}
            )
            models_data = models_proxy.execute_kw(
                conn.database, uid, conn.password,
                'ir.model', 'read', [model_ids], {'fields': ['model', 'name']}
            )
            self.sample_tables = '\n'.join([m['model'] for m in models_data])

            self.test_details = f"""
            <div class='o_connection_details'>
                <h4>Odoo</h4>
                <table class='table table-sm'>
                    <tr><td><strong>Versión:</strong></td><td>{self.database_version}</td></tr>
                    <tr><td><strong>Modelos:</strong></td><td>{self.table_count}</td></tr>
                </table>
                <h5>Modelos de Ejemplo:</h5>
                <ul>{''.join(f'<li>{m["model"]} - {m["name"]}</li>' for m in models_data)}</ul>
            </div>
            """

    def _get_file_details(self, details_html):
        """Obtener detalles de archivos"""
        conn = self.connection_id
        file_count = len(conn.file_ids) if conn.file_ids else 0

        self.table_count = file_count
        self.database_version = conn.db_type.upper()

        file_list = []
        for f in conn.file_ids[:10]:
            file_list.append(f.name)

        self.sample_tables = '\n'.join(file_list)

        self.test_details = f"""
        <div class='o_connection_details'>
            <h4>Archivos {conn.db_type.upper()}</h4>
            <table class='table table-sm'>
                <tr><td><strong>Archivos:</strong></td><td>{file_count}</td></tr>
            </table>
            <h5>Archivos Cargados:</h5>
            <ul>{''.join(f'<li>{f}</li>' for f in file_list)}</ul>
        </div>
        """

    def _get_generic_details(self, details_html):
        """Obtener detalles genéricos"""
        self.test_details = """
        <div class='o_connection_details'>
            <p>Conexión establecida. Detalles adicionales no disponibles para este tipo de conexión.</p>
        </div>
        """

    def action_close(self):
        """Cerrar wizard"""
        return {'type': 'ir.actions.act_window_close'}

    def action_proceed_to_project(self):
        """Proceder a crear proyecto con esta conexión"""
        self.ensure_one()

        if self.test_result != 'success':
            raise UserError(_('Debe tener una conexión exitosa para continuar'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'migration.project',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_connection_id': self.connection_id.id,
            }
        }
