# SISTEMA DE DEDUPLICACIÓN DE NOTIFICACIONES DE TELEGRAM

## Problema Resuelto

Anteriormente, cuando había una venta, se enviaban **múltiples mensajes duplicados** (hasta 3 veces):
1. Mensaje principal con información de la venta
2. Mensaje corto con número de orden
3. Posibles duplicados por múltiples instancias ejecutándose simultáneamente

## Solución Implementada

### 1. File Locking (Bloqueo de Archivos)

Se implementó un sistema de bloqueo usando `fcntl` que garantiza que:
- Solo una instancia del notificador puede ejecutarse a la vez
- Si hay otra instancia corriendo, la nueva se salta automáticamente
- Previene condiciones de carrera (race conditions)

**Archivo de lock**: `storage/telegram_notifier.lock`

### 2. Deduplicación Inteligente por Hash

Cada mensaje tiene un hash único basado en:
- `pack_id`: ID de la orden en MercadoLibre
- `marketplace`: Sitio (MLM, MLU, MLB, etc.)
- `asin`: Producto de Amazon
- `fecha`: Día actual

**Fórmula del hash**:
```
SHA256(pack_id|marketplace|asin|fecha)[:16]
```

Este hash se almacena en `storage/telegram_messages_sent.json` con:
- Timestamp del envío
- Datos de la orden
- Auto-limpieza de mensajes más viejos de 24 horas

### 3. Mensaje Unificado

Ahora se envía **UN SOLO MENSAJE** que incluye toda la información:

```
🎉 ¡NUEVA VENTA!

📦 [Producto]
🏷️ Marca: [Marca]
👤 Comprador: [Usuario]

━━━━━━━━━━━━━━━━━━━━━
💰 FINANCIERO
━━━━━━━━━━━━━━━━━━━━━
📊 Cantidad: X
💵 Total pagado: $XX.XX
💰 Recibís (neto): $XX.XX
✅ Ganancia: $XX.XX

━━━━━━━━━━━━━━━━━━━━━
🛒 COMPRAR EN AMAZON
━━━━━━━━━━━━━━━━━━━━━
[ASIN]
💲 Precio: $XX.XX (+ $4.00 envío)
🔗 [Link directo]

━━━━━━━━━━━━━━━━━━━━━
📋 NÚMERO DE ORDEN
━━━━━━━━━━━━━━━━━━━━━
MLM-XXXXXXXXXX

🔗 Ver orden completa en MercadoLibre
```

**Ventajas**:
- Todo en un solo mensaje
- Fácil de copiar el número de orden (formato `<code>`)
- Links directos a Amazon Business y ML
- Información financiera completa

## Flujo del Sistema

```
┌─────────────────────────────────────┐
│  Nueva ejecución del notificador    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Intentar adquirir lock             │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
    ✅ Lock OK    ❌ Lock OCUPADO
        │             │
        │             └──► Salir (otra instancia corriendo)
        │
        ▼
┌─────────────────────────────────────┐
│  Consultar órdenes de ML            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Para cada orden:                   │
│  1. Generar hash único              │
│  2. ¿Ya se envió este hash?         │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
    ❌ Ya enviado  ✅ Nuevo
        │             │
        │             └──► Formatear y enviar mensaje unificado
        │                  │
        └──► Skip          ▼
                    ┌─────────────────────────┐
                    │  Guardar hash + datos   │
                    │  Registrar en DB        │
                    │  Generar Excel          │
                    └─────────────────────────┘
```

## Archivos Importantes

- **Script principal**: `scripts/tools/telegram_sales_notifier.py`
- **Lock file**: `storage/telegram_notifier.lock`
- **Deduplicación**: `storage/telegram_messages_sent.json`
- **Log de ventas**: `storage/logs/sales_notified.json`

## Estadísticas Mejoradas

El sistema ahora reporta:
- Total órdenes revisadas
- Nuevas ventas detectadas
- Ya notificadas (total)
  - └─ Duplicados bloqueados (desglose)
- Notificaciones enviadas
- Errores

## Ejemplo de Ejecución

```bash
python3 scripts/tools/telegram_sales_notifier.py
```

**Salida**:
```
════════════════════════════════════════════════════════════════
🔔 VERIFICANDO NUEVAS VENTAS
════════════════════════════════════════════════════════════════
📅 2025-12-20 15:30:00
🔒 Lock adquirido - procesando...

🔐 Obteniendo información del seller...
✅ Seller ID: 123456789

📋 Ventas ya notificadas: 5
📦 Consultando órdenes recientes...
✅ Encontradas 10 órdenes

────────────────────────────────────────────────────────────────
🆕 NUEVA VENTA DETECTADA
────────────────────────────────────────────────────────────────
   Pack ID (ML): 2024-12345678
   Order ID: 9876543210
   Marketplace: MLM
   Item ID: MLM123456789
   CBT ID: CBT123456
   Estado: paid
   🔍 Buscando ASIN en BD...
   ✅ ASIN encontrado: B07QGHK6Q8
   🔑 Hash: a1b2c3d4e5f6g7h8
   📤 Enviando notificación unificada a Telegram...
   ✅ Notificación enviada exitosamente
   💾 Hash registrado para evitar duplicados
   💾 Registrando venta en DB y actualizando Excel...
   ✅ Venta registrada, Excel generado y subido a Dropbox

════════════════════════════════════════════════════════════════
📊 RESUMEN
════════════════════════════════════════════════════════════════
Total órdenes revisadas:  10
Nuevas ventas:            1
Ya notificadas:           9
  └─ Duplicados bloqueados: 0
Notificaciones enviadas:  1
Errores:                  0

📄 Log guardado en: storage/logs/sales/check_20251220_153005.json
```

## Mantenimiento

El sistema es **auto-mantenible**:
- Los hashes más viejos de 24 horas se eliminan automáticamente
- No requiere limpieza manual
- Los logs se guardan en `storage/logs/sales/` para auditoría

## Despliegue en Servidor

Si tienes el notificador corriendo en loop en el servidor, el file locking garantiza que:
- Solo una instancia procesará ventas
- Las demás instancias se saltarán automáticamente
- No hay duplicados ni condiciones de carrera

## Beneficios

✅ **Cero mensajes duplicados**
✅ **Un solo mensaje limpio y completo**
✅ **Protección contra ejecuciones concurrentes**
✅ **Deduplicación inteligente por hash**
✅ **Auto-limpieza de datos antiguos**
✅ **Logs detallados para debugging**
✅ **Fácil de copiar información (número de orden, ASIN)**

## Migración

El sistema es **100% compatible con versiones anteriores**:
- Mantiene el archivo `sales_notified.json` existente
- Agrega el nuevo sistema de hashes sin romper nada
- Funciona inmediatamente sin configuración adicional
