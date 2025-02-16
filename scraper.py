import dataclasses
import os
import sys
from enum import Enum
from typing import List, Optional, Tuple, Match, Any, Union
from urllib.error import HTTPError
from bs4 import BeautifulSoup, NavigableString, Tag
import urllib.request as fetch
from pymongo import MongoClient
import re

from ancestry import Ancestry, AncestryHeader
from creature import Creature, Header, Action, Sidebar, Strike
from source import Source
from trait import Trait
from local_config import config


class GameType(Enum):
    CREATURE = 'creature'
    SPELL = 'spell'
    TRAIT = 'trait'
    WEAPON = 'weapon'
    ANCESTRY = 'ancestry'


# includes empty strings for bad pages on AoN
def fetch_pages(typ: GameType, cache_only: bool = None) -> Optional[List[str]]:
    pages: List[str] = []
    if typ == GameType.CREATURE:
        fetch_url: str = 'https://2e.aonprd.com/Monsters.aspx?id={}'
        data_path: str = 'data/creatures/{}.html'
        max_id: int = 982
    elif typ == GameType.TRAIT:
        fetch_url: str = 'https://2e.aonprd.com/Traits.aspx?id={}'
        data_path: str = 'data/traits/{}.html'
        max_id: int = 316
    elif typ == GameType.ANCESTRY:
        fetch_url: str = 'https://2e.aonprd.com/Ancestries.aspx?id={}'
        data_path: str = 'data/ancestries/{}.html'
        max_id: int = 22
    else:
        return None

    print('Fetching {}'.format(typ))
    for m_id in range(1, max_id):
        if os.path.exists(data_path.format(m_id)):
            print('found cached {}'.format(m_id))
            with open(data_path.format(m_id), 'r', encoding='utf8') as inf:
                pages.append(inf.read())
        elif cache_only:
            print('appending empty string to id {} (for enumeration purposes)'.format(m_id))
            pages.append('')
        elif not cache_only:
            print('fetching {}'.format(m_id))
            try:
                with fetch.urlopen(fetch_url.format(m_id)) as res:
                    s = res.read()
                    if s:
                        pages.append(s)
                        with open(data_path.format(m_id), 'wb') as outf:
                            outf.write(s)
                    else:
                        pass  # TODO USE CACHE HERE
            except HTTPError:
                print('ERROR fetching {}'.format(m_id))
                pages.append('')
    return pages


def get_abilities(start_tag: Tag) -> Tuple[List[Action], Tag]:
    ability_tag = start_tag
    while ability_tag.next:
        if ability_tag.name == 'b' or ability_tag.name == 'hr':
            break
        ability_tag = ability_tag.next

    abilities: List[Action] = []
    descr_arr: List[str] = []
    name_arr: List[str] = []
    inter_str: str = ''
    while ability_tag.next:
        if ability_tag.name == 'hr':
            descr_arr.append(inter_str)
            break
        if type(ability_tag) == NavigableString:
            inter_str = ''.join((inter_str, ability_tag.string))
        elif ability_tag.name == 'b':
            if ability_tag.string and ability_tag.string.strip() != 'Trigger' and ability_tag.string.strip() != 'Effect':
                name_arr.append(ability_tag.string.strip())
            elif not ability_tag.string and type(ability_tag.next) == NavigableString:
                name_arr.append(ability_tag.next.string.strip())  # just assume next NavigableString is the label
        elif ability_tag.name and ability_tag.get('alt') and ability_tag.get('class') == ['actiondark']:
            inter_str = ''.join((inter_str, ability_tag.get('alt')))
        elif ability_tag.name == 'br':
            descr_arr.append(inter_str)
            inter_str = ''
        ability_tag = ability_tag.next

    ability_re = re.compile(r'\s*((?P<cost>(Single Action|Two Actions|Three Actions|Reaction|Free Action)+)\s*)?'
                            r'(\((?P<traits>[\w, ]+)\)\s*)?'
                            r'(Trigger\s*(?P<trigger>[\w\d\s\-()\'’+.,]+)[.;]?\s*Effect\s*)?'
                            r'(Requirements\s*(?P<requirements>[\w\d\s\-()\'’+.,]+);\s*)?'
                            r'(Effect\s*)?(?P<description>.*)\s*')
    for (name, descr) in zip(name_arr, descr_arr):
        if name == 'Items':
            continue
        descr = descr.replace(name, '', 1)
        ab_match = re.match(ability_re, descr)
        act = Action()
        if not ab_match:
            raise ValueError('no ability match found for ability')
        act.cost = ab_match.group('cost') if ab_match.group('cost') else ''
        act.trigger = ab_match.group('trigger') if ab_match.group('trigger') else ''
        act.traits = [x.strip() for x in ab_match.group('traits').split(',')] if ab_match.group('traits') else []
        act.requirements = ab_match.group('requirements') if ab_match.group('requirements') else ''
        act.description = ab_match.group('description')
        act.name = name
        abilities.append(act)
    return abilities, ability_tag


