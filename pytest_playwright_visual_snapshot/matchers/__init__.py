from .base import ImageMatcher, MatchResult
from .odiff_matcher import ODiffBinaryNotFoundError, ODiffMatcher
from .pixelmatch_matcher import PixelmatchMatcher

_REGISTRY: dict[str, ImageMatcher] = {
    "pixelmatch": PixelmatchMatcher(),
    "odiff": ODiffMatcher(),
}


def get_matcher(name: str) -> ImageMatcher:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown image matcher {name!r}. Known matchers: {known}"
        ) from None


__all__ = [
    "ImageMatcher",
    "MatchResult",
    "ODiffBinaryNotFoundError",
    "ODiffMatcher",
    "PixelmatchMatcher",
    "get_matcher",
]
