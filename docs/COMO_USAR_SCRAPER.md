# 🚀 GUÍA: SCRAPER DE AMAZON CON TU CUENTA

## ✅ Setup (solo una vez)

```bash
# 1. Instalar ChromeDriver
brew install chromedriver

# 2. Instalar Selenium
pip3 install --break-system-packages selenium
```

## 🔐 PRIMER USO (Login manual - solo una vez)

```bash
python3 scripts/research/amazon_scraper_with_login.py --asin B0CYM126TT --login
```

**Qué pasará:**
1. Se abrirá Chrome
2. Verás la página de login de Amazon
3. Ingresa tu email/contraseña
4. Completa 2FA si lo tienes
5. Espera a que termine de scrapear
6. ¡Las cookies quedarán guardadas!

## ⚡ USOS SIGUIENTES (automático)

```bash
# Ya NO necesitas --login, usa las cookies guardadas:
python3 scripts/research/amazon_scraper_with_login.py --asin B0CYM126TT
python3 scripts/research/amazon_scraper_with_login.py --asin B0DBZS6MHK
python3 scripts/research/amazon_scraper_with_login.py --asin B0CQGFYSNC
```

## 📁 Reviews se guardan en

```
storage/reviews_{ASIN}.json
```

## 🤖 Usar reviews con Claude (Q&A inteligente)

```bash
# Primero configura tu API key de Anthropic:
echo "ANTHROPIC_API_KEY=tu_key_aqui" >> .env

# Luego pregunta lo que quieras:
python3 scripts/research/product_qa_with_rag.py --asin B0CYM126TT --question "¿Es resistente al agua?"
python3 scripts/research/product_qa_with_rag.py --asin B0CYM126TT --summary
python3 scripts/research/product_qa_with_rag.py --asin B0CYM126TT --suggest
```

## 🔄 Si expiran las cookies

```bash
# Vuelve a hacer login:
python3 scripts/research/amazon_scraper_with_login.py --asin B0CYM126TT --login
```

## ⚠️ Problemas comunes

### "chromedriver not found"
```bash
brew install chromedriver
```

### "chromedriver can't be opened" (Mac)
```bash
xattr -d com.apple.quarantine $(which chromedriver)
```

### "Selenium not installed"
```bash
pip3 install --break-system-packages selenium
```

## 🎯 WORKFLOW COMPLETO

```bash
# 1. Scrape reviews (primera vez con login)
python3 scripts/research/amazon_scraper_with_login.py --asin B0CYM126TT --login

# 2. Usa Claude para análisis inteligente
python3 scripts/research/product_qa_with_rag.py --asin B0CYM126TT --summary

# 3. Haz preguntas específicas
python3 scripts/research/product_qa_with_rag.py --asin B0CYM126TT --question "¿Cuánto dura la batería?"
```

## 📝 Notas

- Las cookies se guardan en `storage/amazon_cookies.pkl`
- Duran varios días/semanas
- Si Amazon pide login de nuevo, usa `--login`
- El scraper es anti-detección (simula navegador real)
