s=list()
for i in range(10):
    tmp=int(input("请输入第%d个数字"%(i+1)))
    s.append(tmp)

print(s)

s.sort()
print(s)
print(s[-1])
print(s[0])


