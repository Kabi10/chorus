"""Tests for the consensus analysis logic in main.py."""
import pytest
from chorus.main import (
    _build_consensus,
    _jaccard,
    _keywords,
    _tokenize_sentences,
    _sentence_words,
)

# ── _jaccard ──────────────────────────────────────────────────────────────────

def test_jaccard_identical_sets():
    assert _jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

def test_jaccard_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

def test_jaccard_partial_overlap():
    score = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
    # intersection=2, union=4 → 0.5
    assert score == pytest.approx(0.5)

def test_jaccard_empty_both():
    assert _jaccard(set(), set()) == 0.0

def test_jaccard_one_empty():
    assert _jaccard({"a", "b"}, set()) == 0.0

def test_jaccard_single_shared():
    assert _jaccard({"x"}, {"x"}) == 1.0

# ── _keywords ─────────────────────────────────────────────────────────────────

def test_keywords_returns_at_most_top_n():
    kws = _keywords("machine learning deep learning neural network", top_n=2)
    assert len(kws) <= 2

def test_keywords_ranks_by_frequency():
    text = "learning learning learning machine machine neural"
    kws = _keywords(text, top_n=3)
    assert kws[0] == "learning"  # most frequent

def test_keywords_filters_stopwords():
    text = "the quick brown fox is a fast animal and it runs"
    kws = _keywords(text, top_n=10)
    stopwords = {"the", "is", "and", "it", "a"}
    assert not (stopwords & set(kws))

def test_keywords_minimum_word_length():
    # Words < 3 chars are excluded by the regex [a-z]{3,}
    kws = _keywords("an ox is in the box", top_n=10)
    assert all(len(w) >= 3 for w in kws)

def test_keywords_empty_text():
    assert _keywords("", top_n=5) == []

# ── _tokenize_sentences ───────────────────────────────────────────────────────

def test_tokenize_splits_on_period():
    text = "The sky is blue and bright today. The grass is very green outside."
    sents = _tokenize_sentences(text)
    assert len(sents) == 2

def test_tokenize_splits_on_exclamation():
    text = "This is amazing and wonderful! This is also quite interesting here."
    sents = _tokenize_sentences(text)
    assert len(sents) >= 1

def test_tokenize_filters_short_sentences():
    text = "Hi. This sentence is long enough to pass the twenty character filter."
    sents = _tokenize_sentences(text)
    assert all(len(s) > 20 for s in sents)
    assert not any(s == "Hi." for s in sents)

def test_tokenize_empty_text():
    assert _tokenize_sentences("") == []

# ── _sentence_words ───────────────────────────────────────────────────────────

def test_sentence_words_removes_stopwords():
    words = _sentence_words("The quick brown fox jumps over the lazy dog")
    assert "the" not in words   # in _STOP_WORDS
    assert "quick" in words     # not a stop word
    assert "brown" in words     # not a stop word

def test_sentence_words_lowercase():
    words = _sentence_words("Machine Learning Is Great")
    assert "machine" in words
    assert "learning" in words

def test_sentence_words_minimum_length():
    words = _sentence_words("an ox in box runs fast today")
    assert all(len(w) >= 3 for w in words)

# ── _build_consensus ──────────────────────────────────────────────────────────

_RESP_A = (
    "Machine learning is a powerful subset of artificial intelligence. "
    "Neural networks enable deep learning capabilities for complex tasks."
)
_RESP_B = (
    "Machine learning forms a core part of artificial intelligence today. "
    "Neural networks are the foundation of modern deep learning systems."
)
_RESP_C = (
    "Quantum computing will revolutionize cryptography and security. "
    "Blockchain technology ensures immutable distributed ledger records."
)


def test_build_consensus_returns_all_keys():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    for key in ("platform_count", "agreed_themes", "unique_points",
                "platform_scores", "top_keywords", "consensus_keywords", "summary_stats"):
        assert key in result


def test_build_consensus_platform_count():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B, "claude": _RESP_C})
    assert result["platform_count"] == 3


def test_build_consensus_single_platform():
    result = _build_consensus({"gemini": _RESP_A})
    assert result["platform_count"] == 1
    # No pairs to score
    assert result["platform_scores"] == {"gemini": {}}
    # No other platforms to agree with, so agreed_themes empty
    assert result["agreed_themes"] == []


def test_build_consensus_similar_responses_have_agreed_themes():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    # Both discuss machine learning + neural networks — expect at least one agreed theme
    assert len(result["agreed_themes"]) > 0


def test_build_consensus_divergent_responses_have_unique_points():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_C})
    # Very different topics — expect unique points on both sides
    assert len(result["unique_points"]) > 0


def test_build_consensus_platform_scores_are_between_0_and_1():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    for scores in result["platform_scores"].values():
        for score in scores.values():
            assert 0.0 <= score <= 1.0


def test_build_consensus_similar_responses_score_higher_than_divergent():
    similar = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    divergent = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_C})
    sim_score = similar["platform_scores"]["gemini"]["chatgpt"]
    div_score = divergent["platform_scores"]["gemini"]["chatgpt"]
    assert sim_score > div_score


def test_build_consensus_summary_stats_word_count():
    result = _build_consensus({"gemini": _RESP_A})
    stats = result["summary_stats"]["gemini"]
    assert stats["words"] > 0
    assert stats["sentences"] > 0
    assert stats["chars"] == len(_RESP_A)


def test_build_consensus_top_keywords_per_platform():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    for plat in ("gemini", "chatgpt"):
        assert plat in result["top_keywords"]
        assert isinstance(result["top_keywords"][plat], list)


def test_build_consensus_consensus_keywords_appear_in_both():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    # "learning", "machine", "neural" appear in both — expect them in consensus keywords
    ck = result["consensus_keywords"]
    assert any(k in ck for k in ("learning", "machine", "neural", "networks"))


def test_build_consensus_agreed_themes_coverage_is_valid():
    result = _build_consensus({"gemini": _RESP_A, "chatgpt": _RESP_B})
    for theme in result["agreed_themes"]:
        assert 0.0 <= theme["coverage"] <= 1.0
        assert isinstance(theme["platforms"], list)
        assert len(theme["platforms"]) >= 1
