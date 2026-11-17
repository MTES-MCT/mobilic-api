from enum import Enum


class PastRegistrationJustification(str, Enum):
    OUBLI = "oubli"
    PHONE_ISSUE = "probleme_telephone"
    TECHNICAL_MALFUNCTION = "dysfonctionnement_technique"
    __description__ = """
Motif de saisie de temps a posteriori. Valeurs possibles.
- "oubli" : Oubli
- "probleme_telephone" : Problème téléphone
- "dysfonctionnement_technique" : Dysfonctionnements techniques
"""


MOTIF_VALUES = frozenset(m.value for m in PastRegistrationJustification)
