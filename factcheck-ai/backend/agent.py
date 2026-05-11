import json
import time
import asyncio
from urllib.parse import urlparse
from typing import AsyncGenerator, Dict, Any, List
from .config import GEMINI_API_KEY, trusted_domains
from .cache import fact_cache
from .search import whitelist_search
from .graph_rag import graph_rag_analyzer


class FactCheckAgent:
    """
    Autonomous Research Agent that coordinates intelligent fact-checking.
    Uses Gemini AI for query classification, smart search query generation,
    evidence evaluation, and verdict determination.
    Falls back to enhanced heuristics when no API key is available.
    """
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.use_real_gemini = False
        self.model = None

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
                self.use_real_gemini = True
                print("Gemini API configured successfully — Autonomous Agent Mode ACTIVE.")
            except Exception as e:
                print(f"Failed to initialize Gemini model: {e}. Falling back to heuristic mode.")
                self.use_real_gemini = False

    async def _gemini_call(self, prompt: str) -> str:
        """Helper to call Gemini in a thread pool and return raw text."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: self.model.generate_content(prompt)
        )
        return response.text.strip()

    async def _gemini_json(self, prompt: str) -> dict:
        """Call Gemini and parse the response as JSON."""
        text = await self._gemini_call(prompt)
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    # ─── STEP 1: Classify the query ───────────────────────────────
    async def _classify_query(self, claim: str) -> dict:
        """Use Gemini to classify whether this is a simple factual question or a claim to verify."""
        if not self.use_real_gemini:
            return self._classify_query_heuristic(claim)

        prompt = f"""Phân loại câu sau đây vào MỘT trong hai loại:
1. "FACTUAL_SIMPLE" — Câu hỏi có đáp án cụ thể, có thể tra cứu được (ví dụ: ngày sinh, thủ đô, sự kiện lịch sử cụ thể)
2. "CLAIM_VERIFY" — Tuyên bố/tin tức cần kiểm chứng tính đúng sai

Câu: "{claim}"

Trả lời ĐÚNG format JSON (không markdown):
{{"type": "FACTUAL_SIMPLE" hoặc "CLAIM_VERIFY", "reason": "lý do ngắn gọn"}}"""
        try:
            return await self._gemini_json(prompt)
        except Exception as e:
            print(f"Classification failed: {e}")
            return {"type": "CLAIM_VERIFY", "reason": "fallback"}

    def _classify_query_heuristic(self, claim: str) -> dict:
        """Heuristic classification when Gemini is unavailable."""
        q_indicators = ["là gì", "là ai", "sinh ngày", "sinh năm", "bao nhiêu", "ở đâu",
                        "khi nào", "năm nào", "ngày nào", "thủ đô", "dân số", "cao bao nhiêu",
                        "who is", "when", "where", "what is", "how many", "born"]
        claim_lower = claim.lower()
        if any(q in claim_lower for q in q_indicators) or claim.strip().endswith("?"):
            return {"type": "FACTUAL_SIMPLE", "reason": "heuristic: question pattern detected"}
        return {"type": "CLAIM_VERIFY", "reason": "heuristic: statement pattern"}

    # ─── STEP 2: Generate smart search queries ───────────────────
    async def _generate_search_queries(self, claim: str, query_type: str) -> List[str]:
        """Use Gemini to generate optimal search queries."""
        if not self.use_real_gemini:
            return self._generate_queries_heuristic(claim)

        prompt = f"""Bạn là chuyên gia tìm kiếm thông tin. Hãy tạo 2-4 search queries tối ưu để tìm kiếm trên internet nhằm {"trả lời câu hỏi" if query_type == "FACTUAL_SIMPLE" else "kiểm chứng tuyên bố"} sau:

"{claim}"

Yêu cầu:
- Tạo queries bằng CẢ tiếng Việt và tiếng Anh nếu phù hợp
- Queries phải đa dạng góc nhìn để tìm được nhiều nguồn khác nhau
- Nếu là kiểm chứng tin, thêm query tìm bác bỏ/debunk

