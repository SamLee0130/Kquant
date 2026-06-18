"""
지수 레지스트리 테스트
"""
import pytest

from src.data.index_registry import (
    INDEX_REGISTRY, DEFAULT_INDEX_KEYS, MAX_COMPARISON_INDICES, get_index,
)


class TestRegistryIntegrity:
    def test_keys_match_info_key(self):
        """딕셔너리 키와 IndexInfo.key 일치"""
        for key, info in INDEX_REGISTRY.items():
            assert key == info.key

    def test_currency_limited_to_supported(self):
        """CurrencyConverter는 USD/KRW만 지원"""
        for info in INDEX_REGISTRY.values():
            assert info.currency in ("USD", "KRW")

    def test_kospi_uses_korean_etf(self):
        info = get_index("kospi200")
        assert info.currency == "KRW"
        assert info.etf_ticker.endswith(".KS")


class TestDefaults:
    def test_default_keys_exist(self):
        for key in DEFAULT_INDEX_KEYS:
            assert key in INDEX_REGISTRY

    def test_defaults_within_max(self):
        assert len(DEFAULT_INDEX_KEYS) <= MAX_COMPARISON_INDICES

    def test_get_unknown_key_raises(self):
        with pytest.raises(KeyError):
            get_index("unknown_index")
