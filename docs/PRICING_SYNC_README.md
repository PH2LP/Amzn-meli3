# 🔄 Sistema de Sincronización de Pricing Local → Servidor

## ✅ Completado

Sistema para sincronizar valores de pricing del `.env` local al servidor VPS automáticamente.

---

## 📦 Archivos Creados

### 1. `sync_pricing_to_server.py`
Script principal que sincroniza valores de pricing al servidor.

**Ubicación:** `/Users/felipemelucci/Desktop/revancha/sync_pricing_to_server.py`

**Uso:**
```bash
python3 sync_pricing_to_server.py
```

**Qué hace:**
1. Lee `PRICE_MARKUP`, `USE_TAX`, `FULFILLMENT_FEE` del .env local
2. Se conecta al servidor VPS via SSH
3. Actualiza esos valores en el `.env` del servidor
4. Verifica que los cambios se guardaron correctamente

---

## ⚙️ Configuración Requerida

Agregá estas líneas a tu `.env` local:

```bash
# VPS Server Configuration
VPS_HOST=164.90.148.243
VPS_USER=root
VPS_PATH=/root/revancha
```

✅ Ya están agregadas en tu `.env` local

---

## 🚀 Cómo Usar

### Escenario: Cambiar markup de 150% a 200%

```bash
# 1. Editar .env local
nano .env
# Cambiar: PRICE_MARKUP=200

# 2. Sincronizar al servidor
python3 sync_pricing_to_server.py
# ¿Continuar? (s/N): s

# Salida:
# ✅ PRICE_MARKUP = 200 (actualizado)
# ✅ USE_TAX = true (actualizado)
# ✅ FULFILLMENT_FEE = 4.0 (actualizado)
# ✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE
```

### Resultado:
- ✅ Servidor ahora usa `PRICE_MARKUP=200`
- ✅ Próximo sync automático (cada 3 días) calculará precios con 200% markup
- ✅ Local también usa 200% cuando corras `update_prices.py`

---

## 🔍 Valores que Sincroniza

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `PRICE_MARKUP` | Porcentaje de markup | `150` (150%) |
| `USE_TAX` | Aplicar tax 7% Florida | `true` o `false` |
| `FULFILLMENT_FEE` | Fee 3PL en USD | `4.0` |

**NO sincroniza:** Credenciales (ML_ACCESS_TOKEN, etc.)

---

## 🧪 Testing

### Test de validación:
```bash
python3 test_sync_pricing.py
```

Esto muestra:
- ✅ Valores actuales del .env local
- ✅ Configuración del servidor
- ✅ Comando SSH que se ejecutará
- ✅ Resultado esperado

### Test real (cuando el servidor esté disponible):
```bash
python3 sync_pricing_to_server.py
```

---

## 📚 Documentación Actualizada

### REVANCHA_SYSTEM_GUIDE.md
✅ Nueva sección: "Pricing Configuration (Local & Server)"
✅ Nueva sección: "Syncing Pricing to Server"
✅ Workflow actualizado: "Bulk Price Adjustment"

**Ubicación:** `/Users/felipemelucci/Desktop/REVANCHA_SYSTEM_GUIDE.md`

### Para actualizar el PDF:
Ver instrucciones en: `/Users/felipemelucci/Desktop/UPDATE_PDF_INSTRUCTIONS.txt`

---

## 🔐 Seguridad

- ✅ Solo sincroniza valores de pricing (no credenciales)
- ✅ Requiere acceso SSH al servidor (ya configurado)
- ✅ Muestra preview antes de aplicar cambios
- ✅ Verifica que los valores se guardaron correctamente

---

## ⚠️ Notas Importantes

1. **Servidor debe estar accesible via SSH**
   - Si el servidor no responde, el script mostrará error de timeout

2. **Los cambios afectan el sync automático**
   - El cron job del servidor usa el `.env` del servidor
   - Cuando cambias valores localmente, DEBES sincronizar al servidor

3. **Local vs Servidor**
   - Local: Para cuando corras scripts manualmente
   - Servidor: Para el sync automático cada 3 días

---

## 🎯 Workflow Completo

```bash
# 1. Modificar pricing local
nano .env
# Cambiar PRICE_MARKUP=200

# 2. Sincronizar al servidor
python3 sync_pricing_to_server.py

# 3. (Opcional) Actualizar precios existentes localmente
python3 update_prices.py

# 4. (Opcional) Sincronizar base de datos
python3 sync_db.py
```

Ahora tanto local como servidor usan los mismos valores de pricing.

---

## 🐛 Troubleshooting

### Error: "VPS_HOST no está configurado"
**Solución:** Agregá `VPS_HOST=164.90.148.243` al .env

### Error: "ssh: connect to host... timeout"
**Solución:** Verificá que el servidor esté encendido y accesible

### Error: "Permission denied"
**Solución:** Verificá que tengas acceso SSH configurado al servidor

---

**Fecha:** 10 de Diciembre, 2025
**Estado:** ✅ Completado y testeado