Trả lời ĐÚNG format JSON (không markdown):
{{"queries": ["query1", "query2", "query3"]}}"""
        try:
            data = await self._gemini_json(prompt)
            return data.get("queries", [claim])
        except Exception as e:
            print(f"Query generation failed: {e}")
            return self._generate_queries_heuristic(claim)

    def _generate_queries_heuristic(self, claim: str) -> List[str]:
        """Generate search queries without Gemini."""
        queries = [claim[:150]]
        words = [w for w in claim.split() if len(w) > 2]
        if len(words) > 4:
            queries.append(" ".join(words[:5]))
        keywords_check = claim[:100] + " tin giả hay thật"
        if len(claim) > 20:
            queries.append(keywords_check)
        return queries

    # ─── STEP 3: Evaluate evidence and decide ────────────────────
    async def _evaluate_evidence(self, claim: str, query_type: str,
                                  evidence: List[Dict], page_contents: Dict[str, str] = None) -> dict:
        """Use Gemini to evaluate all collected evidence and produce a verdict."""
        if not self.use_real_gemini:
            return self._generate_simulated_verdict(claim, evidence, {"nodes": [], "edges": [], "has_conflict": False, "conflict_message": ""})

        # Build evidence context string
        evidence_text = ""
        for i, ev in enumerate(evidence[:12], 1):
            evidence_text += f"\n--- Nguồn {i} ({ev['domain']}) {'[TRUSTED]' if ev.get('is_trusted') else '[UNVERIFIED]'} ---\n"
            evidence_text += f"Title: {ev['title']}\n"
            evidence_text += f"Snippet: {ev['snippet']}\n"
            # Add full page content if available
            if page_contents and ev['url'] in page_contents and page_contents[ev['url']]:
                evidence_text += f"Nội dung chi tiết: {page_contents[ev['url']][:1500]}\n"

        if query_type == "FACTUAL_SIMPLE":
            prompt = f"""Bạn là FactCheckAI — trợ lý tra cứu thông tin thông minh và CHÍNH XÁC TUYỆT ĐỐI.

Câu hỏi / Tuyên bố: "{claim}"

Dưới đây là thông tin thu thập được từ internet:
{evidence_text}

QUY TRÌNH BẮT BUỘC — PHẢI TUÂN THỦ TỪNG BƯỚC:

BƯỚC 1: Trích xuất DỮ LIỆU CỤ THỂ từ tuyên bố:
- Tên người, tổ chức, địa điểm
- Ngày tháng năm sinh, năm sự kiện, mốc thời gian CỤ THỂ
- Số liệu, con số cụ thể
- Chức vụ, vai trò

BƯỚC 2: Trích xuất DỮ LIỆU TƯƠNG ỨNG từ các nguồn bằng chứng:
- Tìm CHÍNH XÁC các thông tin tương ứng trong bằng chứng
- Ghi rõ nguồn nào nói gì

BƯỚC 3: SO SÁNH CHÉO TỪNG CHI TIẾT:
- So sánh từng dữ liệu cụ thể (ngày, số, tên, chức vụ...)
- Nếu tuyên bố nói "sinh ngày X" nhưng bằng chứng cho thấy "sinh ngày Y" → đó là SAI
- Nếu tuyên bố nói con số A nhưng thực tế là B → đó là SAI
- CHỈ khi TẤT CẢ chi tiết cụ thể đều khớp mới được coi là VERIFIED

⚠️ CẢNH BÁO QUAN TRỌNG:
- KHÔNG BAO GIỜ xác nhận VERIFIED chỉ vì tìm thấy tên người/chủ đề trong bằng chứng
- Phải kiểm tra TỪNG con số, TỪNG ngày tháng, TỪNG chi tiết cụ thể
- Nếu ngày sinh, năm sinh, số liệu KHÔNG KHỚP → verdict phải là "FALSE"
- Nếu không tìm thấy dữ liệu cụ thể để so sánh → verdict phải là "PENDING"

Trả lời ĐÚNG format JSON (không markdown):
{{
    "claim": "{claim}",
    "verdict": "VERIFIED" hoặc "FALSE" hoặc "PENDING",
    "confidence": <0-100>,
    "explanation": "Phân tích chi tiết: liệt kê dữ liệu trong tuyên bố vs dữ liệu trong bằng chứng, chỉ rõ khớp hay không khớp.",
    "direct_answer": "Câu trả lời ngắn gọn nhất, nêu rõ thông tin đúng nếu tuyên bố sai.",
    "sources": [tên các nguồn domain đã sử dụng]
}}"""
        else:
            prompt = f"""Bạn là FactCheckAI — Chuyên gia kiểm chứng tin tức NGHIÊM NGẶT NHẤT.
Nhiệm vụ: Xác minh tính đúng đắn của tuyên bố dựa trên bằng chứng thu thập từ TOÀN BỘ internet.

