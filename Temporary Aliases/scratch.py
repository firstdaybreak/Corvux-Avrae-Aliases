# Maneuver Module

c = character()
com = combat()
feats = load_json(c.get_cvar("SWFeats", "{}"))

def maneuver(args):
    tags = ["name", "superiorityDice", "maneuverMod", "dice", "diceTotal", "dmgType", "prof_bonus", "spell_mod"]
    format = ["#uses#", "#desc#", "#counterChange#", "#color#", "#image#", "#dice#", "#diceTotal#",
              "#targetOutput#", "#hp#", "#name#", "#damageText#", "#combatantFooter#", "#thp#", "#superiorityDice#", "#dc#" ]
    lvl = get_level()
    prof_bonus=c.stats.prof_bonus
    spell_mod = c.spellbook.spell_mod if c.spellbook.spell_mod else 0
    image = c.image
    color = c.csettings.color
    name = c.name
    a = argparse(args)
    out = f"embed -thumb {image} -color {color}"
    sm = a.get("sm")
    mm = a.get('mm')

    if sm:
        c.create_cc_nx("Superiority Mastery", 0, c.stats.prof_bonus, "long", "square")

    # Find the Feature
    feature = get_maneuver(args)

    # Param Parsing
    i = '-i' in args
    crit = 'crit' in args
    fail = 'fail' in args
    pss = 'pass' in args
    superiorityDice = '1d4' if lvl < 5 or sm else '1d6' if lvl < 9 else '1d8' if lvl < 16 else '1d12'
    superiorityDice += f"mi{a.last('mi')}" if a.last('mi') else f"mi{2 if 'd4' in superiorityDice or 'd6' in superiorityDice else 3 if 'd8' in superiorityDice else 4 if 'd10' in superiorityDice else 5}" if "PerfectManeuver" in feats.get("Discoveries",[]) else ""
    superiorityDice = superiorityDice.replace('1d', '2d') + "kh1" if a.last('savage') or 'adv' in args else superiorityDice

    type = a.last('type') if a.last('type') else feature.sub
    maneuverMod = get_mod(type)
    cc = "Superiority Mastery" if sm else "Channel the Force" if mm else "Superiority Dice"
    superiorityDice += f"+{ceil(maneuverMod/2)}" if mm else ''
    ccNum = 0 if i else feature.ccnum if feature and "ccnum" in feature else -1
    cc_valid = (c.cc_exists(cc) and c.get_cc(cc) or i)
    dmgType = a.last("dtype") if a.last("dtype") else feature.dmgType if "dmgType" in feature else "none"

    v = bool(lvl>=0 and cc_valid and feature)
    if v:
        ccNum = ccNum if v and not i else 0
        c.mod_cc(cc,ccNum) if v and not i else ""

        # Straight Superiority Dice Rolls
        dice = do_roll(feature,superiorityDice, maneuverMod, args) if feature and "roll" in feature and feature.roll else ""

        diceTotal = dice.total if dice else 0

        targets = get_targets(feature, args)

        combatantFooter = []

        # Replace tags
        feature = dump_json(feature)
        for x in tags:
            feature = feature.replace(f"#{x}#", str(get(x)).replace('"', '′'))
        feature = load_json(feature)

        if a.last('dev'):
            return err(f"{feature}")

        # Do some rolls
        dc = int(a.last('dc')) if a.last('dc') else roll(feature.save.dc) if "save" in feature and "dc" in feature.save else 8+c.stats.prof_bonus+maneuverMod
        damage = vroll(f"""{f'-({feature.damage + roll_add(feature,dmgType,args)})' if dmgType == "healing" else f'{feature.damage + roll_add(feature,dmgType, args)}'}""", 2 if crit else 1) if "damage" in feature else vroll("0")
        thp = vroll(feature.thp) if "thp" in feature else vroll("0")

        # Start processing targets
        targetHeader = [f'-f "{target[0].name}|' for target in targets]

        # Damage
        targetDamage = [target[0].damage(
            damage.consolidated() + ((f'+{target[1].join("d", "+")}') if target[1].get("d") else "")).damage + (
                            "" if (target[0].set_hp(target[0].max_hp) if target[0].hp > target[0].max_hp else "") or (
                                combatantFooter := combatantFooter + [
                                    f' {str(target[0])}']) else "") if "damage" in feature else "" for target in targets]

        # Temp HP
        targetTHP = [("" if (target[0].set_temp_hp(thp.total) if target[0].temp_hp < thp.total else "") or (
            combatantFooter := combatantFooter + [
                f' {str(target[0])}']) else "") + f'**Temporary Hit Points:** {thp.total}' if "thp" in feature else "" for
                     target in targets]

        # Effect
        targetEffect = []
        for target in targets:
            if com and "effect" in feature:
                if "parent" in feature.effect and not (peff := com.me.get_effect(feature.effect.parent.name.replace("#target#", target[0].name))):
                    peff = com.me.add_effect(feature.effect.parent.name.replace("#target#", target[0].name),
                                             desc=feature.effect.parent.desc if "desc" in feature.effect.parent else None,
                                             duration=feature.effect.parent.duration if "duration" in feature.effect.parent else -1,
                                             concentration=feature.effect.parent.conc if "conc" in feature.effect.parent else False,
                                             end=feature.effect.parent.end if "end" in feature.effect.parent else False
                                             )
                else:
                    peff = get("peff")

                eff = target[0].add_effect(feature.effect.name.replace("#target#", target[0].name),
                                           desc=feature.effect.desc if "desc" in feature.effect else "",
                                           duration=feature.effect.duration if "duration" in feature.effect else -1,
                                           concentration=feature.effect.conc if "conc" in feature.effect else False,
                                           end=True if "end " in feature.effect else False,
                                           passive_effects=feature.effect.passive_effects if "passive_effects" in feature.effect else None,
                                           parent=peff
                                           )
            targetEffect.append(f'**Effect**: {eff}' if get("eff") else "")

        # Text
        targetText = [feature.targetText.replace("#superiorityDice#", superiorityDice) if "targetText" in feature else ""
                      for target in targets]

        # Save
        targetSave = []
        if "save" in feature:
            for target in targets:
                save = target[0].save(feature.save.type,target[1].adv(False, True) if "adv" in target[1] or "dis" in target[1] else a.adv(False, True))
                option = feature.save.fail if (save.total < dc or fail) and not pss and "fail" in feature.save else feature.save.success if (save.total >= dc or pss) and "success" in feature.save else {}
                s_str = f"**{feature.save.type.upper()} Save**: {save}; {'Automatic Failure!' if fail else 'Automatic Pass!' if pss else 'Failure!' if save.total < dc else 'Success!'}\n"
                if "damage" in option:
                    dmg = target[0].damage(option.damage + ((f'+{target[1].join("d", "+")}') if target[1].get("d") else "")).damage
                    s_str += f"{dmg}\n"
                    combatantFooter += combatantFooter + [f' {str(target[0])}\n']

                if "effect" in option:
                    if "parent" in option.effect and not (peff := com.me.get_effect(option.effect.name.replace("#target#", target[0].name))):
                        peff = com.me.add_effect(option.effect.parent.name.replace("#target#", target[0].name),
                                                 desc=option.effect.parent.desc if "desc" in option.effect.parent else "",
                                                 duration=option.effect.parent.duration if "duration" in option.effect.parent else -1,
                                                 concentration=option.effect.parent.conc if "conc" in option.effect.parent else False,
                                                 end=option.effect.parent.end if "end" in option.effect.parent else False)
                    else:
                        peff = get("peff")

                    eff = target[0].add_effect(option.effect.name.replace("#target#", target[0].name),
                                               desc=option.effect.desc if "desc" in option.effect else "",
                                               duration=option.effect.duration if "duration" in option.effect else -1,
                                               concentration=option.effect.conc if "conc" in option.effect else False,
                                               passive_effects=option.effect.passive_effects if "passive_effects" in option.effect else None,
                                               parent=peff)
                    s_str+=f"{eff}\n"

                targetSave.append(f"{s_str}")


        # Close off the fields
        targetCloser = ['"' for target in targets]

        _ = (("" if (c.set_temp_hp(thp.total) if c.temp_hp<thp.total else "") or (combatantFooter:=combatantFooter+[f'{name}: {c.hp_str()}']) else "") or f'**Temporary Hit Points:** {thp.total}' if "thp" in feature else "") or (c.modify_hp(-damage.total) or ("" if (c.set_hp(hp) if c.hp>hp else "") or (combatantFooter:=combatantFooter+[f' {name}: {c.hp_str()}']) else "") if "damage" in feature else "") if not com and "self" in feature and feature.self else ""

        save_results = ' '.join(["\n".join([get(x)[i] for x in
                                            ["targetHeader", "targetDamage", "targetTHP", "targetEffect", "targetText",
                                             "targetSave", "targetCloser"] if get(x) and get(x)[i]]) for i in
                                 range(len(targets))])

        r = ["uses",
             feature.validUse,
             f'{cc}{" ("+("+" if ccNum>0 else "")+str(ccNum)+")" if ccNum else ""}|{c.cc_str(cc)}' if cc and c.cc_exists(cc) else "*None*",
             color,
             image,
             dice,
             diceTotal,
             save_results,
             c.hp_str(),
             c.name,
             damage,
             "\n".join(combatantFooter) if get("combatantFooter") else "",
             thp,
             superiorityDice,
             dc
             ]

        out += " " + feature.desc

        for i in range(len(format)):
            out = out.replace(format[i], str(r[i]))
    elif not c.cc_exists(cc) and not i:
        return err(f"No counter name `{cc}` exists")
    elif not c.get_cc(cc) and not i:
        out += f''' -title "{name} attempts {feature.name}." -desc "Unfortunately there are no `{cc}` to do it. Take a short/long reset then try again"'''
    else:
        return err(f"Something went wrong here. Let Corvux know and he'll break it better.")

    if sm:
        out += f''' -f "Superiority Mastery|Choose one maneuver you know. When you would use the chosen maneuver, you can use a d4 instead of expending a superiority die. You can do so a number of times equal to your proficiency bonus. You regain all expended uses when you complete a long rest."'''

    if mm:
        out += f''' -f "Masters Maneuver|When you would use a maneuver, you can expend a use of your Channel the force. You do not expend a die to use the maneuver and if you would roll the maneuver die for the maneuver, you add half your maneuver modifier to the result." '''

    return out