# parse all of the strikes found after start_tag
# if reaching a header (h1/2/3) or a spellcasting entry, or a sidebar entry, or div.class is ['clear'], stop iterating
def get_strikes(start_tag: Tag) -> Tuple[List[Action], Tag]:
    strikes: List[Action] = []
    tag = start_tag  # assumed start at the 'b' Speed tag
    active_entries: Optional[List[Tag]] = tag.previous.find_all_next('span', class_=['hanging-indent'])
    strike_str = ''
    strike_re = re.compile(r'\s*(?P<typ>Melee|Ranged)\s*'
                           r'(?P<cost>SingleAction|TwoActions|ThreeActions)\s*'
                           r'(?P<name>[\w\d\s\-()\'’+.,]+)\s*'
                           r'(?P<mod>[+\-]+\d+)\s*'
                           r'(?P<multi>\[[+\-]+\d+/[+\-]+\d+\]\s*)?'
                           r'(\((?P<traits>[\w, ]+)\)\s*)?'
                           r'(,\s*Damage\s*(?P<damage>[\w\d\s\-()\'’+.,]+)\s*)?'
                           r'(,\s*Effect\s*(?P<effect>[\w\d\s\-()\'’+.,]+)\s*)?')
    for entry in active_entries:
        strike_str = ''.join([x.string for x in entry.children if not x.name])
        match = re.match(strike_re, strike_str)
        if match:
            gd = match.groupdict()
            strike = Strike(gd['cost'], gd['name'], gd['traits'].split(','), gd['frequency'], gd['description'],
                            damage=gd['damage'], strikeType=gd['typ'])
            strikes.append(strike)

    return strikes, tag


def get_spells(c: Creature, start_tag: Tag) -> Tuple[Creature, Tag]:
    tag = start_tag.next
    return c, tag


def get_sidebars(start_tag: Tag) -> Tuple[List[Sidebar], Tag]:
    sidebars: List[Sidebar] = []
    tag = start_tag.next
    return sidebars, tag


