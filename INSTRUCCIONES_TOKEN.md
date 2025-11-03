# 🔑 CÓMO ARREGLAR EL ACCESS TOKEN PARA RESPONDER PREGUNTAS

## Problema Actual

El access token en `.env` NO tiene los permisos necesarios para:
- ❌ Buscar preguntas sin responder
- ❌ Postear respuestas automáticamente

**Error recibido:**
```
PA_UNAUTHORIZED_RESULT_FROM_POLICIES - PolicyAgent blocked request
```

---

## Solución: Generar Token con Scopes Correctos

### Opción 1: Desde MercadoLibre Developer Portal (Más Fácil)

1. **Ir al Developer Portal:**
   - Argentina: https://developers.mercadolibre.com.ar/apps
   - México: https://developers.mercadolibre.com.mx/apps
   - Brasil: https://developers.mercadolibre.com.br/apps

2. **Seleccionar tu App** (o crear una si no existe)

3. **Ir a "Credentials" o "Credenciales"**

4. **Generar Access Token con estos scopes:**
   - ✅ `offline_access` - Para refresh token
   - ✅ `read` - Para leer preguntas
   - ✅ `write` - Para postear respuestas

5. **Copiar el nuevo token y actualizar `.env`:**
   ```bash
   ML_ACCESS_TOKEN=APP_USR-XXXXXXXXX-XXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXXXX
   ```

---

### Opción 2: OAuth Flow Manual (Recomendado para Producción)

1. **Obtener tu APP_ID y APP_SECRET**
   - Ve a: https://developers.mercadolibre.com.ar/apps
   - Copia `APP_ID` y `CLIENT_SECRET`

2. **URL de Autorización**

   Reemplaza `TU_APP_ID` y abre en navegador:

   ```
   https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id=TU_APP_ID&redirect_uri=https://localhost&scope=offline_access,read,write
   ```

   **Importante:** Los scopes deben ser: `offline_access,read,write`

3. **Autorizar la App**
   - Inicia sesión en MercadoLibre
   - Acepta los permisos
   - Serás redirigido a `https://localhost?code=TG-XXXXXXX...`

4. **Copiar el CODE de la URL**
   ```
   https://localhost?code=TG-64fd96a5-48c9-4ce2-9988-03a47b77b4e0
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                          Este es el CODE
   ```

5. **Intercambiar CODE por ACCESS_TOKEN**

   ```bash
   curl -X POST "https://api.mercadolibre.com/oauth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code" \
     -d "client_id=TU_APP_ID" \
     -d "client_secret=TU_CLIENT_SECRET" \
     -d "code=TG-XXXXXXX" \
     -d "redirect_uri=https://localhost"
   ```

   **Respuesta:**
   ```json
   {
     "access_token": "APP_USR-XXXXX-XXXXXX-XXXXXX...",
     "token_type": "Bearer",
     "expires_in": 21600,
     "refresh_token": "TG-XXXXXXX...",
     "scope": "offline_access read write"
   }
   ```

6. **Actualizar `.env` con el nuevo token:**
   ```bash
   ML_ACCESS_TOKEN=APP_USR-XXXXX-XXXXXX-XXXXXX...
   ML_REFRESH_TOKEN=TG-XXXXXXX...
   ```

---

## Verificar que el Token Funciona

Ejecuta estos comandos para verificar:

### 1. Verificar token actual:
```bash
curl -s "https://api.mercadolibre.com/users/me" \
  -H "Authorization: Bearer $ML_ACCESS_TOKEN" | python3 -m json.tool
```

**Debe retornar tu información de usuario, NO un error 403.**

### 2. Verificar acceso a preguntas:
```bash
./venv/bin/python3 auto_answer_questions.py
```

**Debe mostrar:**
```
📩 Encontradas X preguntas sin responder
```

NO debe mostrar error 500 o 403.

---

## Solución Temporal (Mientras Arreglas el Token)

Usa el script manual para responder preguntas específicas:

```bash
./venv/bin/python3 answer_specific_question.py
```

O directamente con argumentos:
```bash
./venv/bin/python3 answer_specific_question.py <question_id> "<texto pregunta>" <item_id>
```

Ejemplo:
```bash
./venv/bin/python3 answer_specific_question.py 1572433991 "¿Cuánto demora el envío?" MLA1234567890
```

---

## Scopes Necesarios para Cada Funcionalidad

| Funcionalidad | Scope Requerido |
|---------------|-----------------|
| Publicar items | `write` |
| Leer preguntas | `read` |
| Responder preguntas | `write` |
| Refresh token automático | `offline_access` |
| Ver mensajes | `read` |
| Enviar mensajes | `write` |

**Para el sistema completo necesitas:** `offline_access,read,write`

---

## Refresh Token Automático (Opcional)

Si quieres que el token se renueve automáticamente cada 6 horas, guarda el `refresh_token` en `.env`:

```bash
ML_REFRESH_TOKEN=TG-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXXXX
```

Luego crea un cron job:
```bash
crontab -e
```

Agregar:
```
0 */5 * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 refresh_ml_token.py
```

---

## ✅ Checklist Final

- [ ] Nuevo token generado con scopes: `offline_access,read,write`
- [ ] Token actualizado en `.env`
- [ ] Verificado con `curl` que el token funciona
- [ ] Ejecutado `auto_answer_questions.py` sin errores
- [ ] (Opcional) Refresh token configurado en `.env`
- [ ] (Opcional) Cron job para auto-refresh

---

**Última actualización:** 2025-11-02
