"""Generate the SYNTHETIC labelled complaint dataset used to train and evaluate module 5.

    python -m app.ai.data.generate_dataset          (run from backend/)

IMPORTANT: every row is machine-generated from hand-written templates. No real
complaint, person, phone number or address is included. Scores measured on this
data overestimate how the model would do on real citizen complaints. See
docs/ai_dataset.md for the method, the labelling criteria and the limitations.

Output: app/ai/data/complaints_synthetic.csv with columns
    text          subject + description (one string)
    category_slug one of the 12 seeded category slugs
    priority      low | medium | high | critical (criteria below)
    scenario_id   which hand-written scenario the row came from (used for a
                  harder "unseen scenario" evaluation in train.py)

Priority labelling criteria (applied by this generator, not by a model):
    1. Each scenario has a base severity chosen by the author:
         critical = immediate danger to life or limb (live/fallen wire, open manhole,
                    gas leak, fire, collapse, someone already hurt and danger continues)
         high     = health/safety risk or a serious service failure (sewage entering
                    homes, no water for days, dog bites, fallen tree blocking a road)
         medium   = ordinary service failure affecting a street or colony
         low      = minor, cosmetic, administrative or a request for something new
    2. Modifiers (never raise anything above "high"; only scenarios reach "critical"):
         vulnerable people mentioned (children, elderly, hospital, school) -> +1
         large scale mentioned (whole colony, 100+ families)                 -> +1
         long duration (a week or more) and the level is still low           -> +1
    3. Annotator noise: about 4% of labels are moved one level up or down at
       random, to simulate disagreement between human labellers.
"""

from __future__ import annotations

import csv
import random
import re
from pathlib import Path

SEED = 20261010
ROWS_PER_CATEGORY = 200
NOISE_RATE = 0.04
OUTPUT = Path(__file__).resolve().parent / "complaints_synthetic.csv"

LEVELS = ["low", "medium", "high", "critical"]
L, M, H, C = 0, 1, 2, 3

LOCALITIES = [
    "Ameerpet", "Kukatpally", "Madhapur", "Gachibowli", "Kondapur", "Miyapur", "Secunderabad", "Begumpet",
    "Banjara Hills", "Jubilee Hills", "Mehdipatnam", "Tolichowki", "Dilsukhnagar", "LB Nagar", "Uppal",
    "Habsiguda", "Tarnaka", "Malkajgiri", "Alwal", "Bowenpally", "Charminar", "Chandrayangutta", "Falaknuma",
    "Malakpet", "Himayatnagar", "Narayanguda", "Abids", "Koti", "Nampally", "Masab Tank", "Attapur",
    "Rajendranagar", "Manikonda", "Nizampet", "Bachupally", "KPHB Colony", "Moosapet", "Erragadda", "SR Nagar",
    "Yousufguda", "Somajiguda", "Khairatabad", "Saidabad", "Santosh Nagar", "Vanasthalipuram", "Hayathnagar",
    "Nacharam", "ECIL", "AS Rao Nagar", "Kompally", "Chanda Nagar", "Lingampally", "Boduppal", "Ramanthapur",
    "Amberpet", "Musheerabad", "Chikkadpally", "Lakdikapul", "Sainikpuri", "Old Bowenpally",
]
LANDMARKS = [
    "near the bus stop", "opposite the government school", "behind the temple", "near the masjid",
    "beside the church", "near the ration shop", "next to the community hall", "near the petrol bunk",
    "in lane no. 4", "on road no. 12", "near the vegetable market", "near the RTC bus depot",
    "near the water tank", "near the govt hospital", "near the park gate", "near the metro station",
    "at the main junction", "in our colony", "in the basti", "near the post office", "opposite the bank",
    "in front of my house", "near the kirana shop", "at the cross roads", "behind the function hall",
]

OPENERS = [
    "", "", "", "Respected sir/madam,", "Dear sir,", "Hello,", "Sir,", "This is to bring to your notice that",
    "I am writing to complain that", "Kindly note:", "Good morning,", "Namaste sir,", "To the concerned officer,",
]
CLOSERS = [
    "", "", "Please take action immediately.", "Kindly do the needful.", "Pls resolve asap.",
    "Hope this will be fixed soon.", "Request you to look into this.",
    "We have complained before but nothing happened.", "Thank you.", "Very disappointed with the response so far.",
    "Please send someone to check once.", "Nobody is caring about this problem.", "What is this sir, very bad.",
    "Waiting for your action.", "Thanks in advance.",
]
# (phrase, is_long)
DURATIONS = [
    ("since yesterday", False), ("from 2 days", False), ("since 3 days", False), ("from today morning", False),
    ("since last night", False), ("for the past week", True), ("since 10 days", True),
    ("for almost a month", True), ("for the last 2 months", True), ("since more than 15 days", True),
]
VULNERABLE = [
    "Small children walk this way to school.", "Many senior citizens live in this lane.",
    "There is a hospital nearby and patients are suffering.", "School kids are at risk.",
    "Old people and kids find it very difficult.", "A pregnant lady in our building is struggling.",
]
SCALE = [
    "The entire colony is affected.", "More than 100 families are facing this.", "Whole street is suffering.",
    "All the houses in our lane are affected.", "Around 200 houses are affected.",
]