Tuyên bố cần kiểm chứng: "{claim}"

Bằng chứng thu thập:
{evidence_text}

QUY TRÌNH BẮT BUỘC — PHẢI TUÂN THỦ TỪNG BƯỚC:

BƯỚC 1: Trích xuất MỌI DỮ LIỆU CỤ THỂ từ tuyên bố:
- Tên người, tổ chức, địa điểm
- Ngày tháng năm, mốc thời gian CỤ THỂ (ví dụ: sinh ngày X, năm Y)
- Số liệu, con số cụ thể
- Chức vụ, vai trò, sự kiện

BƯỚC 2: Trích xuất DỮ LIỆU TƯƠNG ỨNG từ bằng chứng:
- Tìm CHÍNH XÁC thông tin tương ứng trong từng nguồn bằng chứng
- Nếu nguồn nói "sinh ngày 10/7/1957" mà tuyên bố nói "sinh 4/8/1965" → GHI NHẬN sự khác biệt

BƯỚC 3: SO SÁNH CHÉO TỪNG CHI TIẾT CỤ THỂ:
- So sánh TỪNG con số, TỪNG ngày tháng giữa tuyên bố và bằng chứng
- Chỉ 1 chi tiết sai = toàn bộ tuyên bố là FALSE

⚠️ QUY TẮC NGHIÊM NGẶT — KHÔNG ĐƯỢC VI PHẠM:
1. KHÔNG BAO GIỜ xác nhận VERIFIED chỉ vì chủ đề/tên người xuất hiện trong nguồn tin cậy
2. Phải kiểm tra TỪNG chi tiết: ngày sinh, năm, số liệu, chức vụ, địa điểm
3. Nếu BẤT KỲ con số hoặc ngày tháng nào KHÔNG KHỚP → verdict = "FALSE"
4. Nếu các nguồn chỉ đề cập chủ đề chung mà KHÔNG xác nhận chi tiết cụ thể → verdict = "PENDING"
5. VERIFIED chỉ khi có bằng chứng TRỰC TIẾP xác nhận TỪNG chi tiết trong tuyên bố

Ví dụ:
- Tuyên bố "A sinh ngày 4/8/1965" + Bằng chứng nói "A sinh ngày 10/7/1957" → FALSE (ngày sinh sai)
- Tuyên bố "Dân số X là 100 triệu" + Bằng chứng nói "95 triệu" → FALSE (số liệu sai)
- Tuyên bố "A sinh ngày 4/8/1961" + Bằng chứng xác nhận "4/8/1961" → VERIFIED

