# ⚡ Quick Start - main4.py

## 1️⃣ Prueba Rápida (Un ASIN)

```bash
python3 test_main4.py
```

Esto procesa solo el primer ASIN (`B092RCLKHN`) para verificar que todo funciona.

**Output esperado:**
```
🧪 TEST MODE - main4.py
🎯 ASIN de prueba: B092RCLKHN
✅ JSON encontrado
🚀 Iniciando procesamiento...

🔍 Detectando categoría...
✅ Categoría: CBT3697 (Headphones)
🤖 Completando schema con IA...
✅ Schema completado: 38/45 atributos
🔍 Double-check de calidad con IA...
✅ Validación exitosa
🚀 Publicando en MercadoLibre...
✅ Publicado exitosamente: CBT123456789

✅ PRUEBA EXITOSA
```

## 2️⃣ Procesamiento Completo (Todos los ASINs)

```bash
python3 src/main4.py
```

Procesa los 14 ASINs en `resources/asins.txt`.

**Duración estimada:** 3-5 minutos
**Output final:**
```
📊 RESUMEN FINAL
✅ Exitosos: 14/14
❌ Fallidos: 0/14
📈 Tasa de éxito: 100.0%
```

## 3️⃣ Revisar Resultados

### Logs Principales
```bash
# Ver todo el proceso
cat storage/logs/main4_publish.log

# Ver últimas 50 líneas
tail -50 storage/logs/main4_publish.log
```

### Resultados por ASIN
```bash
# Ver resultado de un ASIN específico
cat storage/logs/main4_output/B092RCLKHN_published.json

# Listar todos los publicados
ls storage/logs/main4_output/*_published.json

# Ver errores (si hay)
ls storage/logs/main4_output/error_*.json
```

## 4️⃣ Verificación en MercadoLibre

Cada archivo `*_published.json` contiene:
- `item_id`: ID del producto en ML (CBT123456789)
- `category_id`: Categoría asignada
- `base_price`: Precio original de Amazon
- `net_proceeds`: Precio de venta (con markup)

Puedes verificar en ML:
```
https://www.mercadolibre.com/jm/item?id={item_id}
```

## ⚠️ Troubleshooting

### "No existe {ASIN}.json"
**Solución:** Coloca el JSON en `storage/asins_json/{ASIN}.json`

### "No se pudo detectar categoría"
**Solución:** Verifica que el JSON tenga `title` y `description`

### "Rate limited"
**Solución:** El sistema espera automáticamente, solo observa

### Error 3510 (atributo inválido)
**Solución:** Revisa `storage/logs/main4_output/error_*.json`

## 🎯 Configuración Rápida

### .env mínimo requerido
```bash
ML_ACCESS_TOKEN=APP_USR-1758699366225963-110214-xxxxx
OPENAI_API_KEY=sk-proj-xxxxx
MARKUP_PCT=40
```

### Markup (Ganancia)
- `MARKUP_PCT=40` → 40% de ganancia sobre precio base
- Precio Amazon: $10 → Precio ML: $14 (40% markup)

## 📈 Optimización de Costos OpenAI

**Costo por ASIN:** ~$0.02-0.04
- CategoryMatcherV2: ~100 tokens (~$0.001)
- Schema Completion (GPT-4o): ~2500 tokens (~$0.015)
- Double-Check (GPT-4o-mini): ~750 tokens (~$0.0015)

**14 ASINs = ~$0.28-0.56 USD**

Para reducir costos:
1. Ejecuta solo ASINs nuevos (no re-procesar)
2. Usa cache de categorías (ya implementado)
3. Ajusta `temperature=0` en prompts (ya implementado)

## 🚀 Modo Producción (1000+ ASINs)

Para volúmenes grandes:

```python
# En main4.py, ajusta el delay:
time.sleep(1)  # Reducir de 3s a 1s entre ASINs
```

**Rate limits de ML:**
- 1500 requests/minuto/seller
- Con delay 1s → ~60 ASINs/minuto → SAFE ✅

**Procesamiento estimado:**
- 100 ASINs: ~20-30 minutos
- 1000 ASINs: ~3-5 horas
- 10000 ASINs: ~30-50 horas

## 📊 Monitoreo en Tiempo Real

```bash
# Terminal 1: Ejecutar main4
python3 src/main4.py

# Terminal 2: Ver logs en tiempo real
tail -f storage/logs/main4_publish.log

# Terminal 3: Contar exitosos
watch -n 5 'ls storage/logs/main4_output/*_published.json | wc -l'
```

## 🎉 ¿Todo Funciona?

Si la prueba rápida fue exitosa:

1. ✅ CategoryMatcherV2 funcionando
2. ✅ IA completando atributos correctamente
3. ✅ Validación automática activa
4. ✅ Publicación en ML exitosa
5. ✅ Multi-marketplace (MLM, MLB, MLC, MCO) activo

**¡Estás listo para procesar todos los ASINs!** 🚀

```bash
python3 src/main4.py
```

---

**Para más detalles:** Ver `MAIN4_README.md`
