# ==================== 导入依赖 ====================
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import re
import json
from typing import Any
from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth, Message, ChatEventType
from cozepy.exception import CozeAPIError

# ==================== Flask 应用初始化 ====================
# 创建 Flask 应用实例，指定静态文件目录为前端构建产物目录
app = Flask(__name__, static_folder='front-end/dist', static_url_path='')
# 启用跨域资源共享（CORS），允许前端跨域访问后端 API
CORS(app)

# ==================== Coze AI 智能体配置 ====================
# Coze API 基础 URL（中国区）
coze_api_base = COZE_CN_BASE_URL
# Coze API 访问令牌，用于身份验证
coze_api_token = os.environ.get('COZE_API_TOKEN',
                                'pat_Ay5MQdVJ3ZRP9q7l3YoHHb4jlTjbEhNks5cP9hatMMCkUGgzq1JeoDKPnFDz5ky9')
# SCB18-200kVA 变压器智能体 ID
coze_bot_id_100kw = os.environ.get('COZE_BOT_ID_100KW', '7594731318777397284')
# SCB14-630kVA 变压器智能体 ID
coze_bot_id_500kw = os.environ.get('COZE_BOT_ID_500KW', '7599587749351931914')
# 开关调度智能体 ID
coze_bot_id_switch = os.environ.get('COZE_BOT_ID_SWITCH', '7599882439477592115')
# 规划建议智能体 ID
coze_bot_id_advice = os.environ.get('COZE_BOT_ID_ADVICE', '7615261656637227014')
# 用户 ID，用于 Coze API 调用标识
coze_user_id = os.environ.get('COZE_USER_ID', '123456789')

# 初始化 Coze 客户端
coze_client = None
if coze_api_token:
    coze_client = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)


class TransformerCalculator:
    """
    本地变压器参数计算类
    
    用于计算变压器的损耗功率等参数，替代智能体调用以提高响应速度。
    计算公式：
    - 负载系数 β = 当前输出功率 / 额定功率
    - 负载损耗 P_k = β² × 额定负载损耗
    - 总损耗 P_总 = 空载损耗 + 负载损耗
    """

    # 变压器标准参数配置
    # 包含不同容量变压器的标准损耗参数
    # 损耗计算公式：
    # - 空载损耗 P₀ = 定值（与负载无关）
    # - 负载损耗 Pₖ = β² × Pₖₙ（β为负载率）
    # - 总损耗 P总 = P₀ + Pₖ
    CONFIGS = {
        200: {
            'max_power_kw': 200.0,  # 额定容量 (kVA) - SCB18-200kVA 一级能效
            'no_load_loss_kw': 0.32,  # 空载损耗 P₀ (kW)
            'full_load_loss_kw': 1.80,  # 额定负载损耗 Pₖₙ (kW)
        },
        630: {
            'max_power_kw': 630.0,  # 额定容量 (kVA) - SCB14-630kVA 二级能效
            'no_load_loss_kw': 0.92,  # 空载损耗 P₀ (kW)
            'full_load_loss_kw': 5.80,  # 额定负载损耗 Pₖₙ (kW)
        },
    }

    @classmethod
    def get_config(cls, max_power_kw):
        """
        根据最大功率获取最接近的配置
        
        Args:
            max_power_kw: 变压器的额定最大功率 (kVA)
            
        Returns:
            dict: 包含 max_power_kw, no_load_loss_kw, full_load_loss_kw 的配置字典
        """
        if max_power_kw >= 400:
            return cls.CONFIGS[630]
        return cls.CONFIGS[200]

    @classmethod
    def calculate(cls, max_power_kw, current_power_kw):
        """
        计算变压器参数
        
        根据变压器的额定功率和当前输出功率，计算损耗功率等参数。
        
        Args:
            max_power_kw: 变压器的额定最大功率 (kVA)
            current_power_kw: 当前输出功率 (kVA)
            
        Returns:
            tuple: (max_power_kw, loss_power_kw, no_load_loss_kw, full_load_loss_kw, answer_text)
            - max_power_kw: 额定最大功率
            - loss_power_kw: 总损耗功率
            - no_load_loss_kw: 空载损耗
            - full_load_loss_kw: 额定负载损耗
            - answer_text: 人类可读的计算结果描述

        注意：当输出功率为0时，变压器可关机，不产生损耗功率
        """
        config = cls.get_config(max_power_kw)

        p_n = float(max_power_kw) if max_power_kw else config['max_power_kw']
        p_0 = config['no_load_loss_kw']
        p_kn = config['full_load_loss_kw']
        # 功率因数固定为 0.8
        cos_phi = 0.8

        current_p = float(current_power_kw) if current_power_kw else 0.0

        if current_p <= 0:
            total_loss_kw = 0.0
            answer = f"铭牌容量：{p_n:.0f}kVA | 状态：关机（无损耗） | 当前功率：0kW"
            return p_n, total_loss_kw, p_0, p_kn, answer, 0.0, 0.0

        # 视在功率 S = P / cosφ
        apparent_power_kva = current_p / cos_phi if cos_phi > 0 else 0.0

        # 负载率 β = S / S_额定
        beta = apparent_power_kva / p_n if p_n > 0 else 0.0

        # 负载损耗 Pₖ = β² × Pₖₙ
        load_loss_kw = beta * beta * p_kn

        # 总损耗 P总 = P₀ + Pₖ
        total_loss_kw = p_0 + load_loss_kw

        answer = (
            f"铭牌容量：{p_n:.0f}kVA | "
            f"当前功率：{current_p:.1f}kW | "
            f"视在功率：{apparent_power_kva:.1f}kVA | "
            f"负载系数β：{beta:.2f} | "
            f"空载损耗P₀：{p_0:.2f}kW | "
            f"负载损耗Pₖ：{load_loss_kw:.3f}kW | "
            f"总损耗：{total_loss_kw:.3f}kW"
        )

        return p_n, total_loss_kw, p_0, p_kn, answer, apparent_power_kva, beta


class Transformer:
    """
    变压器类

    表示电力系统中的变压器设备，负责电压转换和电能传输。

    属性说明：
    - max_power_kw: 铭牌容量 (kVA)
    - max_active_power_kw: 最大有功功率 (kW) = 铭牌容量 × 0.8
    - current_power_kw: 当前功率 (kW)
    - loss_power_kw: 损耗功率 (kW)
    """

    def __init__(self, id_, name, max_power_kw, loss_power_kw, current_power_kw, max_active_power_kw=None):
        """
        初始化变压器实例

        Args:
            id_: 变压器唯一标识符
            name: 变压器名称
            max_power_kw: 铭牌容量 (kVA)
            loss_power_kw: 损耗功率 (kW)
            current_power_kw: 当前功率 (kW)
            max_active_power_kw: 最大有功功率 (kW)，默认为 max_power_kw × 0.8
        """
        self.id = id_
        self.name = name
        self.max_power_kw = max_power_kw
        self.loss_power_kw = loss_power_kw
        self.current_power_kw = current_power_kw
        # 最大有功功率 = 铭牌容量 × 0.8
        self.max_active_power_kw = max_active_power_kw if max_active_power_kw is not None else (max_power_kw * 0.8 if max_power_kw else 0)
        # 空载损耗 (kW)
        self.no_load_loss_kw = 0.0
        # 额定负载损耗 (kW)
        self.full_load_loss_kw = 0.0
        # 功率因数（固定 0.8，不保存到类属性）
        self._power_factor = 0.8


# ==================== 时间片配置 ====================
# 时间标签（对应前端 TIME_LABELS）
# 用于模拟一天中不同时段的负荷变化
TIME_LABELS = ['0:00', '4:00', '8:00', '12:00', '16:00', '20:00']

# 全局时间片计数器（0-5，对应6个时间点）
current_time_slice = 0


class User:
    """
    用户类
    
    表示电力系统中的用电用户，包含用户的用电需求和负荷曲线。
    """

    def __init__(self, id_, name, demand_power, user_type='residential', load_profile=None):
        """
        初始化用户实例
        
        Args:
            id_: 用户唯一标识符
            name: 用户名称
            demand_power: 需求功率 (kVA)
            user_type: 用户类型（residential-居民, commercial-商业, industrial-工业）
            load_profile: 负荷曲线，6个时间点的实际功率值列表
        """
        self.id = id_
        self.name = name
        self.user_type = user_type
        # 负荷曲线：6个时间点的实际功率值（由前端传递）
        self.load_profile = load_profile if load_profile and isinstance(load_profile, list) and len(
            load_profile) == 6 else [demand_power] * 6
        # 当前实际需求功率
        self.demand_power = self.load_profile[0] if self.load_profile else demand_power

    def get_power_at_time(self, time_index):
        """
        获取指定时间点的功率值

        Args:
            time_index: 时间片索引（0-5），对应 6个时间点
            
        Returns:
            float: 该时间点的功率值 (kVA)
        """
        idx = time_index % len(self.load_profile) if self.load_profile else 0
        return self.load_profile[idx] if self.load_profile else self.demand_power

    def to_dict(self):
        """
        转换为字典格式
        
        用于 JSON 序列化，返回给前端。
        """
        return {
            'id': self.id,
            'name': self.name,
            'type': 'user',
            'demandPowerKw': self.demand_power,
            'userType': self.user_type,
            'loadProfile': self.load_profile,
        }


class Switch:
    """
    开关类
    
    表示电力系统中的开关设备，用于控制电路的通断和电能分配。
    """
    
    def __init__(self, id_, name, config=None):
        """
        初始化开关实例
        
        Args:
            id_: 开关唯一标识符
            name: 开关名称
            config: 开关配置，记录连接的变压器及其启用状态
        """
        self.id = id_
        self.name = name
        # 配置字典：{变压器ID: 是否启用}
        self.config = config or {}


# ==================== 时间片管理函数 ====================

def update_user_load_factors():
    """
    根据当前时间片更新所有用户的实际需求功率
    
    在调度过程中，当时间片变化时调用此函数，
    将每个用户的需求功率更新为其负荷曲线上对应时间点的值。
    """
    global current_time_slice
    for user in users.values():
        user.demand_power = user.get_power_at_time(current_time_slice)


