from swift import start_servers
from queue import Queue


outq = Queue()
inq = Queue()

start_servers(outq, inq)

while 1:
    pass
