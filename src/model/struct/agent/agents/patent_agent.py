# =============================================================================
# PatentAgent — KIPRIS API 기반 특허 검색
# =============================================================================
# 역할: 특허 관련 질의를 감지하고 KIPRIS Plus API를 호출하여 결과를 수집
# =============================================================================

import re
import json

try:
    from .base_agent import BaseAgent
except ImportError:
    from base_agent import BaseAgent


class PatentAgent(BaseAgent):
    name = "patent"
    description = "KIPRIS Plus API를 사용하여 특허 검색을 수행합니다."

    def run(self, message="", classification=None, **kwargs):
        """특허 검색이 필요한 경우 KIPRIS API를 호출.

        Args:
            message: 사용자 원본 메시지
            classification: KeywordAgent 결과 dict

        Returns:
            dict with 'patents' (list) and 'patent_query' (str) and 'has_patents' (bool)
        """
        classification = classification or {}
        category = classification.get("category", "")
        keywords = classification.get("keywords", [])
        query = classification.get("query", "")

        # 특허 검색이 필요한지 판단
        needs_patent = self._needs_patent_search(message, category)
        if not needs_patent:
            return {"has_patents": False, "patents": [], "patent_query": ""}

        # KIPRIS API 호출
        patent_query = query or " ".join(keywords[:3])
        patents = self._search_kipris(patent_query)

        return {
            "has_patents": len(patents) > 0,
            "patents": patents,
            "patent_query": patent_query,
        }

    def _needs_patent_search(self, message, category):
        """특허 검색 필요 여부 판단."""
        q = (message or "").lower()
        if category == "특허 검색":
            return True
        if any(kw in q for kw in ["특허", "patent", "kipris", "출원", "등록번호"]):
            return True
        return False

    def _search_kipris(self, query):
        """KIPRIS Plus API 호출."""
        try:
            config = self.ctx.get("wiz").config("research") if self.ctx.get("wiz") else None
            if not config:
                return []

            import requests
            import xml.etree.ElementTree as ET

            endpoint = getattr(config, "kipris_plus_endpoint", "")
            api_key = getattr(config, "kipris_plus_api_key", "")
            if not endpoint or not api_key:
                return []

            api_key_param = getattr(config, "kipris_plus_api_key_param", "accessKey")
            query_param = getattr(config, "kipris_plus_query_param", "word")
            docs_start_param = getattr(config, "kipris_plus_docs_start_param", "docsStart")
            docs_count_param = getattr(config, "kipris_plus_docs_count_param", "docsCount")
            timeout = getattr(config, "kipris_plus_timeout", 20)

            params = {
                api_key_param: api_key,
                query_param: query,
                docs_start_param: getattr(config, "kipris_plus_docs_start", "1"),
                docs_count_param: getattr(config, "kipris_plus_docs_count", "10"),
            }
            default_params = getattr(config, "kipris_plus_default_params", {})
            if isinstance(default_params, dict):
                params.update(default_params)

            resp = requests.get(endpoint, params=params, timeout=timeout, verify=False)
            if resp.status_code != 200:
                return []

            # XML 파싱
            items = self._parse_kipris_xml(resp.text)
            if not items:
                # JSON 시도
                try:
                    data = resp.json()
                    items = self._parse_kipris_json(data)
                except Exception:
                    pass

            return items[:10]
        except Exception:
            return []

    def _parse_kipris_xml(self, xml_text):
        """KIPRIS XML 응답 파싱."""
        import xml.etree.ElementTree as ET
        items = []
        try:
            root = ET.fromstring(xml_text)
            for item_el in root.iter("item"):
                item = {}
                for child in item_el:
                    tag = child.tag
                    text = (child.text or "").strip()
                    if text:
                        item[tag] = text
                if item:
                    items.append(self._normalize_patent(item))
        except Exception:
            pass
        return items

    def _parse_kipris_json(self, data):
        """KIPRIS JSON 응답 파싱."""
        items = []
        try:
            if isinstance(data, dict):
                body = data.get("response", {}).get("body", {})
                item_list = body.get("items", {}).get("item", [])
                if isinstance(item_list, dict):
                    item_list = [item_list]
                for raw in item_list:
                    if isinstance(raw, dict):
                        items.append(self._normalize_patent(raw))
        except Exception:
            pass
        return items

    def _normalize_patent(self, raw):
        """특허 항목을 통일된 포맷으로 정규화."""
        return {
            "title": raw.get("inventionTitle") or raw.get("title") or "",
            "applicant": raw.get("applicantName") or raw.get("applicant") or "",
            "applicationNumber": raw.get("applicationNumber") or raw.get("appNo") or "",
            "applicationDate": raw.get("applicationDate") or raw.get("appDate") or "",
            "publicationNumber": raw.get("publicationNumber") or raw.get("pubNo") or "",
            "publicationDate": raw.get("publicationDate") or raw.get("pubDate") or "",
            "registerNumber": raw.get("registerNumber") or raw.get("regNo") or "",
            "registerDate": raw.get("registerDate") or raw.get("regDate") or "",
            "abstract": raw.get("astrtCont") or raw.get("abstract") or "",
        }
