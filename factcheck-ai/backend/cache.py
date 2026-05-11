import json
import os
from typing import Dict, Any, Optional
from .config import CACHE_FILE

class FactCheckCache:
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.cache: Dict[str, Any] = {}
        self._load_cache()
        if not self.cache:
            self._pre_index_defaults()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def _normalize_claim(self, claim: str) -> str:
        # Simple normalization: strip, lowercase, remove special punctuation for matching
        import re
        normalized = claim.strip().lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Remove extra whitespaces
        normalized = " ".join(normalized.split())
        return normalized

    def get(self, claim: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_claim(claim)
        if not normalized or len(normalized) < 3:
            return None
        # Check for exact match
        if normalized in self.cache:
            return self.cache[normalized]
        
        # Stricter fuzzy check: both must be substantial length and similar size
        for cached_normalized, data in self.cache.items():
            if len(normalized) > 30 and len(cached_normalized) > 30:
                shorter = min(len(normalized), len(cached_normalized))
                longer = max(len(normalized), len(cached_normalized))
                # Only match if the shorter is at least 70% of the longer
                if shorter / longer > 0.7:
                    if normalized in cached_normalized or cached_normalized in normalized:
                        return data
        return None

    def set(self, claim: str, result: Dict[str, Any]):
        normalized = self._normalize_claim(claim)
        self.cache[normalized] = result
        self._save_cache()

    def get_all_records(self) -> Dict[str, Any]:
        return self.cache

    def clear(self):
        self.cache = {}
        self._save_cache()

    def _pre_index_defaults(self):
        # Pre-indexed factual claims to showcase instant cache retrieval (Section 5.4)
        defaults = {
            "chinh phu viet nam chinh thuc phe duyet de an phat trien nguon nhan luc nganh ban dan den nam 2030": {
                "claim": "Chính phủ Việt Nam chính thức phê duyệt Đề án phát triển nguồn nhân lực ngành bán dẫn đến năm 2030.",
                "verdict": "VERIFIED",
                "confidence": 98,
                "sources": [
                    {"domain": "chinhphu.vn", "url": "https://chinhphu.vn/de-an-ban-dan-2030", "title": "Phê duyệt Đề án phát triển nguồn nhân lực ngành bán dẫn đến năm 2030, định hướng đến năm 2050"},
                    {"domain": "baochinhphu.vn", "url": "https://baochinhphu.vn/thu-tuong-ky-quyet-dinh-ban-dan", "title": "Quyết định phê duyệt nhân lực công nghệ cao ngành bán dẫn"},
                    {"domain": "vnexpress.net", "url": "https://vnexpress.net/viet-nam-dao-tao-50000-ky-su-ban-dan", "title": "Kế hoạch đào tạo 50.000 kỹ sư bán dẫn của Việt Nam"}
                ],
                "explanation": "Đề án phát triển nguồn nhân lực ngành bán dẫn đã được Thủ tướng Chính phủ chính thức ký duyệt ban hành. Đề án đặt mục tiêu đào tạo ít nhất 50.000 nhân lực có trình độ đại học trở lên phục vụ ngành công nghiệp bán dẫn đến năm 2030, tập trung vào thiết kế vi mạch, đóng gói và kiểm thử.",
                "graph": {
                    "nodes": [
                        {"id": "1", "label": "Chính phủ Việt Nam", "type": "organization"},
                        {"id": "2", "label": "Đề án bán dẫn", "type": "event"},
                        {"id": "3", "label": "Năm 2030", "type": "time"},
                        {"id": "4", "label": "50.000 kỹ sư", "type": "quantity"},
                        {"id": "5", "label": "Đào tạo vi mạch", "type": "concept"}
                    ],
                    "edges": [
                        {"source": "1", "target": "2", "relation": "phê duyệt"},
                        {"source": "2", "target": "3", "relation": "mốc thời gian"},
                        {"source": "2", "target": "4", "relation": "mục tiêu quy mô"},
                        {"source": "2", "target": "5", "relation": "nội dung trọng tâm"}
                    ]
                }
            },
            "thanh pho ho chi minh co tuyet roi day dac lan dau tien trong lich su vao thang 5 nam nay": {
                "claim": "Thành phố Hồ Chí Minh có tuyết rơi dày đặc lần đầu tiên trong lịch sử vào tháng 5 năm nay.",
                "verdict": "FALSE",
                "confidence": 99,
                "sources": [
                    {"domain": "vtv.vn", "url": "https://vtv.vn/tin-gia-tuyet-roi-tphcm", "title": "Cảnh báo tin giả: Không hề có tuyết rơi tại TP.HCM"},
                    {"domain": "thanhnien.vn", "url": "https://thanhnien.vn/thuc-hu-buc-anh-tuyet-roi-giua-sai-gon", "title": "Thực hư bức ảnh 'tuyết rơi trắng xóa' ở trung tâm Quận 1"},
                    {"domain": "vnexpress.net", "url": "https://vnexpress.net/khi-hau-tphcm-khong-the-co-tuyet", "title": "Chuyên gia khí tượng: TP.HCM nằm trong vùng nhiệt đới, tuyệt đối không có tuyết"}
                ],
                "explanation": "Đây hoàn toàn là tin giả (Fake News) lan truyền trên mạng xã hội dựa trên ảnh cắt ghép bằng AI. Khí hậu TP.HCM là nhiệt đới xavan với nhiệt độ quanh năm dao động từ 25°C đến 39°C. Việc có tuyết rơi tại một thành phố nhiệt đới cận xích đạo ở độ cao thấp là bất khả thi về mặt vật lý và khí tượng học.",
                "graph": {
                    "nodes": [
                        {"id": "1", "label": "TP. Hồ Chí Minh", "type": "location"},
                        {"id": "2", "label": "Tuyết rơi dày đặc", "type": "event"},
                        {"id": "3", "label": "Tháng 5 (Mùa mưa nóng)", "type": "time"},
                        {"id": "4", "label": "Khí hậu Nhiệt đới", "type": "concept"},
                        {"id": "5", "label": "Ảnh AI ghép", "type": "concept"}
                    ],
                    "edges": [
                        {"source": "1", "target": "2", "relation": "mâu thuẫn vật lý"},
                        {"source": "1", "target": "4", "relation": "đặc trưng khí hậu"},
                        {"source": "2", "target": "3", "relation": "sai mốc thời tiết"},
                        {"source": "2", "target": "5", "relation": "nguồn gốc tin giả"}
                    ]
                }
            },
            "tram vu tru quoc te iss vua phat hien sinh vat ngoai hanh tinh di dong bam ngoai vo khoang tau": {
                "claim": "Trạm vũ trụ quốc tế ISS vừa phát hiện sinh vật ngoài hành tinh di động bám ngoài vỏ khoang tàu.",
                "verdict": "PENDING",
                "confidence": 75,
                "sources": [
                    {"domain": "nhandan.vn", "url": "https://nhandan.vn/iss-hoat-dong-bao-tri", "title": "Các phi hành gia thực hiện đi bộ ngoài không gian bảo trì ISS"},
                    {"domain": "chinhphu.vn", "url": "https://chinhphu.vn/khoa-hoc-vu-tru", "title": "Tổng quan về hoạt động nghiên cứu vũ trụ"}
                ],
                "explanation": "Hiện tại chưa có bất kỳ công bố khoa học hoặc xác minh chính thức nào từ các cơ quan hàng không vũ trụ uy tín (NASA, Roscosmos, ESA) cũng như các báo chí chính thống Việt Nam xác nhận sự việc này. Các tin tức chính thống trên Whitelist chỉ ghi nhận các hoạt động bảo trì thông thường ngoài không gian. Tin tức này cần chờ thêm thông tin xác minh kiểm chứng (PENDING).",
                "graph": {
                    "nodes": [
                        {"id": "1", "label": "Trạm ISS", "type": "location"},
                        {"id": "2", "label": "Sinh vật ngoài hành tinh", "type": "concept"},
                        {"id": "3", "label": "Đi bộ không gian", "type": "event"},
                        {"id": "4", "label": "NASA/Cơ quan Vũ trụ", "type": "organization"},
                        {"id": "5", "label": "Chưa xác minh", "type": "concept"}
                    ],
                    "edges": [
                        {"source": "1", "target": "3", "relation": "diễn ra hoạt động"},
                        {"source": "2", "target": "1", "relation": "tin đồn bám ngoài"},
                        {"source": "4", "target": "5", "relation": "trạng thái thông báo"},
                        {"source": "2", "target": "5", "relation": "phân loại tin tức"}
                    ]
                }
            }
        }
        for key, val in defaults.items():
            self.cache[key] = val
        self._save_cache()

# Singleton cache instance
fact_cache = FactCheckCache()
