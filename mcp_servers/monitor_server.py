"""真实数据驱动的 Prometheus/cAdvisor 监控 MCP Server。"""

import logging
import functools
import json
import math
import os
import re
from urllib.parse import quote
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from fastmcp import FastMCP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Monitor_MCP_Server")

mcp = FastMCP("Monitor")


CONTAINER_TARGETS: Dict[str, Dict[str, Any]] = {
    "aiops-api": {
        "display_name": "运维助手 API（包含对话与故障诊断编排）",
        "aliases": [
            "运维助手", "助手服务", "助手API", "对话Agent", "对话助手",
            "故障诊断", "故障诊断Agent", "API服务",
        ],
    },
    "aiops-celery-worker": {
        "display_name": "Celery 异步任务与知识库索引",
        "aliases": [
            "Celery", "Celery任务", "Celery Worker", "异步任务", "索引任务",
            "知识库索引", "知识库上传任务", "文件索引", "文件上传任务",
        ],
    },
    "aiops-mcp-monitor": {
        "display_name": "监控 MCP 服务",
        "aliases": ["监控MCP", "MCP Monitor", "监控工具", "监控服务"],
    },
    "aiops-mcp-cls": {
        "display_name": "腾讯云 CLS 日志查询 MCP 服务",
        "aliases": ["CLS", "CLS MCP", "MCP CLS", "腾讯云日志", "日志服务", "日志查询"],
    },
    "milvus-standalone": {
        "display_name": "Milvus 向量数据库",
        "aliases": ["Milvus", "向量数据库", "知识库数据库", "向量库"],
    },
    "aiops-redis": {
        "display_name": "Redis 缓存与任务队列",
        "aliases": ["Redis", "缓存", "会话缓存", "任务队列", "消息队列"],
    },
}

RESTARTABLE_CONTAINERS = {
    "aiops-celery-worker",
    "aiops-mcp-cls",
    "milvus-standalone",
    "aiops-redis",
}

AMBIGUOUS_CONTAINER_ALIASES: Dict[str, list[str]] = {
    "agent": ["aiops-api", "aiops-mcp-monitor", "aiops-mcp-cls"],
    "mcp": ["aiops-mcp-monitor", "aiops-mcp-cls"],
    "任务": ["aiops-celery-worker", "aiops-redis"],
}


CONTAINER_METRICS: Dict[str, Dict[str, Any]] = {
    "cpu": {
        "aliases": ["cpu", "处理器"],
        "promql": 'sum(rate(container_cpu_usage_seconds_total{{job="cadvisor",name={name}}}[5m])) * 100',
        "unit": "percent_of_one_cpu_core",
        "metric_name": "container_cpu_usage_percent",
    },
    "memory": {
        "aliases": ["memory", "内存", "内存使用量"],
        "promql": 'sum(container_memory_working_set_bytes{{job="cadvisor",name={name}}}) / 1024 / 1024',
        "unit": "MiB",
        "metric_name": "container_memory_working_set_mib",
    },
    "memory_percent": {
        "aliases": ["memorypercent", "内存占用率", "内存使用率"],
        "promql": '100 * sum(container_memory_working_set_bytes{{job="cadvisor",name={name}}}) / clamp_min(sum(container_spec_memory_limit_bytes{{job="cadvisor",name={name}}}), 1)',
        "unit": "percent_of_memory_limit",
        "metric_name": "container_memory_limit_percent",
    },
    "network_rx": {
        "aliases": ["networkrx", "网络接收", "接收流量", "入站流量"],
        "promql": 'sum(rate(container_network_receive_bytes_total{{job="cadvisor",name={name}}}[5m]))',
        "unit": "bytes_per_second",
        "metric_name": "container_network_receive_bytes_per_second",
    },
    "network_tx": {
        "aliases": ["networktx", "网络发送", "发送流量", "出站流量"],
        "promql": 'sum(rate(container_network_transmit_bytes_total{{job="cadvisor",name={name}}}[5m]))',
        "unit": "bytes_per_second",
        "metric_name": "container_network_transmit_bytes_per_second",
    },
    "filesystem_read": {
        "aliases": ["filesystemread", "磁盘读取", "文件读取", "读io"],
        "promql": 'sum(rate(container_fs_reads_bytes_total{{job="cadvisor",name={name}}}[5m]))',
        "unit": "bytes_per_second",
        "metric_name": "container_filesystem_read_bytes_per_second",
    },
    "filesystem_write": {
        "aliases": ["filesystemwrite", "磁盘写入", "文件写入", "写io"],
        "promql": 'sum(rate(container_fs_writes_bytes_total{{job="cadvisor",name={name}}}[5m]))',
        "unit": "bytes_per_second",
        "metric_name": "container_filesystem_write_bytes_per_second",
    },
}


