from logging import Filter
import client.logger as logger
from client.logger import PROGRESS_LEVEL

logger = logger.logger


class ProgressReporter:
    def __init__(self, l, length):
        self.l = l
        self.max_length = length

    def __iter__(self):
        self.i = -1
        return self

    def __next__(self):
        if self.i < self.max_length - 1:
            self.i += 1
            logger.info("???")
            logger.progress("{0}/{1}".format(self.i + 1, self.max_length))
            return (self.i, self.l[self.i])
        else:
            raise StopIteration


if __name__ == "__main__":
    total_steps = 3
    time_range = (list(reversed(range(0, total_steps))))

    for i, d in ProgressReporter(time_range, total_steps):
        index = total_steps - i - 1
        print("i:", i, "d:", d, "index:", index)
