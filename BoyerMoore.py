class BoyerMoore:

    def __init__(self, text='', pattern=''):
        self.text = text
        self.pattern = pattern
        self.n = len(self.text)
        self.m = len(self.pattern)

    def boyer_moore(self, begin=0):
        good_suffix = self.get_good_suffix()
        bad_character = self.get_bad_character()

        j = begin
        while j <= (self.n - self.m):
            i = self.m - 1
            while i >= 0 and self.pattern[i] == self.text[i + j]:
                i -= 1
            if i < 0:
                return j
            else:
                j += max(bad_character[ord(self.text[i + j])] - self.m + 1 + i, good_suffix[i])
        return -1

    def get_suffix(self):
        f = 0
        g = self.m - 1
        suff = [0] * 256
        suff[self.m - 1] = self.m

        for i in range(self.m - 2, -1, -1):
            if i > g and suff[i + self.m - 1 - f] < i - g:
                suff[i] = suff[i + self.m - 1 - f]
            else:
                if i < g:
                    g = i
                f = i
                while g >= 0 and self.pattern[g] == self.pattern[g + self.m - 1 - f]:
                    g -= 1
                suff[i] = f - g

        return suff

    def get_good_suffix(self):
        gs = [self.m] * self.m
        suffix = self.get_suffix()

        j = 0
        for i in range(self.m - 1, -1, -1):
            if i + 1 == suffix[i]:
                while j < self.m - 1 - i:
                    if self.m == gs[j]:
                        gs[j] = self.m - 1 - i
                    j += 1

        for i in range(self.m - 1):
            gs[self.m - 1 - suffix[i]] = self.m - 1 - i

        return gs

    def get_bad_character(self):
        bc = [self.m] * 256

        for i in range(self.m - 1):
            bc[ord(self.pattern[i])] = self.m - 1 - i

        return bc


if __name__ == '__main__':
    text = 'Hello, this is my sentence that is to be searched.'
    pattern = 'this'
    pattern2 = 'class '
    filepath = 'basicInfo/UI.bak'
    # with open(filepath, 'r', encoding='UTF-8') as f:
    #     text = f.read()
    bm = BoyerMoore(text, pattern)
    print(text)
    print(pattern)
    print("Matched Position:", bm.boyer_moore())
    # print(text.find(pattern))
    # print([1] * 5)