class Wire:
    """
    导线类
    
    表示电力系统中连接各组件的导线，传输电能。
    """
    
    def __init__(self, id_, name, power, status, from_component, to_component):
        """
        初始化导线实例
        
        Args:
            id_: 导线唯一标识符
            name: 导线名称
            power: 传输功率 (kVA)
            status: 导线状态（normal-正常, warning-警告, error-错误, offline-离线）
            from_component: 起始组件 ID
            to_component: 目标组件 ID
        """
        self.id = id_
        self.name = name
        self.power = power
        self.status = status
        self.from_component = from_component
        self.to_component = to_component


# ==================== 全局状态存储 ====================
# 变压器字典：{ID: Transformer实例}
transformers = {}
# 用户字典：{ID: User实例}
users = {}
# 开关字典：{ID: Switch实例}
switches = {}
# 导线字典：{ID: Wire实例}
wires = {}
# 下一个节点 ID（自增）
next_node_id = 1
# 下一条导线 ID（自增）
next_wire_id = 1

# 黑板：存储 AI 调度结果和中间状态
# 用于在调度过程中共享数据
blackboard: dict[str, Any] = {
    'ai_results': {
        'transformers': {},  # 变压器 AI 结果
        'users': {},         # 用户 AI 结果
        'switches': {},      # 开关 AI 结果
    },
    'dispatch': {},         # 调度状态
}


def set_ai_result(kind, entity_id, data):
    """
    设置 AI 结果到黑板
    
    Args:
        kind: 实体类型（transformers, users, switches）
        entity_id: 实体 ID
        data: AI 返回的结果数据
    """
    if 'ai_results' not in blackboard:
        blackboard['ai_results'] = {}
    if kind not in blackboard['ai_results']:
        blackboard['ai_results'][kind] = {}
    blackboard['ai_results'][kind][entity_id] = data


def get_ai_result(kind, entity_id):
    """
    从黑板获取 AI 结果
    
    Args:
        kind: 实体类型（transformers, users, switches）
        entity_id: 实体 ID
        
    Returns:
        dict: AI 结果数据，不存在则返回 None
    """
    return blackboard.get('ai_results', {}).get(kind, {}).get(entity_id)


def snapshot_network():
    """
    生成网络拓扑快照
    
    将当前网络中的所有组件状态序列化为字典格式，
    用于 AI 调度输入或结果返回。
    
    Returns:
        dict: 包含 transformers, users, switches, wires 的快照数据
    """
    return {
        'transformers': {
            tid: {
                'id': t.id,
                'name': t.name,
                'maxPowerKw': t.max_power_kw,
                'maxActivePowerKw': t.max_active_power_kw,
                'lossPowerKw': t.loss_power_kw,
                'currentPowerKw': t.current_power_kw,
                'recommendedPowerKw': getattr(t, 'recommended_power_kw', None),
            }
            for tid, t in transformers.items()
        },
        'users': {
            uid: u.to_dict() if hasattr(u, 'to_dict') else {
                'id': u.id,
                'name': u.name,
                'userType': getattr(u, 'user_type', 'residential'),
                'demandPowerKw': u.demand_power,
                'loadProfile': getattr(u, 'load_profile', []),
            }
            for uid, u in users.items()
        },
        'switches': {
            sid: {
                'id': s.id,
                'name': s.name,
                'config': s.config,
            }
            for sid, s in switches.items()
        },
        'wires': {
            wid: {
                'id': w.id,
                'name': w.name,
                'power': w.power,
                'status': w.status,
                'fromComponent': w.from_component,
                'toComponent': w.to_component,
            }
            for wid, w in wires.items()
        },
    }


def reset_all_state():
    """
    重置所有全局状态
    
    清空所有组件和导线，重置 ID 计数器和黑板。
    通常在用户清空画布或重新开始时调用。
    """
    global transformers, users, switches, wires, next_node_id, next_wire_id, blackboard, current_time_slice
    transformers = {}
    users = {}
    switches = {}
    wires = {}
    next_node_id = 1
    next_wire_id = 1
    current_time_slice = 0  # 重置时间片计数器
    blackboard = {
        'ai_results': {
            'transformers': {},
            'users': {},
            'switches': {},
        },
        'dispatch': {},
    }


def _safe_float(v, default=0.0):
    """
    安全转换为浮点数
    
    Args:
        v: 待转换的值
        default: 转换失败时的默认值
        
    Returns:
        float: 转换后的浮点数
    """
    try:
        x = float(v)
        # 检查是否为 NaN
        if x != x:
            return default
        return x
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=None):
    """
    安全转换为整数
    
    Args:
        v: 待转换的值
        default: 转换失败时的默认值
        
    Returns:
        int: 转换后的整数，失败返回 default
    """
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _estimate_transformer_loss_kw(transformer, active_power_kw, power_factor=0.8):
    """
    估算变压器损耗功率

    根据变压器的参数和有功功率，估算损耗功率。

    Args:
        transformer: 变压器实例
        active_power_kw: 有功功率 (kW)
        power_factor: 功率因数，默认 0.8

    Returns:
        float: 估算的损耗功率 (kW)
    """
    active_p = max(0.0, _safe_float(active_power_kw, 0.0))
    max_p = max(0.0, _safe_float(getattr(transformer, 'max_power_kw', 0.0), 0.0))
    no_load = _safe_float(getattr(transformer, 'no_load_loss_kw', 0.0), 0.0)
    full_load = _safe_float(getattr(transformer, 'full_load_loss_kw', 0.0), 0.0)
    cos_phi = _safe_float(power_factor, 0.8)

    if active_p <= 0 or max_p <= 0:
        return 0.0

    # 视在功率 S = P / cosφ
    apparent_power = active_p / cos_phi if cos_phi > 0 else 0.0

    # 负载率 β = S / S_额定
    beta = apparent_power / max_p

    # 总损耗 = 空载损耗 + β² × 额定负载损耗
    return no_load + (beta * beta) * full_load


def _get_switch_adjacent_ids(switch_id):
    """
    获取开关相邻的变压器和用户 ID
    
    通过遍历导线，找出与指定开关直接相连的变压器和用户。
    
    Args:
        switch_id: 开关 ID
        
    Returns:
        tuple: (变压器ID列表, 用户ID列表)
    """
    t_ids = set()
    u_ids = set()
    sw = switches.get(switch_id)
    sw_config = sw.config if sw else {}
    
    # 遍历所有导线，找出与开关相连的组件
    for w in wires.values():
        if w.from_component == switch_id:
            other = w.to_component
        elif w.to_component == switch_id:
            other = w.from_component
        else:
            continue

        # 确保 other 是整数类型进行比较
        try:
            other_int = int(other)
        except (TypeError, ValueError):
            continue

        if other_int in transformers:
            # 检查开关配置中是否启用了该变压器（兼容字符串和整数键）
            # 默认为 True，只有明确设置为 False 时才认为关闭
            enabled = sw_config.get(str(other_int), sw_config.get(other_int, True))
            if enabled:
                t_ids.add(other_int)
        if other_int in users:
            u_ids.add(other_int)
    return sorted(list(t_ids)), sorted(list(u_ids))


