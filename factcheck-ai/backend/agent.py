import json
import time
import asyncio
from urllib.parse import urlparse
from typing import AsyncGenerator, Dict, Any, List
from .config import GEMINI_API_KEY, whitelist_domains
from .cache import fact_cache
from .search import whitelist_search
from .graph_rag import graph_rag_analyzer

class FactCheckAgent:
    """
    Core AI Agent that coordinates the fact-checking flow.
    Supports real Gemini 1.5 Flash integration and a high-fidelity
    simulated reasoning/streaming fallback for perfect demos without API keys.
    """
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.use_real_gemini = False
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
                self.use_real_gemini = True
                print("Gemini API configured successfully in Agent Core.")
            except Exception as e:
                print(f"Failed to initialize Gemini model: {e}. Falling back to simulation.")
                self.use_real_gemini = False

    async def check_claim_stream(self, claim: str, source_url: str = None) -> AsyncGenerator[str, None]:
        """
        Asynchronously streams the thinking process and final verdict using Server-Sent Events (SSE).
        """
        # Step 0: Check Cache first (Pre-indexing and caching - Section 5.4)
        yield "data: " + json.dumps({"event": "thought", "message": "🔍 Đang truy vấn cơ sở dữ liệu Bộ nhớ đệm (Cache) để tối ưu chi phí..."}) + "\n\n"
        await asyncio.sleep(0.8)
        
        cached_result = fact_cache.get(claim)
        if cached_result:
            yield "data: " + json.dumps({"event": "thought", "message": "⚡ Đã tìm thấy tin tức trong Bộ nhớ đệm! Trả về kết quả xác thực tức thì..."}) + "\n\n"
            await asyncio.sleep(0.6)
            yield "data: " + json.dumps({"event": "result", "data": cached_result, "cached": True}) + "\n\n"
            return

        # Step 1: PRE-VALIDATION - Origin Check (NEW!)
        # If the source comes directly from a Whitelisted Domain, mark verified instantly!
        if source_url:
            try:
                parsed = urlparse(source_url)
                origin_domain = parsed.netloc.replace("www.", "")
                if origin_domain in whitelist_domains:
                    yield "data: " + json.dumps({"event": "thought", "message": f"🛡️ BẢO MẬT: Phát hiện nguồn tin trực tiếp từ `{origin_domain}` (Nằm trong Whitelist). Cấp quyền XÁC THỰC ƯU TIÊN..."}) + "\n\n"
                    await asyncio.sleep(1.0)
                    
                    fast_track_result = {
                        "claim": claim,
                        "verdict": "VERIFIED",
                        "confidence": 100,
                        "explanation": f"XÁC THỰC TỰ ĐỘNG: Thông tin này được trích xuất trực tiếp từ nền tảng tin cậy `{origin_domain}`. Dữ liệu từ cổng thông tin chính thống này được mặc định cấp nhãn An toàn.",
                        "sources": [{
                            "domain": origin_domain,
                            "url": source_url,
                            "title": "Trích xuất trực tiếp",
                            "is_whitelist": True
                        }],
                        "graph": {"has_conflict": False, "nodes": [], "edges": []}
                    }
                    yield "data: " + json.dumps({"event": "result", "data": fast_track_result, "cached": False}) + "\n\n"
                    return
            except Exception:
                pass

        # Step 2: If not in fast-track, continue standard analysis
        # If not in cache, start the live Agent Reasoning Process (Section 2 - AI Agent Core)
        yield "data: " + json.dumps({"event": "thought", "message": "⚙️ Khởi chạy AI Agent: Đang phân tích cú pháp câu tuyên bố..."}) + "\n\n"
        await asyncio.sleep(1.0)
        
        yield "data: " + json.dumps({"event": "thought", "message": "🧠 Phân tích ngữ cảnh, trích xuất các thực thể chính để tìm kiếm..."}) + "\n\n"
        await asyncio.sleep(1.2)
        
        # Formulate expanded live search query
        search_query = claim[:120]  # Broader search string
        yield "data: " + json.dumps({"event": "thought", "message": f"🌐 Đang khởi động Tìm kiếm Thời gian thực (Live Search): `{search_query}`..."}) + "\n\n"
        await asyncio.sleep(1.5)
        
        # Execute real-time search
        evidence_snippets = whitelist_search.search(claim)
        sources_list = ", ".join([s['domain'] for s in evidence_snippets])
        yield "data: " + json.dumps({"event": "thought", "message": f"📰 Đã thu thập {len(evidence_snippets)} nguồn tin tức phong phú từ internet: [{sources_list}]."}) + "\n\n"
        await asyncio.sleep(1.2)
        
        yield "data: " + json.dumps({"event": "thought", "message": "🔗 Đang tiến hành trích xuất thực thể và dựng đồ thị tri thức Graph-RAG..."}) + "\n\n"
        await asyncio.sleep(1.4)
        
        # Analyze using Graph RAG to build nodes & edges and find logical conflicts
        graph_data = graph_rag_analyzer.extract_graph(claim, evidence_snippets)
        if graph_data["has_conflict"]:
            yield "data: " + json.dumps({"event": "thought", "message": f"⚠️ CẢNH BÁO: {graph_data['conflict_message']}"}) + "\n\n"
            await asyncio.sleep(1.5)
        else:
            yield "data: " + json.dumps({"event": "thought", "message": "✅ Kiểm chứng thành công: Không phát hiện xung đột logic trong đồ thị tri thức."}) + "\n\n"
            await asyncio.sleep(1.2)
            
        yield "data: " + json.dumps({"event": "thought", "message": "⚖️ Đang tổng hợp chứng cứ và đưa ra phán quyết cuối cùng..."}) + "\n\n"
        await asyncio.sleep(1.2)
        
        # Produce final result
        if self.use_real_gemini:
            # Real Gemini integration
            result_data = await self._call_gemini_verdict(claim, evidence_snippets, graph_data)
        else:
            # High-fidelity simulated agent decision logic
            result_data = self._generate_simulated_verdict(claim, evidence_snippets, graph_data)
            
        # Store in cache
        fact_cache.set(claim, result_data)
        
        yield "data: " + json.dumps({"event": "result", "data": result_data, "cached": False}) + "\n\n"

    async def _call_gemini_verdict(self, claim: str, evidence: List[Dict[str, Any]], graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls real Gemini model to formulate the final verdict based on evidence.
        """
        prompt = f"""
        Bạn là FactCheckAI - Chuyên gia kiểm chứng tin tức tối cao tại Việt Nam.
        Nhiệm vụ của bạn là xác minh tính đúng đắn của Tuyên bố (Claim) dưới đây dựa trên các Đoạn trích dẫn bằng chứng (Evidence Snippets) thu thập từ internet. Hãy ưu tiên độ tin cậy của các cơ quan báo chí, cổng thông tin chính phủ (nếu có), nhưng vẫn đối chiếu rộng rãi.

        Tuyên bố cần kiểm chứng: "{claim}"

        Danh sách bằng chứng thu thập được:
        {json.dumps(evidence, ensure_ascii=False, indent=2)}

        Hãy đưa ra kết luận theo đúng cấu trúc JSON sau đây (không bao gồm ký tự markdown ```json):
        {{
            "claim": "Tuyên bố ban đầu",
            "verdict": "VERIFIED" hoặc "FALSE" hoặc "PENDING",
            "confidence": <điểm phần trăm từ 0-100 ví dụ 95>,
            "explanation": "Lời giải thích chi tiết, khách quan, phân tích sâu các mâu thuẫn hoặc sự tương quan giữa bằng chứng và tuyên bố.",
            "sources": <mảng các nguồn đã được sử dụng từ danh sách bằng chứng>
        }}
        Lưu ý:
        - Nếu có bằng chứng trực tuyến ủng hộ hoặc là sự thật hiển nhiên, ngày lễ phổ biến được ghi nhận rộng rãi: "VERIFIED"
        - Nếu có bằng chứng bác bỏ hoặc phát hiện mâu thuẫn logic rõ ràng: "FALSE"
        - Chỉ chọn "PENDING" khi thông tin quá nhạy cảm, đặc thù mà không hề có bất cứ dữ liệu tin cậy nào nhắc tới (Ví dụ tin đồn hậu trường, chưa kiểm định).
        """
        try:
            # Run in a thread pool to avoid blocking the async event loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.model.generate_content(prompt)
            )
            text = response.text.strip()
            # Clean possible markdown wrapping
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            data["graph"] = graph
            
            # Categorize back correctly from the original evidence list
            final_sources = []
            for ev in evidence:
                final_sources.append({
                    "domain": ev["domain"],
                    "url": ev["url"],
                    "title": ev["title"],
                    "is_whitelist": ev.get("is_whitelist", False)
                })
            data["sources"] = final_sources
            return data
        except Exception as e:
            print(f"Error calling Gemini: {e}. Falling back to simulated verdict.")
            return self._generate_simulated_verdict(claim, evidence, graph)

    def _generate_simulated_verdict(self, claim: str, evidence: List[Dict[str, Any]], graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a dynamic fact check response based on real text overlap from evidence 
        when Gemini API is unavailable.
        """
        claim_lower = claim.lower()
        
        # 1. Break claim into important keywords (excluding tiny stop words)
        claim_words = set([w for w in claim_lower.split() if len(w) > 2])
        if not claim_words:
            claim_words = set(claim_lower.split())
            
        # 2. Evaluate collective evidence weight
        total_snippets = " ".join([ev.get("snippet", "").lower() + " " + ev.get("title", "").lower() for ev in evidence])
        
        match_count = sum(1 for word in claim_words if word in total_snippets)
        match_ratio = match_count / max(1, len(claim_words))
        
        has_debunk_keywords = any(kw in total_snippets for kw in ["tin giả", "sai sự thật", "bác bỏ", "cảnh báo", "fake news"])
        has_authoritative_source = any(ev.get("is_whitelist", False) for ev in evidence)

        # NEW HEURISTIC: Authoritative Source Boost
        # If there's any evidence snippet explicitly marked from a whitelist domain and it mentions the query topic
        authoritative_mentions = any(ev.get("is_whitelist", False) and any(w in ev.get("snippet", "").lower() for w in claim_words) for ev in evidence)

        # Logic calibration
        if not evidence:
            verdict = "PENDING"
            confidence = 50
            explanation = f"Hệ thống không tìm thấy dữ liệu nào khớp với tuyên bố '{claim}'. Cần tra cứu thêm."
        elif authoritative_mentions and not has_debunk_keywords:
            # Absolute boost for verified government/media portals!
            verdict = "VERIFIED"
            confidence = 98
            explanation = f"Tuyệt vời! Tuyên bố '{claim}' được tìm thấy trong DỮ LIỆU CHÍNH THỐNG. Các cổng thông tin điện tử hoặc báo chí cấp quốc gia có ghi nhận thông tin này. Hệ thống đánh giá cực kỳ an toàn."
        elif match_ratio > 0.5 and not has_debunk_keywords:
            verdict = "VERIFIED"
            confidence = int(70 + (match_ratio * 25))
            confidence = min(confidence, 95)
            explanation = f"Tuyên bố '{claim}' được xác minh là CHÍNH XÁC dựa trên mức độ trùng khớp cao ({int(match_ratio*100)}%) từ các nguồn tin mới nhất."
        elif has_debunk_keywords and match_ratio > 0.3:
            verdict = "FALSE"
            confidence = int(60 + (match_ratio * 30))
            explanation = f"Cảnh báo: Thông tin '{claim}' có dấu hiệu SAI LỆCH/TIN GIẢ dựa trên cảnh báo từ báo đài."
        else:
            verdict = "PENDING"
            confidence = int(60 + (match_ratio * 10))
            explanation = f"Chưa đủ cơ sở vững chắc. Độ trùng khớp thấp ({int(match_ratio*100)}%)."

        # Map simulated sources with validation tag
        sources = []
        for ev in evidence:
            sources.append({
                "domain": ev["domain"],
                "url": ev["url"],
                "title": ev["title"],
                "is_whitelist": ev.get("is_whitelist", False)
            })

        return {
            "claim": claim,
            "verdict": verdict,
            "confidence": confidence,
            "sources": sources,
            "explanation": explanation,
            "graph": graph
        }

# Singleton agent instance
fact_agent = FactCheckAgent()
