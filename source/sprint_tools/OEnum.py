import enum

class OrderedEnum(enum.Enum):
  def __ge__(self, other):
    if self.__class__ is other.__class__:
      return self.value >= other.value
    return NotImplemented
  def __gt__(self, other):
    if self.__class__ is other.__class__:
      return self.value > other.value
    return NotImplemented
  def __le__(self, other):
    if self.__class__ is other.__class__:
      return self.value <= other.value
    return NotImplemented
  def __lt__(self, other):
    if self.__class__ is other.__class__:
      return self.value < other.value
    return NotImplemented


class PrintVerbosity(OrderedEnum):
    NONE     = 99
    ERRORS   = 3
    WARNINGS = 2
    INFO     = 1
    ALL      = 0