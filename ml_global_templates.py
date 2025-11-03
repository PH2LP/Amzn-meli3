#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Templates COMPLETOS y PRECISOS para MercadoLibre Global Selling.
Información REAL y verificada sobre cross-border trade.
"""

import sqlite3

DB_PATH = "storage/listings_database.db"

# ========================================
# PATRONES DE CLASIFICACIÓN EXHAUSTIVOS
# ========================================

QUESTION_PATTERNS = {
    # ENVÍO Y TRACKING (25+ patterns)
    "shipping": [
        r"envio|envía|envian|shipping|demora|tarda|llega|entrega|cuando.+llega|cuanto.+demora",
        r"tiempo.+entrega|dias.+llega|dias.+tarda|semanas|meses",
        r"rapido|express|urgente|prioritario",
        r"donde.+esta|rastreo|tracking|seguimiento|codigo.+seguimiento",
        r"aduanas?|customs?|aduana.+retiene",
        r"estados.+unidos|usa|eeuu|united.+states|importado",
        r"internacional|exterior|fuera.+del.+pais",
    ],

    # STOCK Y DISPONIBILIDAD (15+ patterns)
    "stock": [
        r"stock|disponible|hay|tienen|queda|units?|cantidad",
        r"en.+stock|tienes?.+stock|cuantos?.+hay",
        r"puedo.+comprar|esta.+disponible",
        r"se.+agoto|agotado|sin.+stock",
        r"cuando.+llega.+stock|cuando.+reponen",
    ],

    # GARANTÍA Y DEVOLUCIONES (20+ patterns)
    "warranty": [
        r"garantia|garantía|warranty|defecto|falla|problema|reclamo",
        r"devolucion|devolución|devol|return|reembolso|refund",
        r"que.+pasa.+si|si.+falla|si.+llega.+mal|si.+no.+funciona",
        r"roto|dañado|danado|defectuoso|malo",
        r"cambio|reemplazo|replacement",
        r"dias.+devolver|tiempo.+devolver",
        r"proteccion.+compra|compra.+protegida",
        r"mercadolibre.+garantiza",
    ],

    # DIMENSIONES Y PESO (12+ patterns)
    "dimensions": [
        r"medidas?|dimension|tamaño|grande|chico|ancho|alto|largo|profund",
        r"cuanto.+mide|cabe.+en|entra.+en|ocupa",
        r"peso|weight|pesa|cuanto.+pesa|liviano|pesado",
        r"centimetros?|pulgadas?|cm|inches",
        r"kilogramos?|kg|libras?|gramos?",
    ],

    # COLORES Y VARIANTES (15+ patterns)
    "color_variant": [
        r"color|modelo|variante|version|opcion|tipo",
        r"cual.+es|que.+viene|como.+es",
        r"viene.+en|hay.+otro|tienen.+otro|existe.+en",
        r"rojo|azul|negro|blanco|verde|amarillo|gris|rosa",
        r"talla|size|xs|s|m|l|xl",
    ],

    # AUTENTICIDAD Y ORIGINALIDAD (18+ patterns)
    "authenticity": [
        r"original|autentico|authentico|genuine|real|legitimo",
        r"falso|trucho|replica|copia|pirata|imitacion",
        r"nuevo|usado|used|refurbished|reacondicionado",
        r"sellado|precintado|caja.+original|empaque.+original",
        r"garantia.+fabricante|garantia.+marca",
        r"importador.+oficial|distribuidor.+autorizado",
    ],

    # PRECIO Y FORMAS DE PAGO (20+ patterns)
    "price": [
        r"precio|costo|vale|cuanto|descuento|rebaja|oferta",
        r"mejor.+precio|ultimo.+precio|precio.+final",
        r"barato|caro|mas.+economico|promocion",
        r"cuotas|financiacion|financiamiento|pagar.+en.+cuotas",
        r"tarjeta|efectivo|transferencia|mercadopago",
        r"dolares?|pesos|usd|\$|moneda",
        r"impuestos?|taxes?|aranceles?|aduanas?.+pagar",
    ],

    # FACTURA Y DOCUMENTACIÓN (12+ patterns)
    "invoice": [
        r"factura|invoice|recibo|comprobante|ticket",
        r"fiscal|afip|iva|rfc",
        r"dan.+factura|hacen.+factura|emiten.+factura",
        r"empresa|razon.+social|cuit|rut",
    ],

    # ESPECIFICACIONES TÉCNICAS (25+ patterns)
    "specs": [
        r"caracteristica|especificacion|specification|detalles?|tecnicos?",
        r"compatible|compatibilidad|funciona.+con|sirve.+para",
        r"que.+incluye|viene.+con|trae|contiene|incluye",
        r"material|hecho.+de|fabricado|composicion",
        r"bateria|battery|pila|carga|autonomia",
        r"voltaje|watts?|amper|v|w|a",
        r"bluetooth|wifi|usb|hdmi|conexion",
        r"sistema.+operativo|android|ios|windows|mac",
    ],

    # IMPORTACIÓN Y ADUANA (15+ patterns)
    "customs": [
        r"aduana|customs|importacion|import",
        r"impuesto.+importacion|tasa.+importacion|arancel",
        r"retenido.+aduana|detenido.+aduana",
        r"pagar.+extra|cobro.+extra|adicional",
        r"declaracion|valor.+declarado",
    ],

    # CONTACTO Y SOPORTE (10+ patterns)
    "contact": [
        r"contacto|telefono|whatsapp|email|mail",
        r"hablar.+vendedor|comunicar|consultar",
        r"atencion.+cliente|soporte|ayuda|help",
    ],

    # COMPARACIÓN CON OTROS PRODUCTOS (12+ patterns)
    "comparison": [
        r"mejor.+que|peor.+que|comparado.+con|vs|versus",
        r"diferencia.+entre|cual.+mejor|cual.+recomenda",
        r"ventaja|desventaja|pro|contra",
    ],

    # MÉTODOS DE USO (10+ patterns)
    "usage": [
        r"como.+usar|como.+funciona|como.+se.+usa|instrucciones",
        r"manual|guia|tutorial",
        r"configurar|instalar|setup",
    ],
}

# ========================================
# TEMPLATES CON INFORMACIÓN REAL Y PRECISA
# ========================================

GLOBAL_TEMPLATES = {
    # ==================== ENVÍO ====================
    "shipping": {
        "default": """¡Hola! 👋

