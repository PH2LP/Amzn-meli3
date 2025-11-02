# Amazon → MercadoLibre CBT Pipeline

Pipeline automatizado para importar productos desde Amazon SP-API y publicarlos en MercadoLibre CBT (Cross-Border Trade) en múltiples países.

## Características

- Descarga automática de productos desde Amazon SP-API
- Detección inteligente de categorías usando embeddings + IA
- Transformación y mapeo de atributos
- Publicación multi-país en MercadoLibre CBT
- Gestión automática de imágenes
- Manejo inteligente de dimensiones y GTINs

## Tasa de Éxito

**12/14 ASINs publicados exitosamente (85.7%)**

## Estructura del Proyecto

```
revancha/
├── main.py                      # Pipeline principal
├── amazon_api.py                # Cliente Amazon SP-API
├── transform_mapper_new.py      # Transformación Amazon → ML
├── mainglobal.py                # Publicación en MercadoLibre CBT
├── category_matcher.py          # Matching de categorías con IA
├── uploader.py                  # Gestor de imágenes
├── utils/                       # Scripts de utilidad
│   ├── auto_refresh_token.py   # Refresh token ML
│   ├── auto_refresh_token_amzn.py  # Refresh token Amazon
│   └── verificar_publicaciones.py  # Verificador de publicaciones
├── data/                        # Datos de categorías y embeddings
│   ├── cbt_categories.json
│   ├── cbt_categories_meta.json
│   └── cbt_embeddings.npy
├── asins_json/                  # JSONs descargados de Amazon
├── logs/                        # Logs y caches
│   ├── publish_ready/          # JSONs listos para publicar
│   ├── categories/             # Cache de categorías
│   ├── ai_title_cache.json
│   ├── ai_desc_cache.json
│   ├── category_cache.json
│   └── pipeline_report.json
├── schemas/                     # Schemas CBT de categorías
├── asins.txt                    # Lista de ASINs a procesar
├── .env                         # Credenciales (no incluido en repo)
└── REPORTE_FINAL.md            # Reporte de resultados

```

## Requisitos

- Python 3.8+
- Entorno virtual (venv)
- Credenciales Amazon SP-API
- Credenciales MercadoLibre
- API Key OpenAI

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/PH2LP/Amzn-meli3.git
cd revancha
```

2. Crear entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar `.env`:
```env
# Amazon SP-API
AMAZON_CLIENT_ID=your_client_id
AMAZON_CLIENT_SECRET=your_client_secret
AMAZON_REFRESH_TOKEN=your_refresh_token

# MercadoLibre
MELI_CLIENT_ID=your_client_id
MELI_CLIENT_SECRET=your_client_secret
MELI_REFRESH_TOKEN=your_refresh_token

# OpenAI
OPENAI_API_KEY=your_api_key
```

## Uso

### Pipeline Completo

1. Agregar ASINs al archivo `asins.txt`:
```
B092RCLKHN
B0BGQLZ921
B0CYM126TT
```

2. Ejecutar pipeline:
```bash
python3 main.py
```

El pipeline ejecutará automáticamente:
- Descarga de Amazon SP-API
- Transformación y mapeo
- Detección de categoría
- Publicación en MercadoLibre CBT

### Scripts de Utilidad

Refresh token de MercadoLibre:
```bash
python3 utils/auto_refresh_token.py
```

Verificar publicaciones:
```bash
python3 utils/verificar_publicaciones.py
```

Refresh token de Amazon:
```bash
python3 utils/auto_refresh_token_amzn.py
```

## Flujo del Pipeline

```
1. main.py lee asins.txt
     ↓
2. amazon_api.py descarga JSON de Amazon
     ↓
3. transform_mapper_new.py transforma datos
     ↓
4. category_matcher.py detecta categoría CBT
     ↓
5. mainglobal.py publica en MercadoLibre
     ↓
6. Reporte guardado en logs/pipeline_report.json
```

## Mejoras Implementadas

- ✅ Dimensiones de paquete coinciden exactamente con Amazon JSON
- ✅ Estimación inteligente cuando faltan dimensiones (basado en peso)
- ✅ Filtrado de valores placeholder (en_US, kilograms, etc)
- ✅ Detección de GTINs duplicados con retry automático
- ✅ Manejo de errores con reintentos inteligentes
- ✅ Category matching con embeddings + refinamiento IA

## Problemas Conocidos

### Unfixable (requieren intervención manual)

**B0DRW69H11** - Error 5101: Shipping mode not supported
- Categoría CBT455425 (Water Filtration) no soporta envío remoto

**B0CLC6NBBX** - Error 7810: GTIN required
- Categoría CBT123325 (Headphones) requiere GTIN obligatoriamente
- Producto no tiene GTIN válido del fabricante

## Logs y Reportes

- `logs/pipeline_report.json` - Reporte automático del pipeline
- `logs/verification_report.json` - Verificación de items publicados
- `REPORTE_FINAL.md` - Reporte consolidado con métricas

## Soporte

Para reportar issues o contribuir:
- GitHub Issues: https://github.com/PH2LP/Amzn-meli3/issues

## Licencia

Proyecto privado

---

**Última actualización:** 2025-11-02
**Versión:** 1.0
