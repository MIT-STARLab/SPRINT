import threading
class BlockingDict:
    """
    A threadsafe version of a dictionary.
    All actions (put, get, keyExists) requires the object's lock to proceed.

    """

    def __init__(self):
        self.queue = {}
        self.cv = threading.Condition()

    def put(self, key, value):
        """
        Places value associated with given key

        :param key:
        :param value:
        :return: None
        """
        with self.cv:
            self.queue[key] = value
            self.cv.notifyAll()
            

    def keyExists(self,key):
        """
        Determines if the key exists
        :param key: The key
        :return: True if key exists
        """
        with self.cv:
            return key in self.queue

    def get(self,key):
        """
        Gets and removes the key-value pair.
        blocks until key is in queue
        :param key: The input key
        :return:  The value of the key
        """
        with self.cv:
            self.cv.wait_for(lambda: key in self.queue)
            result = self.queue.pop(key)
            return result

    def __str__(self):
        with self.cv:
            return self.queue.__str__()
