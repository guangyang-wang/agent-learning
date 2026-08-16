d = {"name": "Tom", "age": 18}

# 存取
print(d["name"])             # Tom
d["age"] = 20                # 修改
d["city"] = "NY"             # 新增（键不存在即新增）
print(d)                     # {'name': 'Tom', 'age': 20, 'city': 'NY'}
print("name" in d)           # True（判断键是否存在）
print(d.get("name"))         # Tom
print(d.get("job", "未知"))   # 未知（键不存在返回默认值）

# 常用方法
d["c"] = 3
d.update({"d": 4, "e": 5})   # 批量合并
print(d.pop("c"))            # 3（删并返回）
print(d.setdefault("f", 0))  # 0（f 不存在则设默认值）
print(list(d.keys()))        # ['name','age','city','d','e','f']

# 合并（Python 3.9+）
d1 = {"a": 1}
d2 = {"b": 2, "a": 9}
print(d1 | d2)               # {'a': 9, 'b': 2} 后者覆盖
print({**d1, **d2})          # 解包合并，结果同上

# 遍历
for k in d:                  # 遍历键
    print(k, end=" ")
print()
for k, v in d.items():       # 遍历 键+值（最常用）
    print(k, v)

# 字典推导式
print({x: x ** 2 for x in range(3)})   # {0: 0, 1: 1, 2: 4}

# defaultdict 与 Counter
from collections import defaultdict, Counter

cnt = defaultdict(int)
cnt["a"] += 1                # 键不存在也直接 +1
print(cnt)                   # defaultdict(<class 'int'>, {'a': 1})

print(Counter("hello"))      # Counter({'l': 2, 'h': 1, 'e': 1, 'o': 1})
print(Counter([1, 2, 2, 3])) # Counter({2: 2, 1: 1, 3: 1})