def parse_creatures(pages: List[str]) -> Optional[List[object]]:
    # parse the families of creatures from http://2e.aonprd.com/Monsters.aspx?Letter=All
    try:
        with fetch.urlopen('http://2e.aonprd.com/Monsters.aspx?Letter=All') as inf:
            fam_page = inf.read()
            if not fam_page:
                raise ValueError('unable to fetch families table from AoN')
    except Exception:
        print('error fetching family table')
        sys.exit(1)

    fam_table: List[Tag] = BeautifulSoup(fam_page, 'html.parser').find_all('tr')
    fams = {}
    for tr in fam_table[1:]:
        name = tr.findChildren('td')[0].a.u.string
        fam = str(tr.findChildren('td')[1].string).strip()
        if fams.get(fam):
            fams.get(fam).append(name)
        else:
            fams[fam] = [name]

    creatures: List[object] = []
    for ind, page in enumerate(pages):
        if page == '':
            continue  # placeholder to properly ennumerate "bad" array items
        print('parsing id={}\tof\t{}'.format(ind + 1, len(pages)))
        creature: Creature = Creature()
        main_tag = BeautifulSoup(page, 'html.parser').find('span', id='ctl00_MainContent_DetailedOutput')

        # id/name/level
        creature.id = ind + 1
        creature.name = str(main_tag.h1.string)
        creature.level = main_tag.find('span', text=re.compile('Creature -?[0-9]+')).text.split()[1]

        # source
        source_tag = main_tag.find('b', text=re.compile('^Source$')).find_next('a', class_='external-link').find_next(
            'i').text
        src = [s.strip() for s in str(source_tag).split('pg.')]
        creature.source.book = src[0]
        creature.source.page = int(src[1])

        # HP TODO REWORK THE WHOLE SECTION
        hp_tag = main_tag
        hp_re = re.compile(r'\s*HP\s*(?P<hp>[0-9]+);?\s*(?P<hp_notes>[\w\d\s\-()\'’+.,]*);?\s*')
        while hp_tag.next:
            if hp_tag.name and hp_tag.name == 'b' and hp_tag.text == 'HP':
                break
            hp_tag = hp_tag.next

        hp_str = ''
        while hp_tag.next:
            if hp_tag.name == 'br' or hp_tag.name == 'hr':
                # or (hp_tag.name == 'b' and hp_tag.string in ['Immunities', 'Resistances', 'Weaknesses']):
                break
            if type(hp_tag) == NavigableString:
                hp_str = ''.join((hp_str, hp_tag.string))
            hp_tag = hp_tag.next

        hp_match = re.match(hp_re, hp_str)
        creature.hitPoints = int(hp_match.groupdict().get('hp'))
        creature.hitPointsNotes = hp_match.groupdict().get('hp_notes')

        regen_re = re.compile(
            r'\s*[rR]egeneration (?P<regen>[0-9]+)\s*,?\s*\(?deactivated by\s*(?P<deactivated>[\w ]+)\)?\s*')
        hardness_re = re.compile(r'\s*[hH]ardness (?P<hard>[0-9]+)')
        if creature.hitPointsNotes:
            creature.hitPointsNotes = ''.join(
                re.split(re.compile(r'\s*HP [0-9]+[,;]+\s*'), creature.hitPointsNotes)[1:]).strip(' ;,')
            regen_match: Match = re.match(regen_re, creature.hitPointsNotes)
            if regen_match:
                creature.regeneration = int(regen_match.group('regen'))
                creature.deactivatedBy = regen_match.group('deactivated')
            hardness_match: Match = re.match(hardness_re, creature.hitPointsNotes)
            if hardness_match:
                creature.hardness = int(hardness_match.group('hard'))
                creature.hitPointsNotes = re.sub(hardness_re, '', creature.hitPointsNotes)

        # Immunities; Weaknesses; Resistances
        imm_pattern = re.compile(
            r'\s*(Immunities\s*(?P<imm>[\w\d\s\-(),\']*);?)?\s*(Weaknesses\s*(?P<weak>[\w\d\s\-(),\']*);?)?\s*(Resistances\s*(?P<res>[\w\d\s\-(),\']*);?)?')
        imm_str = ''
        while hp_tag.next:
            if hp_tag.name == 'br' or hp_tag.name == 'hr':
                break
            if type(hp_tag) == NavigableString:
                imm_str = ''.join([imm_str, hp_tag.string])
            hp_tag = hp_tag.next

        imm_match = re.match(imm_pattern, imm_str)
        creature.immunities = [x.strip() for x in imm_match.group('imm').split(',')] if imm_match.group('imm') else []
        creature.weaknesses = [x.strip() for x in imm_match.group('weak').split(',')] if imm_match.group('weak') else []
        creature.resistances = [x.strip() for x in imm_match.group('res').split(',')] if imm_match.group('res') else []

        # Traits
        trait_tag = main_tag
        while trait_tag.next:  # scan through until traits section
            if trait_tag.name and (trait_tag.get('class') == ['traituncommon']):
                creature.rarity = 'uncommon'
            if trait_tag.name and (trait_tag.get('class') == ['traitrare']):
                creature.rarity = 'rare' if trait_tag.a.string == 'Rare' else 'unique'
            if trait_tag.name and trait_tag.get('class') == ['traitalignment']:
                break
            trait_tag = trait_tag.next

        while trait_tag.next:
            if trait_tag.name == 'br' or trait_tag.name == 'hr':
                break

            if trait_tag.name and trait_tag.get('class') == ['traitalignment']:
                creature.alignment = trait_tag.text
            if trait_tag.name and trait_tag.get('class') == ['traitsize']:
                creature.size = trait_tag.text
            if trait_tag.name and trait_tag.get('class') == ['trait']:
                t: Trait = Trait(name=trait_tag.text, description=trait_tag.get('title'))
                creature.traits.append(t)
            trait_tag = trait_tag.next

        # Perception and senses
        sense_tag = trait_tag
        sense_str = ''
        sense_re = re.compile(r'\s*Perception\s*(?P<per>[+-]?[0-9]+);?\s*(?P<per_notes>[\w\d\s\-()\'+.,]*)?\s*')
        while sense_tag.next:
            if sense_tag.name == 'b' and sense_tag.string == 'Perception':
                break
            sense_tag = sense_tag.next
        while sense_tag.next:
            if sense_tag.name == 'br' or sense_tag.name == 'hr':
                break
            elif type(sense_tag) == NavigableString:
                sense_str = ''.join((sense_str, sense_tag.string))
            sense_tag = sense_tag.next

        sense_match = re.match(sense_re, sense_str)
        creature.perception = int(sense_match.group('per'))
        creature.senses = [x.strip() for x in sense_match.group('per_notes').split(',')]

        # languages
        language_tag = sense_tag.find_next('b', text='Languages')
        language_re = re.compile(r'\s*Languages\s*(?P<langs>[\w\d\s\-()\'+.,]*);?\s*(?P<comms>[\w\d\s\-()\'+.,]*)?\s*')
        if language_tag:
            language_str = ''
            while language_tag.next:
                if language_tag.name == 'br' or language_tag.name == 'hr':
                    break
                elif type(language_tag) == NavigableString:
                    language_str = ''.join((language_str, language_tag.string))
                language_tag = language_tag.next

            language_match = re.match(language_re, language_str)
            creature.languages = [x.strip() for x in language_match.group('langs').split(',')]
            creature.otherCommunication = [x.strip() for x in language_match.group('comms').split(',')]

        # skills
        skill_tag = sense_tag.find_next('b', text='Skills')
        skills_re = re.compile(r'\s*Skills\s*(?P<skills>[\w\d\s\-()\'+.,]*)')
        skill_re = re.compile(r'(?P<name>[\w ]*)\s*(?P<mod>[+-]+[0-9]+)\s*(?P<notes>\([\w\d\s\-()\'+.,]*\))?\s*')
        if skill_tag:
            skill_str = ''
            while skill_tag.next:
                if skill_tag.name == 'br' or skill_tag.name == 'hr':
                    break
                elif type(skill_tag) == NavigableString:
                    skill_str = ''.join((skill_str, skill_tag.string))
                skill_tag = skill_tag.next

            skill_match = re.match(skills_re, skill_str)
            for s in re.finditer(skill_re, skill_match.group('skills')):
                skill = Header(s.group('name'), s.group('notes'), int(s.group('mod')))
                creature.skills.append(skill)

        # ability mods
        abm_tag = main_tag
        abm_str = ''
        abm_re = re.compile(
            r'\s*Str\s*(?P<str>[+-][0-9]+),\s*Dex\s*(?P<dex>[+-][0-9]+),\s*Con\s*(?P<con>[+-][0-9]+),\s*Int\s*(?P<int>[+-][0-9]+),\s*Wis\s*(?P<wis>[+-][0-9]+),\s*Cha\s*(?P<cha>[+-][0-9]+)\s*')
        while abm_tag.next:
            if abm_tag.name == 'b' and abm_tag.string == 'Str':
                break
            abm_tag = abm_tag.next

        while abm_tag.next:
            if abm_tag.name == 'br' or abm_tag.name == 'hr':
                break
            elif type(abm_tag) == NavigableString:
                abm_str = ''.join((abm_str, abm_tag.string))
            abm_tag = abm_tag.next

        abmods = re.match(abm_re, abm_str)
        creature.abilityMods = [int(x) for x in abmods.groups()]

        # items
        # (for some reason these are listed in the template as ABOVE interaction abilities, but are often NOT)
        item_tag = abm_tag
        item_str = ''
        item_re = re.compile(r'\s*(?P<item>[\w\d\s\-()\'+.,]+),?\s*')
        while item_tag.next:
            if item_tag.name == 'b' and item_tag.string == 'Items':
                break
            item_tag = item_tag.next

        while item_tag.next:
            if item_tag.name == 'br' or item_tag.name == 'hr':
                break
            elif type(item_tag) == NavigableString:
                item_str = ''.join((item_str, item_tag.string))
            item_tag = item_tag.next

        if item_str:
            item_str = item_str.replace('Items', '', 1)
            item_matches = re.findall(item_re, item_str)
            creature.items = [x.strip() for x in item_matches if x.strip()]

        # interaction abilities
        creature.interactionAbilities, _ = get_abilities(abm_tag)

        # AC
        ac_tag = main_tag
        while ac_tag.next and not creature.ac:
            if ac_tag.name and ac_tag.name == 'b' and ac_tag.text == 'AC' and type(ac_tag.next) == NavigableString:
                creature.ac = int(
                    re.match(re.compile(r'\s*(?P<ac>[0-9]+)[;,]?\s*'), ac_tag.next_sibling.string).group('ac'))
            ac_tag = ac_tag.next

        # AC notes, iterate until saves
        while ac_tag.next:
            if ac_tag.name == 'b' and ac_tag.text == 'Fort':
                break
            elif not ac_tag.name:
                creature.acNotes = ''.join([creature.acNotes, ac_tag.string])
            ac_tag = ac_tag.next

        if creature.acNotes:
            creature.acNotes = re.sub(re.compile(r'\s*AC\s*[0-9]+\s*[;,]*'), '', creature.acNotes).strip()
        # iterate through the whole row until hr/br, then parse the resulting string for saves and notes
        save_pattern = re.compile(r'\s*Fort\s*(?P<fort>[+\-][0-9]+)\s*(?P<fort_notes>[\w\d\s\-()\'+.,]*),\s*'
                                  r'Ref\s*(?P<ref>[+\-][0-9]+)\s*(?P<ref_notes>[\w\d\s\-()\'+.,]*),\s*'
                                  r'Will\s*(?P<will>[+\-][0-9]+)\s*(?P<will_notes>[\w\d\s\-()\'+.,]*);?'
                                  r'(?P<save_notes>[\w\d\s\-()\'+.,]*)?\s*')
        saves_str = ''
        while ac_tag.next:
            if ac_tag.name == 'hr' or ac_tag.name == 'br':
                break
            if type(ac_tag) == NavigableString:
                saves_str = ''.join([saves_str, ac_tag.string])
            ac_tag = ac_tag.next

        saves_match = re.match(save_pattern, saves_str)

        creature.fortitude = int(saves_match.group('fort'))
        creature.fortitudeNotes = saves_match.group('fort_notes')
        creature.reflex = int(saves_match.group('ref'))
        creature.reflexNotes = saves_match.group('ref_notes')
        creature.will = int(saves_match.group('will'))
        creature.willNotes = saves_match.group('will_notes')
        creature.saveNotes = saves_match.group('save_notes')

        # automatic abilities
        creature.automaticAbilities, _ = get_abilities(hp_tag)

        # speed
        speed_tag = hp_tag.next
        speed_str = ''
        while speed_tag.next:
            if speed_tag.name == 'b' and speed_tag.string == 'Speed':
                break
            speed_tag = speed_tag.next
        while speed_tag.next and speed_tag.name != 'hr' and speed_tag.name != 'br':
            if type(speed_tag) == NavigableString and speed_tag.string.strip() != 'Speed':
                speed_str = ''.join((speed_str, speed_tag.string))
            speed_tag = speed_tag.next
        creature.speed = speed_str

        # offensive/proactive abilities
        action_tag: Tag = speed_tag.next
        creature.strikes, action_tag = get_strikes(action_tag)
        creature, action_tag = get_spells(creature, action_tag)
        creature.activeAbilities, action_tag = get_abilities(action_tag)
        creature.sidebars, action_tag = get_sidebars(action_tag)

        # set family
        creature.family = [k for (k, v) in fams.items() if creature.name in v]
        creature.family = creature.family[0] if creature.family else '—'

        # NAVIGABLE STRINGS CAUSE RECURSION MAX DEPTH EXCEPTIONS. Convert to str before setting fields
        creatures.append(dataclasses.asdict(creature))

    return creatures


