# 定义与调用
def greet(name):
    """文档字符串：说明函数用途"""
    return f"Hello, {name}"

print(greet("Tom"))              # Hello, Tom

# 返回值：多返回值底层是元组
def swap(a, b):
    return b, a

x, y = swap(1, 2)                # 解包
print(x, y)                      # 2 1
print(swap(1, 2))                # (2, 1) 其实是一个元组

def no_return():
    print("无 return")

print(no_return())               # None（默认返回）

# 参数：默认参数
def power(x, n=2):
    return x ** n

print(power(3))                  # 9
print(power(3, 3))               # 27

# 参数：关键字参数
def person(name, age, city):
    return f"{name} {age} {city}"

print(person(name="Tom", age=18, city="NY"))   # Tom 18 NY

# 参数：可变参数 *args
def total(*nums):
    return sum(nums)

print(total(1, 2, 3))            # 6，nums 是元组 (1,2,3)

# 参数：关键字可变参数 **kwargs
def info(**kw):
    return kw

print(info(name="Tom", age=18))  # {'name': 'Tom', 'age': 18}

# 作用域
x = 10

def outer():
    y = 20
    def inner():
        nonlocal y               # 修改外层局部变量
        y += 1
        global x                 # 修改全局变量
        x += 1
    inner()
    return y

print(outer())                   # 21
print(x)                         # 11

# lambda 匿名函数
add = lambda a, b: a + b
print(add(1, 2))                 # 3

# 高阶函数
nums = [1, 2, 3, 4]
print(list(map(lambda n: n * 2, nums)))           # [2, 4, 6, 8]
print(list(filter(lambda n: n % 2 == 0, nums)))   # [2, 4]
print(sorted(nums, key=lambda n: -n))             # [4, 3, 2, 1]
from functools import reduce
print(reduce(lambda a, b: a + b, nums))           # 10

# 闭包
def make_counter():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    return inc

c = make_counter()
print(c(), c())                  # 1 2

# 装饰器
def timer(fn):
    def wrapper(*args, **kwargs):
        print("执行前...")
        result = fn(*args, **kwargs)
        print("执行后...")
        return result
    return wrapper

@timer
def say(name):
    return f"hi {name}"

print(say("Tom"))                # 打印两行日志，再返回 hi Tom

# 生成器 yield
def count(n):
    i = 0
    while i < n:
        yield i
        i += 1

for num in count(3):
    print(num, end=" ")          # 0 1 2
print()
