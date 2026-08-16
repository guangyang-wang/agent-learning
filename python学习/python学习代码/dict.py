d = {"name": "Tom", "age": 18}

print(d["name"])            # Tom
d["age"] = 20               # 修改
d["city"] = "NY"            # 新增（键不存在即新增）
print(d)                    # {'name': 'Tom', 'age': 20, 'city': 'NY'}
print("name" in d)          # True
print(d.get("name"))        # Tom
print(d.get("job", "未知"))  # 未知（键不存在返回默认值）

for k, v in d.items():
    print(k, v)