def parse_traits(pages: List[str]) -> Optional[List[object]]:
    traits: List[Any] = []
    for ind, page in enumerate(pages):
        if page == '':
            continue  # placeholder to properly enumerate "bad" array items
        print('parsing id={}\tof\t{}'.format(ind + 1, len(pages)))
        trait = Trait()
        whole_text = BeautifulSoup(page, 'html.parser').find('span', {'id': 'ctl00_MainContent_DetailedOutput'})

        # get name
        trait.id = ind + 1
        trait.name = str(whole_text.h1.string)

        # get description
        if whole_text.find(True, text=re.compile('This trait was not listed')):
            trait.description = None
        else:
            d_node = whole_text.find('a', class_='external-link',
                                     href=re.compile('https://paizo.com/products/')).findNext('br')
            while d_node and not d_node.name == 'h2':
                if type(d_node) == NavigableString or d_node.text:
                    trait.description = ''.join([trait.description, str(d_node.string)])
                d_node = d_node.next_sibling

        # get source
        src_tuple: Tuple[str, str] = whole_text.find('a', class_='external-link',
                                                     href=re.compile('https://paizo.com/products/')).string.split('pg.')
        trait.source.book = src_tuple[0].strip()
        trait.source.page = int(src_tuple[1].strip())

        # pymongo does not accept anything but dicts and mutablemappings, hence asdict()
        traits.append(dataclasses.asdict(trait))

    # now we put them in the groups defined on https://2e.aonprd.com/Traits.aspx
    with fetch.urlopen('http://2e.aonprd.com/Traits.aspx') as res:
        if not res:
            raise HTTPError
        s = res.read()
        traits_main_page = BeautifulSoup(s, 'html.parser').find('span', id='ctl00_MainContent_DetailedOutput')
    d_node = traits_main_page
    group_label = ''
    while d_node:
        if d_node.name == 'h2':
            group_label = str(d_node.string.split('Traits')[0].strip())
        if d_node.name == 'span' and d_node.attrs.get('class') == ['trait']:
            for t in traits:
                if group_label and d_node.get('title') == t.get('name'):
                    t['groups'].append(group_label)
        d_node = d_node.next_element
    return traits


