# Ejemplos de Uso - Sistema de Comisiones

## Caso de Uso 1: Configuración Básica

### Escenario
Una empresa tiene 3 equipos de ventas de Mercado Libre:
- Mercado Libre Full
- Mercado Libre Agencia
- Mercado Libre Clásico

Todos deben tener el mismo porcentaje de comisión (0.5%).

### Configuración

1. **Crear Equipo Unificado:**
   ```
   Nombre: Mercado Libre
   Equipos:
     - Mercado Libre Full
     - Mercado Libre Agencia
     - Mercado Libre Clásico
   Porcentaje de Comisión: 0.5%
   ```

2. **Crear Reglas de Alcance:**
   ```
   Regla 1: 100% alcance → 100% recompensa
   Regla 2: 95% alcance → 90% recompensa
   Regla 3: 90% alcance → 80% recompensa
   Regla 4: 85% alcance → 70% recompensa
   Regla 5: 80% alcance → 60% recompensa
   ```

3. **Crear Meta para Vendedor:**
   ```
   Periodo: Diciembre 2024
   Vendedor: Juan Pérez
   Meta: $100,000.00
   ```

## Caso de Uso 2: Cálculo de Comisión

### Escenario
El vendedor Juan Pérez vendió $95,000 en el mes de diciembre y todas las ventas fueron pagadas.

### Proceso

1. **Marcar Ventas como Pagadas:**
   - Ir a cada orden de venta de Juan Pérez del mes
   - Hacer clic en "Marcar Comisión Pagada"

2. **Crear Cálculo de Comisión:**
   ```
   Periodo: Diciembre 2024
   Vendedor: Juan Pérez
   Base de Cálculo: Total (con impuestos)
   ```

3. **Resultado Automático:**
   ```
   Total Vendido: $95,000.00
   Meta: $100,000.00
   Alcance de Meta: 95%
   Porcentaje de Recompensa: 90% (según regla)
   Porcentaje de Comisión del Equipo: 0.5%

   Cálculo:
   Comisión = $95,000 × 0.5% × 90%
   Comisión = $95,000 × 0.005 × 0.90
   Comisión = $427.50
   ```

## Caso de Uso 3: Diferentes Equipos con Diferentes Comisiones

### Escenario
La empresa tiene dos canales con diferentes comisiones:
- Canal A (Amazon): 1.0% de comisión
- Canal B (eBay): 0.8% de comisión

### Configuración

1. **Crear Equipos Unificados:**
   ```
   Equipo 1:
     Nombre: Amazon
     Equipos: Amazon México, Amazon USA
     Porcentaje: 1.0%

   Equipo 2:
     Nombre: eBay
     Equipos: eBay México, eBay Internacional
     Porcentaje: 0.8%
   ```

2. **Meta General:**
   ```
   Periodo: Diciembre 2024
   Vendedor: (vacío - aplica a todos)
   Meta: $200,000.00
   ```

## Caso de Uso 4: Vendedor con Meta Individual

### Escenario
María García es una vendedora senior con meta individual más alta que la general.

### Configuración

```
Meta General:
  Periodo: Diciembre 2024
  Vendedor: (vacío)
  Meta: $100,000.00

Meta Individual de María:
  Periodo: Diciembre 2024
  Vendedor: María García
  Meta: $150,000.00
```

**Resultado:** María será evaluada contra $150,000 mientras que otros vendedores contra $100,000.

## Caso de Uso 5: Cálculo sobre Subtotal vs Total

### Escenario
Comparación de cálculo con y sin impuestos.

### Ejemplo

Venta: $10,000 (subtotal) + $1,600 (IVA 16%) = $11,600 (total)

**Opción 1: Base = Subtotal**
```
Comisión = $10,000 × 0.5% × 100% = $50.00
```

**Opción 2: Base = Total**
```
Comisión = $11,600 × 0.5% × 100% = $58.00
```

## Flujo Completo del Proceso

```
1. Configuración (una vez)
   ├── Crear Equipos Unificados
   ├── Crear Reglas de Alcance
   └── Crear Metas Mensuales

2. Durante el Mes
   ├── Realizar Ventas
   ├── Generar Facturas
   ├── Recibir Pagos
   └── Marcar Comisiones como Pagadas

3. Fin de Mes
   ├── Crear Cálculo de Comisión
   ├── Revisar Resultados
   ├── Confirmar Cálculo
   └── Marcar como Pagado

4. Histórico
   └── Consultar Comisiones Pagadas
```

## Reportes y Análisis

### Análisis Pivot
Puedes analizar las comisiones por:
- Vendedor
- Mes
- Equipo Unificado
- Estado

### Gráficos
Visualiza:
- Comisiones por vendedor (gráfico de barras)
- Tendencias mensuales
- Comparación de alcance de metas

## Preguntas Frecuentes

### ¿Qué pasa si un vendedor no alcanza la meta mínima?
El sistema buscará la regla de alcance más cercana hacia abajo. Si alcanza 75% y tu regla más baja es 80%, no obtendrá recompensa a menos que agregues una regla para 75% o menos.

### ¿Puedo cambiar la meta después de crear el cálculo?
Sí, pero deberás hacer clic en "Recalcular" en el registro de cálculo para que se actualice.

### ¿Cómo manejo devoluciones?
Las devoluciones (credit notes) no se incluyen automáticamente. Deberás ajustar manualmente o crear una regla específica para manejar devoluciones.

### ¿Puedo tener múltiples reglas de alcance activas?
Sí, el sistema siempre tomará la regla de alcance más alta que cumpla el vendedor.

### ¿Qué pasa si olvido marcar ventas como pagadas?
Las ventas no marcadas como pagadas no se incluirán en el cálculo de comisiones. Puedes marcarlas posteriormente y hacer clic en "Recalcular".
