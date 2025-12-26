# -*- coding: utf-8 -*-

from odoo import models, api, fields
import logging
import json
import threading

_logger = logging.getLogger(__name__)


class MigrationKafkaService(models.AbstractModel):
    _name = 'migration.kafka.service'
    _description = 'Servicio de Kafka para Migración'

    @api.model
    def get_kafka_config(self):
        """Obtener configuración de Kafka

        Para Kubernetes (Strimzi en namespace default):
        - bootstrap_servers: migration-hub-kafka-bootstrap:9092

        Para Docker Compose local:
        - bootstrap_servers: kafka:9092

        Para desarrollo local:
        - bootstrap_servers: localhost:9092
        """
        ICP = self.env['ir.config_parameter'].sudo()

        # Default para Kubernetes con Strimzi (mismo namespace)
        default_servers = 'migration-hub-kafka-bootstrap:9092'

        return {
            'bootstrap_servers': ICP.get_param('migration_hub.kafka_servers', default_servers),
            'schema_registry_url': ICP.get_param('migration_hub.schema_registry_url', ''),
            'consumer_group': ICP.get_param('migration_hub.consumer_group', 'odoo_migration'),
            'security_protocol': ICP.get_param('migration_hub.kafka_security_protocol', 'PLAINTEXT'),
            'sasl_mechanism': ICP.get_param('migration_hub.kafka_sasl_mechanism', ''),
            'sasl_username': ICP.get_param('migration_hub.kafka_sasl_username', ''),
            'sasl_password': ICP.get_param('migration_hub.kafka_sasl_password', ''),
        }

    @api.model
    def get_producer_config(self):
        """Obtener configuración para el Producer"""
        config = self.get_kafka_config()
        producer_config = {
            'bootstrap.servers': config['bootstrap_servers'],
            'acks': 'all',
            'retries': 3,
            'retry.backoff.ms': 1000,
            'max.in.flight.requests.per.connection': 1,
            'enable.idempotence': True,
        }

        # Agregar autenticación si está configurada
        if config['security_protocol'] != 'PLAINTEXT':
            producer_config['security.protocol'] = config['security_protocol']
            if config['sasl_mechanism']:
                producer_config['sasl.mechanism'] = config['sasl_mechanism']
                producer_config['sasl.username'] = config['sasl_username']
                producer_config['sasl.password'] = config['sasl_password']

        return producer_config

    @api.model
    def get_consumer_config(self, group_suffix=''):
        """Obtener configuración para el Consumer"""
        config = self.get_kafka_config()
        consumer_config = {
            'bootstrap.servers': config['bootstrap_servers'],
            'group.id': f"{config['consumer_group']}{group_suffix}",
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
            'max.poll.interval.ms': 300000,
        }

        # Agregar autenticación si está configurada
        if config['security_protocol'] != 'PLAINTEXT':
            consumer_config['security.protocol'] = config['security_protocol']
            if config['sasl_mechanism']:
                consumer_config['sasl.mechanism'] = config['sasl_mechanism']
                consumer_config['sasl.username'] = config['sasl_username']
                consumer_config['sasl.password'] = config['sasl_password']

        return consumer_config

    @api.model
    def test_connection(self, servers=None):
        """Probar conexión a Kafka con información detallada"""
        result = {
            'success': False,
            'message': '',
            'details': {},
            'steps': [],
        }

        try:
            from confluent_kafka.admin import AdminClient, KafkaException

            config = self.get_kafka_config()
            bootstrap_servers = servers or config['bootstrap_servers']

            result['steps'].append({
                'step': 'Configuración',
                'status': 'ok',
                'detail': f"Servidores: {bootstrap_servers}"
            })

            # Crear cliente admin
            admin_config = {'bootstrap.servers': bootstrap_servers}

            # Agregar autenticación si está configurada
            if config['security_protocol'] != 'PLAINTEXT':
                admin_config['security.protocol'] = config['security_protocol']
                if config['sasl_mechanism']:
                    admin_config['sasl.mechanism'] = config['sasl_mechanism']
                    admin_config['sasl.username'] = config['sasl_username']
                    admin_config['sasl.password'] = config['sasl_password']
                result['steps'].append({
                    'step': 'Autenticación',
                    'status': 'ok',
                    'detail': f"Protocolo: {config['security_protocol']}"
                })

            result['steps'].append({
                'step': 'Conectando',
                'status': 'pending',
                'detail': 'Intentando conexión...'
            })

            admin = AdminClient(admin_config)

            # Listar topics para verificar conexión
            metadata = admin.list_topics(timeout=10)

            result['steps'][-1]['status'] = 'ok'
            result['steps'][-1]['detail'] = 'Conexión establecida'

            # Obtener información del cluster
            brokers = metadata.brokers
            topics = list(metadata.topics.keys())

            # Filtrar topics del sistema
            user_topics = [t for t in topics if not t.startswith('__')]
            migration_topics = [t for t in user_topics if 'migration' in t.lower()]

            result['steps'].append({
                'step': 'Cluster Info',
                'status': 'ok',
                'detail': f"{len(brokers)} broker(s) activo(s)"
            })

            result['steps'].append({
                'step': 'Topics',
                'status': 'ok',
                'detail': f"{len(user_topics)} topics ({len(migration_topics)} de migración)"
            })

            # Detalles
            result['details'] = {
                'brokers': [{'id': b.id, 'host': b.host, 'port': b.port} for b in brokers.values()],
                'total_topics': len(topics),
                'user_topics': len(user_topics),
                'migration_topics': migration_topics,
                'all_topics': user_topics[:20],  # Primeros 20
            }

            result['success'] = True
            result['message'] = f"Kafka conectado: {len(brokers)} broker(s), {len(user_topics)} topics"

            return result

        except ImportError:
            result['steps'].append({
                'step': 'Dependencia',
                'status': 'error',
                'detail': 'Módulo confluent_kafka no instalado'
            })
            result['message'] = 'Error: Módulo confluent_kafka no instalado. Ejecutar: pip install confluent-kafka'
            return result

        except Exception as e:
            error_msg = str(e)
            result['steps'].append({
                'step': 'Error',
                'status': 'error',
                'detail': error_msg[:200]
            })

            # Mensajes de error más claros
            if 'timed out' in error_msg.lower():
                result['message'] = f'Error: Timeout conectando a Kafka. Verificar que el servidor esté corriendo y accesible en: {bootstrap_servers}'
            elif 'refused' in error_msg.lower():
                result['message'] = f'Error: Conexión rechazada. Verificar que Kafka esté corriendo en: {bootstrap_servers}'
            elif 'resolve' in error_msg.lower():
                result['message'] = f'Error: No se puede resolver el hostname. Verificar DNS o usar IP directa: {bootstrap_servers}'
            else:
                result['message'] = f'Error: {error_msg}'

            return result

    @api.model
    def start_migration(self, project):
        """Iniciar proceso de migración con Kafka"""
        _logger.info(f'Iniciando migración Kafka para proyecto {project.id}')

        # Obtener orden de migración
        resolver = self.env['migration.dependency.resolver']
        ordered_mappings = resolver.build_dependency_graph(project)

        if not ordered_mappings:
            _logger.warning('No hay mapeos para migrar')
            return False

        # Crear topics si no existen
        self._create_topics(project, ordered_mappings)

        # Iniciar productor en background
        thread = threading.Thread(
            target=self._run_producer,
            args=(project.id, [m.id for m in ordered_mappings])
        )
        thread.daemon = True
        thread.start()

        # Iniciar consumidor en background
        consumer_thread = threading.Thread(
            target=self._run_consumer,
            args=(project.id,)
        )
        consumer_thread.daemon = True
        consumer_thread.start()

        return True

    def _create_topics(self, project, mappings):
        """Crear topics de Kafka para el proyecto"""
        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            config = self.get_kafka_config()
            admin = AdminClient({
                'bootstrap.servers': config['bootstrap_servers']
            })

            prefix = project.kafka_topic_prefix

            topics_to_create = []
            for mapping in mappings:
                topic_name = f"{prefix}.{mapping.source_table}"
                topics_to_create.append(NewTopic(
                    topic_name,
                    num_partitions=3,
                    replication_factor=1,
                ))

            # Topic para errores (DLQ)
            topics_to_create.append(NewTopic(
                f"{prefix}.dlq",
                num_partitions=1,
                replication_factor=1,
            ))

            # Crear topics
            futures = admin.create_topics(topics_to_create)
            for topic, future in futures.items():
                try:
                    future.result()
                    _logger.info(f'Topic creado: {topic}')
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        _logger.error(f'Error creando topic {topic}: {e}')

        except ImportError:
            _logger.warning('confluent_kafka no disponible, usando migración directa')
        except Exception as e:
            _logger.error(f'Error creando topics: {e}')

    def _run_producer(self, project_id, mapping_ids):
        """Ejecutar productor de Kafka (en thread separado)"""
        try:
            from confluent_kafka import Producer

            # Necesitamos un nuevo cursor para el thread
            with api.Environment.manage():
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)

                    project = env['migration.project'].browse(project_id)
                    config = self.get_kafka_config()

                    producer_config = self.get_producer_config()
                    producer = Producer(producer_config)

                    for mapping_id in mapping_ids:
                        mapping = env['migration.table.mapping'].browse(mapping_id)
                        self._produce_table_data(env, producer, project, mapping)

                    producer.flush()
                    _logger.info(f'Productor finalizado para proyecto {project_id}')

        except Exception as e:
            _logger.error(f'Error en productor Kafka: {e}')

    def _produce_table_data(self, env, producer, project, mapping):
        """Producir datos de una tabla a Kafka"""
        topic = f"{project.kafka_topic_prefix}.{mapping.source_table}"

        # Leer datos del origen
        connection = project.source_connection_id
        if not connection:
            return

        try:
            conn = connection.get_connection()
            cursor = conn.cursor()

            # Query para obtener datos
            schema = mapping.source_schema or 'public'
            table = mapping.source_table

            if connection.db_type == 'postgresql':
                cursor.execute(f'SELECT * FROM "{schema}"."{table}"')
            else:
                cursor.execute(f'SELECT * FROM {table}')

            columns = [desc[0] for desc in cursor.description]
            batch_size = mapping.batch_size or 100
            batch = []

            for row in cursor:
                record = dict(zip(columns, row))

                # Serializar a JSON
                message = json.dumps(record, default=str)

                producer.produce(
                    topic,
                    key=str(record.get('id', '')),
                    value=message.encode('utf-8'),
                    callback=self._delivery_callback,
                )

                batch.append(record)

                if len(batch) >= batch_size:
                    producer.poll(0)
                    batch = []

            conn.close()
            _logger.info(f'Datos producidos para {table}: {mapping.row_count} registros')

        except Exception as e:
            _logger.error(f'Error produciendo datos de {mapping.source_table}: {e}')

    def _delivery_callback(self, err, msg):
        """Callback para confirmación de entrega"""
        if err:
            _logger.error(f'Error entregando mensaje: {err}')

    def _run_consumer(self, project_id):
        """Ejecutar consumidor de Kafka (en thread separado)"""
        try:
            from confluent_kafka import Consumer

            with api.Environment.manage():
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)

                    project = env['migration.project'].browse(project_id)
                    config = self.get_kafka_config()

                    # Suscribirse a todos los topics del proyecto
                    topics = [
                        f"{project.kafka_topic_prefix}.{m.source_table}"
                        for m in project.table_mapping_ids
                        if m.state == 'mapped'
                    ]

                    consumer_config = self.get_consumer_config(f'_{project_id}')
                    consumer = Consumer(consumer_config)

                    consumer.subscribe(topics)
                    _logger.info(f'Consumidor suscrito a: {topics}')

                    transformer = env['migration.data.transformer']

                    while True:
                        # Verificar si el proyecto sigue en ejecución
                        project = env['migration.project'].browse(project_id)
                        if project.state not in ('running',):
                            break

                        msg = consumer.poll(1.0)
                        if msg is None:
                            continue
                        if msg.error():
                            _logger.error(f'Error en mensaje: {msg.error()}')
                            continue

                        # Procesar mensaje
                        try:
                            topic = msg.topic()
                            value = json.loads(msg.value().decode('utf-8'))

                            # Encontrar el mapeo correspondiente
                            table_name = topic.split('.')[-1]
                            mapping = project.table_mapping_ids.filtered(
                                lambda m: m.source_table == table_name
                            )

                            if mapping:
                                result = transformer.transform_and_insert(mapping[0], value)
                                if result.get('success'):
                                    mapping.migrated_records += 1
                                else:
                                    mapping.error_records += 1

                            cr.commit()

                        except Exception as e:
                            _logger.error(f'Error procesando mensaje: {e}')
                            cr.rollback()

                    consumer.close()

        except ImportError:
            _logger.warning('confluent_kafka no disponible')
        except Exception as e:
            _logger.error(f'Error en consumidor Kafka: {e}')

    @api.model
    def pause_migration(self, project):
        """Pausar migración"""
        # El consumidor verificará el estado y se detendrá
        _logger.info(f'Pausando migración del proyecto {project.id}')

    @api.model
    def resume_migration(self, project):
        """Reanudar migración"""
        # Reiniciar consumidor
        thread = threading.Thread(
            target=self._run_consumer,
            args=(project.id,)
        )
        thread.daemon = True
        thread.start()
        _logger.info(f'Reanudando migración del proyecto {project.id}')

    @api.model
    def stop_migration(self, project):
        """Detener migración"""
        # El consumidor verificará el estado y se detendrá
        _logger.info(f'Deteniendo migración del proyecto {project.id}')
