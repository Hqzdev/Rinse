from rapidfuzz import fuzz


class RapidFuzzTextSimilarity:
    def score(self, left: str, right: str) -> float:
        return float(fuzz.token_sort_ratio(left, right))
