from dataclasses import dataclass, field
from typing import List

from source import Source
from trait import Trait


@dataclass
class Action:
    cost: str = ''
    name: str = ''
    traits: List[str] = field(default_factory=list)
    description: str = ''
    trigger: str = ''
    requirements: str = ''


@dataclass
class Header:
    name: str = ''
    text: str = ''
    modifier: int = 0


@dataclass
class Creature:
    id: int = 0
    source: Source = field(default_factory=Source)
    rarity: str = 'common'
    name: str = ''
    level: int = 0
    alignment: str = ''
    traits: List[Trait] = field(default_factory=list)
    perception: int = 0
    senses: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    otherCommunication: List[str] = field(default_factory=list)
    skills: List[Header] = field(default_factory=list)
    abilityMods: List[int] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    interactionAbilities: List[Action] = field(default_factory=list)
    family: str = ''
    ac: int = 0
    acNotes: str = ''
    fortitude: int = 0
    fortitudeNotes: str = ''
    reflex: int = 0
    reflexNotes: str = ''
    will: int = 0
    willNotes: str = ''
    saveNotes: str = ''
    hitPoints: int = 0
    hitPointsNotes: str = ''
    hardness: int = 0
    regeneration: int = 0
    deactivatedBy: str = ''
    immunities: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    resistances: List[str] = field(default_factory=list)
    automaticAbilities: List[Action] = field(default_factory=list)
    reactiveAbilities: List[Action] = field(default_factory=list)
    size: str = ''
    speed: str = ''
    actions: List[Action] = field(default_factory=list)
    description: str = ''
    bestiary: List[Header] = field(default_factory=list)
