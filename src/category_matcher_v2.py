"""
Category Matcher v2 - Sistema Híbrido de Detección de Categorías
Combina Embeddings (sentence-transformers) + IA (GPT-4o-mini)

Arquitectura:
1. CategoryDatabase: Gestiona base de datos de categorías CBT
2. EmbeddingMatcher: Búsqueda por similitud usando embeddings
3. AIValidator: Validación semántica con IA
4. CategoryMatcherV2: Orquestador principal

Autor: Pipeline v2.0
Fecha: 2025-11-04
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import requests
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI


# ═══════════════════════════════════════════════════════════════════════════
# 1. CATEGORY DATABASE - Storage Layer
# ═══════════════════════════════════════════════════════════════════════════

class CategoryDatabase:
    """
    Gestiona la base de datos local de categorías CBT
    - Descarga categorías de ML API
    - Cache local con TTL de 7 días
    - Persistencia en JSON
    """

    def __init__(self, cache_dir: str = "storage/category_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_file = self.cache_dir / "category_database.json"
        self.metadata_file = self.cache_dir / "category_metadata.json"
        self.embeddings_file = self.cache_dir / "category_embeddings.npy"

        self.categories: Dict = {}
        self.embeddings: Optional[np.ndarray] = None
        self.category_ids: List[str] = []

        self.ml_token = os.getenv('ML_ACCESS_TOKEN')
        self.refresh_interval_days = 7

    def load_or_fetch_categories(self, force_refresh: bool = False) -> Dict:
        """
        Carga categorías desde cache o las descarga de ML API
        """
        # Verificar si cache existe y es válido
        if not force_refresh and self._is_cache_valid():
            print("📦 Cargando categorías desde cache...")
            self.categories = self._load_from_cache()
            print(f"✅ {len(self.categories)} categorías CBT cargadas desde cache")
            return self.categories

        # Cache inválido o force refresh → descargar de ML
        print("🌐 Descargando categorías CBT desde MercadoLibre API...")
        self.categories = self._fetch_from_ml_api()

        # Guardar en cache
        self._save_to_cache()
        print(f"✅ {len(self.categories)} categorías CBT descargadas y guardadas en cache")

        return self.categories

    def _is_cache_valid(self) -> bool:
        """Verifica si el cache es válido (existe y no expiró)"""
        if not self.db_file.exists() or not self.metadata_file.exists():
            return False

        try:
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)

            last_updated = datetime.fromisoformat(metadata['last_updated'])
            expiry_date = last_updated + timedelta(days=self.refresh_interval_days)

            return datetime.now() < expiry_date
        except Exception as e:
            print(f"⚠️ Error verificando cache: {e}")
            return False

    def _load_from_cache(self) -> Dict:
        """Carga categorías desde archivo JSON"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                categories = json.load(f)

            # Cargar category_ids para mantener orden
            self.category_ids = list(categories.keys())

            return categories
        except Exception as e:
            print(f"❌ Error cargando cache: {e}")
            return {}

    def _fetch_from_ml_api(self) -> Dict:
        """
        Descarga todas las categorías CBT desde MercadoLibre API
        Usa el dump de categorías existente como base
        """
        categories = {}

        # Leer desde el dump existente
        dump_file = Path("resources/cbt_categories_all.json")

        if dump_file.exists():
            print(f"📂 Leyendo categorías desde dump: {dump_file}")
            try:
                with open(dump_file, 'r', encoding='utf-8') as f:
                    raw_categories = json.load(f)

                # Convertir a formato de database
                for cat_id, cat_data in raw_categories.items():
                    if not cat_id.startswith('CBT'):
                        continue

                    # Construir path desde path_from_root
                    path_parts = [p['name'] for p in cat_data.get('path_from_root', [])]
                    path_str = ' > '.join(path_parts) if path_parts else cat_data.get('name', '')

                    categories[cat_id] = {
                        'id': cat_id,
                        'name': cat_data.get('name', ''),
                        'path': path_str,
                        'path_from_root': cat_data.get('path_from_root', []),
                        'attributes_count': 0,  # No disponible en este formato
                        'required_attrs': [],  # Se puede obtener bajo demanda si es necesario
                        'embedding': None  # Se calculará después
                    }

                print(f"✅ {len(categories)} categorías CBT procesadas desde dump")

            except Exception as e:
                print(f"❌ Error leyendo dump: {e}")

        self.category_ids = list(categories.keys())
        return categories

    def _save_to_cache(self):
        """Guarda categorías en cache JSON"""
        try:
            # Guardar database
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.categories, f, ensure_ascii=False, indent=2)

            # Guardar metadata
            metadata = {
                'last_updated': datetime.now().isoformat(),
                'category_count': len(self.categories),
                'version': '2.0'
            }
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            print(f"💾 Cache guardado: {self.db_file}")

        except Exception as e:
            print(f"❌ Error guardando cache: {e}")

    def get_category(self, cbt_id: str) -> Optional[Dict]:
        """Obtiene categoría por ID"""
        return self.categories.get(cbt_id)

    def get_all_categories(self) -> Dict:
        """Retorna todas las categorías"""
        return self.categories

    def save_embeddings(self, embeddings: np.ndarray):
        """Guarda embeddings calculados"""
        try:
            np.save(self.embeddings_file, embeddings)
            self.embeddings = embeddings
            print(f"💾 Embeddings guardados: {self.embeddings_file}")
        except Exception as e:
            print(f"❌ Error guardando embeddings: {e}")

    def load_embeddings(self) -> Optional[np.ndarray]:
        """Carga embeddings desde archivo"""
        if self.embeddings_file.exists():
            try:
                self.embeddings = np.load(self.embeddings_file)
                print(f"📦 {len(self.embeddings)} embeddings cargados desde cache")
                return self.embeddings
            except Exception as e:
                print(f"❌ Error cargando embeddings: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 2. EMBEDDING MATCHER - Similarity Search
# ═══════════════════════════════════════════════════════════════════════════

class EmbeddingMatcher:
    """
    Genera embeddings y encuentra categorías similares
    Usa sentence-transformers para embeddings multilingües
    """

    def __init__(self, database: CategoryDatabase):
        self.database = database
        self.model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

        print(f"🤖 Cargando modelo de embeddings: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        print("✅ Modelo de embeddings cargado")

        self.category_embeddings: Optional[np.ndarray] = None

        # Cliente OpenAI para identificación de tipo de producto
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Token de MercadoLibre para verificar categorías
        self.ml_token = os.getenv('ML_ACCESS_TOKEN')

        # Cache de verificación de categorías leaf
        self.leaf_cache = {}

        self._build_index()

    def _build_index(self):
        """
        Construye índice de embeddings de categorías
        - Si existe cache → cargar
        - Si no existe → calcular y guardar
        """
        # Intentar cargar desde cache
        cached_embeddings = self.database.load_embeddings()

        if cached_embeddings is not None and len(cached_embeddings) == len(self.database.categories):
            self.category_embeddings = cached_embeddings
            print("✅ Usando embeddings desde cache")
            return

        # No hay cache → calcular embeddings
        print("🔨 Calculando embeddings para todas las categorías...")
        categories = self.database.get_all_categories()

        if not categories:
            print("⚠️ No hay categorías para calcular embeddings")
            return

        # Preparar textos para embedding
        texts = []
        for cat_id in self.database.category_ids:
            cat = categories[cat_id]
            text = self._category_to_text(cat)
            texts.append(text)

        # Calcular embeddings en batch
        start_time = time.time()
        self.category_embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            batch_size=32,
            convert_to_numpy=True
        )
        elapsed = time.time() - start_time

        print(f"✅ {len(self.category_embeddings)} embeddings calculados en {elapsed:.1f}s")

        # Guardar en cache
        self.database.save_embeddings(self.category_embeddings)

    def _category_to_text(self, category: Dict) -> str:
        """Convierte categoría a texto para embedding"""
        text = f"{category['name']} {category['path']}"
        return text

    def _identify_product_type_with_ai(self, title: str, product_hints: dict = None) -> str:
        """
        Usa IA para identificar el tipo exacto de producto y generar palabras clave
        optimizadas para el embedding

        Args:
            title: Título del producto
            product_hints: Hints adicionales del JSON de SP API (productType, browseClassification, etc.)
        """
        # Construir hints adicionales si existen
        hints_text = ""
        if product_hints:
            if product_hints.get('productType'):
                hints_text += f"\n- Amazon Product Type: {product_hints['productType']}"
            if product_hints.get('browseClassification'):
                hints_text += f"\n- Amazon Browse Category: {product_hints['browseClassification']}"
            if product_hints.get('item_type_keyword'):
                hints_text += f"\n- Item Type Keyword: {product_hints['item_type_keyword']}"

        prompt = f"""Analiza este título de producto e identifica su CATEGORÍA EN MERCADOLIBRE.

TÍTULO: {title}
{hints_text}

TAREA: Responde SOLO con 3-5 palabras clave en INGLÉS que describan la CATEGORÍA genérica del producto.

REGLAS CRÍTICAS:
1. **RELOJES - Distinguir tipo exacto**:
   - "Smartwatch" o "Apple Watch" o "Galaxy Watch" → di "smartwatch" (tiene conectividad/apps)
   - "Digital Watch" o "Sport Watch" SIN mencionar apps/Bluetooth → di "digital wristwatch" (NO es smartwatch)
   - "GPS Running Watch" (Garmin, etc) → "smartwatch fitness" SI tiene conectividad
   - productType="WRIST_WATCH" + browseClassification="Wrist Watches" → "wristwatch" (genérico)

2. Un "Building Set" o "LEGO" o productType="TOY_BUILDING_BLOCK" ES un "building toy" → di "building toy"
3. "Bluetooth Earphones" o "Headphones" o productType="HEADPHONES" ES "headphones" → di "headphones"
4. "Earrings" o "Pendientes" ES "jewelry" → di "jewelry earrings"
5. productType="RECREATION_BALL" → di "sports ball"
6. productType="SKIN_TREATMENT_MASK" → di "facial mask"
7. Usa el nombre GENÉRICO de la categoría, NO las características específicas

EJEMPLOS CORRECTOS:
- "Garmin Forerunner 55, GPS Running Watch with Bluetooth" → "smartwatch wearable fitness" (tiene conectividad)
- "Apple Watch Series 8 GPS" → "smartwatch wearable" (es smartwatch)
- "GOLDEN HOUR Digital Sport Watch" (browseClassification: Wrist Watches, NO menciona apps/Bluetooth) → "digital wristwatch sport" (NO es smartwatch)
- "Casio Sport Watch Waterproof" → "digital wristwatch" (NO es smartwatch)
- "LEGO Creator 3 in 1 Building Set" (productType: TOY_BUILDING_BLOCK) → "building toy playset"
- "Samsung Galaxy Buds Bluetooth" (productType: HEADPHONES) → "headphones earbuds audio"
- "Basketball Ball Size 3" (productType: RECREATION_BALL) → "sports ball basketball"
- "Korean Face Mask" (productType: SKIN_TREATMENT_MASK) → "facial mask skincare"
- "Nail Polish" → "nail polish cosmetics" (NO "nail polish racks")

IMPORTANTE: Responde SOLO las palabras clave, nada más:"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=30,
                messages=[{"role": "user", "content": prompt}]
            )

            keywords = response.choices[0].message.content.strip()
            print(f"   🔍 IA identificó tipo: '{keywords}'")
            return keywords

        except Exception as e:
            print(f"   ⚠️ Error en identificación IA: {e}")
            return ""

    def _product_to_text(self, product: Dict) -> str:
        """Convierte producto a texto para embedding, priorizando el título"""
        parts = []

        # PRIORIDAD 1: Título (repetido 3 veces para dar más peso)
        if product.get('title'):
            title = product['title']
            parts.append(f"{title}")  # Repetir 3 veces para dar más peso semántico
            parts.append(f"{title}")
            parts.append(f"{title}")

            # BOOST DIRECTO: Keywords desde productType y browseClassification de SP API
            sp_keywords = []

            if product.get('productType'):
                product_type = product['productType']
                # Mapeo de productType de Amazon → keywords para MercadoLibre
                type_mapping = {
                    'TOY_BUILDING_BLOCK': 'building toy blocks construction',
                    'HEADPHONES': 'headphones audio electronics wireless',
                    'GPS_OR_NAVIGATION_SYSTEM': 'smartwatch wearable gps fitness',
                    'WRIST_WATCH': 'watch wristwatch timepiece',
                    'RECREATION_BALL': 'sports ball recreation',
                    'SKIN_TREATMENT_MASK': 'facial mask skincare treatment',
                    'SKIN_CARE_AGENT': 'skincare beauty cosmetics',
                    'NAIL_POLISH_BASE_COAT': 'nail polish cosmetics beauty',
                    'ART_CRAFT_KIT': 'craft kit art creative',
                }
                if product_type in type_mapping:
                    sp_keywords.append(type_mapping[product_type])
                    print(f"   📦 ProductType hint: {product_type} → {type_mapping[product_type]}")
                else:
                    # FALLBACK: Convertir productType a keywords automáticamente
                    fallback_keywords = product_type.lower().replace('_', ' ')
                    sp_keywords.append(fallback_keywords)
                    print(f"   📦 ProductType hint (fallback): {product_type} → {fallback_keywords}")

            if product.get('browseClassification'):
                browse = product['browseClassification']
                # Mapeo de browseClassification → keywords
                browse_mapping = {
                    'Wrist Watches': 'watch wristwatch timepiece',
                    'Running GPS Units': 'smartwatch gps running fitness',
                    'Building Blocks': 'building toy blocks construction',
                    'Headphones': 'headphones audio electronics',
                    'Nail Polish': 'nail polish cosmetics beauty',
                    'Face Masks': 'facial mask skincare',
                }
                for key, keywords in browse_mapping.items():
                    if key.lower() in browse.lower():
                        sp_keywords.append(keywords)
                        print(f"   🏷️  Browse hint: {browse} → {keywords}")
                        break

            # Agregar keywords de SP API (repetir 3 veces)
            for kw in sp_keywords:
                for _ in range(3):
                    parts.append(kw)

            # BOOST CON IA: Identificar tipo exacto de producto y agregar palabras clave
            # Extraer hints del producto si están disponibles
            product_hints = {}
            if product.get('productType'):
                product_hints['productType'] = product['productType']
            if product.get('browseClassification'):
                product_hints['browseClassification'] = product['browseClassification']
            if product.get('item_type_keyword'):
                product_hints['item_type_keyword'] = product['item_type_keyword']

            ai_keywords = self._identify_product_type_with_ai(title, product_hints if product_hints else None)
            if ai_keywords:
                # Repetir 5 veces para dar MUCHO peso a las palabras clave de IA
                for _ in range(5):
                    parts.append(ai_keywords)

        # PRIORIDAD 2: Marca
        if product.get('brand'):
            parts.append(f"Marca: {product['brand']}")

        # PRIORIDAD 3: Características principales (bullet points)
        if product.get('features'):
            # Manejar tanto listas de strings como listas de dicts
            features_list = product['features'][:5]
            if features_list and isinstance(features_list[0], dict):
                # Es lista de dicts con formato {id, name, value_name}
                features = ', '.join([f"{f.get('name', '')}: {f.get('value_name', '')}" for f in features_list if isinstance(f, dict)])
            elif features_list and isinstance(features_list[0], str):
                # Es lista de strings
                features = ', '.join(features_list)
            else:
                features = ''

            if features:
                parts.append(f"Características: {features}")

        # PRIORIDAD 4: Descripción (limitada y con menos peso)
        if product.get('description'):
            desc = product['description'][:300]  # Reducido de 500 a 300 chars
            parts.append(f"Descripción: {desc}")

        return ' '.join(parts)

    def find_similar_categories(
        self,
        product: Dict,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Encuentra las top K categorías más similares al producto

        Returns:
            List de dicts con: {category_id, similarity_score, category_data}
        """
        if self.category_embeddings is None:
            print("❌ No hay embeddings disponibles")
            return []

        # Generar embedding del producto
        product_text = self._product_to_text(product)
        product_embedding = self.model.encode(
            [product_text],
            convert_to_numpy=True
        )[0]

        # Calcular similitud coseno con todas las categorías
        similarities = self._cosine_similarity(
            product_embedding,
            self.category_embeddings
        )

        # Obtener top K índices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Construir resultado
        results = []
        categories = self.database.get_all_categories()

        for idx in top_indices:
            cat_id = self.database.category_ids[idx]
            cat_data = categories[cat_id]

            results.append({
                'category_id': cat_id,
                'similarity_score': float(similarities[idx]),
                'category_data': cat_data
            })

        # POST-PROCESAMIENTO: Forzar inclusión de categorías específicas según AI identification
        # Extraer título para re-identificar
        if product.get('title'):
            title = product['title']
            ai_keywords = self._identify_product_type_with_ai(title)

            # Mapeo de palabras clave AI → categorías CBT a forzar
            forced_categories = {}

            if 'smartwatch' in ai_keywords.lower():
                # Incluir categorías Smartwatch específicas
                forced_categories.update({
                    'CBT352679': 0.55,  # Smartwatches (Cell Phones)
                    'CBT399230': 0.54,  # Smartwatches (Watches)
                })
                print(f"   💡 Forzando inclusión de categorías Smartwatch")
            elif 'wristwatch' in ai_keywords.lower() or ('watch' in ai_keywords.lower() and 'smart' not in ai_keywords.lower()):
                # Es un reloj digital/deportivo, NO smartwatch
                forced_categories.update({
                    'CBT1442': 0.56,  # Wristwatches (relojes digitales/deportivos)
                })
                print(f"   💡 Forzando inclusión de categorías Wristwatches (digital/sport)")

            if 'building toy' in ai_keywords.lower() or 'playset' in ai_keywords.lower():
                forced_categories.update({
                    'CBT455425': 0.90,  # Building Toys (PADRE - el filtro LEAF obtendrá sus hijos automáticamente)
                })
                print(f"   💡 Forzando inclusión de categorías Building Toys")

            if 'headphones' in ai_keywords.lower() or 'earbuds' in ai_keywords.lower():
                forced_categories.update({
                    'CBT3697': 0.60,    # Headphones
                })
                print(f"   💡 Forzando inclusión de categorías Headphones")

            if 'jewelry' in ai_keywords.lower() and 'earring' in ai_keywords.lower():
                forced_categories.update({
                    'CBT457415': 0.60,  # Earrings
                })
                print(f"   💡 Forzando inclusión de categorías Earrings")

            if 'nail polish' in ai_keywords.lower():
                forced_categories.update({
                    'CBT29890': 0.60,  # Nail Polish (el producto, no accesorios)
                })
                print(f"   💡 Forzando inclusión de categorías Nail Polish (producto principal)")

            # Insertar categorías forzadas en los resultados
            for cat_id, forced_sim in forced_categories.items():
                if cat_id in categories and cat_id not in [r['category_id'] for r in results]:
                    results.insert(0, {
                        'category_id': cat_id,
                        'similarity_score': forced_sim,
                        'category_data': categories[cat_id],
                        'forced': True  # Marcar como forzada
                    })

        # FILTRAR SOLO CATEGORÍAS LEAF antes de retornar
        print(f"   🔍 Filtrando categorías para quedarse solo con LEAF (hojas)...")
        results = self._filter_leaf_categories(results[:top_k])

        return results[:top_k]  # Mantener solo top_k después de filtrar

    def _is_leaf_category(self, cat_id: str) -> bool:
        """
        Verifica si una categoría es LEAF (hoja) consultando la API de MercadoLibre
        Una categoría es leaf si NO tiene subcategorías (children_categories == 0)

        Returns:
            True si es leaf (puede publicar), False si es padre (tiene hijos)
        """
        # Verificar cache primero
        if cat_id in self.leaf_cache:
            return self.leaf_cache[cat_id]

        try:
            url = f"https://api.mercadolibre.com/categories/{cat_id}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                children = data.get('children_categories', [])
                is_leaf = len(children) == 0

                # Guardar en cache
                self.leaf_cache[cat_id] = is_leaf

                return is_leaf
            else:
                print(f"   ⚠️ Error verificando categoría {cat_id}: HTTP {response.status_code}")
                # En caso de error, asumir que es leaf para no bloquear
                return True

        except Exception as e:
            print(f"   ⚠️ Error verificando categoría {cat_id}: {e}")
            # En caso de error, asumir que es leaf para no bloquear
            return True

    def _get_category_children(self, cat_id: str) -> List[str]:
        """
        Obtiene los IDs de las subcategorías (hijos) de una categoría

        Returns:
            Lista de IDs de subcategorías
        """
        try:
            url = f"https://api.mercadolibre.com/categories/{cat_id}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                children = data.get('children_categories', [])
                return [child['id'] for child in children]
            else:
                return []

        except Exception as e:
            print(f"   ⚠️ Error obteniendo hijos de {cat_id}: {e}")
            return []

    def _filter_leaf_categories(self, candidates: List[Dict]) -> List[Dict]:
        """
        Filtra candidatos para quedarse SOLO con categorías LEAF.
        Si encuentra categorías PADRE con buena similitud, DESCIENDE a sus hijos.

        Args:
            candidates: Lista de candidatos de find_similar_categories

        Returns:
            Lista con categorías leaf (originales + hijos de padres)
        """
        leaf_candidates = []
        parent_candidates = []
        categories_db = self.database.get_all_categories()

        for candidate in candidates:
            cat_id = candidate['category_id']
            is_leaf = self._is_leaf_category(cat_id)

            if is_leaf:
                leaf_candidates.append(candidate)
            else:
                parent_candidates.append(candidate)

        # DESCENSO AUTOMÁTICO: Si hay categorías PADRE, obtener sus hijos
        if parent_candidates:
            print(f"   🌿 Encontradas {len(parent_candidates)} categorías PADRE (no-leaf)")

            for parent in parent_candidates[:5]:  # Procesar top 5 padres
                cat_id = parent['category_id']
                cat_name = parent['category_data']['name']
                parent_sim = parent['similarity_score']

                print(f"      🔽 {cat_id} '{cat_name}' (sim: {parent_sim:.3f}) → Obteniendo hijos...")

                # Obtener hijos
                children_ids = self._get_category_children(cat_id)

                if children_ids:
                    print(f"         📁 {len(children_ids)} subcategorías encontradas")

                    # Agregar hijos como candidatos con similitud heredada del padre
                    # IMPORTANTE: Solo agregar si el hijo es LEAF (0 hijos)
                    for child_id in children_ids:
                        if child_id in categories_db:
                            # Verificar si este hijo es LEAF antes de agregarlo
                            if self._is_leaf_category(child_id):
                                # Heredar similitud del padre, reducida en 0.02 (mínima penalización)
                                child_sim = parent_sim - 0.02

                                leaf_candidates.append({
                                    'category_id': child_id,
                                    'similarity_score': child_sim,
                                    'category_data': categories_db[child_id],
                                    'inherited_from': cat_id  # Marcar que viene de un padre
                                })

                                child_name = categories_db[child_id]['name']
                                print(f"         ✅ Agregado hijo LEAF: {child_id} '{child_name}' (sim: {child_sim:.3f})")
                            else:
                                # Si el hijo también es PADRE, descender recursivamente a sus hijos
                                child_name = categories_db[child_id]['name']
                                print(f"         ⚠️ Hijo {child_id} '{child_name}' es PADRE → descendiendo...")
                                grandchildren_ids = self._get_category_children(child_id)
                                if grandchildren_ids:
                                    for grandchild_id in grandchildren_ids:
                                        if grandchild_id in categories_db and self._is_leaf_category(grandchild_id):
                                            # Heredar similitud del abuelo, con doble penalización
                                            grandchild_sim = parent_sim - 0.04
                                            leaf_candidates.append({
                                                'category_id': grandchild_id,
                                                'similarity_score': grandchild_sim,
                                                'category_data': categories_db[grandchild_id],
                                                'inherited_from': f"{cat_id} > {child_id}"
                                            })
                                            grandchild_name = categories_db[grandchild_id]['name']
                                            print(f"            ✅ Agregado nieto LEAF: {grandchild_id} '{grandchild_name}' (sim: {grandchild_sim:.3f})")
                else:
                    print(f"         ⚠️ No se pudieron obtener hijos")

        # Ordenar por similitud después de agregar hijos
        leaf_candidates.sort(key=lambda x: x['similarity_score'], reverse=True)

        if leaf_candidates:
            print(f"   ✅ {len(leaf_candidates)} categorías LEAF válidas (originales + hijos de padres)")
        else:
            print(f"   ⚠️ NO se encontraron categorías leaf! Usando todas como fallback")
            # Si no hay ninguna leaf, retornar todas (para evitar que el sistema se rompa)
            return candidates

        return leaf_candidates

    def _cosine_similarity(
        self,
        vec1: np.ndarray,
        vec2: np.ndarray
    ) -> np.ndarray:
        """Calcula similitud coseno entre un vector y una matriz"""
        # Normalizar vectores
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2, axis=1, keepdims=True)

        # Producto punto = similitud coseno
        return np.dot(vec2_norm, vec1_norm)


