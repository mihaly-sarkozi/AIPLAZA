"""
Cím (postal address) kulcsszavak – HU, EN, ES.
Közterület típusok, épület, emelet, ajtó, kerület, stb.
"""
from __future__ import annotations

# Magyar közterület típusok (elírásokkal: lph=lépcsház, cim=cím)
KOZTERULET_TIPUSOK_HU = [
    "utca",
    "út",
    "útja",
    "tér",
    "tere",
    "körút",
    "körútja",
    "körönd",
    "sugárút",
    "sétány",
    "sor",
    "köz",
    "köze",
    "fasor",
    "dűlő",
    "lejtő",
    "rakpart",
    "part",
    "liget",
    "park",
    "lakótelep",
    "telep",
    "major",
    "tanya",
    "zug",
    "zsákutca",
    "átjáró",
    "alsó sor",
    "felső sor",
    "alsó utca",
    "felső utca",
    "határút",
    "bekötőút",
    "összekötő út",
    "elkerülő út",
    "vasút sor",
    "vasút utca",
    "ipartelep",
    "ipari park",
    "pincesor",
    "külterület",
    "hrsz",
    "helyrajzi szám",
]

# Címre utaló szavak – épület, emelet, ajtó, kerület, város, stb.
ADDRESS_HINT_HU = [
    "épület",
    "epulet",
    "út",
    "ut",
    "útja",
    "utja",
    "tér",
    "ter",
    "utca",
    "lph",
    "lépcsház",
    "lepcshaz",
    "emelet",
    "köz",
    "koz",
    "negyed",
    "kerület",
    "kerulet",
    "ajtó",
    "ajto",
    "város",
    "varos",
    "cím",
    "cim",
    "lakcím",
    "lakcim",
]

# EN szinonímák
ADDRESS_HINT_EN = [
    "street",
    "st",
    "avenue",
    "ave",
    "road",
    "rd",
    "boulevard",
    "blvd",
    "drive",
    "dr",
    "lane",
    "ln",
    "way",
    "court",
    "ct",
    "building",
    "floor",
    "apt",
    "apartment",
    "suite",
    "district",
    "quarter",
    "city",
    "address",
    "lives at",
]

# ES szinonímák
ADDRESS_HINT_ES = [
    "calle",
    "avenida",
    "av",
    "plaza",
    "paseo",
    "camino",
    "carretera",
    "edificio",
    "piso",
    "puerta",
    "distrito",
    "barrio",
    "ciudad",
    "dirección",
    "direccion",
]

import re

# Regex: bármelyik cím kulcsszó (substringként is)
ADDRESS_KEYWORDS_REGEX = re.compile(
    r"(?i)(?:"
    r"épület|epulet|útja?|utja?|tér|ter|utca|"
    r"lph|lépcsház|lepcshaz|emelet|köz|koz|negyed|"
    r"kerület|kerulet|ajtó|ajto|város|varos|"
    r"cím|cim|lakcím|lakcim|"
    r"körút|sugárút|sétány|rakpart|liget|park|"
    r"lakótelep|telep|major|tanya|zug|zsákutca|"
    r"hrsz|helyrajzi\s+szám|"
    r"street|st\b|avenue|ave|road|rd|boulevard|blvd|"
    r"drive|dr|lane|ln|way|court|ct|"
    r"building|floor|apt|apartment|suite|"
    r"district|quarter|city|address|lives\s+at|"
    r"calle|plaza|avenida|paseo|camino|edificio|"
    r"piso|puerta|distrito|barrio|ciudad|dirección|direccion"
    r")"
)
