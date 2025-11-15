# 🔄 Sistema de Renovación Automática de Tokens

Sistema completo de renovación automática para tokens de Amazon SP-API y MercadoLibre.

## 📋 Índice

- [Amazon SP-API: Caché Inteligente](#amazon-sp-api-caché-inteligente)
- [MercadoLibre: Loop Automático](#mercadolibre-loop-automático)
- [Instalación](#instalación)
- [Uso](#uso)
- [Troubleshooting](#troubleshooting)

---

## 🟠 Amazon SP-API: Caché Inteligente

### Cómo Funciona

El sistema de Amazon usa **caché inteligente on-demand**:

1. Cuando cualquier script llama a `get_amazon_access_token()`:
   - Verifica si hay un token válido en `cache/amazon_token.json`
   - Si el token tiene menos de 55 minutos → lo reutiliza
   - Si no existe o expiró → genera uno nuevo automáticamente

2. El token se guarda con timestamp para saber cuándo expira

3. **Completamente automático**: no requiere procesos en background

### Ventajas

✅ **Cero overhead**: Solo genera tokens cuando realmente los necesitas
✅ **Sin procesos extras**: No hay nada corriendo en background
✅ **Eficiente**: Reutiliza tokens válidos, evita llamadas innecesarias a Amazon
✅ **Transparente**: Los scripts existentes funcionan sin cambios

### Archivo Modificado

- `src/integrations/amazon_api.py` - función `get_amazon_access_token()` actualizada

### Cache

- Ubicación: `cache/amazon_token.json`
- Estructura:
  ```json
  {
    "access_token": "Atza|...",
    "timestamp": 1699123456.789
  }
  ```

### Duración del Token

- **Token de Amazon**: Válido por 1 hora (3600 segundos)
- **Caché local**: Renovación a los 55 minutos para seguridad

---

## 🔵 MercadoLibre: Loop Automático

### Cómo Funciona

El sistema de MercadoLibre usa **renovación constante en background**:

1. Un proceso en background renueva el token cada 5.5 horas
2. Actualiza automáticamente el archivo `.env` con el nuevo token
3. Se ejecuta como servicio del sistema (LaunchAgent en macOS)
4. Se reinicia automáticamente si falla
5. Logs completos de cada renovación

### ¿Por Qué Constante?

MercadoLibre requiere el token activo 24/7 porque:
- Recibes notificaciones de ventas en cualquier momento
- Las preguntas de clientes llegan 24/7
- Los webhooks pueden llamarte en cualquier momento

### Archivos Creados

```
scripts/auth/
├── ml_token_loop.py                      # Script principal del loop
├── ml_token_loop.sh                       # Wrapper bash
├── com.revancha.ml_token_refresh.plist    # Configuración macOS LaunchAgent
└── install_ml_token_service.sh            # Instalador automático
```

### Duración del Token

- **Token de MercadoLibre**: Válido por 6 horas
- **Renovación automática**: Cada 5.5 horas para seguridad

---

## 🚀 Instalación

### 1. Sistema de Amazon (Automático)

No requiere instalación. El caché inteligente ya está integrado en `amazon_api.py`.

### 2. Sistema de MercadoLibre

#### Instalación Automática (macOS)

```bash
# Ejecutar el instalador
./scripts/auth/install_ml_token_service.sh
```

Esto:
- ✅ Instala el servicio como LaunchAgent
- ✅ Configura inicio automático al arrancar el sistema
- ✅ Activa el servicio inmediatamente
- ✅ Configura logs automáticos

#### Instalación Manual

Si prefieres ejecutarlo manualmente (sin LaunchAgent):

```bash
# En una terminal, ejecutar:
./scripts/auth/ml_token_loop.sh

# O en background:
nohup ./scripts/auth/ml_token_loop.sh > /dev/null 2>&1 &
```

---

## 🎯 Uso

### Amazon SP-API

**No requiere acción manual**. Simplemente usa tus scripts normalmente:

```python
from src.integrations.amazon_api import get_product_data_from_asin

# Esto automáticamente:
# 1. Verifica si hay token cacheado válido
# 2. Lo reutiliza si es válido
# 3. Genera uno nuevo si expiró
data = get_product_data_from_asin("B0CYM126TT")
```

### MercadoLibre

#### Verificar que el Servicio Está Corriendo

```bash
# Ver status del servicio
launchctl list | grep ml_token

# Ver logs en tiempo real
tail -f logs/ml_token_refresh.log
```

#### Comandos Útiles

```bash
# Detener el servicio
launchctl unload ~/Library/LaunchAgents/com.revancha.ml_token_refresh.plist

# Iniciar el servicio
launchctl load ~/Library/LaunchAgents/com.revancha.ml_token_refresh.plist

# Ver logs
tail -f logs/ml_token_refresh.log

# Ver últimas 50 líneas
tail -50 logs/ml_token_refresh.log
```

---

## 📊 Logs

### Amazon

No genera logs separados. Los mensajes aparecen en los logs de los scripts que usan la API:

```
🔐 Generando nuevo access token de Amazon...
✅ Token generado y cacheado (válido por 55 min)
```

o

```
♻️ Usando token cacheado de Amazon (válido por 42 min más)
```

### MercadoLibre

Tres archivos de log:

```bash
# Log principal con timestamps
logs/ml_token_refresh.log

# Output estándar del servicio
logs/ml_token_refresh_stdout.log

# Errores del servicio
logs/ml_token_refresh_stderr.log
```

Ejemplo del log principal:

```
[2025-11-08 10:30:00] 🔄 Renovando access token de MercadoLibre...
[2025-11-08 10:30:01] ✅ Token renovado exitosamente
[2025-11-08 10:30:01]    Access token: APP_USR-1758699366225963-110813-b0f758a3...
[2025-11-08 10:30:01]    Próxima renovación en 5.5 horas
[2025-11-08 10:30:01] ⏳ Esperando 5.5 horas hasta próxima renovación... (iteración #1)
```

---

## 🔧 Troubleshooting

### Amazon

#### "Error obteniendo access token"

**Causa**: Credenciales incorrectas en `.env`

**Solución**:
```bash
# Verificar que existan estas variables en .env:
grep -E "LWA_CLIENT_ID|LWA_CLIENT_SECRET|REFRESH_TOKEN" .env
```

#### "El token sigue expirando"

**Causa**: El caché no se está guardando correctamente

**Solución**:
```bash
# Verificar que existe el directorio cache/
ls -la cache/

# Ver el contenido del token cacheado
cat cache/amazon_token.json
```

### MercadoLibre

#### El servicio no está corriendo

**Verificar**:
```bash
launchctl list | grep ml_token
```

**Si no aparece, reinstalar**:
```bash
./scripts/auth/install_ml_token_service.sh
```

#### "Error: Faltan credenciales ML en .env"

**Solución**:
```bash
# Verificar que existan:
grep -E "ML_CLIENT_ID|ML_CLIENT_SECRET|ML_REFRESH_TOKEN" .env
```

#### El token no se actualiza en .env

**Verificar permisos**:
```bash
ls -la .env
# Debe ser writable (rw-r--r--)
```

#### Ver errores detallados

```bash
# Ver errores del servicio
tail -f logs/ml_token_refresh_stderr.log

# Ver output completo
tail -f logs/ml_token_refresh_stdout.log
```

---

## 🎉 Resumen

### Amazon SP-API
- ✅ **Automático**: Se activa cuando usas la API
- ✅ **Eficiente**: Caché de 55 minutos
- ✅ **Sin overhead**: Cero procesos en background

### MercadoLibre
- ✅ **Siempre activo**: Renueva cada 5.5 horas
- ✅ **Confiable**: Se reinicia automáticamente si falla
- ✅ **Transparente**: Actualiza .env automáticamente
- ✅ **Persistente**: Se ejecuta al iniciar el sistema

**Resultado**: Nunca más tendrás que renovar tokens manualmente. Todo es automático.