# ═══════════════════════════════════════════════════════════════════════════
# 3. AI VALIDATOR - Semantic Validation
# ═══════════════════════════════════════════════════════════════════════════

class AIValidator:
    """
    Valida y selecciona la mejor categoría usando IA
    Usa GPT-4o-mini para análisis semántico
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"
        self.temperature = 0.1
        self.max_tokens = 300

    def validate_and_select(
        self,
        product: Dict,
        candidates: List[Dict]
    ) -> Dict:
        """
        Valida candidatos y selecciona el mejor usando IA

        Args:
            product: Datos del producto
            candidates: Lista de categorías candidatas (de EmbeddingMatcher)

        Returns:
            {category_id, confidence, reasoning, alternative}
        """
        if not candidates:
            return {
                'category_id': None,
                'confidence': 0.0,
                'reasoning': 'No hay candidatos disponibles',
                'method': 'none'
            }

        # Construir prompt
        prompt = self._build_prompt(product, candidates)

        try:
            # Llamar a IA
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            # Parsear respuesta
            result = json.loads(response.choices[0].message.content)

            # Validar que category_id esté en candidatos
            valid_ids = [c['category_id'] for c in candidates]
            if result['category_id'] not in valid_ids:
                print(f"⚠️ IA retornó categoría inválida: {result['category_id']}")
                # Usar primer candidato como fallback
                result = {
                    'category_id': candidates[0]['category_id'],
                    'confidence': candidates[0]['similarity_score'],
                    'reasoning': 'Fallback: IA retornó categoría no válida',
                    'method': 'fallback'
                }
            else:
                result['method'] = 'ai_validated'

            return result

        except Exception as e:
            print(f"❌ Error en validación IA: {e}")
            # Fallback al primer candidato
            return {
                'category_id': candidates[0]['category_id'],
                'confidence': candidates[0]['similarity_score'],
                'reasoning': f'Fallback: Error IA - {str(e)}',
                'method': 'fallback'
            }

    def _build_prompt(self, product: Dict, candidates: List[Dict]) -> str:
        """Construye prompt para la IA"""

        # Extraer hints de SP API si existen
        sp_hints = ""
        if product.get('productType'):
            sp_hints += f"\n📦 Amazon ProductType: {product['productType']}"
        if product.get('browseClassification'):
            sp_hints += f"\n🏷️  Amazon Browse Category: {product['browseClassification']}"

        # Formatear candidatos con más detalle
        candidates_text = ""
        for i, candidate in enumerate(candidates[:10], 1):
            cat = candidate['category_data']
            sim = candidate['similarity_score']

            # Determinar si es hoja o padre
            is_leaf = len(cat.get('children_categories', [])) == 0
            category_type = "🍃 HOJA (específica)" if is_leaf else "📁 PADRE (genérica)"

            # Detectar si es accesorio
            is_accessory = any(word in cat['name'].lower() for word in ['rack', 'holder', 'stand', 'case', 'bag', 'box', 'accessories', 'kit', 'parts', 'repair'])
            accessory_flag = " ⚠️ ACCESORIO" if is_accessory else ""

            candidates_text += f"{i}. ID: {candidate['category_id']} {category_type}{accessory_flag}\n"
            candidates_text += f"   Nombre: {cat['name']}\n"
            candidates_text += f"   Path: {cat['path']}\n"
            candidates_text += f"   Similitud: {sim:.3f}\n"
            if cat['required_attrs']:
                candidates_text += f"   Atributos requeridos: {', '.join(cat['required_attrs'][:3])}\n"
            candidates_text += "\n"

        prompt = f"""Eres un experto en categorización de productos para MercadoLibre con 10 años de experiencia.

