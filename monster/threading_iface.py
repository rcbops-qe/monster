from futures import ThreadPoolExecutor
from Queue import Queue


def execute(func_list):
    q = Queue()
    output = []

    def f(func):
        q.put(func())

    with ThreadPoolExecutor(max_workers=6) as executor:
        for function in func_list:
            executor.submit(f, function)

    while not q.empty():
        output.append(q.get())
    return output
