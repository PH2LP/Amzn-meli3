# 🔄 Sistema de Auto-Refresh de Token ML - FUNCIONANDO

## ✅ Estado: VERIFICADO Y TESTEADO

Este sistema permite que `main2.py` corra **indefinidamente** sin interrupciones cuando el token de MercadoLibre expira.

---

## 🎯 Problema que Resuelve

**ANTES:**
- `main2.py` corre durante 6+ horas
- Token de ML expira (401 invalid_token)
- Pipeline se detiene con error
- ❌ Tenías que parar main2.py, renovar token manualmente, y reiniciar

**AHORA:**
- `main2.py` detecta automáticamente cuando el token expira
- Renueva el token en segundo plano
- Reintenta la operación con el nuevo token
- ✅ **TODO SIN INTERRUMPIR LA EJECUCIÓN**

---

## 🔧 Cómo Funciona

### 1. Detección Automática de Token Expirado

Cuando cualquier petición HTTP a ML devuelve **401** con "invalid_token" o "expired":

```python
# En http_get, http_post, http_put
if r.status_code == 401 and _retry_count == 0:
    if "invalid_token" in r.text or "expired" in r.text.lower():
        if refresh_ml_token():
            # Reintentar con el nuevo token
            return http_get(url, params, extra_headers, timeout, _retry_count=1)
```

### 2. Renovación Automática del Token

```python
def refresh_ml_token():
    # 1. Lee credenciales de .env (ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REFRESH_TOKEN)
    # 2. Llama a ML API para obtener nuevo access_token
    # 3. Actualiza .env con el nuevo token
    # 4. Actualiza variables globales en memoria (ML_ACCESS_TOKEN, HEADERS)
    # 5. Retorna True si exitoso
```

### 3. Protección Anti-Refresh Múltiple

```python
# Evita hacer múltiples refreshes en menos de 10 segundos
if not force and (time.time() - _last_token_refresh) < 10:
    return True  # Usar token actual
```

### 4. Reintento Automático

Después del refresh exitoso, la función HTTP original se llama recursivamente con `_retry_count=1` para evitar loops infinitos.

---

## ✅ Tests Realizados

### Test 1: Refresh Básico
```bash
python3 test_token_refresh.py
```
**Resultado:** ✅ Token renovado correctamente, variables globales y .env actualizados

### Test 2: Auto-Recovery de 401
```bash
python3 test_http_401_recovery.py
```
**Resultado:** ✅ Detecta 401, renueva token, reintenta y recupera automáticamente

### Test 3: Escenario Real
```bash
python3 test_long_running_scenario.py
```
**Resultado:** ✅ Protección anti-refresh múltiple funciona, operaciones continúan normalmente

---

## 🚀 Uso en Producción

### Ejecutar main2.py normalmente:

```bash
python3 main2.py
```

**El pipeline ahora:**
1. ✅ Corre indefinidamente sin intervención manual
2. ✅ Renueva el token automáticamente cuando expira
3. ✅ Continúa procesando ASINs sin perder progreso
4. ✅ Protegido contra refreshes múltiples accidentales

---

## 🔍 Verificar que Funciona

### Ver logs durante la ejecución:

Cuando el token expire, verás:

```
🔄 Token expirado, renovando automáticamente...
✅ Token renovado: APP_USR-1758699366225963-120911-019de9b6...
```

Y el pipeline continuará procesando el siguiente ASIN sin errores.

### Si ves múltiples intentos de refresh:

```
⏭️  Refresh reciente (<10s), usando token actual
```

Esto es **CORRECTO** - significa que la protección anti-refresh múltiple está funcionando.

---

## 📋 Requisitos en .env

Asegúrate de tener estas variables configuradas:

```bash
ML_CLIENT_ID=1758699366225963
ML_CLIENT_SECRET=tXlL7QRkinZIIVH3j80aKVwtCghnuabC
ML_REFRESH_TOKEN=TG-69381598b35bdc000157a5c8-2629793984
ML_ACCESS_TOKEN=APP_USR-... (se renueva automáticamente)
```

---

## 🐛 Troubleshooting

### Si el refresh falla:

```
❌ Error renovando token: <error>
```

**Verificar:**
1. ✅ ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REFRESH_TOKEN existen en .env
2. ✅ ML_REFRESH_TOKEN es válido (no expiró permanentemente)
3. ✅ Conexión a internet funciona

### Si sigue dando 401 después del refresh:

El sistema solo intenta **1 vez** renovar el token para evitar loops infinitos.
Si el nuevo token también falla → error genuino (verificar credenciales en ML).

---

## 🎯 Diferencia vs Versiones Anteriores

### ❌ ANTES (NO FUNCIONABA):
- Token se cargaba una sola vez al inicio
- Variables globales no se actualizaban después del refresh
- Refresh manual en script separado
- main2.py no detectaba automáticamente cuando expirar

### ✅ AHORA (SÍ FUNCIONA):
- Detección automática de 401 en http_get/http_post/http_put
- refresh_ml_token() actualiza **tanto .env como variables globales**
- Protección anti-refresh múltiple (cooldown de 10 segundos)
- Reintento automático con el nuevo token
- **NO requiere intervención manual**

---

## 📌 Archivos Modificados

1. **src/integrations/mainglobal.py**
   - `refresh_ml_token()`: Función de renovación con protección anti-refresh
   - `http_get()`: Detecta 401 y renueva automáticamente
   - `http_post()`: Detecta 401 y renueva automáticamente
   - `http_put()`: Detecta 401 y renueva automáticamente

---

## ✨ Conclusión

**El sistema está listo para producción.**

Ahora podés dejar `main2.py` corriendo durante días/semanas sin preocuparte por el token expirado.

Para verificar: Ejecutá los 3 tests y luego lanzá main2.py con confianza.

```bash
# Tests
python3 test_token_refresh.py
python3 test_http_401_recovery.py
python3 test_long_running_scenario.py

# Producción
python3 main2.py
```

---

**Fecha:** 11 de Diciembre, 2025
**Estado:** ✅ FUNCIONANDO Y VERIFICADO
