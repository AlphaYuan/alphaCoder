class Stack:

    def __init__(self):
        self.items = []
    
    def top(self):
        if self.is_empty():
            return None
        else:
            return self.items[-1]

    def pop(self, i=0):
        val = self.items[-1-i]
        self.items.pop(-1-i)
        return val

    def popn(self, n):
        if n:
            ret = self.items[-n:]
            self.items[-n:] = []
            return ret
        else:
            return []

    def push(self, item):
        self.items.append(item)

    def is_empty(self):
        return self.items == []


if __name__ == "__main__":
    s = Stack()
    s.push(1)
    print(s.top())
    s.pop()
    print(s.is_empty())