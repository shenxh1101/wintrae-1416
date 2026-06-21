import pandas as pd
from datetime import datetime, timedelta
import random
import os


def generate_sample_data(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    shops = ["旗舰店", "专营店", "专卖店"]
    shifts = ["早班", "中班", "晚班"]
    groups = ["A组", "B组", "C组"]
    first_names = ["张", "李", "王", "刘", "陈", "杨", "黄", "赵", "周", "吴",
                   "徐", "孙", "马", "朱", "胡", "林", "郭", "何", "高", "罗"]
    given_names = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "艳", "杰",
                    "超", "秀兰", "桂英", "丽华", "建国", "玉梅", "建军", "秀英", "丽娟", "秀珍"]

    agents = []
    for i in range(15):
        fn = random.choice(first_names) + random.choice(given_names)
        agents.append({
            "客服ID": f"K{1001 + i}",
            "客服姓名": fn,
            "店铺": random.choice(shops),
            "班次": random.choice(shifts),
            "组别": random.choice(groups),
            "入职日期": (datetime.now() - timedelta(days=random.randint(30, 1000))).strftime("%Y-%m-%d"),
            "是否在职": True
        })
    df_agents = pd.DataFrame(agents)
    agents_path = os.path.join(output_dir, "客服名单示例.xlsx")
    df_agents.to_excel(agents_path, index=False)
    print(f"生成客服名单: {agents_path}")

    conv_data = []
    customers = ["快乐小明", "阳光宝贝", "天空之城", "春暖花开", "夏日微风",
               "秋叶飘零", "冬日暖阳", "星河漫步", "雨后彩虹", "月光骑士",
               "梦想家", "追光者", "小确幸", "大梦想", "棉花糖",
               "小太阳", "向日葵", "蒲公英", "稻草人", "琉璃盏"]

    order_statuses = ["待付款", "待发货", "已发货", "已完成", "退款中", "已退款"]

    customer_msgs_good = [
        "亲，欢迎光临~请问有什么可以帮您的？",
        "您好，这款商品质量怎么样？",
        "亲，这款采用优质面料，舒适透气哦~",
        "那有优惠吗？",
        "亲，现在下单可以享受满减优惠，满199减20，还赠送运费险呢😊",
        "好的，我拍了",
        "感谢您的支持~祝您购物愉快！有问题随时联系我们哦！",
    ]

    customer_msgs_bad1 = [
        "这个东西怎么这么贵？",
        "不知道，你自己看吧",
        "你们这服务态度？",
        "就是这个价，随便你买不买",
        "我要投诉！",
        "随便投诉，我又不是我的问题，关我什么事",
    ]

    customer_msgs_bad2 = [
        "我的快递什么时候到啊都三天了",
        "大概可能差不多就这几天吧尽快给你发",
        "能给个准确时间吗",
        "不清楚，你再等等吧",
    ]

    customer_msgs_timeout = [
        "亲，在吗，我问个问题",
        "", "", "",
        "您好在的，请问什么问题？",
        "我想问问尺码问题的衣服合适吗胖人穿会不会",
        "",
        "稍等我帮您推荐一下，XL比较适合呢",
    ]

    customer_msgs_no_solution = [
        "亲，我的货有问题怎么办？",
        "您好，什么问题呢？",
        "发错颜色了，而且还有质量问题有破洞",
        "这样啊，我知道了",
        "那你们怎么处理呀怎么办呢？",
        "我也不知道，你再想想办法吧",
    ]

    msg_templates = [
        (customer_msgs_good, "good", "已完成"),
        (customer_msgs_bad1, "bad", "已发货"),
        (customer_msgs_bad2, "vague", "待发货"),
        (customer_msgs_timeout, "timeout", "退款中"),
        (customer_msgs_no_solution, "nosolution", "已完成"),
    ]

    conv_id = 1
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    for agent in agents:
        num_convs = random.randint(4, 8)
        for _ in range(num_convs):
            tmpl, qtype, ostatus = random.choice(msg_templates)
            customer = random.choice(customers)
            conv_start = base_time + timedelta(
                hours=random.randint(0, 8),
                minutes=random.randint(0, 59))

            time_offset = 0
            sender_types = []
            for midx, msg_text in enumerate(tmpl):
                if msg_text == "":
                    time_offset += 5
                    continue

                is_customer = (midx % 2 == 1) if qtype != "timeout" else (
                    midx in [0, 4, 5, 7]
                )

                if qtype == "timeout":
                    if midx == 0:
                        is_customer = True
                    elif midx == 4:
                        is_customer = False
                    elif midx == 5:
                        is_customer = True
                    elif midx == 7:
                        is_customer = False
                    else:
                        continue

                if qtype in ["good", "bad", "vague", "nosolution"] and not msg_text:
                    continue

                sender = customer if is_customer else agent["客服姓名"]
                sender_type = "客户" if is_customer else "客服"

                msg_time = conv_start + timedelta(minutes=time_offset)
                if qtype == "timeout" and midx == 4 and midx - 1 >= 0:
                    time_offset += 6

                sender_type_raw = "客户" if is_customer else "客服"

                conv_data.append({
                    "会话ID": f"CONV{conv_id:05d}",
                    "客服ID": agent["客服ID"],
                    "客服姓名": agent["客服姓名"],
                    "店铺": agent["店铺"],
                    "班次": agent["班次"],
                    "订单状态": random.choice(order_statuses) if qtype == "good" else ostatus,
                    "订单号": f"DD{random.randint(100000, 999999)}",
                    "客户昵称": customer,
                    "消息时间": msg_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "发送者": sender,
                    "角色": sender_type_raw,
                    "消息内容": msg_text
                })
                time_offset += random.randint(1, 4)

            conv_id += 1

    df_conv = pd.DataFrame(conv_data)
    convs_path = os.path.join(output_dir, "当日会话示例.xlsx")
    df_conv.to_excel(convs_path, index=False)
    print(f"生成会话数据: {convs_path}，共 {conv_id-1} 个会话，{len(conv_data)} 条消息")

    return agents_path, convs_path


if __name__ == "__main__":
    generate_sample_data("sample_data")
