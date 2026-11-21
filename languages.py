from enum import StrEnum

LANGUAGES = [
    'English',
    'French',
    'Spanish',
    'Dutch',
    'Polish'
]

class LanguageProficiency(StrEnum):
    FRESHY = 'Complete Beginner'
    A1     = 'A1',
    A2     = 'A2',
    B1     = 'B1',
    B2     = 'B2',
    C1     = 'C1',
    C2     = 'C2'
