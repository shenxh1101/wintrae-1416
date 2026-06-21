import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime
import os

from models import Agent, Conversation, Message, ShiftType, OrderStatus


class ImportService:
    @staticmethod
    def _read_file(file_path: str) -> pd.DataFrame:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            return pd.read_excel(file_path)
        elif ext == '.csv':
            try:
                return pd.read_csv(file_path, encoding='utf-8-sig')
            except UnicodeDecodeError:
                return pd.read_csv(file_path, encoding='gbk')
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    @staticmethod
    def _parse_shift(value: str) -> ShiftType:
        mapping = {
            '早班': ShiftType.MORNING,
            '早上': ShiftType.MORNING,
            '白班': ShiftType.MORNING,
            '中班': ShiftType.AFTERNOON,
            '下午': ShiftType.AFTERNOON,
            '晚班': ShiftType.NIGHT,
            '夜班': ShiftType.NIGHT,
            '全天': ShiftType.ALL,
        }
        return mapping.get(str(value).strip(), ShiftType.ALL)

    @staticmethod
    def _parse_order_status(value: str) -> OrderStatus:
        mapping = {
            '待付款': OrderStatus.PENDING_PAYMENT,
            '未付款': OrderStatus.PENDING_PAYMENT,
            '待发货': OrderStatus.PENDING_SHIPMENT,
            '未发货': OrderStatus.PENDING_SHIPMENT,
            '已发货': OrderStatus.SHIPPED,
            '发货中': OrderStatus.SHIPPED,
            '已完成': OrderStatus.COMPLETED,
            '完成': OrderStatus.COMPLETED,
            '交易成功': OrderStatus.COMPLETED,
            '退款中': OrderStatus.REFUNDING,
            '退货中': OrderStatus.REFUNDING,
            '已退款': OrderStatus.REFUNDED,
            '已退货': OrderStatus.REFUNDED,
            '已取消': OrderStatus.CANCELED,
            '取消': OrderStatus.CANCELED,
        }
        return mapping.get(str(value).strip(), OrderStatus.COMPLETED)

    @staticmethod
    def import_agents(file_path: str) -> Tuple[List[Agent], List[str]]:
        errors = []
        agents = []
        df = ImportService._read_file(file_path)

        required_cols = ['客服ID', '客服姓名', '店铺', '班次']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {', '.join(missing)}")

        for idx, row in df.iterrows():
            try:
                agent = Agent(
                    agent_id=str(row['客服ID']).strip(),
                    name=str(row['客服姓名']).strip(),
                    shop=str(row['店铺']).strip(),
                    shift=ImportService._parse_shift(str(row.get('班次', '全天'))),
                    group=str(row.get('组别', '')).strip(),
                    join_date=str(row.get('入职日期', '')).strip() if pd.notna(row.get('入职日期')) else None,
                    is_active=bool(row.get('是否在职', True))
                )
                if not agent.agent_id or not agent.name:
                    errors.append(f"第{idx + 2}行: 客服ID或姓名为空")
                    continue
                agents.append(agent)
            except Exception as e:
                errors.append(f"第{idx + 2}行: {str(e)}")

        return agents, errors

    @staticmethod
    def import_conversations(file_path: str) -> Tuple[List[Conversation], List[str]]:
        errors = []
        conversations = []
        df = ImportService._read_file(file_path)

        conv_col = None
        for candidate in ['会话ID', '会话编号', 'conversation_id', 'conv_id']:
            if candidate in df.columns:
                conv_col = candidate
                break
        if conv_col is None:
            raise ValueError("缺少会话ID列")

        agent_id_col = None
        for candidate in ['客服ID', '客服编号', 'agent_id']:
            if candidate in df.columns:
                agent_id_col = candidate
                break
        if agent_id_col is None:
            raise ValueError("缺少客服ID列")

        agent_name_col = None
        for candidate in ['客服姓名', '客服', 'agent_name']:
            if candidate in df.columns:
                agent_name_col = candidate
                break

        content_cols = []
        for candidate in ['消息内容', '内容', '消息', 'content', 'message']:
            if candidate in df.columns:
                content_cols.append(candidate)
        if not content_cols:
            raise ValueError("缺少消息内容列")

        time_col = None
        for candidate in ['消息时间', '时间', '发送时间', 'timestamp', 'time']:
            if candidate in df.columns:
                time_col = candidate
                break

        sender_col = None
        for candidate in ['发送者', '发送人', 'sender', '角色']:
            if candidate in df.columns:
                sender_col = candidate
                break

        conv_groups = df.groupby(conv_col)
        for conv_id, group in conv_groups:
            try:
                first_row = group.iloc[0]
                shop = str(first_row.get('店铺', '')).strip()
                shift = ImportService._parse_shift(str(first_row.get('班次', '全天')))
                order_status = ImportService._parse_order_status(str(first_row.get('订单状态', '已完成')))
                order_id = str(first_row.get('订单号', '')).strip() if pd.notna(first_row.get('订单号')) else ""
                customer_nick = str(first_row.get('客户昵称', '')).strip() if pd.notna(first_row.get('客户昵称')) else ""
                agent_id = str(first_row[agent_id_col]).strip()
                agent_name = str(first_row[agent_name_col]).strip() if agent_name_col else agent_id

                messages = []
                times = []
                for _, msg_row in group.iterrows():
                    content_parts = [str(msg_row[col]).strip() for col in content_cols if pd.notna(msg_row.get(col))]
                    content = "\n".join([p for p in content_parts if p])
                    if not content:
                        continue

                    ts = None
                    if time_col and pd.notna(msg_row.get(time_col)):
                        try:
                            ts = pd.to_datetime(msg_row[time_col]).to_pydatetime()
                        except Exception:
                            ts = datetime.now()
                    if ts is None:
                        ts = datetime.now()
                    times.append(ts)

                    sender_type = str(msg_row.get(sender_col, '客服')).strip() if sender_col else '客服'
                    is_customer = any(k in sender_type for k in ['客户', '顾客', '买家', 'customer', 'user'])

                    sender = str(msg_row.get(sender_col, agent_name)).strip() if sender_col else agent_name

                    messages.append(Message(
                        timestamp=ts,
                        sender=sender,
                        sender_type=sender_type,
                        content=content,
                        is_customer=is_customer
                    ))

                messages.sort(key=lambda m: m.timestamp)
                start_time = messages[0].timestamp if messages else None
                end_time = messages[-1].timestamp if messages else None

                conv = Conversation(
                    conv_id=str(conv_id),
                    agent_id=agent_id,
                    agent_name=agent_name,
                    shop=shop,
                    shift=shift,
                    order_status=order_status,
                    order_id=order_id,
                    customer_nick=customer_nick,
                    start_time=start_time,
                    end_time=end_time,
                    messages=messages
                )
                conversations.append(conv)
            except Exception as e:
                errors.append(f"会话{conv_id}: {str(e)}")

        return conversations, errors
