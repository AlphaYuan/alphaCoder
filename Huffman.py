import six


class MinHeap:

    def __init__(self):
        self.heapList = [0]
        self.currentSize = 0

    def percUp(self, i):
        while i // 2 > 0:
            if self.heapList[i // 2] > self.heapList[i]:
                tmp = self.heapList[i // 2]
                self.heapList[i // 2] = self.heapList[i]
                self.heapList[i] = tmp
            i = i // 2

    def insert(self, X):
        self.heapList.append(X)
        self.currentSize = self.currentSize + 1
        self.percUp(self.currentSize)

    def percDown(self, i):
        X = self.heapList[i]
        parent = i
        while parent * 2 <= self.currentSize:
            child = parent * 2
            if child != self.currentSize and self.heapList[child] > self.heapList[child + 1]:
                child = child + 1
            if X <= self.heapList[child]:
                break
            else:
                self.heapList[parent] = self.heapList[child]
            parent = child
        self.heapList[parent] = X

    def buildHeap(self, alist):
        self.currentSize = len(alist)
        self.heapList = [0] + alist[:]
        i = self.currentSize // 2
        while i > 0:
            self.percDown(i)
            i = i - 1

    def delMin(self):
        minItem = self.heapList[1]
        self.heapList[1] = self.heapList[self.currentSize]
        self.currentSize = self.currentSize - 1
        self.heapList.pop()
        if self.currentSize != 0:
            self.percDown(1)
        return minItem


class Tree:

    def __init__(self, initdata=None, value=None):
        self.key = initdata
        self.value = value
        self.huffmanCode = None
        self.left = None
        self.right = None

    def __le__(self, other):
        return self.key <= other.key

    def __lt__(self, other):
        return self.key < other.key

    def __ge__(self, other):
        return self.key >= other.key

    def __gt__(self, other):
        return self.key > other.key

    def __add__(self, other):
        return self.key + other.key


class Huffman:

    def __init__(self):
        self.minHeap = MinHeap()
        self.huffmanTree = None
        self.dictionary = dict()
        self.deDictionary = dict()

    def buildHuffmanTree(self, dict0):
        alist = []
        for key in dict0:
            alist.append(Tree(dict0[key], key))

        self.minHeap.buildHeap(alist)
        for i in range(1, self.minHeap.currentSize):
            t = Tree()
            t.left = self.minHeap.delMin()
            t.right = self.minHeap.delMin()
            t.key = t.left + t.right
            self.minHeap.insert(t)
        self.huffmanTree = self.minHeap.delMin()

    def preOrder(self, BT, code='0'):
        if BT:
            if BT.left is None and BT.right is None:
                BT.huffmanCode = code
                self.dictionary[BT.value] = BT.huffmanCode
                self.deDictionary[BT.huffmanCode] = BT.value
                # print(BT.key, ' ', BT.value, ' ', BT.huffmanCode, end='\n')
                return
            self.preOrder(BT.left, code + '0')
            self.preOrder(BT.right, code + '1')

    def encode(self, filename, language: str = None):
        content = ''
        with open(filename, 'r') as f:
            lines = f.readlines()
            for line in lines:
                content += str(line)

        dict0 = {}
        for ch in content:
            dict0.setdefault(ch, 0)
            dict0[ch] += 1

        self.buildHuffmanTree(dict0)
        self.preOrder(self.huffmanTree)

        new = ''.join(list(self.dictionary.values()))
        for ch in content:
            new += self.dictionary[ch]
        newSup = (8 - len(new) % 8)
        new += '0' * newSup

        f = open(filename.rsplit(sep='.', maxsplit=1)[0] + '.ac', 'wb')
        f.write(six.int2byte(newSup))
        f.write(six.int2byte(len(self.dictionary)))
        for v in self.dictionary.values():
            f.write(six.int2byte(len(v)))
        for k in self.dictionary.keys():
            f.write(six.int2byte(ord(k)))
        for i in range(len(new) // 8):
            # tmp = struct.pack('b', int(new[8 * i: 8 + 8 * i], 2))
            # print(tmp)
            # f.write(tmp)
            f.write(six.int2byte(int(new[8 * i: 8 + 8 * i], 2)))
            # print(int(new[8 * i: 8 + 8 * i], 2), end='\t')
        f.flush()
        f.close()

    def decode(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()

        codeSup = data[0]
        dictLength = data[1]
        lengthList = []
        for i in range(dictLength):
            lengthList.append(data[2 + i])
        sumLengthList = sum(lengthList) // 8
        if sum(lengthList) % 8 != 0:
            sumLengthList += 1
        huffmanCodes = ''
        for i in range(sumLengthList):
            huffmanCodes += '0' * (10 - len(bin(data[2 + 2 * dictLength + i]))) + bin(data[2 + 2 * dictLength + i])[2:]

        dictionary = {}
        k = 0
        for i in range(dictLength):
            word = chr(data[dictLength + 2 + i])
            dictionary[word] = huffmanCodes[k:k + lengthList[i]]
            k += lengthList[i]

        content = huffmanCodes[k:]
        k = 2 + 2 * dictLength + sumLengthList
        for i in data[k:]:
            content += '0' * (10 - len(bin(i))) + bin(i)[2:]
        content = content[:-codeSup]

        k = 0
        originalContent = ''
        searchLength = max([len(list(dictionary.values())[i]) for i in range(len(dictionary.values()))])
        while k != len(content):
            for i in range(searchLength):
                if content[k:k + i + 1] in dictionary.values():
                    for key, value in dictionary.items():
                        if value == content[k:k + i + 1]:
                            # print(key, end='\t')
                            originalContent += key
                    k += i + 1
                    break

        # originalContent = originalContent.encode('utf-8').decode('unicode_escape')
        # with open(filename + '.txt', 'w') as f:
        #     f.write(originalContent)
        return originalContent


if __name__ == '__main__':
    filename = input('input filename:')
    # start = time.time()
    flag = int(input('encode or decode:'))
    # flag = 2
    if flag == 1:
        Huffman().encode(filename)  # '6.Harry Potter and The Half-Blood Prince.txt')
    # end = time.time()
    # print('encode finished')
    # print(str(end - start), 's')
    elif flag == 2:
        Huffman().decode(filename)
