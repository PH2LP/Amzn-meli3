# 🚀 GUÍA RÁPIDA: INTERCEPTAR AMAZON RUFUS

## PASO 1: Instalar mitmproxy

```bash
brew install mitmproxy
```

## PASO 2: Iniciar proxy

```bash
# Opción A: Interfaz web (recomendado)
mitmweb

# Se abrirá http://localhost:8081 en tu navegador
```

## PASO 3: Configurar tu iPhone

1. **Conectar a la misma red WiFi** que tu Mac

2. **Configurar proxy en iPhone:**
   - Ve a: Ajustes → WiFi
   - Toca la (i) de tu red WiFi
   - Desplázate a "Proxy HTTP"
   - Selecciona "Manual"
   - Servidor: [IP de tu Mac] (ver abajo cómo obtenerla)
   - Puerto: `8080`
   - Autenticación: OFF
   - Guarda

3. **Obtener IP de tu Mac:**
```bash
# En tu Mac, ejecuta:
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}'
# Anota la IP (ej: 192.168.1.100)
```

## PASO 4: Instalar certificado en iPhone

1. En el iPhone, abre Safari
2. Ve a: **http://mitm.it**
3. Toca "Get mitmproxy-ca-cert.pem" para iOS
4. Permite la descarga del perfil
5. Ve a: Ajustes → Perfil descargado → Instalar
6. Ingresa tu código de acceso
7. **IMPORTANTE:** Ve a Ajustes → General → Información → Configuración de certificados → mitmproxy
8. Activa "Confiar completamente en mitmproxy"

## PASO 5: Abrir Amazon app y usar Rufus

1. Abre la app de Amazon en tu iPhone
2. Busca cualquier producto
3. Abre el chat de Rufus (icono de chat naranja)
4. Haz una pregunta como: "¿Este producto es resistente al agua?"

## PASO 6: Ver tráfico capturado

En tu navegador (http://localhost:8081) verás todas las requests.

**Busca URLs que contengan:**
- `rufus`
- `chat`
- `assistant`
- `genai`
- `conversation`

## PASO 7: Analizar con el script

```bash
# Guardar captura desde mitmweb:
# Flow → Save → amazon_capture.flow

# Analizar:
python3 scripts/research/analyze_amazon_traffic.py amazon_capture.flow
```

## 🔍 QUÉ BUSCAR

Cuando veas una request de Rufus, anota:

```
✅ URL completa
✅ Headers (especialmente):
   - x-api-key
   - x-amz-access-token
   - authorization
   - user-agent
✅ Body de la request
✅ Response
```

## ⚠️ PROBLEMAS COMUNES

### "No veo tráfico de Amazon"
- Amazon puede usar **SSL Pinning**
- Solución: Necesitas jailbreak (iPhone) o root (Android)
- Alternativa: Usar scraper en su lugar

### "El certificado no funciona"
- Asegúrate de confiar completamente en el certificado
- Reinicia la app de Amazon

### "Tráfico encriptado/ilegible"
- Verifica que instalaste el certificado correctamente
- Ve a Configuración de certificados y confía en mitmproxy

## 📱 ALTERNATIVA: Android (más fácil)

Si tienes Android:
```bash
# 1. Habilitar Developer Options
# 2. Conectar por USB
adb devices

# 3. Usar Charles Proxy o Burp Suite
# Android suele ser más fácil para interceptar
```

## ⏭️ SIGUIENTE PASO

Si NO funciona (SSL Pinning), usa el scraper:
```bash
python3 scripts/research/scrape_amazon_reviews.py --asin B0CYM126TT
```