╔══════════════════════════════════════════════════════════════╗
║                    PRODUCTO A CATEGORIZAR                    ║
╚══════════════════════════════════════════════════════════════╝

📌 TÍTULO: {product.get('title', 'N/A')}
🏷️ MARCA: {product.get('brand', 'N/A')}
📝 DESCRIPCIÓN: {product.get('description', 'N/A')[:250]}{sp_hints}

╔══════════════════════════════════════════════════════════════╗
║           CANDIDATOS (Top {len(candidates)} por similitud)              ║
╚══════════════════════════════════════════════════════════════╝

{candidates_text}

╔══════════════════════════════════════════════════════════════╗
║                   INSTRUCCIONES CRÍTICAS                     ║
╚══════════════════════════════════════════════════════════════╝

Tu tarea es seleccionar LA MEJOR categoría del listado de candidatos arriba.

🎯 REGLA #1: TIPO DE PRODUCTO vs TEMA/DECORACIÓN
   El título describe DOS cosas: (1) QUÉ ES el producto y (2) DE QUÉ TEMA/DECORACIÓN es

   **SIEMPRE prioriza QUÉ ES sobre DE QUÉ ES:**

   ✅ CORRECTO - Priorizar tipo de producto:
   - "LEGO Bonsai Trees Building Set" → ES un **building toy** (juguete construcción), NO es una planta
   - "LEGO Dried Flower Centerpiece" → ES un **building toy**, NO es decoración floral
   - "Nail Polish Pink" → ES **esmalte de uñas**, NO accesorios de esmalte
   - "Basketball Ball" → ES una **pelota**, NO un aro
   - "Digital Sport Watch" (sin Bluetooth/apps) → ES **reloj digital** (Wristwatches), NO smartwatch
   - "Smartwatch" o "Apple Watch" → ES **smartwatch** con conectividad

   ❌ INCORRECTO - Confundir tema con tipo:
   - "LEGO Bonsai Building Set" → NO es "planta" o "growing kit", ES "building toy"
   - "Disney Nightmare Building Set" → NO es "decoración", ES "building toy"