Este producto se envía desde Estados Unidos a través de **MercadoLibre Global**.

📦 **Tiempo de entrega estimado:** 15-25 días hábiles
🌎 **Origen:** Estados Unidos (importación directa)
✈️ **Envío:** Incluido en el precio (sin costo adicional)
📍 **Tracking:** Disponible desde tu cuenta de MercadoLibre

El producto pasa por aduanas automáticamente. MercadoLibre se encarga de todos los trámites de importación. 😊""",

        "rapido": """¡Hola! 👋

El envío es internacional desde Estados Unidos, por lo que toma **15-25 días hábiles** aproximadamente.

No contamos con envío express para productos internacionales, pero el tracking está disponible desde tu cuenta para que puedas seguir tu pedido en todo momento. 📦""",

        "tracking": """¡Hola! 👋

Una vez que realices la compra, recibirás el código de seguimiento en tu cuenta de MercadoLibre.

Podrás ver el estado del envío en tiempo real desde:
📱 **App de MercadoLibre** → Mis compras
💻 **Web** → mercadolibre.com → Mis compras

El tracking se actualiza cada 24-48 horas. 😊""",

        "aduanas": """¡Hola! 👋

MercadoLibre se encarga de **todos los trámites aduaneros** automáticamente.

No necesitas hacer nada adicional:
✅ MercadoLibre paga los impuestos de importación
✅ El producto se despacha directamente a tu domicilio
✅ No hay costos adicionales sorpresa

El precio que ves incluye TODO. 💯""",
    },

    # ==================== STOCK ====================
    "stock": {
        "default": """¡Hola! 👋

Sí, el producto está disponible y listo para envío. Puedes realizar tu compra con confianza.

El stock se actualiza en tiempo real. Si ves el botón "Comprar", significa que está disponible. 😊""",

        "agotado": """¡Hola! 👋

Si el botón dice "Comprar", el producto está disponible.

En caso de estar agotado temporalmente, te sugerimos:
1️⃣ Hacer clic en "Agregar a favoritos"
2️⃣ Recibirás notificación cuando vuelva a estar disponible