def parse_table_into_list(tag: Tag) -> List[List[str]]:
    table = []
    rows = [x.find_all('td') for x in [t for t in tag.next.children if t.name and t.name == 'tr']]
    table.append([str(t.find('b').string) for t in rows[0]])
    for col in rows[1:]:
        table.append([str(t.string) for t in col])
    return table


def parse_ancestries(pages: List[str]) -> Optional[List[object]]:
    ancestries: List[Ancestry] = []
    for ind, page in enumerate(pages):
        if page == '':
            continue  # placeholder to properly enumerate "bad" array items
        anc: Ancestry = Ancestry()
        anc.id = ind + 1
        whole_text = BeautifulSoup(page, 'html5lib').find('span', {'id': 'ctl00_MainContent_DetailedOutput'})

        # get name
        name_tags = [t for t in whole_text.find_next('h1').children if t.string]
        for m in name_tags:
            if m.string:
                anc.name = ''.join((anc.name, m.string))

        # if this is just a heritage, we don't parse it
        if 'Heritage' in anc.name:
            continue

        # get rarity and traits
        uncommon: Tag = whole_text.find_next(class_='traituncommon')
        rare: Tag = whole_text.find_next(class_='traitrare')
        if uncommon:
            anc.rarity = uncommon.string.strip()
        elif rare:
            anc.rarity = rare.string.strip()
        traits: List[Tag] = whole_text.find_all_next(class_='trait')
        anc.traits = [str(t.string) for t in traits if t]

        # get source
        src: str = whole_text.find_next(name='b', text='Source').find_next(name='a').string
        anc.source.book = src.split('pg.')[0].strip()
        anc.source.page = int(src.split('pg.')[1])

        # get description and other entries
        m_tag = whole_text.find_next(name='b', text='Source').find_next(name='br')
        d_str = ''
        d_header = ''
        d_entries = []
        while m_tag.next:
            if m_tag.name and m_tag.name == 'h1':
                d_str = d_str.replace(d_header, '', 1)
                d_entries.append(AncestryHeader(d_header, d_str.strip()))
                break
            if type(m_tag) == NavigableString:
                d_str = ''.join((d_str, m_tag.string))
            elif m_tag.name == 'br':
                d_str = ''.join((d_str, '\n'))
            elif m_tag.name == 'h2' or m_tag.name == 'h3':
                d_str = d_str.replace(d_header, '', 1)
                d_entries.append(AncestryHeader(d_header, d_str.strip()))
                d_header = m_tag.string.strip()
                d_str = ''
            m_tag = m_tag.next
        anc.description = d_entries

        # Hit Points, Size, Speed, Ability Boosts (Flaws), Languages, Senses, Extra(s)
        # usually in that order (?)
        # then break when m_tag == m_tag.find_next(name='div', class_='clear').previous.previous.previous
        d_str = ''
        anc.hitPoints = str(m_tag.find_next(name='h2', text='Hit Points').next.next)
        anc.size = str(m_tag.find_next(name='h2', text='Size').next.next)
        anc.speed = str(m_tag.find_next(name='h2', text='Speed').next.next)
        boosts_tag = m_tag.find_next(name='h2', text='Ability Boosts').next.next
        while boosts_tag.next:
            if boosts_tag.name and boosts_tag.name == 'h2':
                break
            if type(boosts_tag) == NavigableString:
                d_str = ''.join((d_str, boosts_tag.string))
            elif boosts_tag.name == 'br':
                d_str = ''.join((d_str, '\n'))
            boosts_tag = boosts_tag.next
        anc.abilityBoosts = [d for d in d_str.split('\n') if d]
        flaws_tag = m_tag.find_next(name='h2', text='Ability Flaw(s)')
        if flaws_tag:
            d_str = ''  # reset
            flaws_tag = flaws_tag.next.next
            while flaws_tag.next:
                if flaws_tag.name and flaws_tag.name == 'h2':
                    break
                if type(flaws_tag) == NavigableString:
                    d_str = ''.join((d_str, flaws_tag.string))
                elif flaws_tag.name == 'br':
                    d_str = ''.join((d_str, '\n'))
                flaws_tag = flaws_tag.next
            anc.abilityFlaws = [d for d in d_str.split('\n') if d]

        lang_tag = m_tag.find_next(name='h2', text='Languages').next_sibling
        d_str = ''
        while lang_tag.next:
            if lang_tag.name and lang_tag.name == 'h2':
                anc.languages.append(d_str)
                break
            if type(lang_tag) == NavigableString:
                d_str = ''.join((d_str, lang_tag.string))
            elif lang_tag.name == 'br':
                anc.languages.append(d_str)
                d_str = ''
            lang_tag = lang_tag.next

        dvision_tag = m_tag.find_next(name='h2', text='Darkvision')
        ll_tag = m_tag.find_next(name='h2', text='Low-Light Vision')
        if dvision_tag:
            anc.senses.append(AncestryHeader('Darkvision', 'You can see in darkness and dim light just as well as you can see in bright light, though your vision in darkness is in black and white.'))
        elif ll_tag:
            anc.senses.append(AncestryHeader('Low-Light Vision', 'You can see in dim light as though it were bright light, so you ignore the concealed condition due to dim light.'))

        # the rest are extras
        extras_tag: Tag = lang_tag.previous.find_next('h2')
        if extras_tag:
            end_tag = [x for x in extras_tag.parent.children][-1]
            d_str: Union[str, List[List[str]]] = ''
            d_header = ''
            while extras_tag.next:
                if extras_tag == end_tag.next:
                    if type(d_str) == str:
                        anc.extras.append(AncestryHeader(d_header, d_str.replace(d_header, '', 1)))
                    elif type(d_str) == list:
                        anc.extras.append(AncestryHeader(d_header, '', d_str))
                    break
                if type(extras_tag) == NavigableString:
                    d_str = ''.join((d_str, extras_tag.string))
                elif extras_tag.name == 'br':
                    d_str = ''.join((d_str, '\n'))
                elif extras_tag.name == 'h2':
                    if d_str != '':
                        anc.extras.append(AncestryHeader(d_header, d_str.replace(d_header, '', 1)))
                    d_header = str(extras_tag.string)
                    d_str = ''
                elif extras_tag.name == 'table':
                    d_str = parse_table_into_list(extras_tag)
                    extras_tag = extras_tag.next_sibling.previous if extras_tag.next_sibling else extras_tag
                extras_tag = extras_tag.next

        ancestries.append(dataclasses.asdict(anc))
    return ancestries


