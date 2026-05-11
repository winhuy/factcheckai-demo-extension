import re

def heuristic(claim, snippets):
    claim_lower = claim.lower()
    claim_words = set([w for w in claim_lower.split() if len(w) > 2])
    if not claim_words:
        claim_words = set(claim_lower.split())

    total_snippets = " ".join(snippets).lower()

    match_count = sum(1 for word in claim_words if word in total_snippets)
    match_ratio = match_count / max(1, len(claim_words))

    has_debunk = any(kw in total_snippets for kw in ["tin giả", "sai sự thật", "bác bỏ", "cảnh báo", "fake news", "hoax", "debunk"])
    
    # Require a higher threshold for authoritative mentions
    authoritative_mentions = False # wait, need to check snippet by snippet
    # we can just use match_ratio
    
    # Check numbers
    numbers_in_claim = set(re.findall(r'\d+', claim))
    numbers_in_snippets = set(re.findall(r'\d+', total_snippets))
    
    numbers_match = True
    if numbers_in_claim:
        numbers_match = all(num in numbers_in_snippets for num in numbers_in_claim)

    if not snippets:
        return "PENDING", 50, "Không tìm thấy dữ liệu..."
    elif has_debunk and match_ratio > 0.3:
        return "FALSE", int(60 + (match_ratio * 30)), "Có dấu hiệu SAI LỆCH/TIN GIẢ..."
    elif not numbers_match:
        return "FALSE", 85, "Các số liệu/thời gian trong tuyên bố không khớp với thông tin từ các nguồn tra cứu."
    elif match_ratio > 0.7:
        return "VERIFIED", int(70 + (match_ratio * 25)), "Tuyên bố được xác minh dựa trên độ trùng khớp cao..."
    else:
        return "PENDING", int(55 + (match_ratio * 15)), "Chưa đủ bằng chứng..."

print(heuristic("Tổng bí thư Tô Lâm sinh 4/8/1965", ["Tổng bí thư Tô Lâm sinh ngày 10/7/1957"]))
