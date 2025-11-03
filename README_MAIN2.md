# main2.py - Pipeline Profesional v2.0

Sistema de pipeline mejorado para Amazon → MercadoLibre CBT con validación IA, retry inteligente y tracking completo.

## 🚀 Características Principales

### ✅ Mejoras sobre main.py original

1. **Pre-flight Health Checks**
   - Verificación automática de credenciales
   - Validación de conectividad API (ML + OpenAI + Amazon)
   - Creación automática de directorios

2. **Base de Datos SQLite para Tracking**
   - Estado de cada ASIN en tiempo real
   - Historial completo de intentos
   - Logs detallados por fase
   - Estadísticas y reportes

3. **Validación IA Pre-Publicación**
   - Validación de imágenes con GPT-4o Vision
   - Validación de categorías
   - Prevención de rechazos de MercadoLibre
   - Detección de problemas antes de publicar

4. **Retry Inteligente**
   - Estrategias diferentes por tipo de error
   - Exponential backoff
   - Detección de GTIN duplicado → Reintento sin GTIN
   - Detección de categoría incorrecta → Regeneración
   - Rate limiting automático

5. **Sistema de Logging Avanzado**
   - Logs por fase (download, transform, validate, publish)
   - Logs en base de datos + consola
   - Reportes detallados en JSON

6. **Modos de Operación**
   - `--dry-run`: Pruebas sin publicar realmente
   - `--skip-validation`: Omitir validación IA (testing rápido)
   - `--force-regenerate`: Regenerar archivos existentes
   - `--asin ASIN`: Procesar solo un producto específico

## 📋 Uso

### Uso Básico

```bash
# Procesar todos los ASINs del archivo resources/asins.txt
python3 main2.py

# Modo dry-run (pruebas sin publicar)
python3 main2.py --dry-run

# Procesar un solo ASIN
python3 main2.py --asin B0CYM126TT

# Omitir validación IA (más rápido, para testing)
python3 main2.py --skip-validation

# Forzar regeneración de archivos ya procesados
python3 main2.py --force-regenerate
```

### Combinación de Flags

```bash
# Dry-run + un solo ASIN (ideal para pruebas)
python3 main2.py --dry-run --asin B0CYM126TT

# Regenerar todo sin validación (rápido)
python3 main2.py --force-regenerate --skip-validation

# Saltar health checks (solo si estás seguro)
python3 main2.py --skip-health-check
```

## 🏗️ Arquitectura

### Fases del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    PRE-FLIGHT CHECKS                        │
│  • Verificar credenciales (ML, Amazon, OpenAI)             │
│  • Verificar conectividad API                              │
│  • Crear directorios necesarios                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   DOWNLOAD PHASE                            │
│  • Descargar desde Amazon SP-API                           │
│  • Retry con exponential backoff (3 intentos)              │
│  • Guardar en storage/asins_json/                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  TRANSFORM PHASE                            │
│  • Transformar con build_mini_ml()                         │
│  • Categorización inteligente IA                           │
│  • Mapeo de atributos                                       │
│  • Guardar en storage/logs/publish_ready/                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                 VALIDATION PHASE                            │
│  • Validar imágenes con GPT-4o Vision                      │
│  • Validar categoría con IA                                │
│  • Detectar problemas antes de publicar                    │
│  • Rechazar si no pasa validación                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   PUBLISH PHASE                             │
│  • Publicar en MercadoLibre CBT                            │
│  • Retry inteligente por tipo de error                     │
│  • GTIN duplicado → Reintentar sin GTIN                    │
│  • Categoría incorrecta → Regenerar                        │
│  • Rate limiting automático                                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    FINAL REPORT                             │
│  • Estadísticas completas                                  │
│  • Reporte JSON guardado                                    │
│  • Base de datos actualizada                                │
└─────────────────────────────────────────────────────────────┘
```

### Base de Datos

El sistema usa SQLite para tracking:

**Ubicación:** `storage/pipeline_state.db`

**Tablas:**

1. **pipeline_runs**: Historial de ejecuciones
2. **asin_status**: Estado actual de cada ASIN
3. **logs**: Logs detallados por fase

### Estructura de Archivos

```
revancha/
├── main2.py                           # ← Nuevo pipeline v2.0
├── main.py                            # ← Pipeline original (sin tocar)
│
├── resources/
│   └── asins.txt                      # Lista de ASINs a procesar
│
├── storage/
│   ├── asins_json/                    # JSONs de Amazon descargados
│   ├── logs/
│   │   ├── publish_ready/             # mini_ml.json listos para publicar
│   │   └── pipeline/                  # Reportes de ejecución
│   └── pipeline_state.db              # Base de datos de tracking
│
└── src/
    ├── amazon_api.py                  # Descarga desde Amazon SP-API
    ├── transform_mapper_new.py        # Transformación principal
    ├── unified_transformer.py         # Transformación IA unificada
    ├── ai_validators.py               # Validadores IA
    ├── smart_categorizer.py           # Categorizador inteligente
    └── mainglobal.py                  # Publicador en ML
