# Cómo Habilitar el Pricing Role en Amazon SP-API

## ¿Qué vas a hacer?
Agregar el permiso "Pricing" a tu app para poder usar el endpoint `getCompetitiveSummary` que acepta ZIP code y retorna `fulfillmentType: AFN/MFN` confiable.

## ⚠️ IMPORTANTE - Esto es SEGURO:
- ✅ NO cambia nada de tu cuenta de vendedor
- ✅ NO afecta tus productos listados
- ✅ Solo agrega un permiso de lectura a tu app
- ✅ Las credenciales (Client ID y Secret) NO cambian
- ✅ Solo necesitás actualizar el Refresh Token al final

---

## PASO 1: Acceder a Developer Console

1. Ir a **Seller Central**: https://sellercentral.amazon.com/

2. En el menú principal, ir a:
   ```
   Apps & Services → Develop Apps
   ```

   O directamente: https://sellercentral.amazon.com/apps/manage

3. Vas a ver una lista de tus aplicaciones (apps)

---

## PASO 2: Identificar tu App Actual

Primero, vamos a verificar qué app estás usando actualmente:

```bash
# En tu terminal, ver el Client ID actual:
grep LWA_CLIENT_ID /Users/felipemelucci/Desktop/revancha/.env
```

Anota el valor (algo como `amzn1.application-oa2-client.xxxxx`)

---

## PASO 3: Editar la App

1. En la lista de apps, buscar la que tenga ese Client ID

2. Click en **"Edit App"** o **"Ver configuración"**

3. Vas a ver una sección que dice **"Roles"** o **"Data Access"**

4. Actualmente deberías tener seleccionados algunos roles. **NO DESMARQUES NADA**, solo vas a **AGREGAR** uno nuevo.

---

## PASO 4: Solicitar el Pricing Role

1. En la sección de Roles, buscar:
   ```
   ☐ Pricing
   ```

2. **Marcar el checkbox** de "Pricing"

3. Te va a pedir que justifiques por qué necesitás este permiso. Escribir algo como:
   ```
   We need access to competitive pricing data to ensure we only
   list FBA products with fast shipping. The getCompetitiveSummary
   operation provides fulfillment type and location-based pricing
   that is critical for our cross-border dropshipping operations.
   ```

4. Click en **"Save and Submit"** o **"Guardar y Enviar"**

---

## PASO 5: Esperar Aprobación

Amazon va a revisar tu solicitud. Esto puede tomar:
- **Mínimo**: 1-2 días
- **Típico**: 3-5 días
- **Máximo**: 1-2 semanas

Vas a recibir un email cuando sea aprobado.

**Mientras tanto:** Tu app sigue funcionando normal con los permisos actuales.

---

## PASO 6: Publicar el Cambio (Después de Aprobación)

Una vez aprobado:

1. Volver a **Developer Console** → Tu app

2. Vas a ver que el rol "Pricing" está aprobado pero en **Draft**

3. Click en **"Publish"** o **"Publicar"** para activarlo

---

## PASO 7: Re-autorizar la App (IMPORTANTE)

Después de publicar, necesitás generar un **nuevo Refresh Token**:

### Opción A: Desde Seller Central (más fácil)

1. Ir a: **Apps & Services → Manage Your Apps**

   https://sellercentral.amazon.com/apps/manage

2. Buscar tu app en la lista

3. Click en **"Authorize"** o **"Re-authorize"**

4. Vas a ver una pantalla mostrando los permisos (ahora incluye Pricing)

5. Click en **"Confirm"** o **"Autorizar"**

6. Te va a mostrar un código. **COPIALO** (es el nuevo Refresh Token)

### Opción B: Desde URL directa

1. Armar esta URL (reemplazá `TU_CLIENT_ID`):
   ```
   https://sellercentral.amazon.com/apps/authorize/consent?application_id=TU_CLIENT_ID&version=beta
   ```

2. Abrila en el browser (mientras estés logueado en Seller Central)

3. Autorizar y copiar el Refresh Token

---

## PASO 8: Actualizar el .env

1. Abrir el archivo `.env`:
   ```bash
   nano /Users/felipemelucci/Desktop/revancha/.env
   ```

2. Buscar la línea:
   ```
   LWA_REFRESH_TOKEN=...valor_viejo...
   ```

3. Reemplazar con el nuevo token que copiaste:
   ```
   LWA_REFRESH_TOKEN=Atzr|nuevo_token_aqui
   ```

4. Guardar (Ctrl+O, Enter, Ctrl+X)

**IMPORTANTE:**
- ✅ `LWA_CLIENT_ID` = NO CAMBIA
- ✅ `LWA_CLIENT_SECRET` = NO CAMBIA
- ✅ `LWA_REFRESH_TOKEN` = SÍ CAMBIA (nuevo)

---

## PASO 9: Probar que Funciona

```bash
cd /Users/felipemelucci/Desktop/revancha
python3 test_competitive_summary.py
```

Si sale bien, deberías ver:
```
✅ Status: 200
✅ RESULTADO:
   fulfillmentType: AFN (FBA) o MFN (FBM)
```

---

## ¿Qué Pasa Si Algo Sale Mal?

### Si te rechazan el Pricing Role:
- Podés apelar explicando mejor tu caso de uso
- O implementar el filtro conservador mientras tanto

### Si el nuevo Refresh Token no funciona:
- Verificar que hayas publicado los cambios (Publish)
- Reintentar la autorización
- El token viejo SIGUE funcionando hasta que autorices con el nuevo

### Si te trabás en algún paso:
- **NO TOQUES** los productos ni la cuenta de vendedor
- Solo estás modificando permisos de la app
- Si no estás seguro, mandame screenshot de lo que ves

---

## Resumen Visual del Proceso

```
1. Seller Central → Develop Apps
2. Edit App → Marcar "Pricing" → Submit
3. [ESPERAR APROBACIÓN - 3-5 días]
4. Publish cambios
5. Re-authorize app → Copiar nuevo Refresh Token
6. Actualizar .env → LWA_REFRESH_TOKEN=nuevo_token
7. Probar endpoint → python3 test_competitive_summary.py
```

---

## ¿Necesitás ayuda?

Si te trabás en algún paso o no encontrás alguna opción, avisame y te guío con screenshots o instrucciones más específicas.