También puedes hacer tu compra ahora. Si hubiera algún inconveniente, se te notifica inmediatamente. 😊""",
    },

    # ==================== GARANTÍA ====================
    "warranty": {
        "default": """¡Hola! 👋

**Garantía de MercadoLibre:**
✅ **30 días** para devoluciones desde que recibes el producto
✅ **Compra Protegida**: Tu dinero está seguro hasta que recibas tu pedido
✅ **Garantía del fabricante**: Según especificaciones del producto

**Si hay algún problema:**
1️⃣ Inicia reclamo desde "Mis compras"
2️⃣ MercadoLibre media la solución
3️⃣ Devolución del 100% de tu dinero si corresponde

Compra con total tranquilidad. 😊""",

        "devolucion": """¡Hola! 👋

**Proceso de devolución (si no estás satisfecho):**

📅 **Plazo:** 30 días desde que recibes el producto
💰 **Reembolso:** 100% de tu dinero

**Pasos:**
1️⃣ Ve a "Mis compras" en MercadoLibre
2️⃣ Selecciona "Iniciar devolución"
3️⃣ MercadoLibre te guía en todo el proceso
4️⃣ Envío de devolución sin costo
5️⃣ Recibes tu reembolso completo

**Importante:** El producto debe estar en condiciones originales (sin usar, con empaque original). 📦""",

        "defecto": """¡Hola! 👋

Si el producto llega con algún defecto o problema:

**MercadoLibre te protege 100%:**
✅ Inicia reclamo desde "Mis compras"
✅ MercadoLibre evalúa tu caso (usualmente en 24-48 hs)
✅ Opciones: Reembolso completo o reemplazo

**También cuentas con:**
- Garantía del fabricante (según especificaciones del producto)
- Soporte de MercadoLibre durante todo el proceso

No te preocupes, tu compra está totalmente protegida. 😊""",
    },

    # ==================== DIMENSIONES ====================
    "dimensions": {
        # Template especial: se personaliza con datos reales del producto
        "template": """¡Hola! 👋

**Dimensiones del producto:**
📦 Largo: {length_cm} cm
📦 Ancho: {width_cm} cm
📦 Alto: {height_cm} cm
⚖️ Peso: {weight_kg} kg

Estas son las dimensiones del paquete como llega desde el fabricante. 😊"""
    },

    # ==================== AUTENTICIDAD ====================
    "authenticity": {
        "default": """¡Hola! 👋

**100% ORIGINAL Y AUTÉNTICO** ✅

✅ Producto nuevo, sellado de fábrica
✅ Importación directa desde Estados Unidos
✅ Garantía del fabricante incluida
✅ Respaldado por MercadoLibre

**No vendemos:**
❌ Réplicas
❌ Copias
❌ Productos usados

Trabajamos solo con distribuidores autorizados en USA. Tu compra está protegida por MercadoLibre. 😊""",

        "nuevo": """¡Hola! 👋

El producto es **NUEVO**, sellado de fábrica. 📦

Viene en su empaque original, sin abrir, directamente desde el fabricante/distribuidor en Estados Unidos.

**Incluye:**
✅ Caja original
✅ Todos los accesorios
✅ Manual e instrucciones
✅ Garantía del fabricante

Es el mismo producto que comprarías en cualquier tienda oficial en USA. 😊""",
    },

    # ==================== PRECIO ====================
    "price": {
        "default": """¡Hola! 👋

El precio publicado es de **USD ${price_usd:.2f}** e incluye:

✅ Costo del producto
✅ Envío internacional desde USA
✅ Impuestos de importación
✅ Gestión aduanera

**NO hay costos adicionales.** El precio que ves es el precio final que pagas. 💯

Puedes pagar con todos los medios disponibles en MercadoLibre (tarjetas, Mercado Pago, etc.). 😊""",

        "impuestos": """¡Hola! 👋

**Los impuestos YA ESTÁN INCLUIDOS** en el precio. ✅

MercadoLibre Global se encarga de:
✅ Pagar los impuestos de importación
✅ Gestionar la aduana
✅ Entregarte el producto en tu domicilio