def write_data(data: List[object], collection_name: str, index_on: str, f_name: str = None) -> None:
    if f_name:
        with open(f_name, 'w', encoding='utf-8') as outfile:
            print('writing to file')
            outfile.writelines(str(x) for x in data)
        print('completed writing {} lines to file {}'.format(len(data), f_name))
    else:
        print('connecting to database...')
        connection = MongoClient(config.mongo_connection_string)
        if not connection:
            print('error connecting to database')
            return
        print('connected! writing records')
        db = connection['2etools']
        if db[collection_name]:
            db[collection_name].drop()
        db.create_collection(collection_name)
        db[collection_name].create_index(index_on)
        db[collection_name].insert_many(data)
        print('done. closing connection')
        connection.close()


def scrape(typ: GameType, cache_only: bool = None, out_file: str = None):
    if typ == GameType.CREATURE:
        col_name: str = 'creatures'
        index_on: str = 'name'
        parse_func = parse_creatures
    elif typ == GameType.TRAIT:
        col_name: str = 'traits'
        index_on: str = 'name'
        parse_func = parse_traits
    elif typ == GameType.ANCESTRY:
        col_name: str = 'ancestries'
        index_on: str = 'name'
        parse_func = parse_ancestries
    else:
        print('Invalid GameType')
        return

    pages: List[str] = fetch_pages(typ, cache_only)
    if not pages:
        print('Pages could not be fetched')
        return

    data: List[object] = parse_func(pages)
    if not data:
        print('Pages could not be parsed')

    write_data(data, col_name, index_on, out_file)


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in [x.value for x in GameType]:
        print('usage: scraper.py TYPE [cache_only] [out_file_name]')
        sys.exit(0)
    game_type: GameType = GameType(sys.argv[1])
    arg_cache_only = None
    out_file_name = None
    if len(sys.argv) >= 3 and sys.argv[2] == 'cache_only':
        arg_cache_only = True
    if len(sys.argv) >= 4 and sys.argv[3]:
        out_file_name = sys.argv[2]
    scrape(game_type, arg_cache_only, out_file_name)