🚫 REGLA #2: NUNCA ELEGIR ACCESORIOS NI CONFUNDIR TEMA CON TIPO

   **A. NO elegir accesorios del producto principal:**
   - "Nail Polish" ≠ "Nail Polish Racks" (rack es accesorio)
   - "Headphones" ≠ "Headphone Cases" (case es accesorio)
   - "Watch" ≠ "Watch Batteries" (batería es accesorio)
   - ⚠️ Candidatos marcados con "ACCESORIO" tienen MENOR prioridad

   **B. NO confundir tema decorativo con tipo de producto:**
   - "LEGO Bonsai" → tipo: building toy, tema: bonsai → elige "Building Toys", NO "Plants"
   - "LEGO Flowers" → tipo: building toy, tema: flores → elige "Building Toys", NO "Decorations"
   - Palabras como "LEGO", "Building Set", "Kit", productType="TOY_BUILDING_BLOCK" indican el TIPO real

📊 REGLA #3: PREFERIR CATEGORÍAS HOJA QUE COINCIDAN CON EL TIPO
   - Categorías "🍃 HOJA" específicas y correctas → PREFERIR SIEMPRE
   - Categorías "📁 PADRE" genéricas → usar solo si no hay hoja apropiada
   - ⚠️ PERO: Una hoja incorrecta (tema) < padre correcto (tipo)

   **Ejemplos:**
   - "LEGO Bonsai Building Set": "Building Blocks" (hoja, tipo correcto) > "Indoor Growing Kits" (hoja, tema confuso)
   - Si hay duda, prefiere la categoría cuyo path contenga el tipo de producto

