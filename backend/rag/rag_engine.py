"""
rag_engine.py - Motor RAG compartido por todos los agentes.
Carga el indice FAISS exportado de Colab y expone consultas
por texto libre, categoria y contexto multimodal.
Opera en modo fallback (listas vacias) si los recursos no estan disponibles.
"""

from __future__ import annotations

import json
from typing import Optional

from backend.shared.config import settings
from backend.shared.logger import get_logger

log = get_logger("rag_engine")


class RAGEngine:
    """
    Motor RAG singleton. Se inicializa una sola vez y es utilizado
    por todos los agentes a traves de la instancia global 'rag'.
    Si los recursos no estan disponibles, opera en modo fallback
    (consultas retornan lista vacia) sin bloquear el arranque.
    """

    _instance: Optional["RAGEngine"] = None

    def __new__(cls) -> "RAGEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._inicializado = False
            cls._instance._vectorstore = None
        return cls._instance

    def inicializar(self) -> None:
        """
        Carga embeddings y FAISS. Llamar UNA vez al arrancar el sistema.
        Activa modo fallback silencioso si los recursos no estan disponibles.
        """
        if self._inicializado:
            return

        self._vectorstore = None
        log.info("Inicializando motor RAG...")

        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as e:
            log.warning(f"No se pudo cargar embeddings: {e}. RAG en modo fallback.")
            self._inicializado = True
            return

        faiss_path = settings.model_paths.faiss_index_dir
        if faiss_path.exists():
            try:
                from langchain_community.vectorstores import FAISS
                log.info(f"Cargando indice FAISS desde {faiss_path}")
                self._vectorstore = FAISS.load_local(
                    str(faiss_path),
                    self._embeddings,
                    allow_dangerous_deserialization=True,
                )
                log.info("Motor RAG listo con indice FAISS.")
            except Exception as e:
                log.warning(f"Error cargando FAISS: {e}. Intentando reconstruir...")
                try:
                    self._vectorstore = self._reconstruir_desde_corpus()
                except Exception as e2:
                    log.warning(f"No se pudo reconstruir RAG: {e2}. Modo fallback.")
        else:
            log.warning("Indice FAISS no encontrado. Intentando reconstruir desde corpus...")
            try:
                self._vectorstore = self._reconstruir_desde_corpus()
            except Exception as e:
                log.warning(f"Corpus no disponible: {e}. RAG en modo fallback.")

        self._inicializado = True
        if self._vectorstore is not None:
            log.info("Motor RAG listo.")
        else:
            log.warning("Motor RAG en modo FALLBACK - sin normativa disponible.")

    def _reconstruir_desde_corpus(self):
        """Reconstruye el indice FAISS desde el corpus JSON."""
        from langchain_community.vectorstores import FAISS
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.docstore.document import Document as LCDocument

        corpus_path = settings.model_paths.corpus_json
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus no encontrado: {corpus_path}")

        with open(corpus_path, encoding="utf-8") as f:
            corpus = json.load(f)

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=60)
        docs = []
        for art in corpus:
            for chunk in splitter.split_text(art["contenido"]):
                docs.append(LCDocument(
                    page_content=chunk,
                    metadata={
                        "id":        art["id"],
                        "titulo":    art["titulo"],
                        "categoria": art.get("categoria", "general"),
                    },
                ))

        vectorstore = FAISS.from_documents(docs, self._embeddings)
        save_dir = settings.model_paths.faiss_index_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(save_dir))
        log.info(f"Indice FAISS guardado en {save_dir}")
        return vectorstore

    def _operativo(self) -> bool:
        """Retorna True si el RAG esta operativo."""
        return self._inicializado and self._vectorstore is not None

    def consultar(
        self,
        query: str,
        k: int = 3,
        categoria: Optional[str] = None,
    ) -> list:
        """
        Consulta semantica al corpus normativo.
        Retorna lista vacia si el RAG esta en modo fallback.
        """
        if not self._operativo():
            return []
        try:
            resultados_raw = self._vectorstore.similarity_search_with_score(
                query, k=k * 3
            )
            out = []
            for doc, score in resultados_raw:
                if categoria and doc.metadata.get("categoria") != categoria:
                    continue
                out.append({
                    "id":         doc.metadata.get("id", ""),
                    "titulo":     doc.metadata.get("titulo", ""),
                    "categoria":  doc.metadata.get("categoria", "general"),
                    "contenido":  doc.page_content,
                    "relevancia": round(1.0 / (1.0 + score), 4),
                })
                if len(out) >= k:
                    break
            return out
        except Exception as e:
            log.warning(f"Error en consulta RAG: {e}")
            return []

    def consultar_por_nivel_y_gases(
        self,
        gases_criticos: list,
        nivel_riesgo: str,
    ) -> list:
        """Consulta contextual combinando gases criticos y nivel de riesgo."""
        query = (
            f"{' '.join(gases_criticos)} nivel {nivel_riesgo} "
            "protocolo evacuacion normativa decreto limite permisible"
        )
        if "EVACUACION" in nivel_riesgo or "EMERGENCIA" in nivel_riesgo:
            query += " evacuacion inmediata art 121 decreto 1886"
        return self.consultar(query, k=settings.rag_k_resultados)

    def consultar_multimodal(
        self,
        gases: list,
        deteccion_visual: str,
        riesgo_geo: bool,
    ) -> list:
        """Consulta cruzada para el Orquestador (fusion multimodal)."""
        tokens = list(gases)
        tokens.append(deteccion_visual)
        if riesgo_geo:
            tokens.append("geomecanica derrumbe estabilidad sostenimiento")
        query = " ".join(tokens) + " emergencia protocolo decreto"
        return self.consultar(query, k=4)


# Instancia global (singleton)
rag = RAGEngine()
