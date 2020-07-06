from typing import List

from source import Source
from dataclasses import dataclass, field


@dataclass
class Trait:
    id: int = 0
    groups: List[str] = field(default_factory=list)
    source: Source = field(default_factory=Source)
    name: str = ''
    description: str = ''

    def __eq__(self, other):
        return self.name == other.name if type(other) == Trait else self.name == other
