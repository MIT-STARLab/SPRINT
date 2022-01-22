from threading import RLock

class MessageIDAssigner:
    """
    A thread-safe UID assigner for messages in the format

    UIDs are integers.

    <Agent ID>:<Message ID>

    """
    def __init__(self,start: int = 0):
        """
        The contructor
        :param start: Starting UID value
        """
        self.nextID = start     # The next ID to use when assigning messages
        self.agent_id = None    # The ID of the agent using the assigner
        self.lock = RLock()     # Lock for threadsafety

    def assign_id(self):
        """
        Assign exactly one message a UID. Requires the agent ID to
        be defined.

        :return: The UID
        """
        if self.agent_id:
            with self.lock:
                self.nextID += 1
                return self.agent_id + ":" + str(self.nextID - 1)
        else:
            self.nextID += 1
            return str(self.nextID)

    def assign_ids(self,num:int):
        """
        Assign multiple messages separate UIDs in one shot.
        :param num: The number of UIDs to generate
        :return: A set of <num> UIDs
        """
        with self.lock:
            return set(self.assign_id() for i in range(num))

    def setAgentID(self,_id:str):

        self.agent_id = _id
