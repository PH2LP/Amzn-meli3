#!/usr/bin/env python3
"""Script para limpiar keywords duplicadas del archivo z Keywoards 9.txt"""

# Keywords a ELIMINAR
keywords_to_remove = [
    # Grupo 1 - Gaming
    "family game console accessories",
    "gaming console replacement components",
    "playstation 2 accessories",
    "playstation spare parts",
    "nintendo console replacement parts",
    "nintendo switch repair kits",
    "xbox gaming consoles",
    "xbox gaming controllers",
    "xbox repair parts",
    "sega gaming accessories",

    # Grupo 2 - Cámaras
    "cámara compacta digital",
    "cámara réflex digital",
    "camcorder carrying bags",
    "dual battery chargers for cameras",
    "long-lasting camera batteries",
    "rechargeable camera batteries",
    "cubre lente de cámara",
    "filtro de lente uv",
    "cápsulas adaptadoras de lentes",
    "compact flash memory cards",
    "high speed memory cards",
    "professional camera memory cards",
    "compact camera teleprompters",
    "dslr teleprompters",
    "portable teleprompters for cameras",
    "teleprompters with remote",
    "camera tripods and stabilizers",

    # Grupo 3 - Proyectores
    "home cinema projectors",
    "portable mini projectors",
    "ceiling projector mounts",
    "ceiling-mounted projector screens",
    "foldable electric screens",
    "foldable manual screens",
    "projector screen kits",
    "wall-mounted manual screens",
    "dustproof projector covers",

    # Grupo 4 - Instrumentos niños
    "children musical drum kits",
    "children's drum kit",
    "children's electric guitar",
    "children's guitar toys",
    "toy acoustic guitar",
    "children's organ toys",
    "children's piano playset",

    # Grupo 5 - Pretend play
    "children play ironing sets",
    "childrens dress-up laundry",
    "children play kitchen food",
    "children pretend cooking set",
    "children pretend play kitchen",
    "kids cooking toys",
    "kids pretend food toys",
    "children pretend supermarket toys",
    "kids supermarket checkout",
    "children pretend tool kits",
    "childrens tool set",
    "children pretend makeup kits",
    "children role play beauty kits",

    # Grupo 6 - Ortopédicos
    "breathable back brace support",
    "breathable lumbar support brace",
    "cushioned knee pads for volleyball",
    "breathable volleyball knee pads",
    "hinged knee brace for sports",
    "orthopedic splint for wrist support",
    "neck brace for neck pain",
    "orthopedic heel cushion pads",
    "gel heel cushions inserts",

    # Grupo 7 - Herramientas
    "electric drills",
    "impact drill sets",
    "cordless impact wrenches",
    "electric impact wrenches",
    "compact impact wrenches",
    "electric screwdrivers",
    "led light screwdrivers",
    "cordless tool kits",
    "electric tool kits",
    "electric tool set with case",
    "multi-piece tool kits",
    "multi-piece tool sets",
    "pneumatic sander machines",
    "heat guns for shrink wrap",
    "dual temperature heat guns",
    "electric paint guns",
    "handheld paint sprayers",
    "pneumatic paint sprayers",
    "drill mixers for home use",
    "handheld paint mixers",

    # Grupo 8 - Inflables
    "inflatable canoes",
    "floatation boards for swimming",
    "bodyboard boards",
    "inflatable pool loungers",
    "inflatable loungers for outdoors",
    "swimming pool inflatables",

    # Grupo 9 - Deportes acuáticos
    "wakeboarding accessories",
    "sports wakeboarding equipment",
    "windsurfing accessories",
    "windsurfing harnesses",
    "windsurfing sails",
    "ski equipment accessories",
    "diving belts",
    "diving gloves",
    "diving hoods",
    "dive knives",

    # Grupo 10 - Perros
    "dog chew toys",
    "dog toy balls",
    "dog toys interactive",
    "dog grooming gloves",
    "dog grooming scissors",
    "dog grooming shampoo",
    "dog deshedding tools",
    "dog obedience training tools",
    "slow feeder dog bowls",
    "dog agility equipment",
    "dog apparel accessories",
    "dog bandanas and scarves",

    # Grupo 11 - Gatos
    "cat muzzles adjustable",

    # Grupo 12 - PC
    "compact desktop pc",
    "desktop computer cases",
    "gaming pc cases",
    "rgb pc cases",

    # Grupo 13 - Gaming PC
    "silent typing keyboards",
    "gaming headphone stands",
    "gaming headset microphones",
    "gamepad controllers for pc",
    "usb computer mice",
    "ergonomic computer mice",
    "high-performance graphics cards",
    "quad-core processors",

    # Grupo 14 - LED
    "dimmable led bulbs",
    "energy efficient light bulbs",
    "led replacement bulbs",
    "colorful led strips for tv",
    "dimmable led strips for tv",
    "dimmable led strips",
    "usb led strip lighting",
    "led floodlight bulbs",
    "dimmable led flood lights",
    "waterproof led flood lights",
    "christmas light garlands",
    "decorative light garlands",
    "halloween decorative lights",
    "outdoor decor lights",
    "outdoor decorative lights",
    "led modular panels",
    "color changing led panels",
    "diy led light panels",
    "wall-mounted led panels",
    "led camping lanterns",
    "led emergency lantern",
    "portable camping lanterns",

    # Grupo 15 - Motos
    "full face motorcycle helmets",
    "motorcycle helmet replacement parts",
    "motorcycle saddle bags",
    "waterproof motorcycle backpacks",
    "wireless motorcycle alarms",
    "motorcycle luggage straps",
    "heavy duty motorcycle locks",
    "motorcycle speakers",

    # Grupo 16 - Bebés
    "manual baby bottle sterilizers",
    "microwave pacifier sterilizers",
    "electric pacifier sterilizers",
    "reusable breast milk bags",
    "large capacity diaper backpacks",
    "hooded baby robes",
    "tible cribs baby furniture",
    "portable baby potties",
    "white noise sound machine",
    "portable white noise machines",

    # Grupo 17 - Juegos mesa
    "childrens poker accessories",
    "children's foosball game set",

    # Grupo 18 - Cafeteras
    "programmable coffee makers",
    "coffee brewing equipment",

    # Grupo 19 - Cables
    "high speed data cables",
    "electronic connectors",
    "power connectors",
    "coaxial flat cables",
    "flexible television flat cables",

    # Grupo 20 - Micrófonos
    "recording microphones",
    "wireless camera microphone systems",
    "childrens karaoke mic",
    "megaphones with siren",

    # Grupo 21 - Seguridad (ajustados)
    "home safety security systems",
    "wireless perimeter alarms",
    "video doorbells with camera",
    "wireless monitoring systems",
    "wireless video monitor systems",

    # Grupo 22 - Manualidades (ajustados)
    "diy jewelry kits",
    "jewelry making materials",
    "jewelry making supplies",
    "candle making kits",
    "cheese making kits",

    # Grupo 23 - Fitness (ajustados)
    "cardio exercise machines",
    "compact stationary bikes",
    "fitness heart rate monitors",
    "fitness smartwatches",
    "smartbands with heart rate monitor",

    # Grupo 24 - Yoga
    "yoga blocks",
    "yoga blocks foam",

    # Grupo Alimentos
    "ice flake machines",
    "milk pasteurization machines",
    "dairy fermentation equipment",
    "dairy processing equipment",
    "meat tenderizers tools",
    "food processing machines",
    "butter churns home use",

    # Drones
    "dron plegable portátil",
]

