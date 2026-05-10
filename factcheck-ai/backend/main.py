import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

from .config import whitelist_domains, DEFAULT_WHITELIST_DOMAINS, PORT, HOST
from .cache import fact_cache
from .agent import fact_agent

app = FastAPI(
    title="FactCheckAI Backend",
    description="Hệ thống xác minh thông tin dựa trên AI Agent & RAG với các nguồn Whitelist chính thống",
    version="1.0.0"
)

# Enable CORS for Chrome Extension and independent frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FactCheckRequest(BaseModel):
    claim: str
    source_url: str = None

class WhitelistAddRequest(BaseModel):
    domain: str

@app.post("/api/fact-check")
async def verify_claim(request: FactCheckRequest):
    """
    Endpoint chính xử lý việc xác minh tin tức và phát ra tiến trình suy nghĩ dạng Streaming SSE.
    """
    if not request.claim.strip():
        raise HTTPException(status_code=400, detail="Nội dung kiểm chứng không được để trống")
        
    return StreamingResponse(
        fact_agent.check_claim_stream(request.claim, request.source_url),
        media_type="text/event-stream"
    )

@app.get("/api/whitelist")
async def get_whitelist():
    """
    Lấy danh sách các tên miền Whitelist hiện tại.
    """
    return {"domains": whitelist_domains}

@app.post("/api/whitelist")
async def add_to_whitelist(request: WhitelistAddRequest):
    """
    Thêm một tên miền mới vào danh sách Whitelist.
    """
    domain = request.domain.strip().lower()
    if not domain:
        raise HTTPException(status_code=400, detail="Tên miền không hợp lệ")
    if domain in whitelist_domains:
        return {"message": "Tên miền đã tồn tại trong Whitelist", "domains": whitelist_domains}
    
    whitelist_domains.append(domain)
    return {"message": f"Đã thêm thành công tên miền {domain}", "domains": whitelist_domains}

@app.delete("/api/whitelist/{domain}")
async def delete_from_whitelist(domain: str):
    """
    Xóa một tên miền khỏi Whitelist.
    """
    domain_clean = domain.strip().lower()
    if domain_clean not in whitelist_domains:
        raise HTTPException(status_code=404, detail="Không tìm thấy tên miền này trong Whitelist")
    
    whitelist_domains.remove(domain_clean)
    return {"message": f"Đã xóa thành công tên miền {domain_clean}", "domains": whitelist_domains}

@app.post("/api/whitelist/reset")
async def reset_whitelist():
    """
    Reset danh sách Whitelist về mặc định.
    """
    global whitelist_domains
    whitelist_domains.clear()
    whitelist_domains.extend(DEFAULT_WHITELIST_DOMAINS)
    return {"message": "Đã reset Whitelist về danh sách mặc định", "domains": whitelist_domains}

@app.get("/api/cache-stats")
async def get_cache_stats():
    """
    Lấy thông số và bản ghi lưu trong cache.
    """
    all_records = fact_cache.get_all_records()
    total_entries = len(all_records)
    
    # Calculate categories
    verified_count = sum(1 for item in all_records.values() if item.get("verdict") == "VERIFIED")
    false_count = sum(1 for item in all_records.values() if item.get("verdict") == "FALSE")
    pending_count = sum(1 for item in all_records.values() if item.get("verdict") == "PENDING")
    
    return {
        "total_cache_entries": total_entries,
        "verified_count": verified_count,
        "false_count": false_count,
        "pending_count": pending_count,
        "records": list(all_records.values())
    }

@app.post("/api/cache/clear")
async def clear_cache():
    """
    Xóa sạch bộ nhớ đệm Cache.
    """
    fact_cache.clear()
    # Re-initialize defaults
    fact_cache._pre_index_defaults()
    return {"message": "Đã xóa sạch và thiết lập lại Cache mặc định"}

# Mount Static Dashboard Files (HTML/CSS/JS)
# First we make sure the static directory exists, then we mount it to the root "/"
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    print(f"Warning: Static directory not found at {static_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
