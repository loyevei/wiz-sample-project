# =============================================================================
# read_page_results Tool — 페이지 API 결과를 공용 함수로 읽어와 정규화 JSON 반환
# =============================================================================
import os
import json
import importlib.util
import sys

from pymilvus import MilvusClient

from base_tool import BaseTool


class ReadPageResultsTool(BaseTool):
    name = "read_page_results"
    description = "Read the actual structured results a page would show by calling shared server-side page result functions. Use this before navigate_to_page so the final answer can summarize real page results."
    input_schema = {
        "type": "object",
        "properties": {
            "page": {
                "type": "string",
                "enum": ["research", "prediction", "theory", "diagnosis"],
                "description": "Target page whose result set should be read"
            },
            "tab": {
                "type": "string",
                "description": "Target tab, e.g. discover, predict, equation"
            },
            "query": {
                "type": "string",
                "description": "Main keyword or question text for the page"
            },
            "params": {
                "type": "object",
                "description": "Additional page parameters"
            },
            "collection": {
                "type": "string",
                "description": "Collection name"
            }
        },
        "required": ["page"]
    }

    class _StubRequest:
        def query(self, key, default=None, *args, **kwargs):
            return default

    class _StubResponse:
        def status(self, *args, **kwargs):
            return None

        def response(self, *args, **kwargs):
            return None

    class _StubProject:
        def __init__(self, base_path):
            self._base_path = base_path

        def fs(self):
            base_path = self._base_path

            class _FS:
                def abspath(self_inner):
                    return base_path

            return _FS()

    class _StubWiz:
        def __init__(self, base_path):
            self.project = ReadPageResultsTool._StubProject(base_path)
            self.request = ReadPageResultsTool._StubRequest()
            self.response = ReadPageResultsTool._StubResponse()

    def _get_wiz(self):
        runtime_wiz = self.ctx.get("wiz") if isinstance(self.ctx, dict) else None
        if runtime_wiz is not None:
            return runtime_wiz
        runtime_wiz = globals().get("wiz")
        if runtime_wiz is not None:
            return runtime_wiz
        return self._StubWiz(self._get_project_root())

    def _get_project_root(self):
        current_path = os.path.abspath(__file__)
        parts = current_path.split(os.sep)
        for marker in ("/src/model/struct/agent/tools/", "/build/src/model/struct/agent/tools/", "/bundle/src/model/struct/agent/tools/"):
            if marker in current_path:
                return current_path.split(marker)[0]

        normalized_parts = [part for part in parts if part]
        if "project" in normalized_parts:
            idx = normalized_parts.index("project")
            if idx + 1 < len(normalized_parts):
                prefix = os.sep if current_path.startswith(os.sep) else ""
                return prefix + os.sep.join(normalized_parts[:idx + 2])

        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_path)))))

    def _load_module(self, relative_path, module_name):
        project_root = self._get_project_root()
        runtime_wiz = self._get_wiz()
        target_path = None
        for candidate in ["src", "build", "bundle"]:
            path = os.path.join(project_root, candidate, relative_path)
            if os.path.exists(path):
                target_path = path
                break
        if target_path is None:
            raise FileNotFoundError(relative_path)

        spec = importlib.util.spec_from_file_location(module_name, target_path)
        mod = importlib.util.module_from_spec(spec)
        mod.wiz = runtime_wiz
        spec.loader.exec_module(mod)
        return mod

    def _resolve_collection(self, requested_collection=""):
        collection = (requested_collection or self.ctx.get("collection", "") or "").strip()
        if collection:
            return collection

        uri = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        if not hasattr(sys, "_milvus_client") or sys._milvus_client is None:
            sys._milvus_client = MilvusClient(uri=uri)

        try:
            collections = sys._milvus_client.list_collections()
        except Exception:
            collections = []

        preferred = [
            "plasma_papers_collection",
            "plasma_papers_eng",
            "plasma_papers",
        ]
        for name in preferred:
            if name in collections:
                return name
        if collections:
            return collections[0]
        return "plasma_papers"

    def _research_discover(self, query, collection, params=None):
        mod = self._load_module("app/page.research/api.py", "page_research_api")
        result = mod.run_discover_data(keyword=query or "", top_k=20, collection_name=collection)
        return {
            "page": "research",
            "tab": "discover",
            "query": query,
            "params": params or {},
            "collection": collection,
            "mode": result.get("mode"),
            "total_hits": result.get("total_hits", result.get("total", 0)),
            "clusters": [
                {
                    "doc_id": item.get("doc_id"),
                    "filename": item.get("filename"),
                    "score": item.get("max_score"),
                    "snippets": [chunk.get("text") for chunk in item.get("chunks", [])[:2]]
                }
                for item in result.get("clusters", [])[:5]
            ],
            "docs": result.get("docs", [])[:5]
        }

    def _research_recommend(self, query, collection, params=None):
        """UI의 '논문 추천' 탭과 동일하게 관심분야 기반 문헌을 추천한다.

        NOTE: page.research/api.py의 recommend_papers()는 wiz.request.query()에 의존하므로,
        read_page_results에서는 동일 로직(임베딩→벡터검색)을 query/collection 기반으로 직접 수행한다.
        """
        mod = self._load_module("app/page.research/api.py", "page_research_api")

        interests = (query or "").strip()
        if not interests:
            return {
                "page": "research",
                "tab": "recommend",
                "query": query,
                "params": params or {},
                "collection": collection,
                "total": 0,
                "papers": [],
                "error": "interests(query) is empty"
            }

        if hasattr(mod, "_recommend_papers_data"):
            raw_papers = mod._recommend_papers_data(interests=interests, collection_name=collection)
            papers = []
            for item in raw_papers[:10]:
                if not isinstance(item, dict):
                    continue
                snippet = item.get("abstract") or item.get("text") or ""
                paper = {
                    "doc_id": item.get("doc_id"),
                    "filename": item.get("filename") or item.get("title") or item.get("doc_id"),
                    "page_num": item.get("page_num", 0),
                    "score": item.get("score", 0),
                    "year": item.get("year", ""),
                    "publication_year": item.get("publication_year", ""),
                    "online_year": item.get("online_year", ""),
                    "accepted_year": item.get("accepted_year", ""),
                    "received_year": item.get("received_year", ""),
                    "relevance": item.get("relevance", ""),
                    "snippets": [snippet[:400]] if snippet else []
                }
                papers.append(paper)
        else:
            model_name = None
            if hasattr(mod, "_get_collection_model"):
                try:
                    model_name = mod._get_collection_model(collection)
                except Exception:
                    model_name = None
            if model_name is None:
                model_name = getattr(mod, "DEFAULT_MODEL", None)

            client = mod._get_client() if hasattr(mod, "_get_client") else None
            if client is None or not client.has_collection(collection):
                return {
                    "page": "research",
                    "tab": "recommend",
                    "query": query,
                    "params": params or {},
                    "collection": collection,
                    "total": 0,
                    "papers": []
                }

            model = mod._get_model(model_name) if hasattr(mod, "_get_model") else None
            if model is None:
                return {
                    "page": "research",
                    "tab": "recommend",
                    "query": query,
                    "params": params or {},
                    "collection": collection,
                    "total": 0,
                    "papers": [],
                    "error": "embedding model not available"
                }

            query_vec = model.encode([interests], normalize_embeddings=True)[0].tolist()
            results = client.search(
                collection_name=collection,
                data=[query_vec],
                limit=15,
                output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
                search_params={"metric_type": "COSINE"}
            )

            seen_docs = set()
            papers = []
            for hit in (results[0] if results and isinstance(results, list) else []):
                entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
                doc_id = entity.get("doc_id", "")
                if not doc_id or doc_id in seen_docs:
                    continue
                seen_docs.add(doc_id)

                filename = entity.get("filename") or doc_id
                text_preview = (entity.get("text", "") or "")[:400]

                papers.append({
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_num": entity.get("page_num", 0),
                    "score": round(hit.get("distance", 0), 4) if isinstance(hit, dict) else 0,
                    "snippets": [text_preview] if text_preview else []
                })

        return {
            "page": "research",
            "tab": "recommend",
            "query": interests,
            "params": params or {},
            "collection": collection,
            "total": len(papers),
            "papers": papers[:10]
        }

    def _prediction_predict(self, query, params, collection):
        mod = self._load_module("app/page.prediction/api.py", "page_prediction_api")
        params = params or {}
        result = mod.run_predict_data(
            process_type=params.get("process_type", ""),
            gas_type=params.get("gas_type", ""),
            pressure=params.get("pressure", ""),
            power=params.get("power", ""),
            temperature=params.get("temperature", ""),
            substrate=params.get("substrate", ""),
            target_property=params.get("target_property", query or ""),
            collection_name=collection
        )
        return {
            "page": "prediction",
            "tab": "predict",
            "query": result.get("query", query),
            "params": params or {},
            "collection": collection,
            "total_searched": result.get("total_searched", 0),
            "predictions": [
                {
                    "filename": item.get("filename"),
                    "relevance": item.get("relevance"),
                    "text": item.get("text"),
                    "extracted_values": item.get("extracted_values", [])[:6]
                }
                for item in result.get("predictions", [])[:5]
            ]
        }

    def _theory_equation(self, query, params, collection):
        mod = self._load_module("app/page.theory/api.py", "page_theory_api")
        params = params or {}
        equation_query = params.get("equationQuery", query or "")
        result = mod.run_search_equations_data(query_eq=equation_query, collection_name=collection)
        return {
            "page": "theory",
            "tab": "equation",
            "query": equation_query,
            "params": params or {},
            "collection": collection,
            "query_classification": result.get("query_classification", {}),
            "total": result.get("total", 0),
            "results": [
                {
                    "filename": item.get("filename"),
                    "score": item.get("score"),
                    "snippet": item.get("snippet"),
                    "equations": item.get("equations", [])[:3]
                }
                for item in result.get("results", [])[:5]
            ]
        }

    def _diagnosis_search(self, query, params, collection):
        mod = self._load_module("app/page.diagnosis/api.py", "page_diagnosis_api")
        params = params or {}
        result = mod.run_search_diagnostic_data(query=query or "", diagnostic_type=params.get("diagType", ""), top_k=20, collection_name=collection)
        return {
            "page": "diagnosis",
            "tab": "search",
            "query": result.get("query", query),
            "params": params or {},
            "collection": collection,
            "total": result.get("total", 0),
            "results": result.get("results", [])[:6]
        }

    def _diagnosis_compare(self, query, params, collection):
        mod = self._load_module("app/page.diagnosis/api.py", "page_diagnosis_api")
        params = params or {}
        method_a = params.get("methodA", query or "")
        method_b = params.get("methodB", "")
        result = mod.run_compare_diagnostics_data(method_a=method_a, method_b=method_b, collection_name=collection)
        return {
            "page": "diagnosis",
            "tab": "compare",
            "query": query,
            "params": params or {},
            "collection": collection,
            "method_a": result.get("method_a"),
            "method_b": result.get("method_b"),
            "common_doc_count": result.get("common_doc_count", 0),
            "analysis": result.get("analysis", {}),
            "results_a": result.get("results_a", [])[:5],
            "results_b": result.get("results_b", [])[:5]
        }

    def _diagnosis_detection(self, collection, params=None):
        mod = self._load_module("app/page.diagnosis/api.py", "page_diagnosis_api")
        result = mod.run_diagnosis_detection_data()
        return {
            "page": "diagnosis",
            "tab": "detection",
            "params": params or {},
            "collection": collection,
            "has_baseline": result.get("has_baseline", False),
            "baseline": result.get("baseline"),
            "stats": result.get("stats", {}),
            "history": result.get("history", [])[:10]
        }

    def _diagnosis_failure(self, query, params, collection):
        mod = self._load_module("app/page.diagnosis/api.py", "page_diagnosis_api")
        params = params or {}
        symptom = params.get("symptom", query or "")
        spectrum_data = params.get("spectrumData", "")
        result = mod.run_failure_reasoning_data(symptom=symptom, spectrum_data=spectrum_data, collection_name=collection)
        return {
            "page": "diagnosis",
            "tab": "failure",
            "query": symptom,
            "params": params or {},
            "collection": collection,
            "summary": result.get("summary", {}),
            "matched_patterns": [
                {
                    "name": item.get("name"),
                    "match_score": item.get("match_score"),
                    "causes": item.get("causes", [])[:4],
                    "solutions": item.get("solutions", [])[:4]
                }
                for item in result.get("matched_patterns", [])[:5]
            ],
            "spectrum_info": result.get("spectrum_info"),
            "evidence_docs": [
                {
                    "filename": item.get("filename"),
                    "score": item.get("score"),
                    "tags": item.get("tags", []),
                    "query_context": item.get("query_context"),
                    "text": item.get("text")
                }
                for item in result.get("evidence_docs", [])[:8]
            ]
        }

    def execute(self, page="", tab="", query="", params=None, collection="", **kwargs):
        if not page:
            return json.dumps({"error": "page is required"}, ensure_ascii=False)

        collection = self._resolve_collection(collection)

        try:
            effective_tab = tab or ("discover" if page == "research" else "predict" if page == "prediction" else "equation" if page == "theory" else "search")
            if page == "research" and effective_tab == "discover":
                result = self._research_discover(query, collection, params)
            elif page == "research" and effective_tab == "recommend":
                result = self._research_recommend(query, collection, params)
            elif page == "prediction" and (tab or "predict") == "predict":
                result = self._prediction_predict(query, params, collection)
            elif page == "theory" and (tab or "equation") == "equation":
                result = self._theory_equation(query, params, collection)
            elif page == "diagnosis" and effective_tab == "search":
                result = self._diagnosis_search(query, params, collection)
            elif page == "diagnosis" and effective_tab == "compare":
                result = self._diagnosis_compare(query, params, collection)
            elif page == "diagnosis" and effective_tab == "detection":
                result = self._diagnosis_detection(collection, params)
            elif page == "diagnosis" and effective_tab == "failure":
                result = self._diagnosis_failure(query, params, collection)
            else:
                result = {
                    "page": page,
                    "tab": tab,
                    "query": query,
                    "collection": collection,
                    "error": f"Unsupported page/tab: {page}/{tab}"
                }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "page": page,
                "tab": tab,
                "query": query,
                "collection": collection,
                "error": str(e)
            }, ensure_ascii=False)


Tool = ReadPageResultsTool