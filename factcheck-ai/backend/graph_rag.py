import re
import asyncio
import json
from typing import Dict, Any, List


class GraphRAGAnalyzer:
    """
    Implements Graph-RAG concepts by extracting key entities, concepts,
    and their relations to build a local knowledge graph. It detects logical
    contradictions (e.g., location/time conflicts) in claims versus evidence.
    
    Now supports AI-powered extraction via Gemini when available.
    """

    async def extract_graph_with_ai(self, text: str, evidence: List[Dict[str, Any]], model) -> Dict[str, Any]:
        """
        Uses Gemini AI to extract entities and relationships for the knowledge graph.
        Falls back to regex-based extraction if AI call fails.
        """
        evidence_text = ""
        for ev in evidence[:5]:
            evidence_text += f"- [{ev.get('domain', '')}] {ev.get('title', '')}: {ev.get('snippet', '')[:200]}\n"

        prompt = f"""Phân tích tuyên bố và bằng chứng sau để trích xuất đồ thị tri thức.

Tuyên bố: "{text}"

Bằng chứng:
{evidence_text}

Trả lời ĐÚNG format JSON (không markdown):
{{
    "nodes": [
        {{"id": "1", "label": "tên thực thể", "type": "organization|location|time|quantity|concept|event|person"}}
    ],
    "edges": [
        {{"source": "1", "target": "2", "relation": "mô tả quan hệ"}}
    ],
    "has_conflict": true/false,
    "conflict_message": "mô tả mâu thuẫn nếu có, hoặc chuỗi rỗng"
}}

Yêu cầu:
- Trích xuất 3-6 thực thể quan trọng nhất
- Xác định quan hệ giữa các thực thể
- Phát hiện mâu thuẫn logic (ví dụ: tuyết ở vùng nhiệt đới, sự kiện tương lai được nói đã xảy ra)
- Luôn trả id dạng string"""

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: model.generate_content(prompt)
            )
            raw = response.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw.strip())

            # Validate structure
            if "nodes" not in data or "edges" not in data:
                raise ValueError("Missing nodes or edges")

            data.setdefault("has_conflict", False)
            data.setdefault("conflict_message", "")
            return data

        except Exception as e:
            print(f"AI graph extraction failed: {e}. Falling back to regex.")
            return self.extract_graph(text, evidence)

    def extract_graph(self, text: str, evidence: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Builds a knowledge graph from text and evidence using regex patterns.
        """
        nodes = []
        edges = []

        # 1. Predefined entity extraction rules based on keywords
        extracted_entities = {}

        # Locations
        locations = re.findall(r'(Hồ Chí Minh|TP.HCM|Hà Nội|Đà Nẵng|Cần Thơ|ISS|Trạm Vũ trụ|Việt Nam)', text, re.IGNORECASE)
        for loc in locations:
            name = "TP. Hồ Chí Minh" if loc.lower() in ["hồ chí minh", "tphcm"] else loc
            extracted_entities[name] = "location"

        # Organizations
        orgs = re.findall(r'(Chính phủ|Bộ Y tế|NASA|VTV|Đài truyền hình|Hội đồng nhân dân|Bộ Công thương)', text, re.IGNORECASE)
        for org in orgs:
            extracted_entities[org] = "organization"

        # Numbers / Quantities
        quantities = re.findall(r'(\d+\s*tỷ|\d+\s*kỹ sư|\d+\s*ca\s*mắc|\d+\s*%)', text, re.IGNORECASE)
        for q in quantities:
            extracted_entities[q] = "quantity"

        # Times
        times = re.findall(r'(Tháng 5|Năm 2030|Năm 2024|Quý I|Hôm nay|Vừa qua)', text, re.IGNORECASE)
        for t in times:
            extracted_entities[t] = "time"

        # Build node list
        node_id = 1
        entity_to_node_id = {}

        for name, etype in extracted_entities.items():
            nodes.append({
                "id": str(node_id),
                "label": name,
                "type": etype
            })
            entity_to_node_id[name.lower()] = str(node_id)
            node_id += 1

        # 2. Add fallback general nodes if list is empty
        if len(nodes) < 3:
            words = [w for w in re.sub(r'[^\w\s]', '', text).split() if len(w) > 4][:4]
            for w in words:
                nodes.append({
                    "id": str(node_id),
                    "label": w.capitalize(),
                    "type": "concept"
                })
                entity_to_node_id[w.lower()] = str(node_id)
                node_id += 1

        # 3. Create edges based on simple rules
        node_list = list(nodes)
        for i in range(len(node_list) - 1):
            source = node_list[i]
            target = node_list[i+1]

            relation = "liên quan"
            if source["type"] == "organization" and target["type"] == "concept":
                relation = "chỉ đạo / công bố"
            elif source["type"] == "location" and target["type"] == "event":
                relation = "nơi diễn ra"
            elif target["type"] == "time":
                relation = "vào lúc"
            elif target["type"] == "quantity":
                relation = "số lượng / quy mô"

            edges.append({
                "source": source["id"],
                "target": target["id"],
                "relation": relation
            })

        # 4. Check for contradictions
        has_conflict = False
        conflict_msg = ""

        text_lower = text.lower()
        if "tuyết" in text_lower and ("hồ chí minh" in text_lower or "tphcm" in text_lower):
            has_conflict = True
            conflict_msg = "Mâu thuẫn logic: Địa điểm TP.HCM (khí hậu nhiệt đới) không thể đồng xuất hiện với hiện tượng Tuyết rơi dày đặc."
            tphcm_node_id = entity_to_node_id.get("tp. hồ chí minh") or entity_to_node_id.get("hồ chí minh") or entity_to_node_id.get("tphcm")
            tuyet_node_id = None
            for n in nodes:
                if "tuyết" in n["label"].lower():
                    tuyet_node_id = n["id"]
                    break
            if not tuyet_node_id:
                tuyet_node_id = str(node_id)
                nodes.append({"id": tuyet_node_id, "label": "Tuyết rơi", "type": "event"})
                node_id += 1
            if not tphcm_node_id:
                tphcm_node_id = str(node_id)
                nodes.append({"id": tphcm_node_id, "label": "TP. Hồ Chí Minh", "type": "location"})
                node_id += 1

            edges.append({
                "source": tphcm_node_id,
                "target": tuyet_node_id,
                "relation": "MÂU THUẪN VẬT LÝ",
                "is_conflict": True
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "has_conflict": has_conflict,
            "conflict_message": conflict_msg
        }


# Singleton analyzer instance
graph_rag_analyzer = GraphRAGAnalyzer()