def log_tool_call(func):
    """装饰器：记录工具调用的日志，包括方法名、参数和返回状态"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__

        # 记录调用信息
        logger.info("=" * 80)
        logger.info(f"调用方法: {method_name}")

        # 记录参数（排除self等）
        if kwargs:
            # 使用 json.dumps 格式化参数，处理可能的序列化错误
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info(f"参数信息:\n{params_str}")
        else:
            logger.info("参数信息: 无")

        # 执行方法
        try:
            result = func(*args, **kwargs)

            # 记录返回状态
            logger.info("返回状态: SUCCESS")

            # 记录返回结果摘要（避免日志过长）
            if isinstance(result, dict):
                summary = {k: v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} with {len(v)} items>"
                          for k, v in list(result.items())[:5]}
                logger.info(f"返回结果摘要: {json.dumps(summary, ensure_ascii=False)}")
            else:
                logger.info(f"返回结果: {result}")

            logger.info("=" * 80)
            return result

        except Exception as e:
            # 记录错误状态
            logger.error("返回状态: ERROR")
            logger.error(f"错误信息: {str(e)}")
            logger.error("=" * 80)
            raise

    return wrapper


# ============================================================
# 辅助函数
# ============================================================

def parse_time_or_default(time_str: Optional[str], default_offset_hours: int = 0) -> datetime:
    """解析时间字符串或返回默认时间。

    Args:
        time_str: 时间字符串（格式：YYYY-MM-DD HH:MM:SS）
        default_offset_hours: 默认时间偏移（小时）

    Returns:
        datetime: 解析后的时间对象
    """
    if time_str:
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    # 返回默认时间（当前时间 + 偏移）
    return datetime.now() + timedelta(hours=default_offset_hours)


def _interval_seconds(interval: str) -> int:
    if interval.endswith("m") and interval[:-1].isdigit():
        return max(60, int(interval[:-1]) * 60)
    if interval.endswith("h") and interval[:-1].isdigit():
        return max(60, int(interval[:-1]) * 3600)
    raise ValueError("interval 仅支持 Nm 或 Nh 格式，例如 1m、5m、1h")


def _prometheus_query_range(
    query: str,
    start_dt: datetime,
    end_dt: datetime,
    step_seconds: int,
) -> list[dict[str, Any]]:
    base_url = os.getenv("PROMETHEUS_BASE_URL", "http://prometheus:9090").rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            f"{base_url}/api/v1/query_range",
            params={
                "query": query,
                "start": start_dt.timestamp(),
                "end": end_dt.timestamp(),
                "step": step_seconds,
            },
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus 查询失败: {payload.get('error', 'unknown error')}")
    return payload.get("data", {}).get("result", [])


def _prometheus_instant_query(query: str) -> list[dict[str, Any]]:
    base_url = os.getenv("PROMETHEUS_BASE_URL", "http://prometheus:9090").rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{base_url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus 查询失败: {payload.get('error', 'unknown error')}")
    return payload.get("data", {}).get("result", [])


def _unavailable_metric(service_name: str, metric_name: str, message: str) -> Dict[str, Any]:
    return {
        "service_name": service_name,
        "metric_name": metric_name,
        "data_source": "prometheus",
        "data_available": False,
        "data_points": [],
        "statistics": {},
        "alert_info": {
            "triggered": None,
            "threshold": None,
            "message": "没有真实指标，无法判断是否触发告警",
        },
        "message": message,
    }


def _normalize_alias(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(value).casefold())


def resolve_container_alias(query: str) -> Dict[str, Any]:
    """Resolve a natural-language container reference without model guessing."""
    normalized = _normalize_alias(query)
    if not normalized:
        return {
            "status": "unsupported",
            "canonical_name": None,
            "candidates": [],
            "message": "未提供容器名称",
        }

    for canonical_name in CONTAINER_TARGETS:
        if normalized == _normalize_alias(canonical_name):
            return {
                "status": "resolved",
                "canonical_name": canonical_name,
                "candidates": [canonical_name],
                "message": f"已解析为容器 {canonical_name}",
            }

    matches: list[str] = []
    for canonical_name, details in CONTAINER_TARGETS.items():
        aliases = sorted(details["aliases"], key=lambda item: len(_normalize_alias(item)), reverse=True)
        if any(_normalize_alias(alias) in normalized for alias in aliases):
            matches.append(canonical_name)

    if len(matches) == 1:
        return {
            "status": "resolved",
            "canonical_name": matches[0],
            "candidates": matches,
            "message": f"已解析为容器 {matches[0]}",
        }
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "canonical_name": None,
            "candidates": matches,
            "message": "目标描述匹配多个容器，请明确选择",
        }

    for alias, candidates in AMBIGUOUS_CONTAINER_ALIASES.items():
        if _normalize_alias(alias) in normalized:
            return {
                "status": "ambiguous",
                "canonical_name": None,
                "candidates": candidates,
                "message": "目标描述过于宽泛，请从候选容器中选择",
            }

    return {
        "status": "unsupported",
        "canonical_name": None,
        "candidates": [],
        "message": "未找到受支持的容器别名，不会猜测目标",
    }


def _resolve_container_metric(metric: str) -> Optional[str]:
    normalized = _normalize_alias(metric)
    if normalized in CONTAINER_METRICS:
        return normalized
    for metric_name, details in CONTAINER_METRICS.items():
        if any(_normalize_alias(alias) == normalized for alias in details["aliases"]):
            return metric_name
    return None


def _container_metric_unavailable(
    requested_target: str,
    metric: str,
    resolution: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    return {
        "requested_target": requested_target,
        "container_name": resolution.get("canonical_name"),
        "resolution_status": resolution.get("status"),
        "candidates": resolution.get("candidates", []),
        "metric": metric,
        "data_source": "prometheus/cadvisor",
        "data_available": False,
        "data_points": [],
        "statistics": {},
        "message": message,
    }





# ============================================================
# 监控数据查询工具
# ============================================================

@mcp.tool()
@log_tool_call
def list_monitored_containers() -> Dict[str, Any]:
    """列出当前助手支持查询的容器以及 cAdvisor 数据可用状态。

    用户没有指定容器、询问“有哪些服务可以查询”或目标名称不确定时，应先调用本工具。
    返回的名称来自固定受支持清单和 Prometheus 实时数据，不代表 Windows 宿主机进程。
    """
    names_regex = "|".join(CONTAINER_TARGETS)
    query = f'container_last_seen{{job="cadvisor",name=~"{names_regex}"}}'
    try:
        result = _prometheus_instant_query(query)
        available_names = {
            str(item.get("metric", {}).get("name", ""))
            for item in result
            if item.get("metric", {}).get("name")
        }
    except Exception as exc:
        logger.error("查询 cAdvisor 容器清单失败: %s", exc)
        return {
            "success": False,
            "data_source": "prometheus/cadvisor",
            "containers": [],
            "message": f"无法从 Prometheus 获取容器清单: {exc}",
        }

    containers = [
        {
            "name": name,
            "display_name": details["display_name"],
            "aliases": details["aliases"],
            "available": name in available_names,
        }
        for name, details in CONTAINER_TARGETS.items()
    ]
    return {
        "success": True,
        "data_source": "prometheus/cadvisor",
        "containers": containers,
        "available_count": sum(1 for item in containers if item["available"]),
        "message": "已从 Prometheus/cAdvisor 核实容器数据可用状态",
    }


@mcp.tool()
@log_tool_call
def query_container_metrics(
    target: str,
    metric: str = "cpu",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1m",
) -> Dict[str, Any]:
    """按自然语言别名查询 Docker 容器的真实资源指标。

    Args:
        target: 容器标准名或用户原始称呼，例如“Celery任务”“向量数据库”。
        metric: cpu、memory、memory_percent、network_rx、network_tx、
            filesystem_read 或 filesystem_write，也支持对应中文名称。
        start_time: 可选，格式 YYYY-MM-DD HH:MM:SS，默认一小时前。
        end_time: 可选，格式 YYYY-MM-DD HH:MM:SS，默认当前时间。
        interval: 数据点间隔，支持 Nm 或 Nh，例如 1m、5m、1h。

    目标有歧义时本工具只返回候选容器，不会查询或猜测。CPU 的 100% 表示占满一个
    CPU 核，多核场景可以超过 100%；数据来源固定为 Prometheus/cAdvisor。
    """
    resolution = resolve_container_alias(target)
    if resolution["status"] != "resolved":
        return _container_metric_unavailable(
            target,
            metric,
            resolution,
            resolution["message"],
        )

    metric_key = _resolve_container_metric(metric)
    if not metric_key:
        return _container_metric_unavailable(
            target,
            metric,
            resolution,
            f"不支持指标 {metric!r}，可选值: {', '.join(CONTAINER_METRICS)}",
        )

    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)
    details = CONTAINER_METRICS[metric_key]
    container_name = str(resolution["canonical_name"])
    promql = details["promql"].format(
        name=json.dumps(container_name, ensure_ascii=False)
    )

    try:
        if end_dt < start_dt:
            raise ValueError("end_time 不能早于 start_time")
        series = _prometheus_query_range(
            promql,
            start_dt,
            end_dt,
            _interval_seconds(interval),
        )
    except Exception as exc:
        logger.error("查询容器指标失败: %s", exc)
        return _container_metric_unavailable(
            target,
            metric_key,
            resolution,
            f"Prometheus/cAdvisor 查询失败: {exc}",
        )

    raw_values = series[0].get("values", []) if series else []
    data_points = []
    for timestamp, raw_value in raw_values:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        data_points.append({
            "timestamp": datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S"),
            "value": round(value, 4),
        })

    if not data_points:
        return _container_metric_unavailable(
            target,
            metric_key,
            resolution,
            f"Prometheus 未找到容器 {container_name!r} 的 {metric_key} 指标",
        )

    values = [point["value"] for point in data_points]
    sorted_values = sorted(values)
    p95_index = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
    return {
        "requested_target": target,
        "container_name": container_name,
        "display_name": CONTAINER_TARGETS[container_name]["display_name"],
        "resolution_status": "resolved",
        "candidates": [container_name],
        "metric": metric_key,
        "metric_name": details["metric_name"],
        "data_source": "prometheus/cadvisor",
        "data_available": True,
        "unit": details["unit"],
        "interval": interval,
        "query_window": {
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "data_points": data_points,
        "statistics": {
            "latest": values[-1],
            "avg": round(sum(values) / len(values), 4),
            "max": max(values),
            "min": min(values),
            "p95": sorted_values[p95_index],
        },
        "message": f"数据来自 Prometheus/cAdvisor，容器 {container_name}",
    }


@mcp.tool()
@log_tool_call
def query_cpu_metrics(
    service_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1m"
) -> Dict[str, Any]:
    """查询服务的 CPU 使用率监控数据。

    `service_name` 必须是用户明确提供的 Prometheus job 标签。不得从示例、历史文档
    或模型猜测中选择服务名。返回值中的 `data_source` 固定为 `prometheus`；当
    `data_available` 为 false 时，调用方必须明确说明无法确认当前 CPU 状态。

    Args:
        service_name: 用户明确提供的 Prometheus job 标签（必填）
        
        start_time: 开始时间（可选，字符串类型）
            格式: "YYYY-MM-DD HH:MM:SS"
            示例: "2026-02-14 10:00:00"
            默认值: 如果不传，默认为当前时间的1小时前
            注意: 必须使用字符串格式，而非时间戳
        
        end_time: 结束时间（可选，字符串类型）
            格式: "YYYY-MM-DD HH:MM:SS"
            示例: "2026-02-14 11:00:00"
            默认值: 如果不传，默认为当前时间
            注意: 必须使用字符串格式，而非时间戳
        
        interval: 数据聚合间隔（可选）
            可选值: "1m" (1分钟), "5m" (5分钟), "1h" (1小时)
            默认值: "1m"
            说明: 控制数据点的时间间隔

    Returns:
        Dict: CPU 监控数据
            - service_name: 服务名称
            - metric_name: 指标名称 (cpu_usage_percent)
            - interval: 数据聚合间隔
            - data_points: 数据点列表，每个点包含:
                * timestamp: 时间点（格式: HH:MM）
                * value: CPU 使用率百分比
            - statistics: 统计信息
                * average: 平均值
                * max: 最大值
                * min: 最小值
            - alert: 告警信息（如有）
                * triggered: 是否触发告警
                * threshold: 告警阈值
                * message: 告警消息
    
    """
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)

    try:
        if end_dt < start_dt:
            raise ValueError("end_time 不能早于 start_time")
        step_seconds = _interval_seconds(interval)
        promql_service = json.dumps(service_name, ensure_ascii=False)
        query = (
            "sum(rate(process_cpu_seconds_total"
            f"{{job={promql_service}}}[5m])) * 100"
        )
        series = _prometheus_query_range(query, start_dt, end_dt, step_seconds)
    except Exception as exc:
        logger.error("查询 Prometheus CPU 指标失败: %s", exc)
        return _unavailable_metric(
            service_name,
            "process_cpu_usage_percent",
            f"Prometheus CPU 查询失败，不能确认当前 CPU 状态: {exc}",
        )

    if not series or not series[0].get("values"):
        return _unavailable_metric(
            service_name,
            "process_cpu_usage_percent",
            f"Prometheus 未找到 job={service_name!r} 的 CPU 指标，不能确认当前 CPU 是否过高",
        )

    data_points = [
        {
            "timestamp": datetime.fromtimestamp(float(timestamp)).strftime("%H:%M"),
            "value": round(float(value), 2),
        }
        for timestamp, value in series[0]["values"]
    ]
    values = [point["value"] for point in data_points]
    sorted_values = sorted(values)
    p95_index = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
    threshold = 80.0
    triggered = max(values) > threshold
    return {
        "service_name": service_name,
        "metric_name": "process_cpu_usage_percent",
        "data_source": "prometheus",
        "data_available": True,
        "interval": interval,
        "data_points": data_points,
        "statistics": {
            "avg": round(sum(values) / len(values), 2),
            "max": max(values),
            "min": min(values),
            "p95": sorted_values[p95_index],
            "spike_detected": triggered,
        },
        "alert_info": {
            "triggered": triggered,
            "threshold": threshold,
            "message": (
                "Prometheus 进程 CPU 使用率超过 80% 阈值"
                if triggered
                else "Prometheus 进程 CPU 使用率未超过 80% 阈值"
            ),
        },
        "message": "数据来自 Prometheus process_cpu_seconds_total",
    }

@mcp.tool()
@log_tool_call
def query_memory_metrics(
    service_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1m"
) -> Dict[str, Any]:
    """查询服务的内存使用监控数据。

    `service_name` 必须是用户明确提供的 Prometheus job 标签。不得猜测服务名。
    当前 Prometheus 只有进程 RSS 字节数，没有主机总内存或容器 limit，因此本工具
    返回真实 RSS MB，不把它伪装成内存百分比，也不自动判断内存告警。

    Args:
        service_name: 用户明确提供的 Prometheus job 标签（必填）
        
        start_time: 开始时间（可选，字符串类型）
            格式: "YYYY-MM-DD HH:MM:SS"
            示例: "2026-02-14 10:00:00"
            默认值: 如果不传，默认为当前时间的1小时前
            注意: 必须使用字符串格式，而非时间戳
        
        end_time: 结束时间（可选，字符串类型）
            格式: "YYYY-MM-DD HH:MM:SS"
            示例: "2026-02-14 11:00:00"
            默认值: 如果不传，默认为当前时间
            注意: 必须使用字符串格式，而非时间戳
        
        interval: 数据聚合间隔（可选）
            可选值: "1m" (1分钟), "5m" (5分钟), "1h" (1小时)
            默认值: "1m"

    Returns:
        Dict: 内存监控数据
            - service_name: 服务名称
            - metric_name: 指标名称 (memory_usage_percent)
            - interval: 数据聚合间隔
            - data_points: 数据点列表，每个点包含:
                * timestamp: 时间点（格式: HH:MM）
                * value: 内存使用率百分比
                * used_gb: 已使用内存（GB）
                * total_gb: 总内存（GB）
            - statistics: 统计信息
                * average: 平均值
                * max: 最大值
                * min: 最小值
            - alert: 告警信息（如有）
                * triggered: 是否触发告警
                * threshold: 告警阈值
                * message: 告警消息
    
    """
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)

    try:
        if end_dt < start_dt:
            raise ValueError("end_time 不能早于 start_time")
        step_seconds = _interval_seconds(interval)
        promql_service = json.dumps(service_name, ensure_ascii=False)
        query = f"sum(process_resident_memory_bytes{{job={promql_service}}})"
        series = _prometheus_query_range(query, start_dt, end_dt, step_seconds)
    except Exception as exc:
        logger.error("查询 Prometheus 内存指标失败: %s", exc)
        return _unavailable_metric(
            service_name,
            "process_resident_memory_mb",
            f"Prometheus 内存查询失败，不能确认当前内存状态: {exc}",
        )

    if not series or not series[0].get("values"):
        return _unavailable_metric(
            service_name,
            "process_resident_memory_mb",
            f"Prometheus 未找到 job={service_name!r} 的内存指标，不能确认当前内存状态",
        )

    data_points = [
        {
            "timestamp": datetime.fromtimestamp(float(timestamp)).strftime("%H:%M"),
            "value_mb": round(float(value) / 1024 / 1024, 2),
        }
        for timestamp, value in series[0]["values"]
    ]
    values_mb = [point["value_mb"] for point in data_points]
    sorted_values = sorted(values_mb)
    p95_index = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
    return {
        "service_name": service_name,
        "metric_name": "process_resident_memory_mb",
        "data_source": "prometheus",
        "data_available": True,
        "interval": interval,
        "data_points": data_points,
        "statistics": {
            "avg_mb": round(sum(values_mb) / len(values_mb), 2),
            "max_mb": max(values_mb),
            "min_mb": min(values_mb),
            "p95_mb": sorted_values[p95_index],
        },
        "alert_info": {
            "triggered": None,
            "threshold": None,
            "message": "缺少主机总内存或容器 limit，不能从 RSS MB 判断内存使用率告警",
        },
        "message": "数据来自 Prometheus process_resident_memory_bytes",
    }

def _restart_docker_container(container_name: str) -> None:
    socket_path = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
    if not os.path.exists(socket_path):
        raise RuntimeError(f"Docker Engine socket 不可用: {socket_path}")
    transport = httpx.HTTPTransport(uds=socket_path)
    with httpx.Client(
        transport=transport,
        base_url="http://docker",
        timeout=45.0,
    ) as client:
        response = client.post(
            f"/containers/{quote(container_name, safe='')}/restart",
            params={"t": 10},
        )
    if response.status_code != 204:
        detail = response.text[:500]
        raise RuntimeError(
            f"Docker Engine 重启失败: HTTP {response.status_code}, {detail}"
        )


def restart_service(service_name: str, reason: str) -> Dict[str, Any]:
    """通过 Docker Engine 实际重启白名单容器。

    本工具属于高风险操作，上层仅在管理员明确批准后才会暴露并调用。为避免中断
    当前控制链路，aiops-api 和 aiops-mcp-monitor 不允许通过本工具自重启。
    """
    if not reason.strip():
        raise ValueError("重启原因不能为空")
    resolution = resolve_container_alias(service_name)
    if resolution["status"] != "resolved":
        raise ValueError(resolution["message"])
    container_name = str(resolution["canonical_name"])
    if container_name not in RESTARTABLE_CONTAINERS:
        raise ValueError(
            f"容器 {container_name} 未纳入可重启白名单；控制面服务禁止自重启"
        )

    _restart_docker_container(container_name)
    completed_at = datetime.now().astimezone().isoformat()
    return {
        "status": "completed",
        "executed": True,
        "data_source": "docker_engine",
        "service_name": service_name,
        "container_name": container_name,
        "reason": reason,
        "completed_at": completed_at,
        "operation_id": f"restart-{container_name}-{int(datetime.now().timestamp())}",
        "message": f"Docker Engine 已完成容器 {container_name} 的重启",
    }


if os.getenv("ENABLE_DOCKER_RESTART", "false").lower() == "true":
    restart_service = mcp.tool()(log_tool_call(restart_service))


if __name__ == "__main__":
    # 使用 streamable-http 模式，运行在 8004 端口
    mcp.run(transport="streamable-http", host=os.getenv("MCP_HOST", "127.0.0.1"), port=8004, path="/mcp")
