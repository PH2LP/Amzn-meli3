# 🔧 Sistema de Corrección Automática de Fotos Pausadas

Sistema inteligente que detecta publicaciones de MercadoLibre pausadas por problemas de imágenes, procesa las fotos con IA y las re-sube automáticamente.

## 📋 Índice

- [Problema que Resuelve](#problema-que-resuelve)
- [Cómo Funciona](#cómo-funciona)
- [Instalación](#instalación)
- [Uso](#uso)
- [Configuración](#configuración)
- [Logs y Monitoreo](#logs-y-monitoreo)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Problema que Resuelve

### El Problema

MercadoLibre pausa publicaciones cuando detecta problemas en las fotos:

- ✋ Texto superpuesto en la imagen
- ✋ Watermarks o logos
- ✋ Mala calidad de imagen
- ✋ Fondo no blanco
- ✋ Producto cortado

**Antes:** Tenías que ir manualmente a cada publicación y usar el botón "Mejorar con IA" desde el panel web.

**Ahora:** El sistema lo hace automáticamente cada 30 minutos.

---

## ⚙️ Cómo Funciona

### Flujo Automático

```
1. 🔍 DETECCIÓN
   ↓
   Busca items pausados con:
   - status: paused + tags: moderation_penalty
   - tags: poor_quality_thumbnail

2. 📥 DESCARGA
   ↓
   Obtiene la imagen problemática del item

3. 🤖 PROCESAMIENTO IA
   ↓
   Usa rembg (IA) para:
   - Remover fondo
   - Limpiar texto/watermarks
   - Agregar fondo blanco limpio

4. 📤 RE-SUBIDA
   ↓
   Sube la imagen mejorada a ML

5. ✅ REACTIVACIÓN
   ↓
   Actualiza el item y lo reactiva

6. 📱 NOTIFICACIÓN
   ↓
   Envía notificación Telegram (opcional)
```

---

## 🚀 Instalación

### 1. Dependencias ya instaladas

El sistema usa `rembg`, que ya fue instalado automáticamente con:

```bash
./venv/bin/pip install 'rembg[cli]'
```

### 2. Configuración en `.env`

Asegúrate de tener estas variables configuradas:

```bash
# MercadoLibre API
ML_ACCESS_TOKEN=APP_USR-...
ML_USER_ID=2629793984

# Telegram (opcional, para notificaciones)
TELEGRAM_BOT_TOKEN=8273559490:...
TELEGRAM_CHAT_ID=5915021583
TELEGRAM_NOTIFICATIONS_ENABLED=true
```

---

## 📖 Uso

### Ejecución Manual (Una Vez)

Para corregir todos los items pausados **ahora**:

```bash
./venv/bin/python3 scripts/tools/fix_paused_pictures.py
```

**Salida esperada:**

```
======================================================================
🚀 INICIANDO CICLO DE CORRECCIÓN DE FOTOS
======================================================================
🔍 Encontrados 3 items pausados con moderation_penalty
🔍 Encontrados 2 items con poor_quality_thumbnail
📋 Total items a procesar: 4

======================================================================
🔧 PROCESANDO ITEM: MLM1234567890
======================================================================
📦 Título: Bicicleta Montaña 29 Pulgadas
📊 Status: paused
🖼️  Fotos: 5
✅ Imagen descargada
🤖 Procesando imagen con IA (rembg)...
✅ Imagen procesada exitosamente
📤 Subiendo imagen mejorada a MercadoLibre...
✅ Imagen subida. Picture ID: 123456-MLM
✅ Imágenes actualizadas en item MLM1234567890
✅ Item MLM1234567890 reactivado exitosamente
✅ ¡CORRECCIÓN EXITOSA!

======================================================================
📊 RESUMEN DE CORRECCIÓN
======================================================================
✅ Exitosos: 3
❌ Fallidos: 1
📋 Total: 4
```

---

### Ejecución Automática (Loop Continuo)

Para que se ejecute **automáticamente cada 30 minutos**:

```bash
./scripts/tools/fix_paused_pictures_loop.sh
```

**Esto mantendrá el proceso corriendo indefinidamente.**

Para detener: `Ctrl+C`

---

### Ejecución en Background

Para dejarlo corriendo en segundo plano:

```bash
nohup ./scripts/tools/fix_paused_pictures_loop.sh > logs/fix_paused_loop_bg.log 2>&1 &
```

Ver el proceso:

```bash
ps aux | grep fix_paused
```

Detener el proceso:

```bash
pkill -f fix_paused_pictures_loop
```

---

### Agregar a Crontab (Recomendado)

Para que se ejecute automáticamente al reiniciar el sistema:

```bash
# Editar crontab
crontab -e

# Agregar esta línea (ejecuta cada hora)
0 * * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/fix_paused_pictures.py >> logs/fix_paused_cron.log 2>&1
```

O cada 30 minutos:

```bash
*/30 * * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/fix_paused_pictures.py >> logs/fix_paused_cron.log 2>&1
```

---

## 🎛️ Configuración

### Personalización del Script

Edita `scripts/tools/fix_paused_pictures.py`:

#### Cambiar comportamiento de imágenes

```python
# Línea 275: Mantener o no las imágenes antiguas
if not update_item_pictures(item_id, new_picture_id, keep_old_pictures=True):
    # keep_old_pictures=True  → Mantiene fotos antiguas, solo reemplaza la primera
    # keep_old_pictures=False → Solo deja la nueva foto procesada
```

#### Ajustar calidad de imagen

```python
# Línea 201: Calidad de JPEG al subir
image.save(img_byte_arr, format='JPEG', quality=95)
# Valores: 1-100 (95 es alta calidad)
```

#### Intervalo del loop

Edita `scripts/tools/fix_paused_pictures_loop.sh`:

```bash
# Línea 30: Cambiar intervalo
sleep 1800  # 1800 segundos = 30 minutos

# Opciones:
# 900  = 15 minutos
# 1800 = 30 minutos
# 3600 = 1 hora
```

---

## 📊 Logs y Monitoreo

### Archivo de Log Principal

```bash
logs/fix_paused_pictures.log
```

Ver en tiempo real:

```bash
tail -f logs/fix_paused_pictures.log
```

### Log del Loop

```bash
logs/fix_paused_pictures_loop.log
```

### Imágenes Temporales

Las imágenes descargadas se guardan temporalmente en:

```
storage/temp_images/
```

**Se pueden eliminar manualmente:**

```bash
rm -rf storage/temp_images/*
```

---

## 🔔 Notificaciones Telegram

Si tienes Telegram configurado, recibirás notificaciones:

### Notificación por Item Corregido

```
✅ Foto Corregida Automáticamente

🆔 Item: MLM1234567890
📦 Bicicleta Montaña 29 Pulgadas
🖼️ Foto procesada con IA y re-subida
✅ Reactivado

🕐 2025-11-08 14:30:00
```

### Notificación Resumen

```
📊 Resumen de Corrección de Fotos

✅ Corregidos: 3
❌ Fallidos: 1
📋 Total procesados: 4

🕐 2025-11-08 14:35:00
```

---

## 🔧 Troubleshooting

### Error: "ML_ACCESS_TOKEN no configurado"

**Solución:**

```bash
# Verificar que existe en .env
cat .env | grep ML_ACCESS_TOKEN

# Si no existe, agregarlo
echo "ML_ACCESS_TOKEN=APP_USR-..." >> .env
```

---

### Error: "rembg not found"

**Solución:**

```bash
# Reinstalar rembg
./venv/bin/pip install 'rembg[cli]'
```

---

### Error: "No se pudo descargar la imagen"

**Causas posibles:**

1. URL de imagen inválida
2. Imagen eliminada de ML
3. Timeout de red

**Solución:**

- El script saltará automáticamente al siguiente item
- Revisar logs para ver detalles

---

### Items no se reactivan automáticamente

**Causas:**

- MercadoLibre requiere revisión manual adicional
- El problema no era solo la foto

**Solución:**

```bash
# Revisar manualmente en MercadoLibre Seller Center
# O intentar reactivar vía API:

curl -X PUT "https://api.mercadolibre.com/items/MLM1234567890" \
  -H "Authorization: Bearer $ML_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

---

### "Imagen procesada pero ML la rechaza"

**Causas:**

- rembg no pudo limpiar completamente el problema
- ML requiere foto completamente nueva

**Solución:**

- Tomar foto nueva del producto manualmente
- Usar herramienta de edición más avanzada (Photoshop, etc.)

---

## 📈 Estadísticas y Rendimiento

### Tiempos Promedio

- Descarga de imagen: **~1-3 segundos**
- Procesamiento IA (rembg): **~3-5 segundos**
- Subida a ML: **~2-4 segundos**
- **Total por item: ~6-12 segundos**

### Límites de API

MercadoLibre no especifica límites estrictos para estos endpoints, pero para ser conservador:

- ✅ **Cada 30 minutos es seguro**
- ✅ **Cada 15 minutos es aceptable**
- ⚠️ **Cada 5 minutos puede ser agresivo**

---

## 🔐 Seguridad

### Permisos Requeridos

El token de ML debe tener estos scopes:

- ✅ `offline_access`
- ✅ `read`
- ✅ `write`

### Datos Sensibles

- ❌ **NO** compartas `logs/` públicamente (contienen item IDs)
- ❌ **NO** subas imágenes temporales a repositorio público
- ✅ Agrega a `.gitignore`:

```gitignore
logs/fix_paused_pictures*.log
storage/temp_images/
```

---

## 📚 API Endpoints Utilizados

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/users/{USER_ID}/items/search` | GET | Buscar items pausados |
| `/items/{ITEM_ID}` | GET | Obtener detalles del item |
| `/quality/picture` | GET | Verificar calidad de imagen |
| `/pictures/items/upload` | POST | Subir nueva imagen |
| `/items/{ITEM_ID}` | PUT | Actualizar item con nueva foto |
| `/items/{ITEM_ID}` | PUT | Reactivar item |

---

## 🆘 Soporte

### Errores Comunes

Revisa `logs/fix_paused_pictures.log` para detalles.

### Reportar Problemas

Si encuentras un bug, incluye:

1. Log completo del error
2. ID del item problemático
3. Detalles del error de ML (si aplica)

---

## 📜 Changelog

### v1.0.0 (2025-11-08)

- ✨ Release inicial
- ✅ Detección automática de items pausados
- ✅ Procesamiento con rembg (IA)
- ✅ Re-subida y reactivación automática
- ✅ Notificaciones Telegram
- ✅ Loop automático cada 30 minutos

---

## 🎯 Próximas Mejoras (Futuro)

- [ ] Múltiples estrategias de procesamiento (rembg + otras IA)
- [ ] Dashboard web para ver estadísticas
- [ ] Integración con API de Claid.ai como backup
- [ ] Pre-procesamiento preventivo antes de publicar
- [ ] Machine Learning para detectar qué fotos fallarán antes de publicar

---

**¡Sistema listo para usar! 🚀**
