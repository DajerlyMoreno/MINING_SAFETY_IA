"""
rag_engine.py — Motor RAG compartido por todos los agentes.
Carga el índice FAISS exportado de Colab y expone consultas
por texto libre, categoría y contexto multimodal.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document as LCDocument

from backend.shared.config import settings
from backend.shared.exceptions import RAGNoInicializado, ModeloNoEncontrado
from backend.shared.logger import get_logger

log = get_logger("rag_engine")


class RAGEngine:
    """
    Motor RAG singleton. Se inicializa una sola vez y es utilizado
    por todos los agentes a través de la instancia global `rag`.

    Capacidades:
      - Cargar índice FAISS pre-construido en Colab.
      - Reconstruir el índice desde el corpus JSON si el FAISS no existe.
      - Consultar por texto libre con filtro opcional por categoría.
      - Consultar con contexto multimodal (gases + visual + geo).
    """

    _instance: Optional["RAGEngine"] = None

    def __new__(cls) -> "RAGEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._inicializado = False
        return cls._instance

    def inicializar(self) -> None:
        """Carga embeddings y FAISS. Llamar UNA vez al arrancar el sistema."""
        if self._inicializado:
            return

        log.info("Inicializando motor RAG...")
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        faiss_path = settings.model_paths.faiss_index_dir
        if faiss_path.exists():
            log.info(f"Cargando índice FAISS desde {faiss_path}")
            self._vectorstore = FAISS.load_local(
                str(faiss_path),
                self._embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            log.warning("Índice FAISS no encontrado. Reconstruyendo desde corpus...")
            self._vectorstore = self._reconstruir_desde_corpus()

        self._inicializado = True
        log.info("Motor RAG listo.")

    def _reconstruir_desde_corpus(self) -> FAISS:
        """
        Reconstruye el índice FAISS desde el corpus JSON.
        Útil cuando el índice de Colab no está disponible.
        """
        corpus_path = settings.model_paths.corpus_json
        if not corpus_path.exists():
            raise ModeloNoEncontrado(str(corpus_path))

        with open(corpus_path, encoding="utf-8") as f:
            corpus = json.load(f)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=60
        )
        docs: list[LCDocument] = []
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

        # Persistir para próximas ejecuciones
        save_dir = settings.model_paths.faiss_index_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(save_dir))
        log.info(f"Índice FAISS guardado en {save_dir}")

        return vectorstore

    def _asegurar_inicializado(self) -> None:
        if not self._inicializado:
            raise RAGNoInicializado("Llamar a rag.inicializar() antes de consultar.")

    def consultar(
        self,
        query: str,
        k: int = 3,
        categoria: Optional[str] = None,
    ) -> list[dict]:
        """
        Consulta semántica al corpus normativo.

        Args:
            query:     Texto de búsqueda en lenguaje natural.
            k:         Número de resultados a retornar.
            categoria: Filtro opcional ('gases','geomecanica','evacuacion','epp').

        Returns:
            Lista de dicts con id, titulo, categoria, contenido, relevancia.
        """
        self._asegurar_inicializado()
        resultados_raw = self._vectorstore.similarity_search_with_score(
            query, k=k * 3  # sobrepasar para filtrar
        )
        out = []
        for doc, score in resultados_raw:
            if categoria and doc.metadata.get("categoria") != categoria:
                continue
            out.append({
                "id":         doc.metadata["id"],
                "titulo":     doc.metadata["titulo"],
                "categoria":  doc.metadata.get("categoria", "general"),
                "contenido":  doc.page_content,
                "relevancia": round(1.0 / (1.0 + score), 4),
            })
            if len(out) >= k:
                break
        return out

    def consultar_por_nivel_y_gases(
        self,
        gases_criticos: list[str],
        nivel_riesgo: str,
    ) -> list[dict]:
        """
        Consulta contextual combinando gases críticos y nivel de riesgo.
        Usado principalmente por el Agente de Gases y el Orquestador.
        """
        query = (
            f"{' '.join(gases_criticos)} nivel {nivel_riesgo} "
            "protocolo evacuación normativa decreto límite permisible"
        )
        if "EVACUACIÓN" in nivel_riesgo or "EMERGENCIA" in nivel_riesgo:
            query += " evacuación inmediata art 121 decreto 1886"
        return self.consultar(query, k=settings.rag_k_resultados)

    def consultar_multimodal(
        self,
        gases: list[str],
        deteccion_visual: str,
        riesgo_geo: bool,
    ) -> list[dict]:
        """Consulta cruzada para el Orquestador (fusión multimodal)."""
        tokens = list(gases)
        tokens.append(deteccion_visual)
        if riesgo_geo:
            tokens.append("geomecánica derrumbe estabilidad sostenimiento")
        query = " ".join(tokens) + " emergencia protocolo decreto"
        return self.consultar(query, k=4)


# ── Instancia global (singleton) ──────────────────────────────────────────────
rag = RAGEngine()