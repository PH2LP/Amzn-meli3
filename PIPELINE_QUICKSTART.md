# 🚀 Pipeline Automático Amazon → MercadoLibre

## Inicio Rápido

El pipeline completo automatiza todo el proceso desde descargar productos de Amazon hasta publicarlos en MercadoLibre.

### 📋 Paso 1: Agregar ASINs

Edita el archivo `new_asins.txt` y agrega tus ASINs (uno por línea):

```bash
# Abre el archivo con tu editor favorito
nano new_asins.txt

# O agrega ASINs desde la terminal
echo 'B092RCLKHN' >> new_asins.txt
echo 'B0BGQLZ921' >> new_asins.txt
echo 'B0CJQG4PMF' >> new_asins.txt
```

### 🎬 Paso 2: Ejecutar Pipeline

```bash
# Ejecutar pipeline completo (publicación real)
./run_pipeline.sh

# O probar primero en modo simulación (sin publicar)
./run_pipeline.sh --dry-run
```

**¡Eso es todo!** El sistema hará todo automáticamente:

1. ⬇️  **Download**: Descarga datos de Amazon SP-API
2. 🔄 **Transform**: Transforma y mapea a formato MercadoLibre
3. ✅ **Validate**: Validación con IA (imágenes + categorías)
4. 📤 **Publish**: Publica en MercadoLibre CBT

---

## 📊 Revisar Resultados

### Reporte en consola
Al finalizar verás un reporte con estadísticas:
```
📊 REPORTE FINAL DEL PIPELINE
════════════════════════════════════════════
⏱️  Tiempo total: 5.2 minutos
📦 Total procesados: 10
✅ Exitosos: 8/10 (80.0%)
❌ Fallidos: 2/10 (20.0%)
```

### Logs detallados
```bash
# Ver último log de ejecución
ls -lt logs/pipeline_run_*.log | head -1 | xargs tail -100

# Ver productos con problemas de GTIN
cat storage/logs/gtin_issues.json
```

### Reportes JSON
```bash
# Reporte completo con todos los detalles
cat storage/logs/pipeline/report_*.json | tail -1
```

---

## ⚙️ Opciones Avanzadas

### Modo simulación (sin publicar)
```bash
./run_pipeline.sh --dry-run
```

### Saltar validación IA (más rápido, menos seguro)
```bash
./run_pipeline.sh --skip-validation
```

### Forzar re-descarga y re-transformación
```bash
./run_pipeline.sh --force-regenerate
```

### Procesar un solo ASIN
```bash
python3 main2.py --asin B092RCLKHN
```

### Usar otro archivo de ASINs
```bash
python3 main2.py --asins-file mi_lista.txt
```

---

## 🔧 Estructura de Archivos

```
new_asins.txt                       # Tu lista de ASINs
run_pipeline.sh                     # Script principal

storage/
├── asins_json/                     # JSONs descargados de Amazon
├── logs/
│   ├── publish_ready/              # JSONs listos para publicar
│   ├── gtin_issues.json            # Productos con problemas de GTIN
│   └── pipeline/                   # Reportes de ejecución
└── pipeline_state.db               # Base de datos de tracking

logs/
└── pipeline_run_*.log              # Logs de cada ejecución
```

---

## 🆘 Problemas Comunes

### Error: "new_asins.txt not found"
Crea el archivo:
```bash
touch new_asins.txt
echo 'B092RCLKHN' > new_asins.txt
```

### Error: "Permission denied"
Haz el script ejecutable:
```bash
chmod +x run_pipeline.sh
```

### Error: "SP-API credentials"
Verifica que tu archivo `.env` tenga las credenciales:
```bash
# Revisa que existan estas variables
grep -E "SP_API|OPENAI|ML_" .env
```

### Productos no se publican (GTIN issues)
Algunos productos requieren GTIN pero Amazon no lo provee. Estos se guardan en:
```bash
cat storage/logs/gtin_issues.json
```

---

## 📚 Documentación Completa

Para más detalles técnicos, revisa:
- `main2.py` - Código fuente del pipeline
- `storage/logs/pipeline/` - Reportes detallados
- `.env.example` - Variables de entorno necesarias

---

## 🎯 Flujo del Pipeline

```
┌─────────────────┐
│  new_asins.txt  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   1. Download   │ --> │ Amazon SP-API    │
│   (SP-API)      │     │ storage/asins/   │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  2. Transform   │ --> │ IA + Mapping     │
│   (IA)          │     │ Mini ML JSON     │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  3. Validate    │ --> │ IA Validation    │
│   (IA)          │     │ Images + Category│
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  4. Publish     │ --> │ MercadoLibre CBT │
│   (ML API)      │     │ 6 países         │
└─────────────────┘     └──────────────────┘
```

---

**¿Preguntas?** Revisa los logs en `logs/` o el código en `main2.py`