def _sanitize_switch_plan(switch_id, plan, remaining_demand_kw, remaining_transformer_kw, allocated_kw_by_transformer):
    """
    清理和验证开关调度计划
    
    对 AI 返回的调度计划进行验证和清理：
    1. 验证分配的变压器和用户是否与开关相连
    2. 确保分配功率不超过变压器剩余容量和用户剩余需求
    3. 计算实际的损耗功率
    
    Args:
        switch_id: 开关 ID
        plan: AI 返回的原始调度计划
        remaining_demand_kw: 用户剩余需求字典 {用户ID: 剩余需求}
        remaining_transformer_kw: 变压器剩余容量字典 {变压器ID: 剩余容量}
        allocated_kw_by_transformer: 变压器已分配功率字典 {变压器ID: 已分配功率}
        
    Returns:
        dict: 清理后的调度计划，包含 allocations, unservedUsers, totalLossKVA, comment
    """
    # 获取开关相邻的变压器和用户
    t_ids, u_ids = _get_switch_adjacent_ids(switch_id)
    t_set = set(t_ids)
    u_set = set(u_ids)

    # 提取 AI 返回的分配列表
    allocations_in = []
    if isinstance(plan, dict):
        a = plan.get('allocations')
        if isinstance(a, list):
            allocations_in = a

    sanitized = []
    total_loss_kw = 0.0

    # 遍历每个分配项，进行验证和清理
    for alloc in allocations_in:
        if not isinstance(alloc, dict):
            continue
        # 只处理变压器到用户的分配
        if alloc.get('fromType') != 'transformer' or alloc.get('toType') != 'user':
            continue
        tid = _safe_int(alloc.get('fromId'))
        uid = _safe_int(alloc.get('toId'))
        if tid is None or uid is None:
            continue
        # 验证变压器和用户是否与开关相连
        if tid not in t_set or uid not in u_set:
            continue

        req = _safe_float(alloc.get('powerKVA') or alloc.get('powerKw'), 0.0)
        if req <= 0:
            continue
        d_rem = _safe_float(remaining_demand_kw.get(uid), 0.0)
        t_rem = _safe_float(remaining_transformer_kw.get(tid), 0.0)

        # 实际分配功率应取: AI建议值、用户剩余需求、变压器剩余容量 三者中的最小值
        power = min(req, d_rem, t_rem)

        # 只有当确实能分配出功率时才进行后续操作
        if power > 0:
            # 更新剩余需求和容量
            remaining_demand_kw[uid] = d_rem - power
            remaining_transformer_kw[tid] = t_rem - power
            allocated_kw_by_transformer[tid] = _safe_float(allocated_kw_by_transformer.get(tid), 0.0) + power

            # 尝试计算 lossKVA，如果它是字符串表达式
            loss_kw_raw = alloc.get('lossKVA') or alloc.get('lossKw')
            loss_kw = 0.0
            if isinstance(loss_kw_raw, (int, float)):
                loss_kw = float(loss_kw_raw)
            elif isinstance(loss_kw_raw, str):
                try:
                    # 处理 JavaScript 表达式：parseFloat(...), Math.pow(...)
                    expr = loss_kw_raw
                    # 替换 Math.pow(x, y) 为 (x)**y
                    expr = re.sub(r'Math\.pow\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'(\1)**\2', expr)
                    # 替换 parseFloat(x) 为 float(x)
                    expr = re.sub(r'parseFloat\s*\(\s*([^)]+)\s*\)', r'float(\1)', expr)
                    # 替换 .toFixed(n) 为 round(x * 10**n) / 10**n
                    expr = re.sub(r'\.toFixed\s*\(\s*(\d+)\s*\)', r'', expr)
                    # 安全检查：仅允许数字和基本运算符
                    if re.match(r'^[0-9.+\-*/()\s]+$', expr):
                        loss_kw = float(eval(expr))
                except (ValueError, SyntaxError):
                    pass

            # 如果 AI 没有给出有效的 lossKVA，自己估算
            if loss_kw == 0.0 and power > 0:
                transformer = transformers.get(tid)
                if transformer:
                    loss_kw = _estimate_transformer_loss_kw(transformer, power, 0.8)

            total_loss_kw += loss_kw
            sanitized.append(
                {
                    'fromType': 'transformer',
                    'fromId': tid,
                    'toType': 'user',
                    'toId': uid,
                    'powerKVA': power,
                    'lossKVA': round(loss_kw, 2),
                }
            )

    # 找出未被供电的用户
    unserved = [uid for uid in u_ids if _safe_float(remaining_demand_kw.get(uid), 0.0) > 0]

    # 尝试重新计算 totalLossKVA 如果它是字符串表达式
    total_loss_kw_raw = plan.get('totalLossKVA') or plan.get('totalLossKw') if isinstance(plan, dict) else 0.0
    if isinstance(total_loss_kw_raw, str):
        try:
            if re.match(r'^[0-9.+\-*/()\s]+$', total_loss_kw_raw):
                total_loss_kw = float(eval(total_loss_kw_raw))
        except (ValueError, SyntaxError):
            pass
    elif isinstance(total_loss_kw_raw, (int, float)):
        pass

    return {
        'allocations': sanitized,
        'unservedUsers': unserved,
        'totalLossKVA': total_loss_kw,
        'comment': plan.get('comment') if isinstance(plan, dict) else '',
    }


def init_dispatch():
    """
    初始化调度流程
    
    在开始 AI 调度前，初始化所有必要的状态：
    1. 重置时间片为 0（首次调度）
    2. 更新用户的负荷系数
    3. 初始化变压器的损耗参数
    4. 初始化调度中间状态
    
    Returns:
        dict: 包含 switches（待调度的开关ID列表）和 currentTimeSlice（当前时间片）
    """
    global current_time_slice

    # 如果是首次调度，初始化时间片为 0
    if 'dispatch_state' not in blackboard:
        current_time_slice = 0

    # 根据当前时间片更新所有用户的负荷系数和实际需求功率
    update_user_load_factors()

    # 生成网络快照
    snapshot = snapshot_network()
    ai_results = blackboard.setdefault('ai_results', {})
    ai_results['transformers'] = {}
    ai_results.setdefault('users', {})
    ai_results['switches'] = {}
    required_power = {}

    # 初始化每个变压器的参数
    for tid, transformer in transformers.items():
        # 重新初始化推荐功率等辅助参数
        max_power_kw = float(transformer.max_power_kw) if transformer.max_power_kw else 0.0
        config = TransformerCalculator.get_config(max_power_kw)
        transformer.no_load_loss_kw = config['no_load_loss_kw']
        transformer.full_load_loss_kw = config['full_load_loss_kw']

        set_ai_result(
            'transformers',
            tid,
            {
                'maxPowerKw': transformer.max_power_kw,
                'maxActivePowerKw': transformer.max_active_power_kw,
                'lossPowerKw': transformer.loss_power_kw,
                'currentPowerKw': transformer.current_power_kw,
                'noLoadLossKw': transformer.no_load_loss_kw,
                'fullLoadLossKw': transformer.full_load_loss_kw,
                'requiredPowerKw': 0.0,
            },
        )

    # 初始化调度中间状态
    remaining_demand_kw = {uid: _safe_float(u.demand_power, 0.0) for uid, u in users.items()}
    allocated_kw_by_transformer = {tid: 0.0 for tid in transformers.keys()}
    remaining_transformer_kw = {tid: max(0.0, _safe_float(t.max_power_kw, 0.0)) for tid, t in transformers.items()}

    # 保存调度中间状态到 blackboard
    blackboard['dispatch_state'] = {
        'snapshot': snapshot,
        'remaining_demand_kw': remaining_demand_kw,
        'allocated_kw_by_transformer': allocated_kw_by_transformer,
        'remaining_transformer_kw': remaining_transformer_kw,
        'required_power': required_power,
        'time_slice': current_time_slice,  # 保存当前时间片
    }

    return {
        'switches': sorted(list(switches.keys())),
        'currentTimeSlice': current_time_slice,
    }


def init_dispatch_continue():
    """
    继续调度初始化
    
    推进时间片，更新用户需求，重置分配状态。
    用于多时间片仿真调度。
    
    Returns:
        dict: 包含 switches, currentTimeSlice, users（更新后的用户数据）
    """
    global current_time_slice

    if 'dispatch_state' not in blackboard:
        return init_dispatch()

    # 推进时间片（0-5，对应6个时间点）
    current_time_slice = (current_time_slice + 1) % 6

    # 更新所有用户的实际需求功率
    update_user_load_factors()

    state = blackboard['dispatch_state']

    # 重置用户剩余需求
    remaining_demand_kw = {uid: _safe_float(u.demand_power, 0.0) for uid, u in users.items()}
    state['remaining_demand_kw'] = remaining_demand_kw

    # 重置变压器已分配功率
    allocated_kw_by_transformer = {tid: 0.0 for tid in transformers.keys()}
    state['allocated_kw_by_transformer'] = allocated_kw_by_transformer

    # 重置变压器剩余容量
    remaining_transformer_kw = {tid: max(0.0, _safe_float(t.max_power_kw, 0.0)) for tid, t in transformers.items()}
    state['remaining_transformer_kw'] = remaining_transformer_kw

    # 更新拓扑快照
    state['snapshot'] = snapshot_network()
    state['required_power'] = {}
    state['time_slice'] = current_time_slice

    # 重置开关 AI 结果
    if 'ai_results' not in blackboard:
        blackboard['ai_results'] = {}
    blackboard['ai_results']['switches'] = {}
    blackboard['planning_suggestions'] = None

    # 重新初始化变压器 AI 结果
    for tid, transformer in transformers.items():
        max_power_kw = float(transformer.max_power_kw) if transformer.max_power_kw else 0.0
        config = TransformerCalculator.get_config(max_power_kw)
        transformer.no_load_loss_kw = config['no_load_loss_kw']
        transformer.full_load_loss_kw = config['full_load_loss_kw']
        transformer.current_power_kw = 0.0

        set_ai_result(
            'transformers',
            tid,
            {
                'maxPowerKw': transformer.max_power_kw,
                'maxActivePowerKw': transformer.max_active_power_kw,
                'lossPowerKw': transformer.loss_power_kw,
                'currentPowerKw': 0.0,
                'noLoadLossKw': transformer.no_load_loss_kw,
                'fullLoadLossKw': transformer.full_load_loss_kw,
                'requiredPowerKw': 0.0,
            },
        )

    # 返回更新后的用户数据
    users_data = {uid: u.to_dict() if hasattr(u, 'to_dict') else {'demandPower': u.demand_power} for uid, u in
                  users.items()}

    return {
        'switches': sorted(list(switches.keys())),
        'currentTimeSlice': current_time_slice,
        'users': users_data,
    }


def dispatch_switch(sid, is_continue=False):
    """
    对单个开关进行调度
    
    调用 AI 智能体对指定开关进行电力分配调度，
    决定如何将变压器的电能分配给用户。
    
    Args:
        sid: 开关 ID
        is_continue: 是否是继续调度（如果是，会附加规划建议作为参考）
        
    Returns:
        dict: 包含 switchId 和 plan（调度计划）
    """
    if 'dispatch_state' not in blackboard:
        return {'error': 'Dispatch not initialized'}

    state = blackboard['dispatch_state']
    sw = switches.get(sid)
    if not sw:
        return {'error': f'Switch {sid} not found'}

    # 获取当前开关相邻的变压器和用户
    adjacent_t_ids, adjacent_u_ids = _get_switch_adjacent_ids(sid)

    # 只包含当前开关相邻用户和变压器的数据
    inbox = {
        'remainingDemandKw': {k: _safe_float(v, 0.0) for k, v in state['remaining_demand_kw'].items() if
                              k in adjacent_u_ids},
        'remainingTransformerKw': {k: _safe_float(v, 0.0) for k, v in state['remaining_transformer_kw'].items() if
                                   k in adjacent_t_ids},
        'allocatedKwByTransformer': {k: _safe_float(v, 0.0) for k, v in state['allocated_kw_by_transformer'].items() if
                                     k in adjacent_t_ids},
    }

    # 如果是继续调度，获取规划建议作为参考
    planning_suggestions = None
    if is_continue:
        cached_suggestions = blackboard.get('planning_suggestions')
        if cached_suggestions and isinstance(cached_suggestions, dict) and not cached_suggestions.get('error'):
            # 过滤出与当前开关相关的建议
            all_suggestions = cached_suggestions.get('suggestions', [])
            if not isinstance(all_suggestions, list):
                all_suggestions = []
            relevant_suggestions = []

            # 获取当前开关连接的变压器和用户
            adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)

            for suggestion in all_suggestions:
                if not isinstance(suggestion, dict):
                    continue
                details = suggestion.get('details', {})
                if not isinstance(details, dict):
                    details = {}
                # 检查建议是否与当前开关相关
                is_relevant = False

                # 检查是否涉及当前开关
                if details.get('switchId') == sid:
                    is_relevant = True

                # 检查是否涉及当前开关连接的变压器
                if details.get('transformerId') in adjacent_t:
                    is_relevant = True

                # 检查是否涉及当前开关连接的用户
                if details.get('userId') in adjacent_u:
                    is_relevant = True

                # 检查建议中的 bridgeSwitches 是否包含当前开关
                bridge_switches = details.get('bridgeSwitches', [])
                if isinstance(bridge_switches, list):
                    for bs in bridge_switches:
                        if isinstance(bs, dict) and bs.get('switchId') == sid:
                            is_relevant = True
                            break

                if is_relevant:
                    relevant_suggestions.append(suggestion)

            if relevant_suggestions:
                planning_suggestions = {
                    'allSuggestions': all_suggestions,
                    'relevantSuggestions': relevant_suggestions,
                    'summary': cached_suggestions.get('summary', {}),
                }

    # 调用 AI 获取调度参数
    text = get_switch_ai_params(sw, global_state=inbox, planning_suggestions=planning_suggestions)
    data = get_ai_result('switches', sid) or {}
    plan = data.get('plan')

    if not isinstance(plan, dict):
        plan = {'allocations': [], 'unservedUsers': [], 'totalLossKVA': 0.0, 'comment': ''}

    # 清理和验证调度计划
    sanitized_plan = _sanitize_switch_plan(
        sid,
        plan,
        state['remaining_demand_kw'],
        state['remaining_transformer_kw'],
        state['allocated_kw_by_transformer'],
    )

    # 保存调度结果到黑板
    set_ai_result(
        'switches',
        sid,
        {
            'input': data.get('input'),
            'answer': text or data.get('answer') or '',
            'plan': sanitized_plan,
            'inbox': inbox,
        },
    )

    return {
        'switchId': sid,
        'plan': sanitized_plan
    }