def get_maneuver(args):
    gvar = load_json(get_gvar("9b5b0cde-2e3c-4a8a-a662-eb843f6e85a8"))
    hlp = not args or ('?' in args or 'help' in args)

    maneuver = [x for x in gvar if not hlp and args[0].lower() in x.name.lower()+(x.syn.lower() if "syn" in x else "")]

    if len(maneuver) == 0:
        return err("Maneuver not found.")

    return maneuver[0]

def do_roll(feature, superiorityDice, maneuverMod, args):
    a = argparse(args)
    roll_str = feature.roll
    roll_str = roll_str.replace('#superiorityDice#', superiorityDice).replace('#maneuverMod#', str(maneuverMod))
    for n, sk in c.skills:
        roll_str = roll_str.replace(f'#{n}#', f'1d20+{sk.value}')
    return vroll(roll_str)

def get_level():
    lvl = 0

    if load_json(c.get_cvar("subclass","{}")).get("BerserkerLevel","") == "Champion":
        lvl = max(int(c.levels.get("Berserker", 0)), lvl)

    if load_json(c.get_cvar("subclass", "{}")).get("ScoutLevel", "") == "Deadeye":
        lvl = max(int(c.levels.get("Scout", 0)),lvl)

    lvl = max(int(c.levels.get("Fighter",0)), int(c.levels.get("Scholar",0)), lvl)

    if lvl == 0:
        lvl = c.levels.total_level

    return lvl

