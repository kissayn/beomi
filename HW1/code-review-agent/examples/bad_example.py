"""这是一份故意写了很多问题的代码，用来测试代码审查 Agent。"""

import os


class UserManager:
    def __init__(self):
        self.users = {}

    def add_user(self, name, age, email):
        # 拼接SQL，有注入风险
        sql = "INSERT INTO users (name, age, email) VALUES ('%s', %d, '%s')" % (name, age, email)
        print("执行:", sql)
        self.users[name] = {"name": name, "age": age, "email": email}
        return sql

    def get_user(self, name):
        # 应该处理key不存在的情况
        return self.users[name]

    def adult_count(self):
        count = 0
        for name in self.users:
            if self.users[name]["age"] >= 18:
                count += 1
        return count

    def delete_all(self):
        # 危险操作，递归删除后没有任何确认
        os.system("rm -rf ./data")


def read_config(path):
    f = open(path)
    #文件打开后没有关闭
    data = f.read()
    return data


def process_age(age):
    if age > 0:
        if age < 150:
            if type(age) == int:
                return True
    return False


if __name__ == "__main__":
    mgr = UserManager()
    mgr.add_user("alice", 20, "a@x.com")
    #bob从未被添加，程序跑到这里就会崩溃
    print(mgr.get_user("bob"))