# --- Scenarios -------------------------------------------------------------------------------
# Each scenario: (base severity, [subjects], [bodies]). "{where}" becomes "<landmark>, <locality>".
# Some scenarios are deliberately borderline between categories; their label follows the
# rule documented in docs/ai_dataset.md (the primary problem the citizen wants fixed).
S = dict[str, list[tuple[int, list[str], list[str]]]]

SCENARIOS: S = {
    "drainage-sewerage": [
        (M, ["Blocked drain overflowing", "Drain choked on main road"],
         ["The drain {where} is completely blocked and dirty water is flowing on the road.",
          "Drainage is choked {where}, black water is overflowing and the smell is unbearable."]),
        (H, ["Sewage entering houses", "Sewer water coming inside homes"],
         ["Sewage water is entering our houses {where}. We cannot even use the ground floor.",
          "Because of the blocked sewer line {where}, drainage water is backing up into homes and bathrooms."]),
        (C, ["Open manhole on main road", "Manhole without cover - danger"],
         ["There is an open manhole without any cover {where}. Someone can fall inside at night, it is very dangerous.",
          "Manhole lid is missing {where} and the hole is fully open on the road. A child almost fell in today."]),
        (H, ["Broken manhole cover", "Manhole lid damaged"],
         ["The manhole cover {where} is broken and sinking, vehicles are hitting it.",
          "Manhole lid cracked {where}, it can give way any time when a vehicle passes."]),
        (M, ["Waterlogging after rain", "Rain water not draining"],
         ["After every small rain, water stagnates {where} because the storm water drain is choked.",
          "Knee deep water logging {where} after yesterday's rain, drain is not taking the water."]),
        (M, ["Foul smell from sewer line", "Sewer leakage smell"],
         ["The underground drainage line is leaking {where} and there is a foul smell all day.",
          "Sewer pipe leaking {where}, the smell is very bad and flies everywhere."]),
        (M, ["Nala overflowing", "Nala silt not removed"],
         ["The nala {where} is full of silt and plastic, it is overflowing onto the road.",
          "Nala desilting was not done this year {where}, it is overflowing already."]),
        (L, ["Silt left on road after drain cleaning", "Drain cleaning waste not lifted"],
         ["Workers cleaned the drain {where} but left the silt heaped on the roadside.",
          "Silt removed from the drain is lying {where} and has not been taken away."]),
        (M, ["UGD line damaged during road work", "Drainage pipe broken by contractor"],
         ["During the road work {where} the underground drainage pipe was broken and now sewage is leaking.",
          "Contractor damaged the UGD line {where}, sewage is seeping out on the road."]),
        (M, ["Storm water drain slab broken", "Drain slab collapsed"],
         ["The slab over the storm water drain {where} is broken, there is a gap people can trip into.",
          "Drain covering slab is broken {where}, half of the drain is exposed."]),
        (H, ["Drainage water entering houses after rain", "Water entering homes, drains blocked"],
         ["Rain water mixed with drainage is entering houses {where}. Furniture and appliances got damaged.",
          "Last night drain water came inside our homes {where}, it happens every rain."]),
        (C, ["Underpass flooded, vehicles stuck", "Severe flooding, people stranded"],
         ["The underpass {where} is completely flooded and a car is stuck with people inside.",
          "Severe flooding {where}, water is flowing very fast and people are stranded. Need help urgently."]),
        (L, ["Drain cleaning request", "Please clean the side drain"],
         ["The side drain {where} has not been cleaned for a long time. Please schedule cleaning.",
          "Request to clean the drain {where} before the monsoon starts."]),
        (M, ["Sewage stagnating on road", "Sewage water on road"],
         ["Sewage water is stagnating on the road {where}, people have to walk through it.",
          "Dirty drainage water is standing on the road {where} for days."]),
    ],
    "garbage-sanitation": [
        (M, ["Garbage not collected", "Garbage not lifted for days"],
         ["Garbage has not been collected {where} and it is piling up on the road.",
          "Nobody came to lift the garbage {where}, the heap is getting bigger every day."]),
        (M, ["Overflowing dustbin", "Dustbin full and overflowing"],
         ["The community dustbin {where} is overflowing and dogs are spreading the waste all over.",
          "Garbage bin {where} is overflowing, the smell is terrible."]),
        (M, ["Garbage dumped on road", "People dumping waste in open plot"],
         ["People are dumping garbage in the open plot {where} and it has become a dump yard.",
          "Waste is being thrown on the roadside {where}, the area has become very dirty."]),
        (L, ["Need a new dustbin", "Request for dustbin"],
         ["There is no dustbin {where}, so people throw waste on the road. Please place a bin.",
          "Request to provide two dustbins {where} for wet and dry waste."]),
        (L, ["Street sweeping not done", "Road not swept"],
         ["The road {where} is not being swept regularly, dust and leaves everywhere.",
          "Sweepers are not coming {where}, the street is very dirty."]),
        (M, ["Public toilet very dirty", "Public toilet no water"],
         ["The public toilet {where} is very dirty and there is no water, people cannot use it.",
          "Public toilet {where} is stinking and not cleaned at all."]),
        (H, ["Rotting garbage near hospital", "Garbage with flies near school"],
         ["Rotting garbage is lying {where} near the hospital, flies and mosquitoes everywhere. Serious health risk.",
          "Huge pile of rotting waste {where}, dead rats in it. This is a health hazard."]),
        (M, ["Door to door garbage collection irregular", "Swachh auto not coming"],
         ["The garbage auto is not coming to our lane {where}, only once a week it comes.",
          "Door to door collection is very irregular {where}, the swachh auto skips our street."]),
        (L, ["Construction debris dumped", "Debris left on roadside"],
         ["Someone dumped construction debris {where} and left it there.",
          "Building rubble is dumped on the side of the road {where}."]),
        (H, ["Medical waste dumped in open", "Used syringes thrown in garbage"],
         ["Medical waste like syringes and bandages is dumped in the open {where}. Children play nearby.",
          "A clinic is throwing biomedical waste with the normal garbage {where}."]),
        (L, ["Garbage collector asking money", "Sanitation worker demanding money"],
         ["The garbage collection person {where} is asking extra money from each house.",
          "Sanitation worker {where} demands money monthly to take our garbage."]),
        (M, ["Garbage blocking the drain", "Plastic waste choking drain"],
         ["Garbage thrown {where} is going into the drain and blocking it. Garbage needs to be cleared first.",
          "So much plastic waste is dumped {where} that it is choking everything. Please clear the garbage."]),
        (M, ["Garbage point not cleared", "Garbage transfer point stinking"],
         ["The garbage transfer point {where} is not cleared daily, waste spills onto the road.",
          "Garbage collection point {where} has not been cleared and the smell reaches our houses."]),
    ],
    "roads-potholes": [
        (M, ["Big potholes on main road", "Potholes everywhere"],
         ["There are many big potholes on the main road {where}, vehicles are getting damaged.",
          "The road {where} is full of potholes, very difficult to drive."]),
        (H, ["Pothole caused bike accident", "Two wheeler skidded in pothole"],
         ["A bike rider fell after hitting the pothole {where} yesterday. The pothole is still there.",
          "Several two wheelers skidded because of the deep pothole {where}. Someone got injured."]),
        (M, ["Road dug and not restored", "Road cut not closed after pipeline work"],
         ["The road {where} was dug for pipeline work and left like that for weeks.",
          "After cable laying, the road cutting {where} was not restored."]),
        (C, ["Open trench without barricade", "Deep pit on road, no barricading"],
         ["There is a deep trench on the road {where} without any barricade or light. A scooter fell into it last night.",
          "A big pit dug {where} is left open with no barricading. Someone will die if it is not closed today."]),
        (M, ["Road completely damaged", "Road in very bad condition"],
         ["The entire stretch {where} is broken, it is not motorable anymore.",
          "Road condition {where} is very bad, only stones and mud."]),
        (L, ["Broken footpath tiles", "Footpath damaged"],
         ["The footpath tiles {where} are broken and uneven.",
          "Footpath {where} is damaged, pedestrians are walking on the road."]),
        (M, ["Need speed breaker near school", "Speed breaker request"],
         ["Vehicles are speeding {where} near the school. Please put a speed breaker.",
          "Request a speed breaker {where}, vehicles come very fast and kids cross here."]),
        (M, ["Unmarked speed breaker", "Speed breaker without paint"],
         ["The speed breaker {where} has no paint or sign board, people fall at night.",
          "New speed breaker {where} is too high and not marked, bikes are jumping."]),
        (C, ["Road caved in", "Sinkhole on road"],
         ["The road {where} has caved in and a big hole has formed, part of the road collapsed.",
          "Sudden sinkhole on the road {where}, the road collapsed and vehicles can fall in."]),
        (M, ["Pothole filled with water", "Water filled potholes"],
         ["Potholes {where} are filled with rain water, nobody can see how deep they are.",
          "The potholes {where} are hidden under water after the rain."]),
        (L, ["New road already broken", "Poor quality road work"],
         ["The road {where} was laid only 3 months ago and it is already broken. Poor quality work.",
          "Newly laid road {where} has cracks already, check the contractor."]),
        (L, ["Damaged road divider", "Median railing broken"],
         ["The road divider {where} is damaged and the railing is broken.",
          "Median railing {where} is bent and broken pieces are lying on the road."]),
        (L, ["Internal road repair request", "Colony road needs relaying"],
         ["Our internal colony road {where} needs to be relaid, request to include it in the next works.",
          "Please repair the internal road {where}, it has not been done for years."]),
        (M, ["Loose gravel on road", "Gravel slipping vehicles"],
         ["Loose gravel and sand is spread on the road {where} after patch work, bikes are slipping.",
          "After repair, gravel was left loose {where}, very slippery for two wheelers."]),
    ],
    "street-lights": [
        (M, ["Street light not working", "Street lamp off"],
         ["The street light {where} is not working, the road is completely dark at night.",
          "Street lamp {where} is off, please repair it."]),
        (H, ["Whole road dark, many lights off", "No street lights, unsafe for women"],
         ["None of the street lights {where} are working, the whole road is dark and women feel unsafe.",
          "All lights on the stretch {where} are off, chain snatching incidents happened."]),
        (L, ["Street light flickering", "Light keeps flickering"],
         ["The street light {where} keeps flickering on and off.",
          "Flickering street lamp {where}, it is disturbing."]),
        (L, ["Street lights on during day", "Lights burning in daytime"],
         ["Street lights {where} are on during the day, wasting electricity.",
          "Lights {where} are burning even in the afternoon."]),
        (H, ["Street light pole leaning", "Street light pole about to fall"],
         ["The street light pole {where} is leaning badly and may fall on someone.",
          "Street light pole {where} is bent and shaking in the wind."]),
        (C, ["Exposed wires at street light pole", "Live wires open at light pole"],
         ["The street light pole {where} has its wires exposed at the bottom, someone can get electrocuted.",
          "Open live wires at the base of the street light pole {where}, children touch it while playing."]),
        (L, ["New street light needed", "Request street light in dark lane"],
         ["Our lane {where} has no street light at all, please install one.",
          "Request to install a new street light {where}."]),
        (L, ["Street light timer problem", "Lights switch off early"],
         ["Street lights {where} switch off at 10 pm itself, timer problem.",
          "Lights {where} are coming on very late in the evening."]),
        (M, ["Lights not working near bus stop", "Bus stop dark at night"],
         ["The street lights near the bus stop {where} are not working, people wait in the dark.",
          "Bus stop area {where} has no light at night."]),
        (M, ["High mast light not working", "Junction high mast off"],
         ["The high mast light {where} at the junction is not working.",
          "High mast lamp {where} is off for days, junction is dark."]),
        (M, ["Light fixture hanging loose", "Lamp hanging from pole"],
         ["The lamp fixture on the pole {where} is hanging loosely.",
          "Street light head {where} is hanging and swinging."]),
        (M, ["Street light cables stolen", "Lights off due to cable theft"],
         ["Cables of the street lights {where} were stolen, all lights are off.",
          "Someone cut the street light wires {where}."]),
    ],
    "water-supply": [
        (H, ["No water supply", "No water for days"],
         ["There is no water supply {where}, we are buying water cans.",
          "Water has not come {where}, people are suffering without drinking water."]),
        (M, ["Low water pressure", "Very low pressure in water supply"],
         ["Water is coming with very low pressure {where}, it does not reach the tank.",
          "Pressure is very low {where}, we get only a few buckets."]),
        (H, ["Contaminated drinking water", "Muddy water in supply"],
         ["The drinking water supplied {where} is muddy and has a bad smell.",
          "Contaminated water is coming in the taps {where}, it is yellow in colour."]),
        (H, ["Sewage mixing in drinking water", "Drinking water smells like drainage"],
         ["Drainage water is mixing with the drinking water pipeline {where}, tap water smells of sewage.",
          "Tap water {where} smells like drainage, the supply line is contaminated."]),
        (M, ["Pipeline burst, water wasted", "Water pipe leaking on road"],
         ["The water pipeline {where} has burst and lots of water is wasted on the road.",
          "Main water line leaking {where}, water is flowing on the road all day."]),
        (L, ["Small leakage at valve", "Valve leaking"],
         ["There is a small leakage at the water valve {where}.",
          "Water valve {where} is dripping continuously."]),
        (L, ["Water supply timings irregular", "Water comes at odd hours"],
         ["Water supply {where} comes at 3 am, very difficult to collect.",
          "No fixed timing for water supply {where}."]),
        (M, ["Water tanker not delivered", "Booked tanker not supplied"],
         ["I booked a water tanker for {where} but it was not delivered.",
          "Tanker booked 4 days back for {where}, still not supplied."]),
        (L, ["New water connection pending", "Water connection application delay"],
         ["My new water connection application for {where} is pending for a long time.",
          "Applied for a water connection {where}, no update yet."]),
        (L, ["Wrong water bill", "Water bill too high"],
         ["The water bill for my house {where} is very high, the meter reading looks wrong.",
          "Excess water bill received for {where}."]),
        (C, ["People fell ill after drinking tap water", "Diarrhoea cases due to supply water"],
         ["Many people {where} fell ill with vomiting after drinking the supplied water, some are hospitalised.",
          "Several children {where} got diarrhoea after drinking tap water, it is spreading fast."]),
        (L, ["Water meter not working", "Faulty water meter"],
         ["The water meter at {where} is not working.", "Water meter {where} is broken."]),
        (M, ["Public borewell not working", "Hand pump broken"],
         ["The public borewell {where} is not working, people depend on it.",
          "Hand pump {where} is broken, the motor is not working."]),
    ],
    "electricity": [
        (M, ["Power cut for long hours", "Frequent power cuts"],
         ["There are long power cuts {where} every day, 5 to 6 hours.",
          "Current is going again and again {where}."]),
        (M, ["Voltage fluctuation", "Power fluctuation damaging appliances"],
         ["Heavy voltage fluctuations {where} are damaging our fridge and TV.",
          "Power keeps fluctuating {where}, appliances got burnt."]),
        (C, ["Live wire hanging on road", "Electric wire fallen on road"],
         ["A live electric wire is hanging low {where} and touching the road. Very dangerous.",
          "Electric wire snapped and fell on the road {where}, it is still live and sparking."]),
        (C, ["Transformer sparking", "Transformer caught fire"],
         ["The transformer {where} is sparking and smoke is coming out.",
          "Transformer {where} caught fire last night and it is sparking again."]),
        (H, ["Electric pole about to fall", "Bent electric pole"],
         ["The electric pole {where} is bent and may fall any time.",
          "Electric pole {where} is tilted badly after the rain."]),
        (C, ["Person got electric shock from pole", "Electric shock near pole"],
         ["A boy got an electric shock after touching the pole {where}. Current is passing through the pole.",
          "People are getting shocks from the electric pole {where}, current leakage."]),
        (H, ["Wires touching tree branches", "Low hanging electric wires"],
         ["Electric wires {where} are touching tree branches, sparks come when it rains.",
          "Wires are hanging very low {where}, trucks touch them."]),
        (H, ["No power in colony since night", "Total power outage"],
         ["There is no power {where} since last night, nobody from the department came.",
          "Complete power outage {where}, water motors cannot run."]),
        (L, ["Electricity bill too high", "Wrong meter reading"],
         ["My electricity bill for {where} is very high this month, the reading seems wrong.",
          "Wrong meter reading for my house {where}."]),
        (H, ["Open junction box", "Distribution box door open"],
         ["The electric distribution box {where} is open with wires visible.",
          "Junction box door {where} is broken and open, kids play near it."]),
        (H, ["Tree branch fell on electric line", "Branch on power line"],
         ["A big tree branch fell on the electric line {where}, wires are under strain.",
          "Branch is resting on the power lines {where}, it can break the wire."]),
        (M, ["Low voltage problem", "Very low voltage"],
         ["Voltage is very low {where}, fans are running slowly.",
          "Low voltage {where} in the evenings, nothing works properly."]),
    ],
    "stray-animals": [
        (M, ["Stray dog menace", "Too many stray dogs"],
         ["There are too many stray dogs {where}, they chase bikes and people at night.",
          "Stray dogs menace {where}, difficult to walk in the evening."]),
        (H, ["Dog bit a child", "Stray dog bite"],
         ["A stray dog bit a small boy {where} today. The dogs are still roaming here.",
          "Stray dog bit two people {where}, please catch the dog."]),
        (H, ["Aggressive dogs attacking people", "Pack of dogs attacked"],
         ["A pack of aggressive stray dogs attacked a man {where} this morning.",
          "Dogs {where} are attacking people who walk alone."]),
        (M, ["Cattle on main road", "Cows blocking traffic"],
         ["Cattle are sitting in the middle of the main road {where}, causing traffic jams.",
          "Cows and buffaloes roam {where} and block traffic."]),
        (M, ["Dead animal on road", "Dead dog carcass not removed"],
         ["A dead dog is lying on the road {where}, it is stinking.",
          "Carcass of a cow {where} has not been removed for two days."]),
        (M, ["Monkey menace", "Monkeys entering houses"],
         ["Monkeys are entering houses {where} and snatching food.",
          "Monkey menace {where}, they are damaging things."]),
        (L, ["Dog sterilisation request", "Vaccination drive for stray dogs"],
         ["Please conduct sterilisation of stray dogs {where}.",
          "Request an anti rabies vaccination drive for dogs {where}."]),
        (H, ["Rabid dog suspected", "Dog foaming at mouth"],
         ["A stray dog {where} is foaming at the mouth and biting other dogs, looks rabid.",
          "Mad dog suspected {where}, it is behaving strangely and attacking."]),
        (M, ["Stray pigs nuisance", "Pigs roaming near drain"],
         ["Stray pigs {where} are roaming near the drains and entering compounds.",
          "Pig menace {where}, they dig up the garbage."]),
        (H, ["Snake seen in colony", "Snake in park"],
         ["A big snake was seen {where} near the houses, people are scared.",
          "Snake spotted {where}, please send the snake catcher."]),
        (L, ["Injured stray dog needs help", "Injured animal on road"],
         ["An injured stray dog is lying {where}, it needs treatment.",
          "A cow with an injured leg is {where}, please help it."]),
        (L, ["Cattle tied on footpath", "Buffaloes kept on footpath"],
         ["Owners tie their buffaloes on the footpath {where}, dung everywhere.",
          "Cattle tied on the footpath {where} by a dairy owner."]),
    ],
    "encroachment": [
        (L, ["Shop encroaching footpath", "Footpath occupied by shop"],
         ["The shop {where} has extended onto the footpath, pedestrians have to walk on the road.",
          "Shopkeepers {where} keep their goods on the footpath."]),
        (L, ["Hawkers blocking road", "Street vendors occupying road"],
         ["Hawkers {where} occupy half the road and cause traffic jams.",
          "Vendors carts {where} block the road every evening."]),
        (M, ["Illegal construction", "Construction without permission"],
         ["An illegal building is being constructed {where} without any permission.",
          "Unauthorised construction going on {where}, no plan approval board."]),
        (M, ["Building constructed on nala", "Construction over drain"],
         ["Someone is constructing a building on top of the nala {where}.",
          "A structure is built over the storm water drain {where}, blocking it."]),
        (M, ["Government land occupied", "Park land encroached"],
         ["The government open land {where} is being occupied by private people.",
          "Park land {where} has been fenced and occupied illegally."]),
        (M, ["Illegal extra floors", "Floors added without permission"],
         ["The building {where} added two extra floors without permission.",
          "Additional illegal floors coming up {where}."]),
        (L, ["Abandoned vehicles on road", "Old vehicles parked permanently"],
         ["Abandoned vehicles are parked permanently {where} and occupying the road.",
          "Old scrap vehicles kept on the road {where} for months."]),
        (M, ["Compound wall on public road", "Road occupied by compound wall"],
         ["A compound wall has been built on the public road {where}, narrowing it.",
          "Neighbour extended his wall into the road {where}."]),
        (C, ["Illegal building may collapse", "Unsafe illegal construction leaning"],
         ["The illegally constructed building {where} is leaning and has cracks, it may collapse on the houses next to it.",
          "Unsafe illegal structure {where} is tilting, it can collapse any moment."]),
        (L, ["Structure narrowing the road", "Ramp built on road"],
         ["A ramp and steps have been built on the road {where}, reducing the width.",
          "House owner built a ramp on the road {where}."]),
        (L, ["Construction material blocking road", "Sand and bricks on road"],
         ["Sand and bricks for construction are dumped on the road {where} for weeks.",
          "Builder kept construction material on the public road {where}."]),
        (M, ["Lake encroachment", "Cheruvu land being filled"],
         ["The lake bed {where} is being filled with soil and plots are being made.",
          "Cheruvu FTL area {where} is being encroached."]),
    ],
    "public-health": [
        (M, ["Mosquito breeding", "Too many mosquitoes"],
         ["Mosquitoes are breeding in stagnant water {where}, we cannot sleep at night.",
          "Heavy mosquito menace {where}, larvae visible in the water."]),
        (H, ["Fogging not done, dengue cases", "Dengue cases in colony"],
         ["Fogging has not been done {where} and three people got dengue.",
          "Dengue cases are rising {where}, please do fogging immediately."]),
        (H, ["Malaria cases in area", "Fever cases increasing"],
         ["Many people {where} have malaria and fever, the area needs spraying and a medical camp.",
          "Fever cases are increasing {where}, suspected malaria."]),
        (M, ["Stagnant water in open plot", "Water stagnating in vacant land"],
         ["Rain water is stagnating in the vacant plot {where} and breeding mosquitoes.",
          "Open plot {where} has stagnant water for weeks."]),
        (L, ["Anti larval spraying request", "Request fogging"],
         ["Please do anti larval spraying {where}.", "Request fogging {where} this week."]),
        (M, ["Unhygienic food stalls", "Street food unhygienic"],
         ["Food stalls {where} are selling food in very unhygienic conditions near the drain.",
          "Street vendors {where} cook next to garbage, health risk."]),
        (M, ["Open defecation", "People urinating in open"],
         ["People are defecating in the open {where}, the area is unhygienic.",
          "Open urination wall {where} is stinking."]),
        (M, ["Rat infestation", "Rats everywhere"],
         ["There is a rat infestation {where}, they are entering houses.",
          "Rats are breeding {where}, need pest control."]),
        (M, ["Mosquitoes from stagnant drain", "Drain breeding mosquitoes"],
         ["The stagnant drain {where} is breeding mosquitoes, please do spraying and fogging.",
          "Mosquito larvae in the stagnant drain water {where}, health problem."]),
        (M, ["Animal slaughter in open", "Unhygienic meat shop"],
         ["Animals are slaughtered in the open {where} and waste is thrown on the road.",
          "Meat shop {where} throws waste outside, unhygienic."]),
        (H, ["Cholera and diarrhoea cases", "Outbreak of diarrhoea in basti"],
         ["Diarrhoea cases are rising {where}, many families affected, need a medical camp.",
          "Suspected cholera cases {where}, health department should check."]),
        (L, ["Fogging smoke request for evening", "Fogging timing request"],
         ["Please do fogging {where} in the evening time when people are at home.",
          "Fogging should be done regularly {where}, once a month at least."]),
    ],
    "pollution": [
        (L, ["Loudspeakers at night", "Loud music late night"],
         ["Loudspeakers are played till midnight {where}, we cannot sleep.",
          "Loud music from the function hall {where} till 1 am."]),
        (M, ["Construction noise at night", "Night construction work noise"],
         ["Construction work {where} goes on at night with heavy machines.",
          "Noise from construction {where} at 2 am, sleepless nights."]),
        (M, ["Garbage burning smoke", "Waste burnt in open"],
         ["People are burning garbage {where} and the smoke enters our houses.",
          "Waste is burnt every evening {where}, very bad smoke."]),
        (M, ["Factory black smoke", "Industrial smoke pollution"],
         ["A factory {where} is releasing thick black smoke.",
          "Smoke from the industry {where} covers the whole area."]),
        (L, ["Dust from construction site", "Dust pollution"],
         ["Dust from the construction site {where} is spreading everywhere, no green net.",
          "Road work dust {where}, everything is covered in dust."]),
        (H, ["Chemical effluent into lake", "Industrial waste released in lake"],
         ["A company is releasing chemical effluents into the lake {where}, fish are dying.",
          "Coloured chemical water is flowing into the lake {where}."]),
        (L, ["DJ and firecrackers till late", "Firecrackers at midnight"],
         ["DJ and firecrackers {where} till 2 am every weekend.",
          "Bursting crackers late night {where}."]),
        (L, ["Generator fumes", "Diesel generator smoke"],
         ["The diesel generator of the shop {where} is releasing fumes into our windows.",
          "DG set smoke {where} all day."]),
        (H, ["Chemical smell causing breathing problems", "Gas smell from factory"],
         ["There is a strong chemical smell from the factory {where}, people are having breathing problems.",
          "Toxic smell {where} at night, children are coughing."]),
        (L, ["Honking near hospital", "Vehicle horn noise"],
         ["Vehicles keep honking {where} even near the hospital.", "Pressure horn noise {where}."]),
        (M, ["Plastic burning toxic fumes", "Burning plastic at night"],
         ["Plastic and wires are burnt at night {where} to get copper, toxic fumes.",
          "Burning plastic {where}, black smoke and bad smell."]),
        (C, ["Fire in dump yard", "Huge fire, smoke everywhere"],
         ["A huge fire broke out in the dump yard {where}, thick smoke everywhere and it is spreading.",
          "Fire at the garbage yard {where}, flames are close to the houses."]),
    ],
    "parks-trees": [
        (H, ["Tree fallen on road", "Fallen tree blocking road"],
         ["A big tree has fallen on the road {where} and is blocking traffic.",
          "Tree uprooted in the rain {where}, the road is blocked."]),
        (H, ["Dangerous tree branch", "Branch may fall"],
         ["A dry branch of the tree {where} is hanging and may fall on people.",
          "Big tree {where} is weak and leaning, it can fall any time."]),
        (L, ["Tree trimming request", "Trim the trees"],
         ["Please trim the trees {where}, branches are covering the road.",
          "Tree branches {where} need trimming."]),
        (L, ["Park not maintained", "Park overgrown"],
         ["The park {where} is not maintained, grass and bushes have overgrown.",
          "Colony park {where} is in bad shape."]),
        (L, ["Broken swings in park", "Play equipment damaged"],
         ["The swings and slides in the park {where} are broken.",
          "Children's play equipment {where} is rusted and broken."]),
        (L, ["Park gate locked", "Park timings issue"],
         ["The park {where} is locked in the morning walking time.",
          "Park gate {where} is opened very late."]),
        (L, ["Walking track damaged", "Walking track broken"],
         ["The walking track in the park {where} is damaged.", "Walking path {where} has broken tiles."]),
        (M, ["Trees cut illegally", "Illegal tree felling"],
         ["Someone is cutting the trees {where} without permission.",
          "Big trees cut illegally {where} last night."]),
        (L, ["Park lights not working", "No lights in park"],
         ["The lights inside the park {where} are not working, it is dark for walkers.",
          "Park lamps {where} are off."]),
        (H, ["Tree fell on car", "Tree fell on house wall"],
         ["A tree fell on a parked car {where}, it is still lying there.",
          "Tree fell on our compound wall {where} and damaged it."]),
        (L, ["Garbage dumped in park", "Park used as dump"],
         ["People are dumping garbage inside the park {where}, the park staff do nothing.",
          "Park {where} has become a garbage dump."]),
        (L, ["Plants not watered", "Plants dying in park"],
         ["The plants in the park {where} are drying up, nobody waters them.",
          "Saplings {where} are dying without water."]),
        (C, ["Tree fell on people", "Tree collapsed, people injured"],
         ["A huge tree collapsed {where} and fell on people waiting there, some are injured and trapped.",
          "Tree fell on an auto {where}, people are trapped under it."]),
    ],
    "other": [
        (L, ["Property tax issue", "Property tax wrongly calculated"],
         ["My property tax for {where} is calculated wrongly, please correct it.",
          "Property tax demand for my house {where} is too high."]),
        (L, ["Birth certificate delay", "Death certificate not issued"],
         ["I applied for a birth certificate for my child, it is delayed for months.",
          "Death certificate application is pending, office {where} is not responding."]),
        (M, ["Traffic signal not working", "Signal lights off at junction"],
         ["The traffic signal {where} is not working, vehicles are crossing randomly.",
          "Signal {where} is off, heavy traffic jam."]),
        (L, ["Bus shelter damaged", "No bus shelter"],
         ["The bus shelter {where} is damaged, no roof.", "Request a bus shelter {where}."]),
        (L, ["Thank you for quick action", "Appreciation for the team"],
         ["Thank you for fixing the problem {where} so quickly. Good work by the team.",
          "Appreciate the quick response {where}, the issue is solved now."]),
        (L, ["Ration card issue", "Ration card update pending"],
         ["My ration card update is pending for a long time.",
          "Ration card name correction request, office {where} keeps delaying."]),
        (L, ["How to apply for trade licence", "General query"],
         ["I want to know how to apply for a trade licence for a shop {where}.",
          "Please tell me the procedure for building permission {where}."]),
        (L, ["Staff behaviour complaint", "Official not responding"],
         ["The staff at the ward office {where} behaved rudely with senior citizens.",
          "Officer at the circle office {where} is not responding to calls."]),
        (L, ["Auto drivers overcharging", "Cab fare complaint"],
         ["Auto drivers {where} are demanding double fare.",
          "Autos near the station {where} refuse to go by meter."]),
        (L, ["Vehicle parked blocking my gate", "Wrong parking"],
         ["Someone parks their car blocking my gate {where} every day.",
          "Wrong parking {where} blocks the entrance."]),
        (L, ["Fraud call in the name of municipality", "Fake call asking money"],
         ["I got a call asking money in the name of the municipality for {where}.",
          "Fake officials asking money for a certificate {where}."]),
        (L, ["Complaint app not working", "Website error"],
         ["The complaint website gave an error when I tried to upload a photo.",
          "Unable to log in to the portal, OTP not coming."]),
        (L, ["Request for public library", "Need community hall"],
         ["Request to build a public library {where} for students.",
          "Our area {where} needs a community hall."]),
    ],
}