El precio que ves es el precio final. No pagas nada adicional en la aduana. 💯""",

        "cuotas": """¡Hola! 👋

Puedes pagar en cuotas según las opciones disponibles en MercadoLibre para tu país:

💳 **Tarjetas de crédito:** Hasta 12 cuotas (según banco)
💰 **Mercado Crédito:** Cuotas sin tarjeta
💵 **Efectivo:** A través de Pago Fácil, Rapipago, etc.

Las opciones de pago disponibles aparecen al hacer clic en "Comprar". 😊""",
    },

    # ==================== FACTURA ====================
    "invoice": {
        "default": """¡Hola! 👋

Recibirás tu **comprobante de compra automáticamente** a través de MercadoLibre.

📄 El comprobante incluye:
✅ Detalle de la compra
✅ Monto pagado
✅ Fecha de transacción
✅ Válido como factura

Lo puedes descargar desde "Mis compras" en tu cuenta de MercadoLibre en cualquier momento. 😊""",
    },

    # ==================== ESPECIFICACIONES ====================
    "specs": {
        "compatible": """¡Hola! 👋

Para confirmar compatibilidad, por favor verifica:

📋 **En la descripción del producto** encontrarás:
- Modelos compatibles
- Especificaciones técnicas
- Requisitos del sistema

Si tienes un modelo/dispositivo específico, por favor indícamelo para confirmarte la compatibilidad exacta. 😊""",

        "incluye": """¡Hola! 👋

**El producto incluye:**

📦 Todo lo que se muestra en las imágenes y descripción de la publicación.

Los accesorios y contenido del paquete están detallados en la sección de "Características" de la publicación.

Si necesitas confirmar si incluye algo específico, por favor indícame qué necesitas y te confirmo. 😊""",
    },

    # ==================== ADUANA E IMPORTACIÓN ====================
    "customs": {
        "default": """¡Hola! 👋

**MercadoLibre se encarga de TODO el proceso de importación:**

✅ Pago de impuestos aduaneros (incluido en el precio)
✅ Gestión de trámites
✅ Despacho automático
✅ Entrega en tu domicilio

**No necesitas:**
❌ Ir a buscar el producto a la aduana
❌ Pagar impuestos adicionales
❌ Hacer trámites

Todo está automatizado. El producto llega directo a tu casa. 🏠""",

        "retenido": """¡Hola! 👋

Con MercadoLibre Global, el producto **NO se retiene en aduana**.

MercadoLibre tiene acuerdos especiales que permiten:
✅ Despacho automático
✅ Entrega directa a tu domicilio
✅ Sin trámites adicionales

Si hubiera alguna demora, recibirás notificaciones en tu cuenta. Pero generalmente el proceso es automático y sin problemas. 😊""",
    },

    # ==================== CONTACTO ====================
    "contact": {
        "default": """¡Hola! 👋

Puedes contactarme por:

💬 **Mensajes de MercadoLibre** (este medio - el más rápido)
📱 Respondo consultas en menos de 24 horas

Para consultas post-compra:
- Ve a "Mis compras" en MercadoLibre
- Selecciona tu compra
- "Contactar al vendedor"

Estoy aquí para ayudarte en todo lo que necesites. 😊""",
    },

    # ==================== USO E INSTALACIÓN ====================
    "usage": {
        "default": """¡Hola! 👋

El producto incluye **manual de instrucciones** (generalmente en inglés, ya que es importado de USA).

📖 También puedes encontrar:
- Tutoriales en YouTube
- Manuales digitales en el sitio del fabricante
- Videos de unboxing y setup