Trả lời ĐÚNG format JSON (không markdown):
{{
    "claim": "Tuyên bố ban đầu",
    "verdict": "VERIFIED" hoặc "FALSE" hoặc "PENDING",
    "confidence": <0-100>,
    "explanation": "Liệt kê cụ thể: dữ liệu trong tuyên bố vs dữ liệu thực tế từ bằng chứng. Chỉ rõ chi tiết nào khớp, chi tiết nào sai.",
    "needs_more_search": <true/false — cần tìm thêm không?>
}}"""

        try:
            result = await self._gemini_json(prompt)
            # Attach sources from evidence
            final_sources = []
            for ev in evidence:
                final_sources.append({
                    "domain": ev["domain"], "url": ev["url"], "title": ev["title"],
                    "is_whitelist": ev.get("is_whitelist", False), "is_trusted": ev.get("is_trusted", False)
                })
            result["sources"] = final_sources
            return result
        except Exception as e:
            print(f"Evaluation failed: {e}")
            return self._generate_simulated_verdict(claim, evidence, {"nodes": [], "edges": [], "has_conflict": False, "conflict_message": ""})

    # ─── MAIN ORCHESTRATOR ────────────────────────────────────────
    async def check_claim_stream(self, claim: str, source_url: str = None) -> AsyncGenerator[str, None]:
        """Asynchronously streams the autonomous research process via SSE."""

        # Step 0: Check Cache
        yield "data: " + json.dumps({"event": "thought", "message": "🔍 Đang truy vấn Bộ nhớ đệm (Cache)..."}) + "\n\n"
        await asyncio.sleep(0.5)

        cached_result = fact_cache.get(claim)
        if cached_result:
            yield "data: " + json.dumps({"event": "thought", "message": "⚡ Tìm thấy trong Cache! Trả kết quả tức thì."}) + "\n\n"
            await asyncio.sleep(0.4)
            yield "data: " + json.dumps({"event": "result", "data": cached_result, "cached": True}) + "\n\n"
            return

        # Step 1: Classify query
        yield "data: " + json.dumps({"event": "thought", "message": "🧠 AI đang phân tích loại câu hỏi..."}) + "\n\n"
        await asyncio.sleep(0.6)

        classification = await self._classify_query(claim)
        query_type = classification.get("type", "CLAIM_VERIFY")
        type_label = "📋 Câu hỏi tra cứu (Factual)" if query_type == "FACTUAL_SIMPLE" else "🔎 Tuyên bố cần kiểm chứng (Claim)"
        yield "data: " + json.dumps({"event": "thought", "message": f"📊 Phân loại: {type_label} — {classification.get('reason', '')}"}) + "\n\n"
        await asyncio.sleep(0.6)

        # Step 2: Generate smart search queries
        yield "data: " + json.dumps({"event": "thought", "message": "🎯 AI đang tạo các search queries thông minh..."}) + "\n\n"
        await asyncio.sleep(0.5)

        search_queries = await self._generate_search_queries(claim, query_type)
        queries_display = " | ".join([f'`{q}`' for q in search_queries])
        yield "data: " + json.dumps({"event": "thought", "message": f"🌐 Tìm kiếm trên TOÀN BỘ INTERNET với {len(search_queries)} queries: {queries_display}"}) + "\n\n"
        await asyncio.sleep(0.8)

        # Step 3: Execute multi-search
        evidence_snippets = whitelist_search.multi_search(search_queries, limit_per_query=5)

        trusted_sources = [s for s in evidence_snippets if s.get('is_trusted', False)]
        unverified_sources = [s for s in evidence_snippets if not s.get('is_trusted', False)]
        sources_list = ", ".join([s['domain'] for s in evidence_snippets[:8]])
        yield "data: " + json.dumps({"event": "thought", "message": f"📰 Thu thập được {len(evidence_snippets)} nguồn ({len(trusted_sources)} chính thống 🟢, {len(unverified_sources)} chưa xác minh 🟡): [{sources_list}]"}) + "\n\n"
        await asyncio.sleep(0.6)

        # Step 3.5: Fetch page content from top sources for deeper analysis
        page_contents = {}
        if evidence_snippets:
            top_urls = [ev["url"] for ev in evidence_snippets[:3]]
            yield "data: " + json.dumps({"event": "thought", "message": f"📖 Đang đọc nội dung chi tiết từ {len(top_urls)} trang web hàng đầu..."}) + "\n\n"
            try:
                page_contents = await whitelist_search.fetch_multiple_pages(top_urls, max_chars_per_page=2000)
                fetched_count = sum(1 for v in page_contents.values() if v)
                yield "data: " + json.dumps({"event": "thought", "message": f"✅ Đã đọc thành công nội dung từ {fetched_count}/{len(top_urls)} trang web."}) + "\n\n"
            except Exception as e:
                yield "data: " + json.dumps({"event": "thought", "message": f"⚠️ Không thể đọc chi tiết trang web: {str(e)[:80]}"}) + "\n\n"
            await asyncio.sleep(0.5)

        # Step 4: Graph-RAG analysis
        yield "data: " + json.dumps({"event": "thought", "message": "🔗 Đang dựng đồ thị tri thức Graph-RAG..."}) + "\n\n"
        await asyncio.sleep(0.6)

        if self.use_real_gemini:
            graph_data = await graph_rag_analyzer.extract_graph_with_ai(claim, evidence_snippets, self.model)
        else:
            graph_data = graph_rag_analyzer.extract_graph(claim, evidence_snippets)

        if graph_data["has_conflict"]:
            yield "data: " + json.dumps({"event": "thought", "message": f"⚠️ CẢNH BÁO: {graph_data['conflict_message']}"}) + "\n\n"
        else:
            yield "data: " + json.dumps({"event": "thought", "message": "✅ Không phát hiện xung đột logic trong đồ thị tri thức."}) + "\n\n"
        await asyncio.sleep(0.5)

        # Step 5: AI evaluates evidence and produces verdict
        yield "data: " + json.dumps({"event": "thought", "message": "⚖️ AI đang tổng hợp và đánh giá toàn bộ bằng chứng..."}) + "\n\n"
        await asyncio.sleep(0.6)

        result_data = await self._evaluate_evidence(claim, query_type, evidence_snippets, page_contents)

        # Step 5.5: If AI says needs more search, do a second round
        if result_data.get("needs_more_search") and self.use_real_gemini:
            yield "data: " + json.dumps({"event": "thought", "message": "🔄 AI yêu cầu tìm kiếm thêm thông tin bổ sung (Vòng 2)..."}) + "\n\n"
            await asyncio.sleep(0.5)

            # Deep search for more results
            extra_evidence = whitelist_search.deep_search(claim, limit=10)
            new_evidence = [e for e in extra_evidence if e["url"] not in {ev["url"] for ev in evidence_snippets}]

            if new_evidence:
                evidence_snippets.extend(new_evidence)
                yield "data: " + json.dumps({"event": "thought", "message": f"📰 Tìm thêm được {len(new_evidence)} nguồn bổ sung. Tổng cộng: {len(evidence_snippets)} nguồn."}) + "\n\n"
                await asyncio.sleep(0.5)

                yield "data: " + json.dumps({"event": "thought", "message": "⚖️ AI đang đánh giá lại với bằng chứng mở rộng..."}) + "\n\n"
                result_data = await self._evaluate_evidence(claim, query_type, evidence_snippets, page_contents)

        # Remove internal flag before sending to client
        result_data.pop("needs_more_search", None)
        result_data.pop("direct_answer", None)

        # Attach graph data
        result_data["graph"] = graph_data

        # Store in cache
        fact_cache.set(claim, result_data)

        yield "data: " + json.dumps({"event": "result", "data": result_data, "cached": False}) + "\n\n"

    def _generate_simulated_verdict(self, claim: str, evidence: List[Dict[str, Any]], graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced heuristic verdict when Gemini API is unavailable.
        Uses smart cross-referencing of dates, numbers, and factual details.
        """
        import re
        claim_lower = claim.lower()
        claim_words = set([w for w in claim_lower.split() if len(w) > 2])
        if not claim_words:
            claim_words = set(claim_lower.split())

        total_snippets = " ".join([ev.get("snippet", "").lower() + " " + ev.get("title", "").lower() for ev in evidence])

        match_count = sum(1 for word in claim_words if word in total_snippets)
        match_ratio = match_count / max(1, len(claim_words))

        has_debunk = any(kw in total_snippets for kw in [
            "tin giả", "sai sự thật", "bác bỏ", "cảnh báo", "fake news", 
            "hoax", "debunk", "không đúng", "không chính xác", "sai lệch"
        ])
        
        # ─── SMART DATE/NUMBER VERIFICATION ─────────────────────────
        # Extract full date patterns from claim (e.g., "4/8/1965", "10-7-1957")
        date_patterns_claim = re.findall(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}', claim)
        # Extract year-like numbers (4 digits starting with 1 or 2)
        years_in_claim = set(re.findall(r'\b[12]\d{3}\b', claim))
        # Extract significant numbers (3+ digits, excluding years already captured)
        significant_numbers_claim = set(re.findall(r'\b\d{3,}\b', claim)) - years_in_claim
        
        # Same extractions from snippets
        date_patterns_snippets = re.findall(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}', total_snippets)
        years_in_snippets = set(re.findall(r'\b[12]\d{3}\b', total_snippets))
        
        # Check if claim contains date-related keywords (sinh, ngày, năm, tháng)
        has_date_context = any(kw in claim_lower for kw in [
            'sinh', 'ngày', 'năm', 'tháng', 'ngay', 'nam', 'thang',
            'born', 'date', 'year'
        ])
        
        date_mismatch = False
        mismatch_details = ""
        
        # Strategy 1: If claim has a full date pattern, check if that exact date appears in snippets
        if date_patterns_claim:
            claim_date = date_patterns_claim[0]
            # Normalize date separators for comparison
            claim_date_normalized = claim_date.replace('-', '/').replace('.', '/')
            snippets_dates_normalized = [d.replace('-', '/').replace('.', '/') for d in date_patterns_snippets]
            
            if snippets_dates_normalized:
                # There ARE dates in snippets - check if our date matches any
                if claim_date_normalized not in snippets_dates_normalized:
                    date_mismatch = True
                    found_date = snippets_dates_normalized[0] if snippets_dates_normalized else "khác"
                    mismatch_details = f"Tuyên bố ghi ngày {claim_date} nhưng các nguồn cho thấy ngày {found_date}."
        
        # Strategy 2: If claim has a year with date context, check year matches
        if not date_mismatch and years_in_claim and has_date_context:
            for year in years_in_claim:
                if year not in years_in_snippets:
                    # The specific year in the claim doesn't appear anywhere in the evidence
                    date_mismatch = True
                    found_years = [y for y in years_in_snippets if abs(int(y) - int(year)) < 50]
                    if found_years:
                        mismatch_details = f"Tuyên bố ghi năm {year} nhưng các nguồn chỉ đề cập năm {', '.join(sorted(found_years))}."
                    else:
                        mismatch_details = f"Không tìm thấy năm {year} trong bất kỳ nguồn nào."
        
        # Strategy 3: Cross-reference — look for known person's actual birthdate in snippets
        # If snippets contain a DIFFERENT date associated with the same subject
        birth_keywords = ['sinh ngày', 'sinh ngay', 'born on', 'date of birth', 
                         'sinh năm', 'sinh nam', 'born in']
        if has_date_context and not date_mismatch:
            for snippet_date in date_patterns_snippets:
                snippet_date_norm = snippet_date.replace('-', '/').replace('.', '/')
                for claim_date in date_patterns_claim:
                    claim_date_norm = claim_date.replace('-', '/').replace('.', '/')
                    if claim_date_norm != snippet_date_norm:
                        # Found a different date in the evidence
                        date_mismatch = True
                        mismatch_details = f"Bằng chứng cho thấy ngày đúng là {snippet_date}, không phải {claim_date} như tuyên bố."
                        break
                if date_mismatch:
                    break

        # ─── VERDICT LOGIC ───────────────────────────────────────────
        authoritative_mentions = any(
            ev.get("is_trusted", False) and match_ratio > 0.6
            for ev in evidence
        )

        if not evidence:
            verdict, confidence = "PENDING", 50
            explanation = f"Không tìm thấy dữ liệu nào liên quan đến '{claim}'. Cần tra cứu thêm."
        elif has_debunk and match_ratio > 0.3:
            verdict = "FALSE"
            confidence = int(60 + (match_ratio * 30))
            explanation = f"Thông tin '{claim}' có dấu hiệu SAI LỆCH/TIN GIẢ dựa trên cảnh báo từ các nguồn."
        elif date_mismatch:
            verdict, confidence = "FALSE", 90
            explanation = f"SAI SỰ THẬT: {mismatch_details} Thông tin cụ thể (ngày tháng/số liệu) trong tuyên bố không khớp với dữ liệu từ các nguồn tra cứu chính thống."
        elif authoritative_mentions and not has_debunk and not date_mismatch:
            # Only verify if we have date context AND the dates matched, OR no dates to check
            if has_date_context and date_patterns_claim and not date_patterns_snippets:
                # Claim has specific dates but NO dates found in snippets to confirm
                verdict, confidence = "PENDING", 60
                explanation = f"Tuyên bố chứa thông tin ngày tháng cụ thể nhưng không tìm được dữ liệu tương ứng để xác minh từ các nguồn."
            else:
                verdict, confidence = "VERIFIED", 95
                explanation = f"Tuyên bố '{claim}' được tìm thấy và xác minh qua nguồn chính thống đáng tin cậy."
        elif match_ratio > 0.6 and not date_mismatch:
            if has_date_context and date_patterns_claim and not date_patterns_snippets:
                verdict, confidence = "PENDING", 60
                explanation = f"Chủ đề khớp nhưng không tìm được dữ liệu ngày tháng cụ thể để xác nhận."
            else:
                verdict = "VERIFIED"
                confidence = min(int(70 + (match_ratio * 25)), 93)
                explanation = f"Tuyên bố được xác minh dựa trên độ trùng khớp cao ({int(match_ratio*100)}%) từ các nguồn internet."
        else:
            verdict, confidence = "PENDING", int(55 + (match_ratio * 15))
            explanation = f"Chưa đủ bằng chứng xác thực. Độ trùng khớp: {int(match_ratio*100)}%."

        sources = [{"domain": ev["domain"], "url": ev["url"], "title": ev["title"],
                     "is_whitelist": ev.get("is_whitelist", False), "is_trusted": ev.get("is_trusted", False)}
                    for ev in evidence]

        return {"claim": claim, "verdict": verdict, "confidence": confidence,
                "sources": sources, "explanation": explanation, "graph": graph}


# Singleton agent instance
fact_agent = FactCheckAgent()
