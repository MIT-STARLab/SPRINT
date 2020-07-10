# TODO - Force upgrade to 3.6
from enum import Enum, auto
class AgentType(Enum):  # To be used for type-based behavior in generalized functions
    GS      = auto() #'GS'
    SAT     = auto() #'SAT'
    GSNET   = auto() #'GSNET'