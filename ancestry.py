from dataclasses import field, dataclass
from typing import List
from source import Source
from trait import Trait


@dataclass
class AncestryHeader:
    header: str = ''
    text: str = ''
    table: List[List[str]] = field(default_factory=list)


@dataclass
class Ancestry:
    id: int = 0
    url: str = ''
    name: str = ''
    rarity: str = 'Common'
    traits: List[Trait] = field(default_factory=list)
    source: Source = field(default_factory=Source)
    description: List[AncestryHeader] = field(default_factory=list)
    hitPoints: int = 0
    size: str = ''
    speed: str = ''
    abilityBoosts: List[str] = field(default_factory=list)
    abilityFlaws: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    extras: List[AncestryHeader] = field(default_factory=list)
    senses: List[AncestryHeader] = field(default_factory=list)