def get_mod(type):
    s = character().stats

    if type == "Mental":
        return max(s.get_mod("wisdom"), s.get_mod("intelligence"), s.get_mod("charisma"), 0)
    elif type == "Physical":
        return max(s.get_mod("strength"), s.get_mod("dexterity"), s.get_mod("constitution"), 0)
    else:
        return max(get_mod("Mental"), get_mod("Physical"))

def get_targets(feature, args):
    a = argparse(args)

    targets = []
    target_cache = a.get('t') + (
        [f'{c.name}'] if feature and "self" in feature and feature.self and com and com.me else [])
    target_cache = [
        [com.get_combatant(i.split('|', 1)[0].replace('{name}', c.name)) or com.get_group(i.split('|', 1)[0]),
         argparse(i.split('|', 1)[1] if '|' in i else '')] for i in target_cache if com]
    _ = [targets.append(i) if 'c' in i[0].type else [targets.append([e, i[1]]) for e in i[0].combatants] for i in
         target_cache if i[0]]

    return targets

def roll_add(feature, dmgType, args):
    a = argparse(args)
    bonus = ""
    lvl = get_level()
    sm = a.get("sm") and feats.get("SupMastery")
    superiorityDice = '1d4' if lvl < 5 or sm else '1d6' if lvl < 9 else '1d8' if lvl < 16 else '1d12'

    # Additional Bonus
    if int(c.levels.get("Scholar", 0)) >= 6 and load_json(c.get_cvar("subclass", "{}")).get("ScholarLevel") == "Physician" and dmgType.lower() == "healing":
        bonus = superiorityDice

    return f'''{f'+{a.join("d", "+")}' if a.get("d") else ""}{f'+{bonus}' if bonus != "" else ""}{f' [{dmgType}]' if dmgType else ''} '''



