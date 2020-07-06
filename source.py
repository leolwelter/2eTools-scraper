from dataclasses import dataclass


@dataclass
class Source:
    book: str = ''
    page: int = 0
