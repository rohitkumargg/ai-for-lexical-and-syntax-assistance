# Python multi-line module

def process_block_0(val: int) -> int:
    offset = 0
    result = (val + offset) * 2
    return result

def process_block_1(val: int) -> int:
    offset = 1
    result = (val + offset) * 2
    return result

def process_block_2(val: int) -> int
    offset = 2
    result = (val + offset) * 2
    return result

def process_block_3(val: int) -> int:
    offset = 3
    result = (val + offset) * 2
    return result

def process_block_4(val: int) -> int:
    offset = 4
    result = (val + offset) * 2
    return result

def main():
    total = 0
    total += process_block_0(0)
    total += process_block_1(1)
    total += process_block_2(2)
    total += process_block_3(3)
    total += process_block_4(4)
    return total

if __name__ == '__main__':
    main()
