from futures import ThreadPoolExecutor
from Queue import Queue


def execute(func_list):
    q = Queue()
    output = []

    def f(func):
        q.put(func())

    with ThreadPoolExecutor(max_workers=6) as executor:
        [executor.submit(f, function) for function in func_list]

    while not q.empty():
        output.append(q.get())

    return output
