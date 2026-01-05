import requests
import json
import time
from datetime import datetime
import urllib3
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

# ==================== QQ邮件通知配置 ====================
# 请务必修改以下为你自己的信息
EMAIL_CONFIG = {
    'smtp_server': 'smtp.qq.com',       # QQ邮箱SMTP服务器地址[citation:1]
    'smtp_port': 465,                    # SSL加密端口[citation:1]
    'sender_email': '*****',  # 发件人邮箱，例如 123456@qq.com
    'sender_name': '车票监控助手',        # 发件人显示名称
    'authorization_code': '*****', # 在QQ邮箱设置中生成的16位授权码，不是密码！[citation:1]
    'receiver_email': '*****' # 接收提醒的邮箱，可以是你自己的另一个邮箱
}
# =======================================================

def send_email_notification(subject, content):
    """
    使用QQ邮箱发送通知邮件
    """
    try:
        # 1. 构建邮件内容
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = formataddr((EMAIL_CONFIG['sender_name'], EMAIL_CONFIG['sender_email']))
        msg['To'] = EMAIL_CONFIG['receiver_email']
        msg['Subject'] = Header(subject, 'utf-8')

        # 2. 连接服务器并发送[citation:1]
        server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['authorization_code'])
        server.sendmail(EMAIL_CONFIG['sender_email'], [EMAIL_CONFIG['receiver_email']], msg.as_string())
        server.quit()
        print(f"[邮件通知] 发送成功: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[邮件通知] 发送失败：认证失败，请检查邮箱地址和授权码是否正确[citation:3]")
    except Exception as e:
        print(f"[邮件通知] 发送失败：{e}")
    return False