def finalize_dispatch():
    """
    完成调度，汇总结果
    
    在所有开关调度完成后，汇总最终结果：
    1. 计算每个变压器的实际输出功率
    2. 重新计算变压器损耗
    3. 生成最终的网络快照
    
    Returns:
        dict: 包含 snapshot, requiredPower, aiResults, currentTimeSlice
    """
    if 'dispatch_state' not in blackboard:
        return {'error': 'Dispatch not initialized'}

    state = blackboard['dispatch_state']
    ai_results = blackboard.get('ai_results', {})

    # 确保 required_power 存在
    if 'required_power' not in state:
        state['required_power'] = {}

    # 更新变压器的实际输出功率
    for tid, transformer in transformers.items():
        req = _safe_float(state['allocated_kw_by_transformer'].get(tid), 0.0)
        state['required_power'][tid] = req
        transformer.current_power_kw = req

    # 开关调度结束后，根据实际分配功率重新计算变压器参数
    for tid, transformer in transformers.items():
        req = _safe_float(state['allocated_kw_by_transformer'].get(tid), 0.0)
        # 重新计算变压器的损耗和answer
        # req 是当前功率 (kW)
        max_power_kw, loss_power_kw, no_load_loss_kw, full_load_loss_kw, answer, apparent_power_kva, beta = TransformerCalculator.calculate(
            transformer.max_power_kw,
            req
        )
        transformer.loss_power_kw = loss_power_kw
        transformer.no_load_loss_kw = no_load_loss_kw
        transformer.full_load_loss_kw = full_load_loss_kw
        transformer.current_power_kw = req

        # 确保 ai_results['transformers'] 存在
        if 'transformers' not in ai_results:
            ai_results['transformers'] = {}

        # 获取或创建变压器结果
        t_result = ai_results['transformers'].get(tid)
        if t_result is None:
            t_result = {
                'maxPowerKw': transformer.max_power_kw,
                'maxActivePowerKw': transformer.max_active_power_kw,
                'noLoadLossKw': no_load_loss_kw,
                'fullLoadLossKw': full_load_loss_kw,
            }
            ai_results['transformers'][tid] = t_result

        # 更新数据
        t_result['currentPowerKw'] = req
        t_result['requiredPowerKw'] = req
        t_result['lossPowerKw'] = loss_power_kw
        t_result['answer'] = answer

    # 确保 snapshot 存在
    snapshot = state.get('snapshot', {})

    # 递归将所有字典键转换为字符串，避免 JSON 序列化时类型不一致的问题
    def stringify_keys(obj):
        """将字典键转换为字符串"""
        if isinstance(obj, dict):
            return {str(k): stringify_keys(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [stringify_keys(item) for item in obj]
        else:
            return obj

    result = {
        'snapshot': stringify_keys(snapshot),
        'requiredPower': stringify_keys(state['required_power']),
        'aiResults': {
            'transformers': stringify_keys(ai_results.get('transformers', {})),
            'switches': stringify_keys(ai_results.get('switches', {})),
            'users': stringify_keys(ai_results.get('users', {}))
        },
        'currentTimeSlice': current_time_slice,
    }

    # 更新黑板中的最后一次调度结果
    blackboard['last_dispatch_result'] = result
    return result


def run_dispatch(is_continue=False):
    """
    运行完整调度流程
    
    依次执行初始化、开关调度、汇总结果的完整流程。
    
    Args:
        is_continue: 是否是继续调度
        
    Returns:
        dict: 调度结果
    """
    # 保留旧接口兼容性，内部调用新流程
    init_dispatch()
    for sid in sorted(list(switches.keys())):
        dispatch_switch(sid, is_continue=is_continue)
    result = finalize_dispatch()

    return result


def get_ai_response(bot_id, question):
    """
    调用 Coze AI 智能体获取响应
    
    通过流式调用 Coze API，获取智能体的文本响应。
    
    Args:
        bot_id: 智能体 ID
        question: 用户问题/提示词
        
    Returns:
        str: AI 返回的文本内容，失败返回 None
    """
    if coze_client is None or not bot_id:
        return None

    text = ''
    try:
        # 流式调用 Coze API
        for event in coze_client.chat.stream(
                bot_id=bot_id,
                user_id=coze_user_id,
                additional_messages=[
                    Message.build_user_question_text(question),
                ],
        ):
            # 接收消息增量
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                if event.message and event.message.content:
                    text += event.message.content
            # 对话完成
            if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                break
    except CozeAPIError:
        return None
    except Exception:
        return None

    return text if text else None


def build_switch_ai_input(switch):
    """
    构建开关 AI 调度的输入数据
    
    收集开关及其相连组件的信息，构建供 AI 分析的数据结构。
    
    Args:
        switch: 开关实例
        
    Returns:
        dict: 包含开关 ID、名称、输入/输出连接、目标等信息的字典
    """
    inputs = []   # 输入端组件（变压器、其他开关）
    outputs = []  # 输出端组件（用户、其他开关）
    
    # 遍历所有导线，找出与开关相连的组件
    for wire in wires.values():
        if wire.to_component == switch.id:
            # 导线终点是当前开关，说明是输入
            from_node, kind = _find_node(wire.from_component)
            if from_node is None:
                continue
            if kind == 'transformer':
                # 变压器参数由本地 TransformerCalculator 类计算
                inputs.append(
                    {
                        'type': 'transformer',
                        'id': from_node.id,
                        'name': from_node.name,
                        'wireId': wire.id,
                        'wireName': wire.name,
                        'wireStatus': wire.status,
                        'wirePowerKw': wire.power,
                        'maxPowerKw': from_node.max_power_kw,
                        'maxActivePowerKw': from_node.max_active_power_kw,
                        'lossPowerKw': from_node.loss_power_kw,
                        'currentPowerKw': from_node.current_power_kw,
                        'noLoadLossKw': from_node.no_load_loss_kw,
                        'fullLoadLossKw': from_node.full_load_loss_kw,
                    }
                )
            elif kind == 'switch':
                inputs.append(
                    {
                        'type': 'switch',
                        'id': from_node.id,
                        'name': from_node.name,
                        'wireId': wire.id,
                        'wireName': wire.name,
                        'wireStatus': wire.status,
                        'wirePowerKw': wire.power,
                    }
                )
        if wire.from_component == switch.id:
            # 导线起点是当前开关，说明是输出
            to_node, kind = _find_node(wire.to_component)
            if to_node is None:
                continue
            if kind == 'user':
                outputs.append(
                    {
                        'type': 'user',
                        'id': to_node.id,
                        'name': to_node.name,
                        'wireId': wire.id,
                        'wireName': wire.name,
                        'wireStatus': wire.status,
                        'wirePowerKw': wire.power,
                        'demandPowerKw': to_node.demand_power,
                    }
                )
            elif kind == 'switch':
                outputs.append(
                    {
                        'type': 'switch',
                        'id': to_node.id,
                        'name': to_node.name,
                        'wireId': wire.id,
                        'wireName': wire.name,
                        'wireStatus': wire.status,
                        'wirePowerKw': wire.power,
                    }
                )
    return {
        'switchId': switch.id,
        'switchName': switch.name,
        'inputs': inputs,
        'outputs': outputs,
        'adjacentTransformers': _get_switch_adjacent_ids(switch.id)[0],
        'adjacentUsers': _get_switch_adjacent_ids(switch.id)[1],
        'objective': '在保证用户获得充足电力的前提下最小化总损耗功率',
    }


def get_switch_ai_params(switch, global_state=None, planning_suggestions=None):
    """
    获取开关 AI 调度参数
    
    调用 AI 智能体获取开关的电力分配方案。
    
    Args:
        switch: 开关实例
        global_state: 全局状态（剩余需求、剩余容量等）
        planning_suggestions: 规划建议（用于参考）
        
    Returns:
        str: AI 返回的原始文本响应
    """
    bot_id = coze_bot_id_switch
    if not bot_id:
        return None

    # 构建输入数据
    payload = build_switch_ai_input(switch)
    if global_state is not None:
        payload['globalState'] = global_state
    if planning_suggestions is not None:
        payload['planningSuggestions'] = planning_suggestions

    # 只传递数据，智能体的提示词已在 Coze 平台配置
    question = json.dumps(payload, ensure_ascii=False, indent=2)

    # 调用 AI 获取响应
    text = get_ai_response(bot_id, question)

    if text is None:
        return None

    # 解析 AI 返回的 JSON
    try:
        cleaned_text = re.sub(r'```json\s*|\s*```', '', text).strip()

        # 处理多个 JSON 块的情况：只取最后一个完整的 JSON
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', text)
        if json_blocks:
            # 使用最后一个 JSON 块
            cleaned_text = json_blocks[-1].strip()
        else:
            # 如果没有代码块标记，尝试提取 JSON
            start = cleaned_text.find('{')
            end = cleaned_text.rfind('}')
            if start >= 0 < end > start:
                cleaned_text = cleaned_text[start:end + 1]

        # 替换 JavaScript 函数调用
        def _replace_js_call(src, name):
            """替换 JavaScript 函数调用为 0.0"""
            token = name + '('
            while True:
                idx = src.find(token)
                if idx < 0:
                    return src
                i = idx + len(token)
                depth = 1
                while i < len(src) and depth > 0:
                    ch = src[i]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                    i += 1
                if depth != 0:
                    return src
                src = src[:idx] + '0.0' + src[i:]

        fixed_text = cleaned_text
        fixed_text = _replace_js_call(fixed_text, 'parseFloat')
        fixed_text = _replace_js_call(fixed_text, 'Math.pow')
        fixed_text = fixed_text.replace('NaN', '0.0').replace('Infinity', '0.0')

        # 移除 JSON 中的尾随逗号（AI 经常输出这种无效 JSON）
        fixed_text = re.sub(r',\s*([}\]])', r'\1', fixed_text)

        # 处理 JSON 中的算术表达式
        def _eval_arithmetic_expr(match):
            """计算算术表达式"""
            expr = match.group(1).strip()
            try:
                # 安全检查：仅允许数字、运算符和括号
                if re.match(r'^[\d\s.+\-*/()]+$', expr):
                    result = eval(expr)
                    return str(round(result, 4))
            except (ValueError, SyntaxError):
                pass
            return match.group(0)

        fixed_text = re.sub(
            r':\s*([\d.\s+\-*/()]+)(?=[,}\]])',
            lambda m: ': ' + _eval_arithmetic_expr(m),
            fixed_text
        )

        plan = json.loads(fixed_text)

    except (json.JSONDecodeError, ValueError, Exception):
        plan = None

    # 保存 AI 结果到黑板
    set_ai_result(
        'switches',
        switch.id,
        {
            'input': payload,
            'answer': text,
            'plan': plan,
        },
    )
    return text


# ==================== API 路由定义 ====================

@app.route('/api/nodes', methods=['POST'])
def create_node():
    """
    创建节点 API
    
    创建变压器、用户或开关节点。
    
    请求体:
        - type: 节点类型（transformer, user, switch）
        - name: 节点名称
        - maxPowerKw: 变压器最大功率（仅变压器，单位kVA）
        - demandPower: 用户需求功率（仅用户）
        - userType: 用户类型（仅用户）
        - loadProfile: 负荷曲线（仅用户）
        - config: 开关配置（仅开关）
        
    返回:
        - id: 创建的节点 ID
        - type: 节点类型
    """
    global next_node_id
    data = request.get_json() or {}
    node_type = data.get('type')
    name = data.get('name') or ''
    node_id = next_node_id
    next_node_id += 1
    
    if node_type == 'transformer':
        # 创建变压器
        max_power_kw = data.get('maxPowerKw', 0)
        loss_power_kw = data.get('lossPowerKw', 0)
        current_power_kw = data.get('currentPowerKw', 0)
        active_power_kw = data.get('maxActivePowerKw', max_power_kw * 0.8 if max_power_kw else 0)
        node = Transformer(node_id, name, max_power_kw, loss_power_kw, current_power_kw, active_power_kw)
        transformers[node_id] = node
    elif node_type == 'user':
        # 创建用户
        demand_power = data.get('demandPower', 0)
        user_type = data.get('userType', 'residential')
        load_profile = data.get('loadProfile')  # 可选，前端传入 6 个时间点的实际功率值

        # 创建用户时传入 user_type 和 load_profile
        node = User(node_id, name, demand_power, user_type, load_profile)
        users[node_id] = node

        # 返回完整的用户信息
        return jsonify({
            'id': node_id,
            'type': node_type,
            'userType': user_type,
            'loadProfile': node.load_profile,
        })
    elif node_type == 'switch':
        # 创建开关
        config = data.get('config') or {}
        node = Switch(node_id, name, config)
        switches[node_id] = node
    else:
        return jsonify({'error': 'invalid type'}), 400
    return jsonify({'id': node_id, 'type': node_type})


@app.route('/api/wires', methods=['POST'])
def create_wire():
    """
    创建导线 API
    
    创建连接两个组件的导线。
    
    请求体:
        - name: 导线名称
        - power: 传输功率
        - status: 导线状态
        - fromComponent: 起始组件 ID
        - toComponent: 目标组件 ID
        
    返回:
        - id: 创建的导线 ID
    """
    global next_wire_id
    data = request.get_json() or {}
    name = data.get('name') or ''
    power = data.get('power', 0)
    status = data.get('status', 'normal')
    # 确保组件 ID 是整数类型
    from_component = int(data.get('fromComponent', 0))
    to_component = int(data.get('toComponent', 0))
    wire_id = next_wire_id
    next_wire_id += 1
    wire = Wire(wire_id, name, power, status, from_component, to_component)
    wires[wire_id] = wire

    # 当导线连接开关和变压器时，自动在开关的 config 中启用该变压器
    switch_node = None
    transformer_id = None
    if from_component in switches and to_component in transformers:
        switch_node = switches[from_component]
        transformer_id = to_component
    elif to_component in switches and from_component in transformers:
        switch_node = switches[to_component]
        transformer_id = from_component

    if switch_node is not None and transformer_id is not None:
        # 自动启用变压器
        switch_node.config[str(transformer_id)] = True

    return jsonify({'id': wire_id})


def _find_node(node_id):
    """
    查找节点
    
    根据节点 ID 在全局字典中查找对应的节点实例。
    
    Args:
        node_id: 节点 ID
        
    Returns:
        tuple: (节点实例, 节点类型) 或 (None, None)
    """
    if node_id in transformers:
        return transformers[node_id], 'transformer'
    if node_id in users:
        return users[node_id], 'user'
    if node_id in switches:
        return switches[node_id], 'switch'
    return None, None


@app.route('/api/nodes/<int:node_id>', methods=['PUT', 'PATCH', 'DELETE'])
def node_detail(node_id):
    """
    节点详情 API

    获取、更新或删除指定节点。

    - GET: 获取节点信息
    - PUT/PATCH: 更新节点信息
    - DELETE: 删除节点（幂等：不存在时也返回成功）
    """
    node, kind = _find_node(node_id)

    if request.method == 'DELETE':
        # 幂等删除：资源不存在时也返回成功
        if node is not None:
            # 删除节点及其相关导线
            if kind == 'transformer':
                del transformers[node_id]
            elif kind == 'user':
                del users[node_id]
            elif kind == 'switch':
                del switches[node_id]
            # 删除与该节点相关的所有导线
            remove_wire_ids = [wid for wid, w in wires.items()
                               if w.from_component == node_id or w.to_component == node_id]
            for wid in remove_wire_ids:
                del wires[wid]
        return jsonify({'status': 'deleted'})

    # PUT/PATCH: 更新节点信息
    if node is None:
        return jsonify({'error': 'node not found'}), 404
    data = request.get_json() or {}
    if 'name' in data:
        node.name = data['name']
    if kind == 'transformer':
        if 'maxPowerKw' in data:
            node.max_power_kw = data['maxPowerKw']
        if 'maxActivePowerKw' in data:
            node.max_active_power_kw = data['maxActivePowerKw']
        if 'lossPowerKw' in data:
            node.loss_power_kw = data['lossPowerKw']
        if 'currentPowerKw' in data:
            node.current_power_kw = data['currentPowerKw']
    elif kind == 'user':
        if 'demandPower' in data:
            node.demand_power = data['demandPower']
        if 'userType' in data:
            node.user_type = data['userType']
        if 'loadProfile' in data and isinstance(data['loadProfile'], list) and len(data['loadProfile']) == 6:
            node.load_profile = data['loadProfile']
            node.demand_power = node.load_profile[current_time_slice] if node.load_profile else node.demand_power
        return jsonify({
            'status': 'updated',
            'user': node.to_dict()
        })
    elif kind == 'switch':
        if 'config' in data:
            node.config = data['config']
    return jsonify({'status': 'updated'})


@app.route('/api/wires/<int:wire_id>', methods=['PATCH', 'DELETE'])
def wire_detail(wire_id):
    """
    导线详情 API

    更新或删除指定导线。

    - PATCH: 更新导线信息
    - DELETE: 删除导线（幂等：不存在时也返回成功）
    """
    wire = wires.get(wire_id)

    if request.method == 'DELETE':
        # 幂等删除：资源不存在时也返回成功
        if wire is not None:
            del wires[wire_id]
        return jsonify({'status': 'deleted'})

    # PATCH: 更新导线信息
    if wire is None:
        return jsonify({'error': 'wire not found'}), 404
    data = request.get_json() or {}
    if 'name' in data:
        wire.name = data['name']
    if 'power' in data:
        wire.power = data['power']
    if 'status' in data:
        wire.status = data['status']
    return jsonify({'status': 'updated'})


@app.route('/api/ai-dispatch', methods=['GET', 'POST'])
def ai_dispatch():
    """
    AI 调度 API
    
    - GET: 获取最后一次调度结果
    - POST: 执行完整调度流程
    """
    if request.method == 'GET':
        last = blackboard.get('last_dispatch_result')
        if not last:
            return jsonify({'error': 'no result'}), 404
        return jsonify(last)

    # POST 请求保留原有的全局调度接口，用于兼容
    result = run_dispatch()
    return jsonify(result)


@app.route('/api/dispatch/init', methods=['POST'])
def api_dispatch_init():
    """初始化调度流程 API"""
    result = init_dispatch()
    return jsonify(result)


@app.route('/api/dispatch/continue', methods=['POST'])
def api_dispatch_continue():
    """继续调度流程 API（推进时间片）"""
    result = init_dispatch_continue()
    return jsonify(result)


@app.route('/api/dispatch/switch/<int:switch_id>', methods=['POST'])
def api_dispatch_switch(switch_id):
    """
    单开关调度 API
    
    对指定开关进行电力分配调度。
    
    请求体参数:
        is_continue: 是否是继续调度（可选，默认为 false）
    """
    data = request.get_json() or {}
    is_continue = data.get('is_continue', False)
    result = dispatch_switch(switch_id, is_continue=is_continue)
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/dispatch/finalize', methods=['POST'])
def api_dispatch_finalize():
    """完成调度并返回最终结果 API"""
    result = finalize_dispatch()
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/switches/<int:node_id>/ai-plan', methods=['POST'])
def switch_ai_plan(node_id):
    """
    开关 AI 计划 API
    
    获取指定开关的 AI 调度计划。
    """
    node, kind = _find_node(node_id)
    if node is None or kind != 'switch':
        return jsonify({'error': 'switch not found'}), 404
    text = get_switch_ai_params(node)
    if text is None:
        return jsonify({'error': 'ai_failed'}), 500
    data = get_ai_result('switches', node_id)
    if data is None:
        data = {'answer': text}
    return jsonify(data)


@app.route('/api/blackboard', methods=['GET'])
def blackboard_all():
    """获取黑板中所有 AI 结果 API"""
    return jsonify(blackboard.get('ai_results', {}))


# ==================== 规划建议系统（基于 Coze 智能体） ====================

def build_network_topology():
    """构建网络拓扑数据，用于规划建议智能体"""
    # 构建变压器数据
    transformer_list = []
    for tid, t in transformers.items():
        max_p = _safe_float(t.max_power_kw, 0.0)  # 铭牌容量 (kVA)
        max_active_p = _safe_float(t.max_active_power_kw, 0.0)  # 最大有功功率 (kW)
        current_p = _safe_float(t.current_power_kw, 0.0)  # 当前输出功率 (kW)
        # 剩余容量 = 最大有功功率 - 当前功率 (单位: kW)
        remaining = max(0.0, max_active_p - current_p)
        # 负载率 = 当前功率 / 最大有功功率 (百分比)
        utilization_rate = (current_p / max_active_p * 100) if max_active_p > 0 else 0.0

        transformer_list.append({
            'id': tid,
            'name': t.name,
            'maxPowerKw': max_p,  # 铭牌容量 (kVA)
            'currentPowerKw': current_p,  # 当前输出功率 (kW)
            'remainingCapacityKw': remaining,  # 剩余容量 (kW)
            'utilizationRate': round(utilization_rate, 2),  # 负载率 (百分比)
        })

    # 构建用户数据
    user_list = []
    for uid, u in users.items():
        demand = _safe_float(u.demand_power, 0.0)
        # 从调度结果中获取实际供电量
        served = 0.0
        if 'dispatch_state' in blackboard:
            for sid, sw_result in blackboard.get('ai_results', {}).get('switches', {}).items():
                plan = sw_result.get('plan', {})
                for alloc in plan.get('allocations', []):
                    if alloc.get('toId') == uid:
                        served += _safe_float(alloc.get('powerKVA') or alloc.get('powerKw'), 0.0)

        unserved = max(0.0, demand - served)

        user_list.append({
            'id': uid,
            'name': u.name,
            'demandPowerKw': demand,
            'servedPowerKw': served,
            'unservedPowerKw': unserved,
        })

    # 构建开关数据
    switch_list = []
    for sid, s in switches.items():
        adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)
        switch_list.append({
            'id': sid,
            'name': s.name,
            'connectedTransformers': adjacent_t,
            'connectedUsers': adjacent_u,
        })

    # 构建连线数据
    wire_list = []
    for wid, w in wires.items():
        from_node, from_kind = _find_node(w.from_component)
        to_node, to_kind = _find_node(w.to_component)

        wire_list.append({
            'id': wid,
            'fromComponent': w.from_component,
            'toComponent': w.to_component,
            'fromType': from_kind,
            'toType': to_kind,
        })

    # 返回符合规划建议智能体格式的数据
    return {
        'transformers': transformer_list,
        'users': user_list,
        'switches': switch_list,
        'wires': wire_list,
    }


def get_planning_advice_from_ai():
    """调用 Coze 智能体获取规划建议"""
    if not coze_bot_id_advice:
        return {'error': '规划建议智能体未配置', 'suggestions': [], 'summary': {}}

    # 构建网络拓扑数据
    network_data = build_network_topology()

    # 只传递数据，智能体的提示词已在 Coze 平台配置
    question = json.dumps(network_data, ensure_ascii=False, indent=2)

    # 调用 Coze API
    text = get_ai_response(coze_bot_id_advice, question)
    if not text:
        return {
            'error': '智能体未返回结果',
            'suggestions': [],
            'summary': {
                'systemStatus': 'unknown',
                'totalSuggestions': 0,
                'highPriorityCount': 0,
                'mediumPriorityCount': 0,
                'lowPriorityCount': 0,
                'overallComment': '无法获取规划建议'
            },
            'networkAnalysis': network_data
        }

    # 解析返回结果
    try:
        # 清理返回文本
        cleaned_text = re.sub(r'```json\s*|\s*```', '', text).strip()
        start = cleaned_text.find('{')
        end = cleaned_text.rfind('}')
        if start >= 0 < end > start:
            cleaned_text = cleaned_text[start:end + 1]

        # 移除 JSON 中的尾随逗号
        cleaned_text = re.sub(r',\s*([}\]])', r'\1', cleaned_text)

        result = json.loads(cleaned_text)

        # 确保必要字段存在
        if 'suggestions' not in result:
            result['suggestions'] = []
        if 'summary' not in result:
            result['summary'] = {
                'systemStatus': 'unknown',
                'totalSuggestions': len(result.get('suggestions', [])),
                'highPriorityCount': 0,
                'mediumPriorityCount': 0,
                'lowPriorityCount': 0,
                'overallComment': ''
            }

        # 补充建议详情中缺失的字段
        for suggestion in result.get('suggestions', []):
            details = suggestion.get('details', {})
            suggestion_type = suggestion.get('type')

            if suggestion_type == 'switch_single_transformer':
                # 补充当前变压器名称
                if 'currentTransformerId' in details and 'currentTransformerName' not in details:
                    tid = details['currentTransformerId']
                    t = transformers.get(tid)
                    details['currentTransformerName'] = t.name if t else f'变压器-{tid}'

            elif suggestion_type == 'redundancy_warning':
                # 补充当前路径信息
                if 'currentPath' in details:
                    current_path = details['currentPath']
                    if isinstance(current_path, dict):
                        # 补充开关名称
                        if 'switchId' in current_path and 'switchName' not in current_path:
                            sid = current_path['switchId']
                            sw = switches.get(sid)
                            current_path['switchName'] = sw.name if sw else f'开关-{sid}'
                        # 补充变压器名称
                        if 'transformerId' in current_path and 'transformerName' not in current_path:
                            tid = current_path['transformerId']
                            t = transformers.get(tid)
                            current_path['transformerName'] = t.name if t else f'变压器-{tid}'

        # 添加网络分析数据
        result['networkAnalysis'] = network_data

        return result

    except json.JSONDecodeError as e:
        return {
            'error': f'解析智能体返回结果失败: {str(e)}',
            'rawResponse': text[:500] if text else '',
            'suggestions': [],
            'summary': {
                'systemStatus': 'unknown',
                'totalSuggestions': 0,
                'highPriorityCount': 0,
                'mediumPriorityCount': 0,
                'lowPriorityCount': 0,
                'overallComment': '解析失败'
            },
            'networkAnalysis': network_data
        }


@app.route('/api/planning-suggestions', methods=['GET', 'POST'])
def get_planning_suggestions():
    """获取规划建议"""

    # 递归将所有字典键转换为字符串，避免 JSON 序列化时类型不一致的问题
    def stringify_keys(obj):
        if isinstance(obj, dict):
            return {str(k): stringify_keys(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [stringify_keys(item) for item in obj]
        else:
            return obj

    if request.method == 'GET':
        # 返回缓存的建议
        cached = blackboard.get('planning_suggestions')
        if cached:
            return jsonify(stringify_keys(cached))

    # 调用智能体获取规划建议
    result = get_planning_advice_from_ai()

    # 确保result是字典类型
    if not isinstance(result, dict):
        result = {'suggestions': [], 'summary': {}, 'error': 'Invalid result type'}

    # 添加网络冗余检测建议
    redundancy_suggestions = analyze_network_redundancy()

    # 合并建议
    if 'suggestions' not in result:
        result['suggestions'] = []

    # 将冗余建议添加到列表中（避免重复）
    existing_types = set()
    for s in result['suggestions']:
        if isinstance(s, dict) and 'details' in s:
            details = s.get('details', {})
            if isinstance(details, dict):
                key = f"{s.get('type')}_{details.get('userId', '')}_{details.get('switchId', '')}"
                existing_types.add(key)

    for rs in redundancy_suggestions:
        if isinstance(rs, dict):
            details = rs.get('details', {})
            if isinstance(details, dict):
                key = f"{rs.get('type')}_{details.get('userId', '')}_{details.get('switchId', '')}"
                if key not in existing_types:
                    result['suggestions'].append(rs)

    # 更新统计信息
    if 'summary' not in result:
        result['summary'] = {}

    result['summary']['totalSuggestions'] = len(result['suggestions'])
    result['summary']['highPriorityCount'] = sum(
        1 for s in result['suggestions'] if isinstance(s, dict) and s.get('priority') == 'high')
    result['summary']['mediumPriorityCount'] = sum(
        1 for s in result['suggestions'] if isinstance(s, dict) and s.get('priority') == 'medium')
    result['summary']['lowPriorityCount'] = sum(
        1 for s in result['suggestions'] if isinstance(s, dict) and s.get('priority') == 'low')

    blackboard['planning_suggestions'] = result
    return jsonify(stringify_keys(result))


@app.route('/api/network-analysis', methods=['GET'])
def get_network_analysis():
    """获取网络分析结果"""
    network_data = build_network_topology()
    return jsonify(network_data)


def analyze_network_redundancy():
    """分析网络冗余性，返回缺乏冗余的建议"""
    suggestions = []

    # 1. 检查用户是否只有单一路径供电
    user_paths = {}  # userId -> list of (transformerId, switchIds)

    for uid, u in users.items():
        user_paths[uid] = []

    # 遍历所有开关，找出每个用户的供电路径
    for sid, sw in switches.items():
        adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)
        for uid in adjacent_u:
            if uid in user_paths:
                for tid in adjacent_t:
                    t_name = transformers[tid].name if tid in transformers else f'变压器{tid}'
                    user_paths[uid].append({
                        'transformerId': tid,
                        'switchId': sid,
                        'transformerName': t_name,
                        'switchName': sw.name,
                    })

    # 检查只有单一路径的用户
    for uid, paths in user_paths.items():
        if len(paths) <= 1:
            u = users.get(uid)
            if u:
                # 找出可以提供备用供电的变压器
                available_backup = []
                for tid, t in transformers.items():
                    # 检查这个变压器是否已经在该用户的路径中
                    already_connected = any(p['transformerId'] == tid for p in paths)
                    if not already_connected:
                        # 找出可以连接的开关
                        for sid, sw in switches.items():
                            sw_adjacent_t, sw_adjacent_u = _get_switch_adjacent_ids(sid)
                            if tid in sw_adjacent_t and uid not in sw_adjacent_u:
                                available_backup.append({
                                    'transformerId': tid,
                                    'transformerName': t.name,
                                    'switchId': sid,
                                    'switchName': sw.name,
                                    'remainingCapacityKw': max(0.0, _safe_float(t.max_active_power_kw, 0.0) - _safe_float(
                                        t.current_power_kw, 0.0)),
                                })
                                break

                if len(paths) == 0:
                    suggestions.append({
                        'type': 'redundancy_critical',
                        'priority': 'high',
                        'title': f'用户 {u.name} 无供电连接',
                        'description': f'用户 {u.name}（需求 {_safe_float(u.demand_power, 0.0):.1f}kVA）当前没有任何供电连接，需要立即建立连接。',
                        'recommendation': '请将用户连接到开关，并确保开关已连接变压器。',
                        'details': {
                            'userId': uid,
                            'userName': u.name,
                            'demandPowerKw': _safe_float(u.demand_power, 0.0),
                            'availableBackup': available_backup[:3],
                        },
                        'actionType': 'connect_user_to_switch',
                        'actionData': {
                            'userId': uid,
                        }
                    })
                elif len(paths) == 1:
                    suggestions.append({
                        'type': 'redundancy_warning',
                        'priority': 'medium',
                        'title': f'用户 {u.name} 缺乏供电冗余',
                        'description': (
                            f'用户 {u.name} 当前只有一条供电路径'
                            f'（通过 {paths[0]["switchName"]} 连接到 {paths[0]["transformerName"]}），'
                            '建议增加备用供电路径以提高可靠性。'
                        ),
                        'recommendation': '建议将用户连接到另一个开关，或增加变压器到现有开关的连接。',
                        'details': {
                            'userId': uid,
                            'userName': u.name,
                            'currentPath': paths[0],
                            'availableBackup': available_backup[:3],
                        },
                        'actionType': 'add_redundant_path',
                        'actionData': {
                            'userId': uid,
                            'currentTransformerId': paths[0]['transformerId'],
                            'currentSwitchId': paths[0]['switchId'],
                        }
                    })

    # 2. 检查开关是否只连接了一个变压器
    for sid, sw in switches.items():
        adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)
        if len(adjacent_t) <= 1 and len(adjacent_u) > 0:
            # 找出可以连接的备用变压器
            available_transformers = []
            for tid, t in transformers.items():
                if tid not in adjacent_t:
                    available_transformers.append({
                        'transformerId': tid,
                        'transformerName': t.name,
                        'remainingCapacityKw': max(0.0,
                                                   _safe_float(t.max_active_power_kw, 0.0) - _safe_float(t.current_power_kw,
                                                                                                  0.0)),
                    })

            if len(adjacent_t) == 0:
                suggestions.append({
                    'type': 'switch_no_transformer',
                    'priority': 'high',
                    'title': f'开关 {sw.name} 未连接变压器',
                    'description': f'开关 {sw.name} 连接了 {len(adjacent_u)} 个用户，但没有连接任何变压器，用户无法获得供电。',
                    'recommendation': '请将开关连接到一个变压器。',
                    'details': {
                        'switchId': sid,
                        'switchName': sw.name,
                        'connectedUsers': len(adjacent_u),
                        'availableTransformers': available_transformers[:3],
                    },
                    'actionType': 'connect_switch_to_transformer',
                    'actionData': {
                        'switchId': sid,
                    }
                })
            elif len(adjacent_t) == 1:
                # 获取当前连接的变压器信息
                tid = adjacent_t[0]
                current_transformer = transformers.get(tid)
                if current_transformer:
                    current_transformer_name = current_transformer.name
                else:
                    current_transformer_name = f'变压器-{tid}'
                suggestions.append({
                    'type': 'switch_single_transformer',
                    'priority': 'low',
                    'title': f'开关 {sw.name} 只连接了一个变压器',
                    'description': (
                        f'开关 {sw.name} 只连接了 {current_transformer_name}，'
                        '建议增加备用变压器连接以提高可靠性。'
                    ),
                    'recommendation': '建议将开关连接到另一个变压器作为备用电源。',
                    'details': {
                        'switchId': sid,
                        'switchName': sw.name,
                        'currentTransformerId': tid,
                        'currentTransformerName': current_transformer_name,
                        'availableTransformers': available_transformers[:3],
                    },
                    'actionType': 'connect_switch_to_transformer',
                    'actionData': {
                        'switchId': sid,
                        'currentTransformerId': tid,
                    }
                })

    return suggestions


def _create_wire_between_components(from_id, to_id, from_type, to_type):
    """创建两个组件之间的连线"""
    global next_wire_id
    wire_id = next_wire_id
    next_wire_id += 1

    new_wire = Wire(
        id_=wire_id,
        name=f'wire-{wire_id}',
        power=0,
        status='normal',
        from_component=from_id,
        to_component=to_id,
    )
    wires[wire_id] = new_wire

    # 如果是变压器连接到开关，更新开关配置
    if from_type == 'transformer' and to_type == 'switch':
        sw = switches.get(to_id)
        if sw:
            if not sw.config:
                sw.config = {}
            sw.config[from_id] = True
    elif from_type == 'switch' and to_type == 'transformer':
        sw = switches.get(from_id)
        if sw:
            if not sw.config:
                sw.config = {}
            sw.config[to_id] = True

    return {
        'id': wire_id,
        'name': new_wire.name,
        'fromComponent': from_id,
        'toComponent': to_id,
        'fromType': from_type,
        'toType': to_type,
    }


def _check_wire_exists(id1, id2):
    """检查两个组件之间是否已存在连线"""
    for w in wires.values():
        if (w.from_component == id1 and w.to_component == id2) or \
                (w.from_component == id2 and w.to_component == id1):
            return True
    return False


@app.route('/api/apply-suggestion', methods=['POST'])
def apply_suggestion():
    """应用规划建议，自动执行线路操作"""
    global next_wire_id

    data = request.get_json() or {}
    action_type = data.get('actionType')
    action_data = data.get('actionData', {})

    result = {
        'success': False,
        'message': '',
        'createdWires': [],
        'deletedWires': [],
    }

    if action_type == 'create_wire':
        # 创建新的电气连接
        from_type = action_data.get('fromType')
        from_id = _safe_int(action_data.get('fromId'))
        to_type = action_data.get('toType')
        to_id = _safe_int(action_data.get('toId'))

        if from_id is None or to_id is None:
            result['message'] = '缺少必要的组件ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 验证组件是否存在
        from_exists = False
        to_exists = False

        if from_type == 'transformer':
            from_exists = from_id in transformers
        elif from_type == 'switch':
            from_exists = from_id in switches

        if to_type == 'switch':
            to_exists = to_id in switches
        elif to_type == 'user':
            to_exists = to_id in users

        if not from_exists or not to_exists:
            result[
                'message'] = f'组件不存在: from_type={from_type}, from_id={from_id}, to_type={to_type}, to_id={to_id}'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 检查是否已存在相同的连线
        for w in wires.values():
            if (w.from_component == from_id and w.to_component == to_id) or \
                    (w.from_component == to_id and w.to_component == from_id):
                result['message'] = '该连接已存在'
                result['requiresManualAction'] = False
                return jsonify(result)

        # 创建新连线
        wire_id = next_wire_id
        next_wire_id += 1

        new_wire = Wire(
            id_=wire_id,
            name=f'wire-{wire_id}',
            power=0,
            status='normal',
            from_component=from_id,
            to_component=to_id,
        )
        wires[wire_id] = new_wire

        # 如果是变压器连接到开关，更新开关配置
        if from_type == 'transformer' and to_type == 'switch':
            sw = switches.get(to_id)
            if sw:
                if not sw.config:
                    sw.config = {}
                sw.config[from_id] = True

        result['success'] = True
        result['message'] = f'已成功创建连接: {from_type}({from_id}) -> {to_type}({to_id})'
        result['createdWires'].append({
            'id': wire_id,
            'name': new_wire.name,
            'fromComponent': from_id,
            'toComponent': to_id,
            'fromType': from_type,
            'toType': to_type,
        })

    elif action_type == 'delete_wire':
        # 删除线路
        wire_id = _safe_int(action_data.get('wireId'))

        if wire_id is None:
            result['message'] = '缺少线路ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 查找要删除的线路
        if wire_id not in wires:
            result['message'] = f'线路 {wire_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        wire_to_delete = wires[wire_id]

        # 如果是变压器连接到开关，更新开关配置
        from_id = wire_to_delete.from_component
        to_id = wire_to_delete.to_component

        if from_id in transformers and to_id in switches:
            sw = switches.get(to_id)
            if sw and sw.config and from_id in sw.config:
                del sw.config[from_id]
        elif to_id in transformers and from_id in switches:
            sw = switches.get(from_id)
            if sw and sw.config and to_id in sw.config:
                del sw.config[to_id]

        # 删除线路
        deleted_wire = {
            'id': wire_id,
            'name': wire_to_delete.name,
            'fromComponent': wire_to_delete.from_component,
            'toComponent': wire_to_delete.to_component,
        }
        del wires[wire_id]

        result['success'] = True
        result['message'] = f'已成功删除线路: {wire_to_delete.name}'
        result['deletedWires'].append(deleted_wire)

    elif action_type == 'connect_transformer_to_switch':
        # 将变压器连接到开关
        transformer_id = _safe_int(action_data.get('transformerId'))
        switch_id = _safe_int(action_data.get('switchId'))

        if transformer_id is None or switch_id is None:
            result['message'] = '缺少变压器ID或开关ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 验证组件存在
        if transformer_id not in transformers:
            result['message'] = f'变压器 {transformer_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        if switch_id not in switches:
            result['message'] = f'开关 {switch_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 检查是否已存在连线
        if _check_wire_exists(transformer_id, switch_id):
            result['message'] = '该变压器和开关已连接'
            result['requiresManualAction'] = False
            return jsonify(result)

        # 创建新连线
        wire_info = _create_wire_between_components(
            transformer_id, switch_id, 'transformer', 'switch'
        )

        transformer = transformers.get(transformer_id)
        result['success'] = True
        result['message'] = f'已将变压器 {transformer.name if transformer else transformer_id} 连接到开关'
        result['createdWires'].append(wire_info)

    elif action_type == 'connect_user_to_switch':
        # 用户连接到开关
        user_id = _safe_int(action_data.get('userId'))
        switch_id = _safe_int(action_data.get('switchId'))

        if user_id is None:
            result['message'] = '缺少用户ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 验证用户存在
        if user_id not in users:
            result['message'] = f'用户 {user_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 如果指定了开关ID，验证并创建连线
        if switch_id is not None:
            if switch_id not in switches:
                result['message'] = f'开关 {switch_id} 不存在'
                result['requiresManualAction'] = True
                return jsonify(result)

            # 检查是否已存在连线
            if _check_wire_exists(user_id, switch_id):
                result['message'] = '该用户和开关已连接'
                result['requiresManualAction'] = False
                return jsonify(result)

            # 创建新连线（方向：开关 -> 用户）
            wire_info = _create_wire_between_components(
                switch_id, user_id, 'switch', 'user'
            )

            user = users.get(user_id)
            sw = switches.get(switch_id)
            result['success'] = True
            result['message'] = f'已将用户 {user.name if user else user_id} 连接到开关 {sw.name if sw else switch_id}'
            result['createdWires'].append(wire_info)
        else:
            # 未指定开关，自动找一个可用的开关
            available_switches = []
            for sid, sw in switches.items():
                adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)
                if user_id not in adjacent_u and len(adjacent_t) > 0:
                    available_switches.append({
                        'switchId': sid,
                        'switchName': sw.name,
                        'connectedTransformers': len(adjacent_t),
                    })

            if available_switches:
                # 自动连接到第一个可用的开关
                target_switch = available_switches[0]
                wire_info = _create_wire_between_components(
                    target_switch['switchId'], user_id, 'switch', 'user'
                )

                user = users.get(user_id)
                result['success'] = True
                result['message'] = (
                    f'已自动将用户 {user.name if user else user_id} '
                    f'连接到开关 {target_switch["switchName"]}'
                )
                result['createdWires'].append(wire_info)
            else:
                result['message'] = '未找到可用的开关，请先创建开关或连接变压器到开关'
                result['requiresManualAction'] = True

    elif action_type == 'connect_switch_to_transformer':
        switch_id = _safe_int(action_data.get('switchId'))
        transformer_id = _safe_int(action_data.get('transformerId'))
        current_transformer_id = _safe_int(action_data.get('currentTransformerId'))

        if switch_id is None:
            result['message'] = '缺少开关ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        if switch_id not in switches:
            result['message'] = f'开关 {switch_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 如果指定了变压器ID，直接连接
        if transformer_id is not None:
            if transformer_id not in transformers:
                result['message'] = f'变压器 {transformer_id} 不存在'
                result['requiresManualAction'] = True
                return jsonify(result)

            # 检查是否已存在连线
            if _check_wire_exists(transformer_id, switch_id):
                result['message'] = '该变压器和开关已连接'
                result['requiresManualAction'] = False
                return jsonify(result)

            # 创建新连线
            wire_info = _create_wire_between_components(
                transformer_id, switch_id, 'transformer', 'switch'
            )

            transformer = transformers.get(transformer_id)
            result['success'] = True
            result['message'] = f'已将变压器 {transformer.name if transformer else transformer_id} 连接到开关'
            result['createdWires'].append(wire_info)
        else:
            # 自动找一个可用的备用变压器
            available_transformers = []
            for tid, t in transformers.items():
                if tid != current_transformer_id:
                    available_transformers.append({
                        'transformerId': tid,
                        'transformerName': t.name,
                        'remainingCapacityKw': max(0.0,
                                                   _safe_float(t.max_active_power_kw, 0.0) - _safe_float(t.current_power_kw,
                                                                                                  0.0)),
                    })

            if available_transformers:
                # 自动创建连线
                target_transformer = available_transformers[0]
                wire_info = _create_wire_between_components(
                    target_transformer['transformerId'], switch_id, 'transformer', 'switch'
                )

                result['success'] = True
                result['message'] = f'已自动将变压器 {target_transformer["transformerName"]} 连接到开关'
                result['createdWires'].append(wire_info)
            else:
                result['message'] = '未找到可用的备用变压器'
                result['requiresManualAction'] = True

    elif action_type == 'add_redundant_path':
        user_id = _safe_int(action_data.get('userId'))
        current_switch_id = _safe_int(action_data.get('currentSwitchId'))

        if user_id is None:
            result['message'] = '缺少用户ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 找一个可用的备用开关
        available_switches = []
        for sid, sw in switches.items():
            if sid != current_switch_id:
                adjacent_t, adjacent_u = _get_switch_adjacent_ids(sid)
                if user_id not in adjacent_u and len(adjacent_t) > 0:
                    available_switches.append({
                        'switchId': sid,
                        'switchName': sw.name,
                        'connectedTransformers': len(adjacent_t),
                    })

        if available_switches:
            # 自动连接到第一个可用的开关
            target_switch = available_switches[0]
            wire_info = _create_wire_between_components(
                target_switch['switchId'], user_id, 'switch', 'user'
            )

            user = users.get(user_id)
            result['success'] = True
            result['message'] = (
                f'已自动将用户 {user.name if user else user_id} '
                f'连接到备用开关 {target_switch["switchName"]}'
            )
            result['createdWires'].append(wire_info)
        else:
            result['message'] = '未找到可用的备用开关，请先创建新的开关或连接变压器到现有开关'
            result['requiresManualAction'] = True

    elif action_type == 'add_transformer_to_switch':
        # 新增变压器并连接到开关
        global next_node_id
        switch_id = _safe_int(action_data.get('switchId'))
        transformer_power_kw = _safe_float(action_data.get('transformerPowerKw'), 500.0)

        if switch_id is None:
            result['message'] = '缺少开关ID'
            result['requiresManualAction'] = True
            return jsonify(result)

        if switch_id not in switches:
            result['message'] = f'开关 {switch_id} 不存在'
            result['requiresManualAction'] = True
            return jsonify(result)

        # 创建新变压器
        transformer_id = next_node_id
        next_node_id += 1

        # 根据容量选择变压器类型
        if transformer_power_kw >= 400:
            transformer_type = 'transformer2'  # SCB14-630kVA
        else:
            transformer_type = 'transformer'  # SCB18-200kVA

        new_transformer = Transformer(
            id_=transformer_id,
            name=f'transformer-{transformer_id}',
            max_power_kw=transformer_power_kw,
            loss_power_kw=0,
            current_power_kw=0,
            max_active_power_kw=transformer_power_kw * 0.8,  # 最大有功功率 = 铭牌容量 × 0.8
        )
        transformers[transformer_id] = new_transformer

        # 创建变压器到开关的连线
        wire_info = _create_wire_between_components(
            transformer_id, switch_id, 'transformer', 'switch'
        )

        sw = switches.get(switch_id)
        result['success'] = True
        result['message'] = (
            f'已新增变压器 {new_transformer.name} ({transformer_power_kw}kVA) '
            f'并连接到开关 {sw.name if sw else switch_id}'
        )
        result['createdTransformer'] = {
            'id': transformer_id,
            'type': transformer_type,
            'name': new_transformer.name,
            'maxPowerKw': transformer_power_kw,
        }
        result['createdWires'].append(wire_info)

    else:
        result['message'] = f'未知的建议类型: {action_type}'
        result['requiresManualAction'] = True

    return jsonify(result)