```

## 🔍 Monitoreo y Debug

### Ver Estado de la Base de Datos

```bash
sqlite3 storage/pipeline_state.db "SELECT asin, status, last_error FROM asin_status ORDER BY updated_at DESC LIMIT 10;"
```

### Ver Logs de un ASIN

```bash
sqlite3 storage/pipeline_state.db "SELECT phase, message, level, timestamp FROM logs WHERE asin = 'B0CYM126TT' ORDER BY timestamp;"
```

### Ver Estadísticas

```bash
sqlite3 storage/pipeline_state.db "SELECT status, COUNT(*) FROM asin_status GROUP BY status;"
```

### Ver Últimas Ejecuciones

```bash
sqlite3 storage/pipeline_state.db "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;"
```

## 🛡️ Estrategias de Retry

### Download Phase
- **Reintentos:** 3
- **Delay:** Exponential backoff (5s, 10s, 15s)
- **Errores comunes:** Rate limiting, timeouts, API errors

### Transform Phase
- **Reintentos:** 2
- **Delay:** 5s fijo
- **Errores comunes:** JSON inválido, categoría no encontrada

### Publish Phase
- **Reintentos:** 3
- **Delay:** Exponential backoff (5s, 10s, 15s)
- **Estrategias específicas:**
  - **GTIN duplicado (3701):** Reintentar sin GTIN
  - **Categoría incorrecta:** Regenerar con nueva categoría
  - **Rate limiting (429):** Esperar 10s y reintentar
  - **Dimensiones inválidas:** Abortar (requiere datos reales)

## 📊 Reportes

Cada ejecución genera un reporte JSON en:

```
storage/logs/pipeline/report_YYYYMMDD_HHMMSS.json
```

**Contenido del reporte:**

```json
{
  "run_id": "20250103_143022",
  "timestamp": "2025-01-03T14:30:22",
  "elapsed_seconds": 1234.56,
  "results": {
    "success": ["B0CYM126TT", "B0DRW8G3WK"],
    "failed": ["B092RCLKHN"],
    "skipped": []
  },
  "statistics": {
    "published": 2,
    "failed": 1,
    "pending": 0
  }
}
```

## 🔧 Configuración

### Variables de Entorno Requeridas

```bash
# MercadoLibre
ML_ACCESS_TOKEN=APP_USR-...
ML_CLIENT_ID=...
ML_CLIENT_SECRET=...

# Amazon SP-API
AMZ_CLIENT_ID=amzn1.application-oa2-client...
AMZ_CLIENT_SECRET=...
AMZ_REFRESH_TOKEN=...

# OpenAI (para IA)
OPENAI_API_KEY=sk-proj-...

# Configuración de precios
MARKUP_PCT=40
```

### Ajustar Configuración

Editar la clase `Config` en main2.py:

```python
class Config:
    # Número de reintentos
    MAX_DOWNLOAD_RETRIES = 3
    MAX_TRANSFORM_RETRIES = 2
    MAX_PUBLISH_RETRIES = 3

    # Delays en segundos
    RETRY_DELAY = 5
    PUBLISH_DELAY = 3
    RATE_LIMIT_DELAY = 10

    # Flags por defecto
    DRY_RUN = False
    SKIP_VALIDATION = False
    FORCE_REGENERATE = False
