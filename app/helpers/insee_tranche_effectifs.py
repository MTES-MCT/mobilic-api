# From : https://www.sirene.fr/sirene/public/variable/tefen
TRANCHE_EFFECTIFS = {
    "NN": [None, None],
    "00": [0, 0],
    "01": [1, 2],
    "02": [3, 5],
    "03": [6, 9],
    "11": [10, 19],
    "12": [20, 49],
    "21": [50, 99],
    "22": [100, 199],
    "31": [200, 249],
    "32": [250, 499],
    "41": [500, 999],
    "42": [1000, 1999],
    "51": [2000, 4999],
    "52": [5000, 9999],
    "53": [10000, None],
}


def format_tranche_effectif(tranche_string):
    tranche = TRANCHE_EFFECTIFS.get(tranche_string)
    if not tranche or tranche[0] is None:
        return "Inconnu"

    if tranche_string == "53":
        return "10000+"

    return f"{tranche[0]}-{tranche[1]}"