@app.route('/api/blackboard/<kind>/<int:entity_id>', methods=['GET'])
def blackboard_entry(kind, entity_id):
    if kind not in ('transformers', 'users', 'switches'):
        return jsonify({'error': 'invalid kind'}), 400

    # 优先获取 AI 结果
    data = get_ai_result(kind, entity_id)
    if data:
        return jsonify(data)

    # 如果没有 AI 结果，尝试构建基础数据返回，避免 404
    if kind == 'transformers' and entity_id in transformers:
        t = transformers[entity_id]
        return jsonify({
            'maxPowerKw': t.max_power_kw,
            'maxActivePowerKw': t.max_active_power_kw,
            'lossPowerKw': t.loss_power_kw,
            'currentPowerKw': t.current_power_kw,
            'recommendedPowerKw': getattr(t, 'recommended_power_kw', None),
            'answer': '',
        })
    elif kind == 'switches' and entity_id in switches:
        return jsonify({
            'answer': '',
        })
    elif kind == 'users' and entity_id in users:
        return jsonify({
            'answer': '',
        })

    return jsonify({'error': 'not found'}), 404


@app.route('/api/reset-all', methods=['POST'])
def reset_all():
    reset_all_state()
    return jsonify({'status': 'reset'})


@app.route('/api/user-types', methods=['GET'])
def get_user_types():
    """获取时间标签"""
    return jsonify({
        'timeLabels': TIME_LABELS,
    })


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_detail(user_id):
    """获取单个用户的详细信息"""
    user = users.get(user_id)
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    return jsonify(user.to_dict())


# ==================== 前端静态文件托管 ====================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """托管前端构建产物，支持 Vue Router 的 history 模式"""
    # 如果请求的是 API 路由，交给其他路由处理
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404

    # 静态文件路径
    dist_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'front-end', 'dist')

    # 如果文件存在，返回静态文件
    if path and os.path.exists(os.path.join(dist_folder, path)):
        return send_from_directory(dist_folder, path)

    # 否则返回 index.html（支持 Vue Router 的 history 模式）
    return send_from_directory(dist_folder, 'index.html')


if __name__ == '__main__':
    # 检查 dist 目录是否存在
    dist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'front-end', 'dist')
    if not os.path.exists(dist_path):
        print("=" * 60)
        print("警告: front-end/dist 目录不存在!")
        print("请先构建前端项目:")
        print("  cd front-end")
        print("  npm run build")
        print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)