```

## 🆚 Comparación: main.py vs main2.py

| Característica | main.py | main2.py |
|----------------|---------|----------|
| Health checks pre-vuelo | ❌ | ✅ |
| Validación IA pre-publicación | ❌ | ✅ |
| Base de datos de tracking | ❌ | ✅ |
| Retry inteligente | ⚠️ Básico | ✅ Avanzado |
| Estrategias por tipo de error | ❌ | ✅ |
| Logs detallados | ⚠️ Console | ✅ DB + Console |
| Reportes JSON | ⚠️ Básico | ✅ Completo |
| Modo dry-run | ❌ | ✅ |
| Procesar ASIN individual | ❌ | ✅ |
| Estadísticas en tiempo real | ❌ | ✅ |
| Rate limiting inteligente | ⚠️ Fijo | ✅ Exponential |

## 🎯 Casos de Uso

### Caso 1: Procesar Lista Nueva de ASINs

```bash
# 1. Agregar ASINs a resources/asins.txt
# 2. Ejecutar con health checks
python3 main2.py
```

### Caso 2: Probar un ASIN sin Publicar

```bash
# Dry-run de un ASIN específico
python3 main2.py --dry-run --asin B0CYM126TT
```

### Caso 3: Regenerar ASINs Fallidos

```bash
# Ver ASINs fallidos
sqlite3 storage/pipeline_state.db "SELECT asin FROM asin_status WHERE status = 'failed';"

# Regenerar forzando
python3 main2.py --force-regenerate
```

### Caso 4: Testing Rápido

```bash
# Saltar validación IA para ir rápido
python3 main2.py --skip-validation --asin B0CYM126TT
```

## 🐛 Troubleshooting

### Error: "Falta ML_ACCESS_TOKEN en .env"

**Solución:** Verificar que el archivo `.env` tenga todas las credenciales:

```bash
cat .env | grep ML_ACCESS_TOKEN
```

### Error: "No se puede conectar a ML API"

**Solución:** Verificar que el token no haya expirado:

```bash
curl -H "Authorization: Bearer $ML_ACCESS_TOKEN" https://api.mercadolibre.com/users/me
```

### Error: "GTIN duplicado (3701)"

**Solución:** El sistema lo maneja automáticamente. Si persiste, verificar:

```bash
sqlite3 storage/pipeline_state.db "SELECT asin, last_error FROM asin_status WHERE last_error LIKE '%3701%';"
```

### Pipeline se detiene en medio

**Solución:** El sistema guarda el estado. Simplemente volver a ejecutar:

```bash
python3 main2.py
```

Los ASINs ya procesados se saltarán automáticamente.

## 🔒 Seguridad

- ✅ No modifica el pipeline original (main.py)
- ✅ Puede eliminarse sin problemas si no funciona
- ✅ Base de datos SQLite local (no afecta otros sistemas)
- ✅ Modo dry-run para pruebas seguras
- ✅ Logs detallados para auditoría

## 📝 Notas Importantes

1. **No interfiere con main.py**: main2.py es completamente independiente
2. **Se puede eliminar**: Si no funciona, simplemente borra main2.py y pipeline_state.db
3. **Base de datos separada**: Usa su propia BD (pipeline_state.db)
4. **Health checks opcionales**: Se pueden saltar con --skip-health-check

## 🚦 Exit Codes

- `0`: Todo exitoso
- `1`: Todos fallaron o error fatal
- `2`: Parcialmente exitoso (algunos ok, algunos fallidos)
- `130`: Interrumpido por usuario (Ctrl+C)

## 📚 Dependencias

Todas las dependencias ya están instaladas en el venv del proyecto:

- openai
- requests
- python-dotenv
- sqlite3 (built-in)

## 🤝 Soporte

Si encuentras problemas:

1. Revisar logs en `storage/logs/pipeline/`
2. Consultar base de datos con comandos SQL arriba
3. Ejecutar con `--dry-run` primero
4. Verificar health checks

## 📅 Changelog

### v2.0 (2025-01-03)
- Sistema completo de pipeline con tracking
- Validación IA pre-publicación
- Retry inteligente por tipo de error
- Base de datos SQLite para estado
- Health checks pre-vuelo
- Modo dry-run
- Reportes JSON detallados
