# Combat skills

**Load for:** any fight: attacking and defending, armed or unarmed. **Untrained:** −1.

The anchor is in **bold** and is always one of the three dice. The other two follow the description of the action; the applications below are examples, not a closed list. Attributes are always written in the order STR, AGI, DFT, VIG, LOG, ITU, NRV, PRS, EMP.

## Fights

- **Order:** the GM decides who acts when, from the situation. There is no initiative roll.
- **Attack:** a contest of the attacker's weapon skill against the defender's Guard (close combat) or Evasion (ranged). The attacker is the active side. Cover is a modifier; full cover blocks the attack.
- **Damage:** a hit deals HP damage equal to its quality, so quality 0 is at most a graze. Weapons don't change this. Track damage to each mob separately in the scene: all instances start at the HP in `mobs.json`.
- **Wounded:** at half HP or less, −2 to physical rolls.
- **0 HP:** mobs and minor NPCs are out of the fight. The player and important NPCs are dying: each beat, an Endurance roll against difficulty 20. Three successes stabilize them, three failures kill them.
- **Massive damage:** a single hit dealing at least the target's max HP kills outright.

The campaign's rules may add armor and other setting details.

## Brawling

*Anchor: STR · Untrained: −1 · Status: canon*

The body as a weapon: striking, grappling, joint locks, and every dirty trick at arm's length. Also covers cyberclaws and fists in armored gloves.

- Haymaker, heavy kick: **STR**, STR, AGI
- Quick jabs, combinations: **STR**, AGI, AGI
- Grapple, choke, pin: **STR**, STR, VIG
- Trip or throw: **STR**, AGI, ITU
- Joint lock, trapping or manipulating a limb (jiu-jitsu): **STR**, DFT, ITU

## Bludgeons

*Anchor: STR · Untrained: −1 · Status: canon*

Any blow that relies on momentum rather than a precise edge: bats, pipes, hammers, axes, rifle butts, chairs.

- Overhead smash: **STR**, STR, VIG
- Controlled swings, keeping distance: **STR**, AGI, ITU
- Improvised or misused weapon (a chair, a reversed sword, a rifle butt): **STR**, DFT, ITU
- Breaking a guard or a weapon: **STR**, STR, ITU

## Slashing

*Anchor: AGI · Untrained: −1 · Status: canon*

Cutting with the whole body, closer to a dance than a duel: sabers, katanas, machetes, the cutting strokes of a longsword, and whips, including monofilament ones.

- Wide cut: STR, **AGI**, ITU
- Flurry of cuts: **AGI**, AGI, DFT
- Whip or monowhip lash: **AGI**, DFT, ITU
- Draw-cut from the sheath: **AGI**, DFT, NRV

## Throwing

*Anchor: AGI · Untrained: −1 · Status: canon*

Throwing and catching: knives, grenades, bottles, a gun tossed to an ally.

- Knife throw: **AGI**, DFT, ITU
- Grenade over cover: STR, **AGI**, ITU
- Long throw: STR, STR, **AGI**
- Catching: **AGI**, DFT, ITU

## Evasion

*Anchor: AGI · Untrained: −1 · Status: canon*

Defending against ranged attacks: dodging, diving, moving under fire, and using cover well (knowing when and where to peek, which direction matters).

- Diving for cover: **AGI**, AGI, ITU
- Zigzagging across open ground: **AGI**, VIG, ITU
- Holding and working a cover position: **AGI**, ITU, NRV

## Fencing

*Anchor: DFT · Untrained: −1 · Status: canon*

Point work: daggers, rapiers, monoblades, bayonets, and the thrusts of a longsword.

- Lunge: AGI, **DFT**, ITU
- Feint and thrust: **DFT**, LOG, ITU
- Knife work at close quarters: STR, AGI, **DFT**
- Stabbing into a gap in the armor: **DFT**, DFT, ITU

## Handguns

*Anchor: DFT · Untrained: −1 · Status: canon*

Any gun held in one hand or two without a stock. Firing modes apply only if the weapon supports them (burst and full auto: machine pistols).

- Aimed or single shot: **DFT**, ITU, NRV
- Quick-draw: AGI, **DFT**, ITU
- Firing on the move: AGI, **DFT**, NRV
- Short burst or full auto: STR, **DFT**, NRV
- Suppressive fire, mostly blind, for the psychological effect: **DFT**, NRV, PRS

## Long guns

*Anchor: DFT · Untrained: −1 · Status: canon*

Assault rifles, shotguns, carbines, hunting rifles, SMGs with stocks. Firing modes apply only if the weapon supports them.

- Aimed or single shot: **DFT**, ITU, NRV
- Short burst: STR, **DFT**, NRV
- Full auto: STR, **DFT**, ITU
- Suppressive fire, mostly blind from cover, for the psychological effect: **DFT**, NRV, PRS
- Close quarters: snap shots while moving through tight spaces: AGI, **DFT**, ITU

## Guard

*Anchor: ITU · Untrained: −1 · Status: canon*

Meeting an attack in close combat. The anchor is reading it in time; the other attributes decide how it is met: blocking, parrying, slipping, breaking free.

- Blocking with the arms: STR, VIG, **ITU**
- Parrying with a weapon: AGI, DFT, **ITU**
- Slipping, ducking: AGI, AGI, **ITU**
- Breaking a hold: STR, STR, **ITU**

## Heavy weapons

*Anchor: NRV · Untrained: −1 · Status: canon*

Anything rested on the ground, a bipod, a mount or a vehicle, including sniper and anti-materiel rifles, belt-fed guns and launchers. Firing modes apply only if the weapon supports them.

- Aimed or single shot: DFT, ITU, **NRV**
- Short burst: STR, DFT, **NRV**
- Full auto: STR, ITU, **NRV**
- Suppressive fire, for the psychological effect: ITU, **NRV**, PRS
- Indirect fire, lobbing over cover (grenade launcher, mortar): LOG, ITU, **NRV**
