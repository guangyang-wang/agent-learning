# -*- coding: utf-8 -*-
"""
阶段 1 · Python 补齐 · 装饰器 (decorator)

装饰器是 Agent 开发绕不开的语法，最常见的两个用途：
    工具自动注册  ->  @register_tool
    FastAPI 路由  ->  @app.get("/xxx")

一句话理解：装饰器 = 给函数"套一层壳"，在不改原函数代码的前提下增加功能。

Java 类比：装饰器 ≈ 注解(Annotation) + AOP 切面，最接近 Spring 的 @Around 环绕通知。
"""


# ============================================================
# 1. 函数是"一等公民"：函数可以当参数传、当返回值返回
#    Java 对应：方法引用 / Lambda / Function 接口
# ============================================================

def greet(name):
    return f"你好，{name}"

# 把函数本身（不带括号）赋给变量
f = greet
print(f("小明"))          # 你好，小明


def make_adder(n):
    # 返回一个新的函数
    def adder(x):
        return x + n
    return adder

add_10 = make_adder(10)
print(add_10(5))          # 15


# ============================================================
# 2. 闭包 (closure)：内层函数"记住"了外层函数的变量 n
#    Java 对应：匿名内部类捕获 final 变量 / Lambda 捕获
# ============================================================
# 上面 make_adder 里的 adder 就是闭包，它记住了 n=10


# ============================================================
# 3. 最简单的装饰器：一个接收函数、返回新函数的函数
# ============================================================

def my_decorator(func):
    def wrapper(*args, **kwargs):
        print(f"--- 调用 {func.__name__} 之前 ---")
        result = func(*args, **kwargs)     # 真正执行原函数
        print(f"--- 调用 {func.__name__} 之后 ---")
        return result
    return wrapper


def say_hello():
    print("Hello!")

# 手动"套壳"：把 say_hello 替换成 wrapper
say_hello = my_decorator(say_hello)
say_hello()
# 输出：
# --- 调用 say_hello 之前 ---
# Hello!
# --- 调用 say_hello 之后 ---


# ============================================================
# 4. @ 语法糖：上面那句"手动套壳"的简写
# ============================================================

@my_decorator
def say_bye():
    print("Bye!")

# @my_decorator 完全等价于  say_bye = my_decorator(say_bye)
say_bye()


# ============================================================
# 5. 带参数的装饰器：装饰器本身也需要"配置"时，外面再包一层
#    结构：def 装饰器工厂(参数) -> 返回真正的装饰器
# ============================================================

def repeat(times):
    """重复执行原函数 times 次"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(times):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator


@repeat(3)
def hello():
    print("你好呀")

hello()   # 打印 3 次"你好呀"


# ============================================================
# 6. functools.wraps：保留原函数的元信息（名字、文档字符串）
#    不加的话，wrapper.__name__ 会变成 "wrapper"
# ============================================================

import functools

def keep_name(func):
    @functools.wraps(func)      # 关键：把原函数的 __name__ 等信息拷过来
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@keep_name
def important_func():
    """这是一段重要的文档"""
    pass

print(important_func.__name__)   # important_func（不加 wraps 会显示 wrapper）
print(important_func.__doc__)    # 这是一段重要的文档


# ============================================================
# 7. 实战：@register_tool —— Agent 开发最常用的装饰器
#    Agent 里有很多工具（计算器、查天气、查订单），
#    用装饰器把它们自动收集到"工具注册表"里，模型就能按名字调用。
#    Java 类比：用注解标记 + 启动时扫描，类似 Spring 的 @Component 组件扫描。
# ============================================================

TOOL_REGISTRY = {}   # 工具注册表：{工具名: 工具信息}

def register_tool(name=None, description=""):
    """工具注册装饰器：把函数自动登记进 TOOL_REGISTRY"""
    def decorator(func):
        tool_name = name or func.__name__
        TOOL_REGISTRY[tool_name] = {
            "func": func,
            "description": description,
        }
        return func
    return decorator


@register_tool(name="add", description="两个数字相加")
def add(a: int, b: int) -> int:
    return a + b


@register_tool(name="query_order", description="根据订单号查询订单金额")
def query_order(order_id: str) -> dict:
    # 模拟数据库查询
    fake_db = {"A001": 99.5, "A002": 199.0}
    return {"order_id": order_id, "amount": fake_db.get(order_id, 0.0)}


# 看看注册表里自动收集到了什么
print("已注册的工具：")
for name, info in TOOL_REGISTRY.items():
    print(f"  {name}: {info['description']}")


# ============================================================
# 与 Java 对比总结
# ============================================================
"""
| 概念          | Python                              | Java                                   |
|---------------|-------------------------------------|----------------------------------------|
| 语法标记      | @decorator                          | @Annotation（注解）                     |
| 本质          | 函数/类 的包装器                     | 需 AOP 框架（Spring AOP）实现            |
| 运行时增强    | wrapper 函数包裹                     | @Around 环绕通知 / 动态代理               |
| 工具注册场景  | @register_tool 存进 dict            | @Component 扫描进容器（IoC）             |
| 元信息保留    | functools.wraps                     | 无需（注解不改变方法本身）                |

核心区别：Python 装饰器是"运行时直接替换函数"；
Java 注解本身"什么都不做"，需要反射 + 框架（Spring）去扫描并处理。
"""
