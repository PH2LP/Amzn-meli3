# 🚀 Amazon → MercadoLibre Pipeline

Sistema automatizado para transformar productos de Amazon en publicaciones de MercadoLibre usando IA.

---

## ⚡ Inicio Rápido

### 1. Configurar Credenciales

Edita el archivo `.env` con tus credenciales:

```bash
nano .env
```

### 2. Agregar Productos

Edita `asins.txt` y agrega los ASINs que quieres publicar (uno por línea):

```bash
nano asins.txt
```

Ejemplo de `asins.txt`:
```
B0F2MJ5H6V
B07LBQR3QY
B0DXHGTMQL
```

### 3. Ejecutar Pipeline

```bash
python3 main2.py
```

¡Eso es todo! El sistema procesará todos los ASINs y los publicará en MercadoLibre.

---

## 📋 Uso Básico

### Procesar todos los ASINs

```bash
python3 main2.py
```

### Procesar un ASIN específico

```bash
python3 main2.py --asin B0F2MJ5H6V
```

### Modo prueba (sin publicar)

```bash
python3 main2.py --dry-run
```

### Ver todas las opciones

```bash
python3 main2.py --help
```

---

## 📂 Archivos Importantes

| Archivo | Descripción |
|---------|-------------|
| `asins.txt` | Lista de ASINs a procesar |
| `main2.py` | Script principal del pipeline |
| `.env` | Credenciales (NO compartir) |
| `requirements.txt` | Dependencias Python |

---

## 📊 Monitorear Ejecución

Abre otra terminal y ejecuta:

```bash
# Ver logs del pipeline
tail -f storage/logs/pipeline/report_*.json

# Ver estado de publicaciones
ls -lh storage/logs/publish_ready/
```

---

## 🔧 Funcionalidades Avanzadas

### Sistema de Respuestas Automáticas

Responde preguntas de clientes automáticamente:

```bash
# Ejecutar una vez
python3 scripts/tools/auto_answer_questions.py

# Ejecutar en loop continuo
./scripts/tools/auto_responder_loop.sh
```

### Sincronización Automática

Sincroniza productos cada 3 días:

```bash
# Configurar cron job
./scripts/tools/setup_sync_cron.sh

# Ejecutar manualmente
python3 scripts/tools/sync_amazon_ml.py
```

---

## 📚 Documentación Completa

Para más detalles, ver:

- **Guía completa**: `docs/GUIA_USO_COMPLETA.md`
- **Auto-responder**: `docs/AUTO_ANSWER_SYSTEM_README.md`
- **Sincronización**: `docs/QUICKSTART_SYNC.md`

---

## 🎯 Características Principales

- ✅ **Detección Inteligente de Categorías** - Embeddings + IA
- ✅ **Sistema de Reintentos** - Hasta 8 intentos automáticos
- ✅ **Publicación Multi-País** - Chile, México, Colombia, Brasil, Argentina
- ✅ **Descripciones Optimizadas** - Formato profesional sin emojis
- ✅ **Respuestas Automáticas** - Sistema inteligente de Q&A
- ✅ **Sincronización Automática** - Actualización periódica de productos

---

## 📁 Estructura del Proyecto

```
revancha/
├── main2.py              # Script principal
├── asins.txt             # Lista de ASINs
├── .env                  # Credenciales
├── requirements.txt      # Dependencias
│
├── src/                  # Código fuente
│   ├── pipeline/         # Lógica del pipeline
│   ├── integrations/     # APIs (Amazon, ML)
│   └── utils/            # Utilidades
│
├── data/                 # Datos y categorías
├── storage/              # Bases de datos y logs
├── scripts/              # Scripts auxiliares
└── docs/                 # Documentación
```

---

## ⚠️ Solución de Problemas

### Error: No se encuentran credenciales

```bash
# Verifica que .env existe y tiene las credenciales
cat .env
```

### Error: No se encuentra asins.txt

```bash
# Crea el archivo
echo "B0F2MJ5H6V" > asins.txt
```

### Error de imports o módulos

```bash
# Reinstala dependencias
pip3 install -r requirements.txt
```

---

## 🚀 Ejecución Completa Paso a Paso

```bash
# 1. Ve al directorio del proyecto
cd /ruta/a/revancha

# 2. Agrega ASINs a procesar
nano asins.txt

# 3. Ejecuta el pipeline
python3 main2.py

# 4. (Opcional) Monitorea en otra terminal
tail -f storage/logs/pipeline/report_*.json
```

---

## 📞 Soporte

- Ver documentación en `docs/`
- Revisar logs en `storage/logs/`
- Consultar `docs/GUIA_USO_COMPLETA.md` para funcionalidades avanzadas

---

**Versión**: 2.0 - Estructura Modular
**Última actualización**: Noviembre 2025