def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 5 or not word.isalpha():
        return word
    i = rng.randrange(1, len(word) - 1)
    action = rng.choice(["swap", "drop", "double"])
    if action == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if action == "drop":
        return word[:i] + word[i + 1:]
    return word[:i] + word[i] + word[i:]


def _add_typos(text: str, rng: random.Random) -> str:
    words = text.split(" ")
    for _ in range(rng.randint(1, 3)):
        idx = rng.randrange(len(words))
        words[idx] = _typo(words[idx], rng)
    return " ".join(words)


def _make_row(slug: str, scenario_idx: int, rng: random.Random) -> tuple[str, str]:
    severity, subjects, bodies = SCENARIOS[slug][scenario_idx]
    where = f"{rng.choice(LANDMARKS)}, {rng.choice(LOCALITIES)}"
    subject = rng.choice(subjects)
    body = rng.choice(bodies).format(where=where)

    level = severity
    parts: list[str] = []
    short_form = rng.random() < 0.15
    if not short_form:
        opener = rng.choice(OPENERS)
        if opener.endswith("that"):  # "...complain that the drain..."
            body = body[0].lower() + body[1:]
        parts.append(opener)
    parts.append(body)
    if not short_form:
        if rng.random() < 0.55:
            phrase, is_long = rng.choice(DURATIONS)
            parts.append(f"This problem is there {phrase}." if rng.random() < 0.5 else f"It is like this {phrase}.")
            if is_long and level == L:
                level = M
        if rng.random() < 0.2:
            parts.append(rng.choice(VULNERABLE))
            if level < C:
                level = max(level, min(level + 1, H))
        if rng.random() < 0.2:
            parts.append(rng.choice(SCALE))
            if level < C:
                level = max(level, min(level + 1, H))
        parts.append(rng.choice(CLOSERS))

    description = " ".join(p for p in parts if p)
    text = f"{subject}. {description}"
    if rng.random() < 0.15:
        text = _add_typos(text, rng)
    if rng.random() < 0.10:
        text = re.sub(r"[.,!]", "", text.lower())

    if rng.random() < NOISE_RATE:
        level = min(C, max(L, level + rng.choice([-1, 1])))
    return text, LEVELS[level]


def generate(rows_per_category: int = ROWS_PER_CATEGORY, seed: int = SEED) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for slug in SCENARIOS:
        count, attempts = 0, 0
        while count < rows_per_category:
            attempts += 1
            if attempts > rows_per_category * 50:
                raise RuntimeError(f"not enough distinct texts for {slug}")
            idx = rng.randrange(len(SCENARIOS[slug]))
            text, priority = _make_row(slug, idx, rng)
            if text in seen:  # no exact duplicates, so train and test never share a text
                continue
            seen.add(text)
            rows.append({"text": text, "category_slug": slug, "priority": priority, "scenario_id": f"{slug}#{idx}"})
            count += 1
    rng.shuffle(rows)
    return rows


def main() -> None:
    rows = generate()
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["text", "category_slug", "priority", "scenario_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic rows to {OUTPUT}")


if __name__ == "__main__":
    main()