🔍 REGLA #4: ANÁLISIS DEL PATH JERÁRQUICO
   - El path muestra la jerarquía: "Categoría Padre > Subcategoría > Específica"
   - Paths más largos = más específicos = generalmente mejores
   - Verifica que el path tenga sentido lógico para el producto

✅ REGLA #5: USAR HINTS DE AMAZON (MÁXIMA PRIORIDAD)
   Los hints de Amazon son **LA VERDAD DEFINITIVA** sobre el tipo de producto:

   - productType="TOY_BUILDING_BLOCK" → **ES juguete de construcción** sin importar el tema (bonsai, flores, etc)
   - browseClassification="Wrist Watches" → **ES reloj de pulsera**
   - browseClassification="Nail Polish" → **ES esmalte**, NO racks
   - productType="HEADPHONES" → **ES auriculares**, NO accesorios

   ⚠️ Si los hints dicen "TOY_BUILDING_BLOCK", IGNORA temas como "plants", "flowers", "decoration"

╔══════════════════════════════════════════════════════════════╗
║                      EJEMPLOS CORRECTOS                      ║
╚══════════════════════════════════════════════════════════════╝

❌ INCORRECTO:
   Título: "LONDONTOWN Nail Polish"
   Categoría elegida: "Nail Polish Racks" ← ERROR! Es el accesorio, no el producto