# Keywords a AGREGAR
keywords_to_add = [
    "snowboard equipment",
    "ski and snowboard gear",
    "winter sports equipment",
]

# Leer archivo
with open('z Keywoards 9.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Filtrar keywords a eliminar (manteniendo líneas vacías)
cleaned_lines = []
removed_count = 0

for line in lines:
    keyword = line.strip()
    if keyword == "" or keyword not in keywords_to_remove:
        cleaned_lines.append(line)
    else:
        removed_count += 1
        print(f"Eliminado: {keyword}")

# Agregar nuevas keywords antes de la última línea vacía
if cleaned_lines and cleaned_lines[-1].strip() == "":
    # Insertar antes de la línea vacía final
    for new_kw in keywords_to_add:
        cleaned_lines.insert(-1, new_kw + "\n")
        print(f"Agregado: {new_kw}")
else:
    # Agregar al final
    for new_kw in keywords_to_add:
        cleaned_lines.append(new_kw + "\n")
        print(f"Agregado: {new_kw}")

# Guardar archivo limpio
with open('z Keywoards 9.txt', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print(f"\n✅ Limpieza completada!")
print(f"📊 Keywords eliminadas: {removed_count}")
print(f"➕ Keywords agregadas: {len(keywords_to_add)}")
print(f"📝 Total keywords final: {len([l for l in cleaned_lines if l.strip() != ''])}")