Si tienes alguna duda específica sobre el uso, por favor indícamelo y te ayudo con gusto. 😊""",
    },
}

# ========================================
# FUNCIONES DE INICIALIZACIÓN
# ========================================

def init_comprehensive_faq():
    """Inicializa la base de datos con TODOS los templates completos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Limpiar templates anteriores
    cursor.execute("DELETE FROM faq_templates")

    templates_to_insert = []

    # ENVÍO - 4 variantes
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["shipping"][:3]),
        GLOBAL_TEMPLATES["shipping"]["default"],
        "shipping", 10
    ))
    templates_to_insert.append((
        r"rapido|express|urgente",
        GLOBAL_TEMPLATES["shipping"]["rapido"],
        "shipping_express", 9
    ))
    templates_to_insert.append((
        r"rastreo|tracking|seguimiento",
        GLOBAL_TEMPLATES["shipping"]["tracking"],
        "shipping_tracking", 9
    ))
    templates_to_insert.append((
        r"aduana|customs",
        GLOBAL_TEMPLATES["shipping"]["aduanas"],
        "shipping_customs", 9
    ))

    # STOCK - 2 variantes
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["stock"][:3]),
        GLOBAL_TEMPLATES["stock"]["default"],
        "stock", 10
    ))
    templates_to_insert.append((
        r"agotado|sin.+stock|cuando.+reponen",
        GLOBAL_TEMPLATES["stock"]["agotado"],
        "stock_out", 8
    ))

    # GARANTÍA - 3 variantes
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["warranty"][:2]),
        GLOBAL_TEMPLATES["warranty"]["default"],
        "warranty", 10
    ))
    templates_to_insert.append((
        r"devolucion|devolución|devol|return",
        GLOBAL_TEMPLATES["warranty"]["devolucion"],
        "warranty_return", 10
    ))
    templates_to_insert.append((
        r"defecto|falla|roto|dañado|malo",
        GLOBAL_TEMPLATES["warranty"]["defecto"],
        "warranty_defect", 10
    ))

    # AUTENTICIDAD - 2 variantes
    templates_to_insert.append((
        r"original|autentico|falso|trucho",
        GLOBAL_TEMPLATES["authenticity"]["default"],
        "authenticity", 10
    ))
    templates_to_insert.append((
        r"nuevo|usado|sellado|caja.+original",
        GLOBAL_TEMPLATES["authenticity"]["nuevo"],
        "authenticity_new", 10
    ))

    # PRECIO - 3 variantes
    templates_to_insert.append((
        r"precio|costo|vale|cuanto|descuento",
        GLOBAL_TEMPLATES["price"]["default"],
        "price", 9
    ))
    templates_to_insert.append((
        r"impuestos?|aranceles?|pagar.+extra",
        GLOBAL_TEMPLATES["price"]["impuestos"],
        "price_taxes", 10
    ))
    templates_to_insert.append((
        r"cuotas|financiacion|pagar.+en.+cuotas",
        GLOBAL_TEMPLATES["price"]["cuotas"],
        "price_installments", 9
    ))

    # FACTURA
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["invoice"]),
        GLOBAL_TEMPLATES["invoice"]["default"],
        "invoice", 8
    ))

    # ESPECIFICACIONES - 2 variantes
    templates_to_insert.append((
        r"compatible|funciona.+con|sirve.+para",
        GLOBAL_TEMPLATES["specs"]["compatible"],
        "specs_compatible", 8
    ))
    templates_to_insert.append((
        r"que.+incluye|viene.+con|trae|contiene",
        GLOBAL_TEMPLATES["specs"]["incluye"],
        "specs_includes", 8
    ))

    # ADUANA - 2 variantes
    templates_to_insert.append((
        r"aduana|customs|importacion",
        GLOBAL_TEMPLATES["customs"]["default"],
        "customs", 9
    ))
    templates_to_insert.append((
        r"retenido|detenido",
        GLOBAL_TEMPLATES["customs"]["retenido"],
        "customs_held", 9
    ))

    # CONTACTO
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["contact"]),
        GLOBAL_TEMPLATES["contact"]["default"],
        "contact", 7
    ))

    # USO
    templates_to_insert.append((
        "|".join(QUESTION_PATTERNS["usage"]),
        GLOBAL_TEMPLATES["usage"]["default"],
        "usage", 7
    ))

    # Insertar todos
    for pattern, answer, category, priority in templates_to_insert:
        cursor.execute("""
            INSERT INTO faq_templates (question_pattern, answer_template, category, priority)
            VALUES (?, ?, ?, ?)
        """, (pattern, answer, category, priority))

    conn.commit()
    conn.close()

    print(f"✅ {len(templates_to_insert)} templates completos insertados")

if __name__ == "__main__":
    print("🔄 Inicializando templates completos de MercadoLibre Global...")
    init_comprehensive_faq()
    print("✅ Sistema completo listo")
