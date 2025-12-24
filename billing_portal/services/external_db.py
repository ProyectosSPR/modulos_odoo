# -*- coding: utf-8 -*-

from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    _logger.warning("psycopg2 no está instalado")


class ExternalDBService(models.AbstractModel):
    _name = 'billing.external.db'
    _description = 'Servicio de Base de Datos Externa'

    def _get_connection(self):
        """Obtiene conexión a la BD externa (mercadoLibre)"""
        if not HAS_PSYCOPG2:
            raise Exception(_('psycopg2 no está instalado'))

        params = self.env['ir.config_parameter'].sudo()

        host = params.get_param('billing_portal.external_db_host')
        port = params.get_param('billing_portal.external_db_port', '5432')
        database = params.get_param('billing_portal.external_db_name')
        user = params.get_param('billing_portal.external_db_user')
        password = params.get_param('billing_portal.external_db_password')

        if not all([host, database, user, password]):
            raise Exception(_('Configuración de BD externa incompleta'))

        return psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

    def validate_receiver_id(self, receiver_id):
        """
        Valida que el receiver_id existe en la BD externa.
        Busca en la tabla shipment.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT DISTINCT receiver_id, status
                FROM shipment
                WHERE receiver_id = %s
                LIMIT 1
            """, (receiver_id,))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result is not None
        except Exception as e:
            _logger.error(f"Error validando receiver_id: {e}")
            return False

    def get_user_orders(self, receiver_id, limit=50):
        """
        Obtiene las órdenes de un usuario desde la BD externa.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    s.order_id,
                    s.receiver_id,
                    s.status as shipment_status,
                    p.status as payment_status,
                    p.transaction_amount,
                    p.money_release_status
                FROM shipment s
                LEFT JOIN pagos_mercadopago p ON s.order_id = p.order_id
                WHERE s.receiver_id = %s
                ORDER BY s.id DESC
                LIMIT %s
            """, (receiver_id, limit))

            results = cursor.fetchall()
            cursor.close()
            conn.close()

            return [dict(row) for row in results]
        except Exception as e:
            _logger.error(f"Error obteniendo órdenes: {e}")
            return []

    def get_order_status(self, order_id):
        """
        Obtiene el estado de una orden específica.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    s.order_id,
                    s.receiver_id,
                    s.status as shipment_status,
                    p.status as payment_status,
                    p.money_release_status,
                    p.transaction_amount
                FROM shipment s
                LEFT JOIN pagos_mercadopago p ON s.order_id = p.order_id
                WHERE s.order_id = %s
                LIMIT 1
            """, (order_id,))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None
        except Exception as e:
            _logger.error(f"Error obteniendo estado de orden: {e}")
            return None

    def update_billing_status(self, order_id, estado, mensaje, progreso, detalles=None):
        """
        Actualiza el estado en la tabla solicitudes_status.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Verificar si existe el registro
            cursor.execute("""
                SELECT id FROM solicitudes_status WHERE order_id = %s
            """, (order_id,))

            existing = cursor.fetchone()

            if existing:
                # Actualizar
                if detalles:
                    cursor.execute("""
                        UPDATE solicitudes_status
                        SET estado = %s,
                            mensaje = %s,
                            progreso = %s,
                            detalles = detalles || %s::jsonb,
                            updated_at = NOW()
                        WHERE order_id = %s
                    """, (estado, mensaje, progreso, psycopg2.extras.Json(detalles), order_id))
                else:
                    cursor.execute("""
                        UPDATE solicitudes_status
                        SET estado = %s,
                            mensaje = %s,
                            progreso = %s,
                            updated_at = NOW()
                        WHERE order_id = %s
                    """, (estado, mensaje, progreso, order_id))
            else:
                # Insertar
                cursor.execute("""
                    INSERT INTO solicitudes_status (order_id, estado, mensaje, progreso, detalles)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                """, (order_id, estado, mensaje, progreso,
                      psycopg2.extras.Json(detalles or {})))

            conn.commit()
            cursor.close()
            conn.close()

            return True
        except Exception as e:
            _logger.error(f"Error actualizando estado: {e}")
            return False

    def get_billing_status(self, order_id):
        """
        Obtiene el estado de facturación de una orden.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT *
                FROM solicitudes_status
                WHERE order_id = %s
            """, (order_id,))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None
        except Exception as e:
            _logger.error(f"Error obteniendo estado de facturación: {e}")
            return None

    def get_user_from_portal(self, identifier):
        """
        Busca un usuario en usuarios_portal por receiver_id o email.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT *
                FROM usuarios_portal
                WHERE receiver_id = %s OR email = %s
                LIMIT 1
            """, (identifier, identifier.lower()))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None
        except Exception as e:
            _logger.error(f"Error buscando usuario: {e}")
            return None

    def create_or_update_portal_user(self, receiver_id, email, data):
        """
        Crea o actualiza un usuario en usuarios_portal.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO usuarios_portal (receiver_id, email, nombre, telefono, rfc, razon_social, domicilio_fiscal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (receiver_id)
                DO UPDATE SET
                    email = EXCLUDED.email,
                    nombre = EXCLUDED.nombre,
                    telefono = COALESCE(EXCLUDED.telefono, usuarios_portal.telefono),
                    rfc = COALESCE(EXCLUDED.rfc, usuarios_portal.rfc),
                    razon_social = COALESCE(EXCLUDED.razon_social, usuarios_portal.razon_social),
                    domicilio_fiscal = COALESCE(EXCLUDED.domicilio_fiscal, usuarios_portal.domicilio_fiscal),
                    ultimo_acceso = NOW(),
                    updated_at = NOW()
            """, (
                receiver_id,
                email.lower(),
                data.get('nombre', ''),
                data.get('telefono', ''),
                data.get('rfc', ''),
                data.get('razon_social', ''),
                psycopg2.extras.Json(data.get('domicilio_fiscal', {}))
            ))

            conn.commit()
            cursor.close()
            conn.close()

            return True
        except Exception as e:
            _logger.error(f"Error creando/actualizando usuario: {e}")
            return False

    def create_portal_session(self, user_id, token, ip_address=None, user_agent=None, duration_hours=24):
        """
        Crea una sesión de portal.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sesiones_portal (usuario_id, session_token, ip_address, user_agent, fecha_expiracion)
                VALUES (%s, %s, %s, %s, NOW() + INTERVAL '%s hours')
                RETURNING id
            """, (user_id, token, ip_address, user_agent, duration_hours))

            session_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()

            return session_id
        except Exception as e:
            _logger.error(f"Error creando sesión: {e}")
            return None

    def validate_portal_session(self, token):
        """
        Valida una sesión de portal.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT s.*, u.*
                FROM sesiones_portal s
                JOIN usuarios_portal u ON s.usuario_id = u.id
                WHERE s.session_token = %s
                  AND s.activa = true
                  AND s.fecha_expiracion > NOW()
            """, (token,))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None
        except Exception as e:
            _logger.error(f"Error validando sesión: {e}")
            return None

    def invalidate_session(self, token):
        """
        Invalida una sesión de portal.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sesiones_portal
                SET activa = false
                WHERE session_token = %s
            """, (token,))

            conn.commit()
            cursor.close()
            conn.close()

            return True
        except Exception as e:
            _logger.error(f"Error invalidando sesión: {e}")
            return False
