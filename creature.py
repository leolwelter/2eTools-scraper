from dataclasses import dataclass, field
from typing import List, Dict
from source import Source
from trait import Trait


class CastingType:
    prepared = 'prepared'
    spontaneous = 'spontaneous'
    focus = 'focus'
    innate = 'innate'


class SpellTradition:
    arcane = 'arcane'
    occult = 'occult'
    divine = 'divine'
    primal = 'primal'


class Sidebar:
    adviceAndRules = 'Advice and Rules'
    lore = 'Additional Lore'
    locations = 'Locations'
    relatedCreatures = 'Related Creatures'
    treasure = 'Treasure and Rewards'


@dataclass
class SpellEntry:
    name: str = ''
    quantity: int = 0  # 0 if spontaneous or focus
    notes: str = ''  # possibly '(at will)' '(constant)' or other notes


@dataclass
class Action:
    cost: str = ''
    name: str = ''
    traits: List[str] = field(default_factory=list)
    frequency: str = ''
    description: str = ''  # also 'Effect' if no damage entry
    trigger: str = ''
    requirements: str = ''
    damage: str = ''


@dataclass
class Strike(Action):
    strikeType: str = ''


@dataclass
class Header:
    name: str = ''
    text: str = ''
    modifier: int = 0


@dataclass
class Sidebar:
    name: str = ''
    text: str = ''
    sidebarType: Sidebar = Sidebar.adviceAndRules


@dataclass
class Spellcasting:
    tradition: SpellTradition = SpellTradition.arcane
    castType: CastingType = CastingType.prepared
    spellDC: int = 10
    spellAttackModifier: int = 0
    spontaneousSlots: Dict[int, int] = field(default_factory=dict)
    spontaneousSpells: Dict[int, List[SpellEntry]] = field(default_factory=dict)
    preparedSpells: Dict[int, List[SpellEntry]] = field(default_factory=dict)
    focusSpells: List[SpellEntry] = field(default_factory=list)
    focusLevel: int = 0
    focusPoints: int = 0
    cantrips: List[str] = field(default_factory=list)  # can be focus cantrips as well


@dataclass
class Creature:
    id: int = 0
    source: Source = field(default_factory=Source)
    rarity: str = 'common'
    family: str = ''
    name: str = ''
    level: int = 0
    alignment: str = ''
    size: str = ''
    traits: List[Trait] = field(default_factory=list)
    perception: int = 0
    senses: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    otherCommunication: List[str] = field(default_factory=list)
    skills: List[Header] = field(default_factory=list)
    abilityMods: List[int] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    interactionAbilities: List[Action] = field(default_factory=list)
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
    speed: str = ''
    strikes: List[Strike] = field(default_factory=list)
    spells: Spellcasting = field(default_factory=Spellcasting)
    innateSpells: Spellcasting = field(default_factory=Spellcasting)
    focusSpells: Spellcasting = field(default_factory=Spellcasting)
    rituals: List[str] = field(default_factory=list)
    activeAbilities: List[Action] = field(default_factory=list)
    description: str = ''
    sidebars: List[Sidebar] = field(default_factory=list)