# 禁用SSL验证的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RefundTicketMonitor:
    def __init__(self):
        # 监控配置
        self.target_start = ""
        self.target_arrival = ""
        self.is_monitoring = False

        # 请求参数
        self.base_params = {
            "StartNodeGis": "",
            "ArrivalNodeGis": "",
            "StartCityCode": "",
            "ArrivalCityCode": "",
            "StartNodeName": "",
            "StartNodeDistrictName": "",
            "ArrivalNodeName": "",
            "ArrivalNodeDistrictName": ""
        }
        # 请求头
        self.headers = {
            "authorization": "",
            "user-agent": "",
            "content-type": "",
            "iswxapp": "",
            "agentappid": "",
            "accept": "",
            "referer": ""
        }

    def set_date(self, target_date):
        """设置监控日期"""
        self.target_date = target_date
        self.params = self.base_params.copy()
        self.params.update({
            "BeginDate": f"{self.target_date} 00:00",
            "EndDate": f"{self.target_date} 23:59",
            "_JsonText": json.dumps({
                "IsNewSearch": True,
                "HasLocation": True,
                "InTiimeStamp": int(time.time() * 1000),
                "LocationGis": "",
                "LocationDistrict": "",
                "LocationCityCode": "",
                "LocationCityName": "",
                "LocationTownship": "",
                "LocationAddress": "",
                "LocationProvince": "",
                "SearchStartDistrict": "",
                "SearchEndDistrict": ""
            })
        })

    def fetch_data(self):
        """获取数据"""
        try:
            url = ""
            response = requests.get(
                url,
                params=self.params,
                headers=self.headers,
                timeout=15,
                verify=False
            )

            if response.status_code == 200:
                return response.json()
            print(f"[网络错误] 状态码: {response.status_code}")
            return None
        except Exception as e:
            print(f"[请求异常] {e}")
            return None

    def get_all_classes(self):
        """获取并格式化当天所有班次信息"""
        print(f"正在获取 {self.target_date} 的班次信息...")
        data = self.fetch_data()

        if not data:
            print("获取数据失败，请检查网络或令牌。")
            return [], []
        if not data.get("success"):
            print(f"API返回失败: {data.get('msg', '未知错误')}")
            return [], []

        all_classes = []
        bus_data = data.get("data", [])
        target_line_found = False

        for line in bus_data:
            if (line.get("StartNodeName") == self.target_start and
                    line.get("ArrivalNodeName") == self.target_arrival):
                target_line_found = True
                class_list_str = line.get("ClassList", "[]")
                try:
                    class_list = json.loads(class_list_str)
                except json.JSONDecodeError:
                    print("班次列表解析失败。")
                    return [], []

                for class_info in class_list:
                    if class_info.get("ClassDate") == self.target_date:
                        all_classes.append({
                            "departure_time": class_info.get("ClassTime", "--:--"),
                            "arrival_time": class_info.get("ArrivalTime", "--:--"),
                            "available_tickets": class_info.get("CanSaleCount", 0),
                            "total_tickets": class_info.get("SeatCount", 0),
                            "runtime": class_info.get("RunTime", 0),
                            "price": class_info.get("MinFullPrice", 0),
                            "gid": class_info.get("GID")  # 保存班次ID
                        })
                break  # 找到目标线路后跳出循环

        if not target_line_found:
            print(f"未找到线路: {self.target_start} -> {self.target_arrival}")
            return [], []

        # 分离有票和无票班次
        no_ticket_classes = [c for c in all_classes if c["available_tickets"] == 0]
        has_ticket_classes = [c for c in all_classes if c["available_tickets"] > 0]

        return all_classes, no_ticket_classes, has_ticket_classes

    def find_target_class(self, departure_time):
        """根据出发时间查找班次详细信息"""
        all_classes, _, _ = self.get_all_classes()
        for class_info in all_classes:
            if class_info["departure_time"] == departure_time:
                return class_info
        return None

    def monitor_refund_ticket(self, target_class_info, check_interval=30, alert_threshold=1):
        """
        监控指定班次的回流票

        Args:
            target_class_info: 目标班次的字典信息
            check_interval: 检查间隔（秒）
            alert_threshold: 提醒阈值（当票数大于等于此值时提醒）
        """
        departure_time = target_class_info["departure_time"]
        print(f"\n🚌 开始监控回流票 🚌")
        print(f"日期: {self.target_date}")
        print(f"班次: {departure_time} -> {target_class_info['arrival_time']}")
        print(f"检查间隔: {check_interval}秒")
        print("=" * 50)

        self.is_monitoring = True
        check_count = 0
        last_ticket_count = 0
        found_refund = False

        try:
            while self.is_monitoring:
                check_count += 1
                current_time = datetime.now().strftime("%H:%M:%S")

                # 重新获取该班次的最新信息
                current_info = self.find_target_class(departure_time)

                if not current_info:
                    print(f"[{current_time}] 第{check_count}次检查: 班次信息获取失败")
                    time.sleep(check_interval)
                    continue

                tickets = current_info["available_tickets"]

                # 记录首次状态
                if check_count == 1:
                    last_ticket_count = tickets
                    print(f"[{current_time}] 初始状态: {tickets}张票")

                # 检查票数变化
                elif tickets != last_ticket_count:
                    print(f"\n{'=' * 40}")
                    print(f"[{current_time}] 票数变化: {last_ticket_count} → {tickets}")

                    # 如果是回流票（从0到有票）
                    if last_ticket_count == 0 and tickets >= alert_threshold:
                        found_refund = True
                        print(f"🎉 发现回流票！{tickets}张可售 🎉")
                        print(f"班次ID: {current_info.get('gid', 'N/A')}")
                        print(f"运行时间: {current_info['runtime']}分钟")
                        print(f"票价: ¥{current_info['price']}")
                        print(f"💥💥💥 快去抢票！ 💥💥💥")

                        # 发出提示音 (可能在某些终端无效)
                        for _ in range(3):
                            print('\a', end='', flush=True)
                            time.sleep(0.3)

                        # ========== 【核心】发送邮件通知 ==========
                        email_subject = f"【回流票提醒】{self.target_date} {departure_time} 班次"
                        email_content = \
                        f"""
                        发现车票回流！
                        日期：{self.target_date}
                        班次：{departure_time} -> {current_info['arrival_time']}
                        当前余票：{tickets} 张
                        票价：¥{current_info['price']}
                        运行时间：{current_info['runtime']}分钟
                        速去抢票！
                        """
                        send_email_notification(email_subject, email_content)
                        # ==========================================

                    elif tickets > last_ticket_count:
                        print(f"📈 票数增加: +{tickets - last_ticket_count}张")
                    elif tickets < last_ticket_count:
                        print(f"📉 票数减少: -{last_ticket_count - tickets}张")

                    last_ticket_count = tickets
                    print(f"{'=' * 40}\n")

                else:
                    # 显示监控状态
                    status_msg = f"[{current_time}] 第{check_count}次检查: {tickets}张票"
                    if tickets == 0:
                        print(f"{status_msg} - 等待回流票...")
                    else:
                        print(f"{status_msg} - 已有票，停止监控")
                        break

                # 如果已经发现回流票，询问是否继续
                if found_refund:
                    user_input = input("\n发现回流票！是否继续监控？(y/n): ").strip().lower()
                    if user_input != 'y' and user_input != '':
                        break
                    found_refund = False

                # 等待下次检查
                if self.is_monitoring:
                    time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n监控被用户中断")
        finally:
            self.is_monitoring = False
            print(f"\n监控结束，共检查 {check_count} 次")


