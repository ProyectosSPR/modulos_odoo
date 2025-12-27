# Kafka Migration Hub - Despliegue en Kubernetes

Este directorio contiene los manifiestos necesarios para desplegar Apache Kafka con Strimzi en Kubernetes para el módulo Migration Hub de Odoo.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                      (namespace: default)                    │
│                                                              │
│  ┌─────────────┐     ┌─────────────────────────────────┐    │
│  │    Odoo     │     │         Kafka Cluster           │    │
│  │   (Pod)     │────▶│  ┌─────────┐  ┌─────────┐      │    │
│  │             │     │  │ Kafka-0 │  │Zookeeper│      │    │
│  └─────────────┘     │  └─────────┘  └─────────┘      │    │
│         │            │        │                        │    │
│         │            │  migration-hub-kafka-bootstrap  │    │
│         │            │        :9092                    │    │
│         │            └─────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ PostgreSQL  │                                            │
│  │   (Pod)     │                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

## Requisitos

- Kubernetes 1.21+
- kubectl configurado con acceso al cluster
- StorageClass disponible (por defecto usa `standard`)
- Recursos mínimos:
  - **Desarrollo**: 2 GB RAM, 2 CPU
  - **Producción**: 6 GB RAM, 4 CPU

## Instalación Rápida

```bash
# 1. Instalar Strimzi Operator
kubectl create -f 'https://strimzi.io/install/latest?namespace=default'

# 2. Esperar a que el operador esté listo
kubectl wait --for=condition=available --timeout=300s deployment/strimzi-cluster-operator

# 3. Crear el cluster de Kafka
kubectl apply -f kafka-cluster.yaml

# 4. Esperar a que Kafka esté listo (2-5 minutos)
kubectl wait kafka/migration-hub --for=condition=Ready --timeout=600s
```

O usar el script automatizado:

```bash
chmod +x install.sh
./install.sh
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `kafka-cluster.yaml` | Cluster Kafka + Zookeeper + Topics predefinidos |
| `install.sh` | Script de instalación automatizada |

## Configuración

### Desarrollo (por defecto)

- 1 réplica de Kafka
- 1 réplica de Zookeeper
- 20 GB de almacenamiento
- Sin TLS

### Producción

Editar `kafka-cluster.yaml` y cambiar:

```yaml
spec:
  kafka:
    replicas: 3  # Alta disponibilidad
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      min.insync.replicas: 2
  zookeeper:
    replicas: 3
```

## Verificación

```bash
# Ver estado del cluster
kubectl get kafka migration-hub

# Ver pods
kubectl get pods -l strimzi.io/cluster=migration-hub

# Ver logs de Kafka
kubectl logs migration-hub-kafka-0

# Listar topics
kubectl exec -it migration-hub-kafka-0 -- bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --list

# Probar producir mensaje
kubectl exec -it migration-hub-kafka-0 -- bin/kafka-console-producer.sh \
    --bootstrap-server localhost:9092 --topic test-migration

# Probar consumir mensaje
kubectl exec -it migration-hub-kafka-0 -- bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic test-migration --from-beginning
```

## Conexión desde Odoo

### Dentro del mismo namespace (default)

El módulo está preconfigurado para conectarse a:

```
migration-hub-kafka-bootstrap:9092
```

No necesitas cambiar nada si Odoo está en el namespace `default`.

### Desde otro namespace

Si Odoo está en otro namespace, usa el FQDN:

```
migration-hub-kafka-bootstrap.default.svc.cluster.local:9092
```

### Configuración manual

1. Ir a **Ajustes > Técnico > Parámetros del Sistema**
2. Buscar `migration_hub.kafka_servers`
3. Cambiar el valor según tu configuración

## Topics Predefinidos

| Topic | Particiones | Descripción |
|-------|-------------|-------------|
| `migration-data` | 6 | Datos de migración |
| `migration-dlq` | 3 | Dead Letter Queue (errores) |
| `migration-events` | 3 | Eventos y logs |

## Troubleshooting

### Kafka no inicia

```bash
# Ver eventos
kubectl describe kafka migration-hub

# Ver logs del operador
kubectl logs deployment/strimzi-cluster-operator
```

### Error de conexión desde Odoo

```bash
# Verificar que el servicio existe
kubectl get svc migration-hub-kafka-bootstrap

# Verificar conectividad desde un pod
kubectl run kafka-test --rm -it --image=busybox -- wget -qO- migration-hub-kafka-bootstrap:9092
```

### Error de almacenamiento

```bash
# Verificar StorageClass disponibles
kubectl get storageclass

# Editar kafka-cluster.yaml y cambiar la clase:
# storage:
#   class: tu-storage-class
```

## Desinstalación

```bash
# Eliminar cluster de Kafka
kubectl delete -f kafka-cluster.yaml

# Eliminar Strimzi Operator
kubectl delete -f 'https://strimzi.io/install/latest?namespace=default'

# Eliminar PVCs (datos)
kubectl delete pvc -l strimzi.io/cluster=migration-hub
```

## Recursos Adicionales

- [Documentación de Strimzi](https://strimzi.io/documentation/)
- [Apache Kafka](https://kafka.apache.org/documentation/)
- [Strimzi GitHub](https://github.com/strimzi/strimzi-kafka-operator)
