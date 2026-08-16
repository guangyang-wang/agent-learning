s = {1, 2, 3, 2}
print(s)             # {1, 2, 3} 自动去重

s.add(4)
s.remove(2)
s.discard(9)         # 不存在也不报错
print(2 in s)        # False
print(len(s))        # 3

a = {1, 2, 3}
b = {2, 3, 4}
print(a | b)         # {1, 2, 3, 4} 并集
print(a & b)         # {2, 3} 交集
print(a - b)         # {1} 差集
print(a ^ b)         # {1, 4} 对称差