✅ CORRECTO:
   Título: "LONDONTOWN Nail Polish"
   browseClassification: "Nail Polish"
   Categoría elegida: "Nail Polish" ← Correcto! Es el producto principal

❌ INCORRECTO:
   Título: "Basketball Ball Size 3"
   Categoría elegida: "Basketball Hoops" ← ERROR! Aro no es pelota

✅ CORRECTO:
   Título: "Basketball Ball Size 3"
   productType: "RECREATION_BALL"
   Categoría elegida: "Balls" ← Correcto! Es una pelota

❌ INCORRECTO:
   Título: "GOLDEN HOUR Digital Sport Watch" (sin mencionar apps/Bluetooth)
   Categoría elegida: "Smartwatches" ← ERROR! NO es smartwatch, es reloj digital

✅ CORRECTO:
   Título: "GOLDEN HOUR Digital Sport Watch"
   browseClassification: "Wrist Watches"
   Categoría elegida: "Wristwatches" ← Correcto! Es reloj digital deportivo

❌ INCORRECTO:
   Título: "LEGO Botanicals Mini Bonsai Trees Building Set"
   productType: "TOY_BUILDING_BLOCK"
   Categoría elegida: "Indoor Growing Kits" ← ERROR! Se confundió con el tema "bonsai/trees"

