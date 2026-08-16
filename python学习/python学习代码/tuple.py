t = (1, 2, 3, 2)

print(t[0])          # 1
print(t[-1])         # 2
print(t[1:3])        # (2, 3)
print(2 in t)        # True
print(len(t))        # 4
print(t.count(2))    # 2
print(t.index(3))    # 2

# 解包
a, b = (1, 2)
print(a, b)          # 1 2

# 单元素元组必须加逗号
print(type((1)))     # <class 'int'>
print(type((1,)))    # <class 'tuple'>

# 不可修改（会报错，可取消注释验证）
# t[0] = 9
# t.append(4)