def display_class_table(classes, title):
    """以表格形式美观地展示班次列表"""
    if not classes:
        return

    print(f"\n{title}")
    print("=" * 80)
    print(f"{'序号':<4} {'出发':<8} {'到达':<8} {'余票/总数':<10} {'运行时间':<10} {'票价':<8} {'状态':<6}")
    print("-" * 80)

    for i, cls in enumerate(classes, 1):
        status = "有票" if cls["available_tickets"] > 0 else "无票"
        status_display = f"\033[92m{status}\033[0m" if status == "有票" else f"\033[91m{status}\033[0m"

        print(f"{i:<4} {cls['departure_time']:<8} {cls['arrival_time']:<8} "
              f"{cls['available_tickets']:>2}/{cls['total_tickets']:<8} "
              f"{cls['runtime']:<10}分钟 ¥{cls['price']:<7} {status_display}")
    print("=" * 80)


def main():
    """主函数 - 交互式界面"""
    print("回流票监控工具 (增强版)")
    print("=" * 50)

    monitor = RefundTicketMonitor()

    # 设置监控日期
    while True:
        date_input = input("\n请输入监控日期 (格式: YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(date_input, "%Y-%m-%d")
            monitor.set_date(date_input)
            break
        except ValueError:
            print("日期格式错误，请重新输入")

    # 获取当天所有班次
    all_classes, no_ticket_classes, has_ticket_classes = monitor.get_all_classes()

    if not all_classes:
        print("未找到任何班次信息，程序退出。")
        return

    # 显示所有班次（分开有票和无票）
    display_class_table(has_ticket_classes, "✅ 有票班次列表")
    display_class_table(no_ticket_classes, "❌ 无票班次列表 (可监控回流票)")

    if not no_ticket_classes:
        print("\n⚠️  当前所有班次都有票，无需监控回流票。")
        return

    # 让用户从无票班次中选择
    print(f"\n请从以上无票班次中选择一个进行监控 (1 到 {len(no_ticket_classes)})")
    print("或输入 0 退出程序")

    while True:
        try:
            choice = int(input(f"\n请输入班次序号 (1-{len(no_ticket_classes)}): "))

            if choice == 0:
                print("退出程序。")
                return
            elif 1 <= choice <= len(no_ticket_classes):
                selected_class = no_ticket_classes[choice - 1]

                # 设置监控参数
                interval_input = input("检查间隔(秒，默认30): ").strip()
                interval = int(interval_input) if interval_input.isdigit() else 30

                threshold_input = input("提醒阈值(当票数>=此值时提醒，默认1): ").strip()
                threshold = int(threshold_input) if threshold_input.isdigit() else 1

                # 显示选择的班次详情并开始监控
                print(f"\n您选择的班次详情:")
                print(f"  出发: {selected_class['departure_time']}")
                print(f"  到达: {selected_class['arrival_time']}")
                print(f"  运行: {selected_class['runtime']}分钟")
                print(f"  票价: ¥{selected_class['price']}")
                print(f"  总座位: {selected_class['total_tickets']}个")

                confirm = input("\n确认开始监控此班次？(y/n, 默认y): ").strip().lower()
                if confirm == '' or confirm == 'y':
                    monitor.monitor_refund_ticket(
                        target_class_info=selected_class,
                        check_interval=interval,
                        alert_threshold=threshold
                    )
                else:
                    print("监控取消。")
                break
            else:
                print(f"序号无效，请输入 1 到 {len(no_ticket_classes)} 之间的数字。")
        except ValueError:
            print("请输入有效的数字。")
        except KeyboardInterrupt:
            print("\n程序被用户中断。")
            return


if __name__ == "__main__":
    main()