✅ CORRECTO:
   Título: "LEGO Botanicals Mini Bonsai Trees Building Set"
   productType: "TOY_BUILDING_BLOCK"
   Categoría elegida: "Building Blocks & Figures" ← Correcto! Es un juguete LEGO, el tema es decorativo

╔══════════════════════════════════════════════════════════════╗
║                   FORMATO DE RESPUESTA                       ║
╚══════════════════════════════════════════════════════════════╝

{{
  "category_id": "CBT123456",
  "confidence": 0.95,
  "reasoning": "Elegí [Nombre Categoría] porque: (1) El título '{product.get('title', '')[:50]}...' describe [tipo exacto de producto], (2) Esta categoría es específica/hoja para [tipo], (3) El path '[path]' es coherente, (4) [Hint de SP API si aplica]",
  "alternative": "CBT789012"
}}

⚠️ IMPORTANTE:
- Responde SOLO con JSON válido
- NO agregues texto antes o después del JSON
- La categoría DEBE existir en el listado de candidatos arriba
- Si hay duda entre varias, elige la más específica (hoja) que NO sea accesorio
"""
        return prompt


# ═══════════════════════════════════════════════════════════════════════════
# 4. CATEGORY MATCHER V2 - Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class CategoryMatcherV2:
    """
    Orquestador principal del sistema híbrido
    Combina embeddings + IA para detección precisa de categorías
    """

    def __init__(self, cache_dir: str = "storage/category_cache"):
        print("\n" + "="*70)
        print("🚀 INICIALIZANDO CATEGORY MATCHER V2")
        print("="*70)

        # Inicializar componentes
        self.database = CategoryDatabase(cache_dir)
        self.database.load_or_fetch_categories()

        self.embedder = EmbeddingMatcher(self.database)
        self.validator = AIValidator()

        print("="*70)
        print("✅ CATEGORY MATCHER V2 LISTO")
        print("="*70 + "\n")

    def find_category(
        self,
        product_data: Dict,
        top_k: int = 30,  # Aumentado de 10 a 30 para incluir más opciones
        min_confidence: float = 0.7,
        use_ai: bool = True
    ) -> Dict:
        """
        Encuentra la mejor categoría para un producto

        Args:
            product_data: Datos del producto (title, description, brand, etc)
            top_k: Número de candidatos para IA (default: 10)
            min_confidence: Confianza mínima aceptable (default: 0.7)
            use_ai: Usar validación IA (default: True)

        Returns:
            {
                'category_id': 'CBT123456',
                'category_name': 'Headphones',
                'category_path': 'Electronics > Audio > Headphones',
                'confidence': 0.95,
                'method': 'hybrid' | 'embedding_only' | 'fallback',
                'reasoning': '...',
                'candidates_considered': 10,
                'processing_time_ms': 250
            }
        """
        start_time = time.time()

        # Fase 1: Similarity search con embeddings
        print(f"🔍 Fase 1: Buscando top {top_k} categorías similares...")
        phase1_start = time.time()
        candidates = self.embedder.find_similar_categories(product_data, top_k)
        phase1_time = (time.time() - phase1_start) * 1000

        if not candidates:
            return self._empty_result()

        print(f"✅ Top {len(candidates)} candidatos encontrados (similarity: {candidates[0]['similarity_score']:.3f})")

        # Fase 2: Validación con IA (opcional)
        if use_ai:
            print("🤖 Fase 2: Validación con IA...")
            phase2_start = time.time()
            ai_result = self.validator.validate_and_select(product_data, candidates)
            phase2_time = (time.time() - phase2_start) * 1000

            # Construir resultado final
            result = self._build_result(
                ai_result,
                candidates,
                phase1_time,
                phase2_time,
                start_time
            )
        else:
            # Solo embeddings, sin IA
            result = self._build_result_embedding_only(
                candidates[0],
                candidates,
                phase1_time,
                start_time
            )

        # Log resultado
        print(f"✅ Categoría seleccionada: {result['category_id']} ({result['category_name']})")
        print(f"   Confianza: {result['confidence']:.2f} | Método: {result['method']}")
        print(f"   Tiempo: {result['processing_time_ms']:.0f}ms")

        return result

    def _build_result(
        self,
        ai_result: Dict,
        candidates: List[Dict],
        phase1_time: float,
        phase2_time: float,
        start_time: float
    ) -> Dict:
        """Construye resultado final con metadata"""
        category_id = ai_result['category_id']
        category = self.database.get_category(category_id)

        if not category:
            # Fallback al primer candidato
            category_id = candidates[0]['category_id']
            category = self.database.get_category(category_id)
            ai_result['method'] = 'fallback'

        total_time = (time.time() - start_time) * 1000

        return {
            'category_id': category_id,
            'category_name': category['name'],
            'category_path': category['path'],
            'confidence': ai_result['confidence'],
            'method': ai_result['method'],
            'reasoning': ai_result.get('reasoning', ''),
            'alternative': ai_result.get('alternative'),
            'candidates_considered': len(candidates),
            'phase1_time_ms': phase1_time,
            'phase2_time_ms': phase2_time,
            'processing_time_ms': total_time,
            'embedding_similarity_top1': candidates[0]['similarity_score']
        }

    def _build_result_embedding_only(
        self,
        best_candidate: Dict,
        candidates: List[Dict],
        phase1_time: float,
        start_time: float
    ) -> Dict:
        """Construye resultado cuando solo se usan embeddings"""
        category_id = best_candidate['category_id']
        category = self.database.get_category(category_id)
        total_time = (time.time() - start_time) * 1000

        return {
            'category_id': category_id,
            'category_name': category['name'],
            'category_path': category['path'],
            'confidence': best_candidate['similarity_score'],
            'method': 'embedding_only',
            'reasoning': 'Categoría seleccionada por similitud de embeddings',
            'candidates_considered': len(candidates),
            'phase1_time_ms': phase1_time,
            'phase2_time_ms': 0,
            'processing_time_ms': total_time,
            'embedding_similarity_top1': best_candidate['similarity_score']
        }

    def _empty_result(self) -> Dict:
        """Retorna resultado vacío en caso de error"""
        return {
            'category_id': None,
            'category_name': None,
            'category_path': None,
            'confidence': 0.0,
            'method': 'none',
            'reasoning': 'No se pudo encontrar categoría',
            'candidates_considered': 0,
            'processing_time_ms': 0
        }


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def test_category_matcher():
    """Función de prueba para Category Matcher V2"""

    # Inicializar matcher
    matcher = CategoryMatcherV2()

    # Producto de prueba
    product = {
        'title': 'Auriculares Bluetooth Inalámbricos con Cancelación de Ruido',
        'description': 'Auriculares over-ear con audio de alta calidad, batería de 30 horas, bluetooth 5.0 y cancelación activa de ruido',
        'brand': 'Sony',
        'features': [
            'Bluetooth 5.0',
            'Cancelación de ruido activa',
            'Batería 30 horas',
            'Over-ear',
            'Micrófono integrado'
        ]
    }

    # Buscar categoría
    result = matcher.find_category(product)

    print("\n" + "="*70)
    print("📊 RESULTADO DE PRUEBA")
    print("="*70)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("="*70 + "\n")

    return result


if __name__ == "__main__":
    # Ejecutar prueba
    test_category_matcher()
