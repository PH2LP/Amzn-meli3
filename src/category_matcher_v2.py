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

    def _product_to_text(self, product: Dict) -> str:
        """Convierte producto a texto para embedding"""
        parts = []

        if product.get('title'):
            parts.append(f"Título: {product['title']}")

        if product.get('description'):
            desc = product['description'][:500]  # Limitar a 500 chars
            parts.append(f"Descripción: {desc}")

        if product.get('brand'):
            parts.append(f"Marca: {product['brand']}")

        if product.get('features'):
            features = ', '.join(product['features'][:5])
            parts.append(f"Características: {features}")

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

        return results

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

        # Formatear candidatos
        candidates_text = ""
        for i, candidate in enumerate(candidates[:10], 1):
            cat = candidate['category_data']
            sim = candidate['similarity_score']
            candidates_text += f"{i}. ID: {candidate['category_id']}\n"
            candidates_text += f"   Nombre: {cat['name']}\n"
            candidates_text += f"   Path: {cat['path']}\n"
            candidates_text += f"   Similitud: {sim:.3f}\n"
            if cat['required_attrs']:
                candidates_text += f"   Atributos requeridos: {', '.join(cat['required_attrs'][:5])}\n"
            candidates_text += "\n"

        prompt = f"""Eres un experto en categorización de productos para MercadoLibre.

PRODUCTO:
Título: {product.get('title', 'N/A')}
Descripción: {product.get('description', 'N/A')[:300]}
Marca: {product.get('brand', 'N/A')}

CANDIDATOS (Top {len(candidates)} categorías por similitud de embeddings):
{candidates_text}

TAREA:
Selecciona la categoría MÁS APROPIADA del listado de candidatos.

CRITERIOS DE SELECCIÓN:
1. Coincidencia semántica precisa con el producto
2. Nivel de especificidad (más específico = mejor)
3. Compatibilidad con atributos requeridos
4. Path jerárquico lógico

IMPORTANTE:
- Debes elegir SOLO una categoría de la lista de candidatos
- NO inventes categorías nuevas
- La categoría debe existir en el listado arriba

FORMATO DE RESPUESTA (JSON válido):
{{
  "category_id": "CBT123456",
  "confidence": 0.95,
  "reasoning": "Esta categoría es la mejor porque...",
  "alternative": "CBT789012"
}}

Responde SOLO con el JSON, sin texto adicional.
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
        top_k: int = 10,
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
