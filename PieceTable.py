from copy import deepcopy

from BoyerMoore import BoyerMoore


class PieceTable:

    def __init__(self, text=''):
        self.original_buffer = text
        self.add_buffer = ''
        self.cur_piece_table = []
        descriptor = {'buffer': 'original', 'start': 0, 'length': len(text)}
        self.cur_piece_table.append(descriptor)
        self.piece_tables = [deepcopy(self.cur_piece_table)]
        self.snaps = 0

    def get_sequence(self):
        text = ''
        for i in range(len(self.cur_piece_table)):
            if not self.cur_piece_table[i]:
                continue
            start = self.cur_piece_table[i]['start']
            length = self.cur_piece_table[i]['length']
            if self.cur_piece_table[i]['buffer'] == 'original':
                text += self.original_buffer[start: start + length]
            elif self.cur_piece_table[i]['buffer'] == 'add':
                text += self.add_buffer[start: start + length]
        return text

    def delete(self, begin: int, end: int):
        pointer = -1
        index1 = 0
        index2 = 0
        len1 = 0
        len2 = 0
        new_piece_table = []

        for i in range(len(self.cur_piece_table)):
            pointer += self.cur_piece_table[i]['length']
            if begin <= pointer:
                index1 = i
                len1 = begin - (pointer - self.cur_piece_table[i]['length'] + 1)
                break

        pointer = -1
        for i in range(len(self.cur_piece_table)):
            pointer += self.cur_piece_table[i]['length']
            if end <= pointer:
                index2 = i
                len2 = pointer - end
                break

        new_piece_table.extend(deepcopy(self.cur_piece_table[:index1]))

        descriptor1 = deepcopy(self.cur_piece_table[index1])
        descriptor1['length'] = len1
        new_piece_table.append(deepcopy(descriptor1))

        descriptor2 = deepcopy(self.cur_piece_table[index2])
        descriptor2['start'] = descriptor2['start'] + descriptor2['length'] - len2
        descriptor2['length'] = len2
        new_piece_table.append(deepcopy(descriptor2))

        new_piece_table.extend(deepcopy(self.cur_piece_table[index2 + 1:]))
        self.piece_tables.append(deepcopy(new_piece_table))
        self.snaps += 1
        self.cur_piece_table = self.piece_tables[self.snaps]

        return self.get_sequence()

    def insert(self, pos: int, text: str):
        pointer = -1
        index = -1
        len1 = 0
        len2 = 0
        new_piece_table = []

        for i in range(len(self.cur_piece_table)):
            pointer += self.cur_piece_table[i]['length']
            if pos <= pointer:
                index = i
                len1 = pos - (pointer - self.cur_piece_table[i]['length'] + 1)
                len2 = pointer - pos + 1
                break

        if index == -1:
            new_piece_table.extend(deepcopy(self.cur_piece_table))
            descriptor = {'buffer': 'add', 'start': len(self.add_buffer), 'length': len(text)}
            self.add_buffer += text
            new_piece_table.append(deepcopy(descriptor))
        else:
            new_piece_table.extend(deepcopy(self.cur_piece_table[: index]))
            descriptor1 = deepcopy(self.cur_piece_table[index])
            descriptor1['length'] = len1
            new_piece_table.append(deepcopy(descriptor1))
            descriptor2 = {'buffer': 'add', 'start': len(self.add_buffer), 'length': len(text)}
            self.add_buffer += text
            new_piece_table.append(deepcopy(descriptor2))
            descriptor3 = deepcopy(self.cur_piece_table[index])
            descriptor3['start'] = descriptor3['start'] + len1
            descriptor3['length'] = len2
            new_piece_table.append(deepcopy(descriptor3))
            new_piece_table.extend(deepcopy(self.cur_piece_table[index + 1:]))

        self.piece_tables.append(deepcopy(new_piece_table))
        self.snaps += 1
        self.cur_piece_table = self.piece_tables[self.snaps]

        return self.get_sequence()

    def copy(self, from_begin: int, from_end: int, to: int):
        s = self.subsequence(from_begin, from_end)
        self.insert(to, s)
        return self.get_sequence()

    def move(self, from_begin: int, from_end: int, to: int):
        s = self.subsequence(from_begin, from_end)
        self.delete(from_begin, from_end)
        self.insert(to, s)
        return self.get_sequence()

    def replace(self, from_begin: int, from_end: int, text: str):
        self.delete(from_begin, from_end)
        self.insert(from_begin, text)
        return self.get_sequence()

    def find(self, pattern: str, begin: int = 0):
        bm = BoyerMoore(self.get_sequence(), pattern)
        return bm.boyer_moore(begin)

    def subsequence(self, begin: int, end: int):
        s = self.get_sequence()
        return s[begin: end + 1]

    def undo(self):
        if self.snaps > 0:
            self.snaps -= 1
            self.cur_piece_table = self.piece_tables[self.snaps]
        return self.get_sequence()

    def redo(self):
        if len(self.piece_tables) > self.snaps + 1:
            self.snaps += 1
            self.cur_piece_table = self.piece_tables[self.snaps]
            return self.get_sequence()
        else:
            pass


if __name__ == '__main__':
    text = 'My'
    text1 = 'My PieceTable implemented in Python'
    insert_text = 'H'
    pt = PieceTable(text)
    print(pt.get_sequence())
    # print('1,37 subsequence: ', pt.subsequence(1, 37))
    print('1,1 delete: ', pt.delete(1, 1))
    print(pt.get_sequence())
    # print('undo: ', pt.undo())
    # print('redo: ', pt.redo())
    # print(pt.delete(0, 1))
    # print(pt.insert(10, insert_text))
    # print(pt.insert(37, insert_text))
    # print(pt.undo())
    # print(pt.delete(1, 5))
    # print(pt.undo())
    # print(pt.redo())
    # print(pt.find('HELLO', 20))
