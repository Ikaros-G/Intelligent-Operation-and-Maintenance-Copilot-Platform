"""Tencent Cloud CLS tools backed by the real Cloud API 3.0 endpoints."""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx
from fastmcp import FastMCP


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CLS_MCP_Server")

mcp = FastMCP("CLS")

CLS_SERVICE = "cls"
CLS_HOST = "cls.tencentcloudapi.com"
CLS_API_VERSION = "2020-10-16"
CLS_DATA_SOURCE = "tencentcloud_cls"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

REGION_CODES = {
    "北京": "ap-beijing",
    "上海": "ap-shanghai",
    "广州": "ap-guangzhou",
    "成都": "ap-chengdu",
    "重庆": "ap-chongqing",
    "南京": "ap-nanjing",
    "香港": "ap-hongkong",
}
DEFAULT_DISCOVERY_REGIONS = tuple(REGION_CODES.values())


class ClsApiError(RuntimeError):
    def __init__(self, message: str, code: str = "", request_id: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id


def log_tool_call(func):
    """Log tool calls without logging credentials or full log payloads."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info("=" * 80)
        logger.info("调用方法: %s", func.__name__)
        safe_kwargs = {
            key: ("<query>" if key == "query" and value else value)
            for key, value in kwargs.items()
        }
        logger.info("参数信息: %s", json.dumps(safe_kwargs, ensure_ascii=False))
        try:
            result = func(*args, **kwargs)
            logger.info(
                "返回状态: %s, data_source=%s",
                "SUCCESS" if not isinstance(result, dict) or result.get("success", True) else "FAILED",
                result.get("data_source") if isinstance(result, dict) else "local_clock",
            )
            return result
        except Exception:
            logger.exception("工具执行失败")
            raise
        finally:
            logger.info("=" * 80)

    return wrapper


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _credentials() -> tuple[str, str]:
    secret_id = os.getenv("TENCENTCLOUD_SECRET_ID", "").strip()
    secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY", "").strip()
    if not secret_id or not secret_key:
        raise ClsApiError(
            "缺少 TENCENTCLOUD_SECRET_ID 或 TENCENTCLOUD_SECRET_KEY",
            code="LocalConfig.MissingCredentials",
        )
    return secret_id, secret_key


def _signed_headers(
    action: str,
    region: str,
    payload: str,
    timestamp: Optional[int] = None,
) -> Dict[str, str]:
    secret_id, secret_key = _credentials()
    request_timestamp = timestamp or int(time.time())
    date = datetime.fromtimestamp(request_timestamp, timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    signed_header_names = "content-type;host"
    canonical_headers = f"content-type:{content_type}\nhost:{CLS_HOST}\n"
    canonical_request = (
        "POST\n/\n\n"
        f"{canonical_headers}\n"
        f"{signed_header_names}\n"
        f"{_sha256_hex(payload)}"
    )
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{CLS_SERVICE}/tc3_request"
    string_to_sign = (
        f"{algorithm}\n{request_timestamp}\n{credential_scope}\n"
        f"{_sha256_hex(canonical_request)}"
    )
    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, CLS_SERVICE)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_header_names}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": CLS_HOST,
        "X-TC-Action": action,
        "X-TC-Version": CLS_API_VERSION,
        "X-TC-Timestamp": str(request_timestamp),
        "X-TC-Region": region,
        "Accept-Encoding": "gzip",
    }


def _call_cls_api(action: str, region: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call Tencent Cloud CLS API 3.0 and return the inner Response object."""
    if not region:
        raise ClsApiError("CLS API 必须指定地域", code="LocalConfig.MissingRegion")
    payload = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    headers = _signed_headers(action, region, payload)
    endpoint = os.getenv("TENCENTCLOUD_CLS_ENDPOINT", f"https://{CLS_HOST}").rstrip("/")
    timeout = float(os.getenv("TENCENTCLOUD_CLS_TIMEOUT", "20"))
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{endpoint}/", content=payload.encode("utf-8"), headers=headers)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise ClsApiError(f"腾讯云 CLS HTTP 请求失败: {exc}", code="LocalNetwork.HttpError") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ClsApiError("腾讯云 CLS 返回了无法解析的响应", code="LocalNetwork.InvalidJson") from exc

    cls_response = body.get("Response", {})
    error = cls_response.get("Error")
    if error:
        raise ClsApiError(
            str(error.get("Message", "腾讯云 CLS API 调用失败")),
            code=str(error.get("Code", "TencentCloud.ApiError")),
            request_id=str(cls_response.get("RequestId", "")),
        )
    logger.info(
        "腾讯云 CLS API 调用成功: action=%s region=%s request_id=%s",
        action,
        region,
        cls_response.get("RequestId", ""),
    )
    return cls_response


def _configured_regions(region_code: Optional[str] = None) -> list[str]:
    if region_code:
        return [region_code]
    raw = os.getenv("TENCENTCLOUD_CLS_REGIONS", "").strip()
    if not raw:
        raw = os.getenv("TENCENTCLOUD_REGION", "").strip()
    if raw:
        regions = [item.strip() for item in raw.split(",") if item.strip()]
        return list(dict.fromkeys(regions))
    return list(DEFAULT_DISCOVERY_REGIONS)


def _error_result(exc: Exception, **extra: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "success": False,
        "data_source": CLS_DATA_SOURCE,
        "error": str(exc),
        "message": "腾讯云 CLS 调用失败，未返回任何替代数据",
    }
    if isinstance(exc, ClsApiError):
        result["error_code"] = exc.code
        result["request_id"] = exc.request_id
    result.update(extra)
    return result


def _format_topic(topic: Dict[str, Any], region: str) -> Dict[str, Any]:
    return {
        "topic_id": topic.get("TopicId"),
        "topic_name": topic.get("TopicName"),
        "logset_id": topic.get("LogsetId"),
        "region_code": region,
        "create_time": topic.get("CreateTime"),
        "retention_days": topic.get("Period"),
        "status": topic.get("Status"),
        "index_enabled": topic.get("Index"),
        "storage_type": topic.get("StorageType"),
        "description": topic.get("Describes", ""),
        "tags": topic.get("Tags") or [],
    }


def _describe_topics(
    name: str,
    region_code: Optional[str],
    precise: bool,
    filter_name: str = "topicName",
) -> Dict[str, Any]:
    regions = _configured_regions(region_code)
    topics: list[Dict[str, Any]] = []
    failures: list[Dict[str, str]] = []
    request_ids: list[str] = []
    for region in regions:
        params: Dict[str, Any] = {
            "Filters": [{"Key": filter_name, "Values": [name]}],
            "Offset": 0,
            "Limit": 100,
            "BizType": 0,
        }
        if precise and filter_name == "topicName":
            params["PreciseSearch"] = 1
        try:
            response = _call_cls_api("DescribeTopics", region, params)
        except Exception as exc:
            failure = _error_result(exc, region_code=region)
            failures.append(
                {
                    "region_code": region,
                    "error_code": str(failure.get("error_code", "")),
                    "error": str(failure["error"]),
                    "request_id": str(failure.get("request_id", "")),
                }
            )
            continue
        request_id = str(response.get("RequestId", ""))
        if request_id:
            request_ids.append(request_id)
        topics.extend(_format_topic(item, region) for item in response.get("Topics") or [])

    return {
        "success": not failures or bool(topics),
        "data_source": CLS_DATA_SOURCE,
        "topics": topics,
        "total": len(topics),
        "regions_queried": regions,
        "failed_regions": failures,
        "request_ids": request_ids,
    }


@mcp.tool()
@log_tool_call
def get_current_timestamp() -> int:
    """Return the current Unix timestamp in milliseconds for CLS time ranges."""
    return int(time.time() * 1000)


@mcp.tool()
@log_tool_call
def get_region_code_by_name(region_name: str) -> Dict[str, Any]:
    """Convert a Tencent Cloud region's Chinese name to its API region code."""
    if region_name in REGION_CODES.values():
        code = region_name
        display_name = next((name for name, value in REGION_CODES.items() if value == code), code)
    else:
        code = REGION_CODES.get(region_name)
        display_name = region_name
    if not code:
        return {
            "success": False,
            "data_source": "tencentcloud_region_catalog",
            "region_name": region_name,
            "region_code": None,
            "message": "未识别该地域名称，请直接提供 ap- 开头的腾讯云地域代码",
        }
    return {
        "success": True,
        "data_source": "tencentcloud_region_catalog",
        "region_name": display_name,
        "region_code": code,
        "configured_for_discovery": code in _configured_regions(),
        "message": "地域代码仅表示名称映射，资源是否存在由 CLS API 查询结果决定",
    }


@mcp.tool()
@log_tool_call
def list_cls_topics(
    region_code: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """List real Tencent Cloud CLS log topics in one or configured regions."""
    if not 1 <= limit <= 100:
        return _error_result(
            ClsApiError("limit 必须在 1 到 100 之间", "InvalidParameter.Limit"),
            topics=[],
            total=0,
        )
    regions = _configured_regions(region_code)
    topics: list[Dict[str, Any]] = []
    failures: list[Dict[str, str]] = []
    request_ids: list[str] = []
    for region in regions:
        try:
            response = _call_cls_api(
                "DescribeTopics",
                region,
                {"Filters": [], "Offset": 0, "Limit": limit, "BizType": 0},
            )
        except Exception as exc:
            failure = _error_result(exc, region_code=region)
            failures.append(
                {
                    "region_code": region,
                    "error_code": str(failure.get("error_code", "")),
                    "error": str(failure["error"]),
                    "request_id": str(failure.get("request_id", "")),
                }
            )
            continue
        request_id = str(response.get("RequestId", ""))
        if request_id:
            request_ids.append(request_id)
        topics.extend(_format_topic(item, region) for item in response.get("Topics") or [])
    return {
        "success": not failures or bool(topics),
        "data_source": CLS_DATA_SOURCE,
        "topics": topics,
        "total": len(topics),
        "regions_queried": regions,
        "failed_regions": failures,
        "request_ids": request_ids,
        "message": f"腾讯云 CLS 返回 {len(topics)} 个真实日志主题",
    }


@mcp.tool()
@log_tool_call
def get_topic_info_by_name(
    topic_name: str,
    region_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Query an exact topic name from Tencent Cloud CLS DescribeTopics."""
    result = _describe_topics(topic_name, region_code, precise=True)
    result["query"] = {"topic_name": topic_name, "region_code": region_code, "precise": True}
    result["message"] = (
        f"腾讯云 CLS 返回 {result['total']} 个精确匹配的日志主题"
        if result["success"]
        else "所有已查询地域的腾讯云 CLS 请求均失败"
    )
    return result


@mcp.tool()
@log_tool_call
def search_topic_by_service_name(
    service_name: str,
    region_code: Optional[str] = None,
    fuzzy: bool = True,
) -> Dict[str, Any]:
    """Find real CLS topics whose topic name matches a service name."""
    result = _describe_topics(service_name, region_code, precise=not fuzzy)
    result["query"] = {
        "service_name": service_name,
        "region_code": region_code,
        "fuzzy": fuzzy,
        "matched_field": "topicName",
    }
    result["message"] = (
        f"腾讯云 CLS 返回 {result['total']} 个匹配的日志主题"
        if result["success"]
        else "所有已查询地域的腾讯云 CLS 请求均失败"
    )
    return result


def _resolve_topic_region(topic_id: str, region_code: Optional[str]) -> str:
    if region_code:
        return region_code
    result = _describe_topics(topic_id, None, precise=True, filter_name="topicId")
    matches = result.get("topics", [])
    if len(matches) == 1:
        return str(matches[0]["region_code"])
    if len(matches) > 1:
        raise ClsApiError(
            "同一 Topic ID 在多个地域返回结果，请显式指定 region_code",
            code="LocalConfig.AmbiguousRegion",
        )
    failures = result.get("failed_regions", [])
    if failures and len(failures) == len(result.get("regions_queried", [])):
        first = failures[0]
        raise ClsApiError(
            f"无法发现 Topic 所在地域: {first.get('error', '')}",
            code=str(first.get("error_code", "TencentCloud.DiscoveryFailed")),
            request_id=str(first.get("request_id", "")),
        )
    raise ClsApiError(
        f"在已配置地域中未找到 Topic {topic_id}",
        code="ResourceNotFound.TopicNotExist",
    )


def _parse_log_content(item: Dict[str, Any]) -> Any:
    content = item.get("LogJson") or item.get("RawLog") or ""
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def _format_timestamp_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        timezone.utc,
    ).astimezone(SHANGHAI_TZ).isoformat()


def _format_log(item: Dict[str, Any]) -> Dict[str, Any]:
    timestamp_ms = int(item.get("Time") or 0)
    timestamp = ""
    if timestamp_ms:
        timestamp = _format_timestamp_ms(timestamp_ms)
    return {
        "timestamp": timestamp,
        "timestamp_ms": timestamp_ms,
        "topic_id": item.get("TopicId"),
        "topic_name": item.get("TopicName"),
        "source": item.get("Source", ""),
        "file_name": item.get("FileName", ""),
        "host_name": item.get("HostName", ""),
        "content": _parse_log_content(item),
        "highlights": item.get("HighLights") or [],
    }


@mcp.tool()
@log_tool_call
def search_log(
    topic_id: str,
    start_time: int,
    end_time: int,
    query: Optional[str] = None,
    limit: int = 100,
    region_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Search real Tencent Cloud CLS logs for a topic and millisecond time range."""
    if not isinstance(start_time, int) or not isinstance(end_time, int):
        return _error_result(
            ClsApiError("start_time 和 end_time 必须是毫秒整数", "InvalidParameter.Time"),
            topic_id=topic_id,
        )
    if end_time < start_time:
        return _error_result(
            ClsApiError("end_time 不能早于 start_time", "InvalidParameter.TimeRange"),
            topic_id=topic_id,
        )
    if not 1 <= limit <= 1000:
        return _error_result(
            ClsApiError("limit 必须在 1 到 1000 之间", "InvalidParameter.Limit"),
            topic_id=topic_id,
        )
    try:
        resolved_region = _resolve_topic_region(topic_id, region_code)
        params = {
            "TopicId": topic_id,
            "From": start_time,
            "To": end_time,
            "QueryString": query or "",
            "QuerySyntax": 1,
            "Limit": limit,
            "Sort": "desc",
            "UseNewAnalysis": True,
        }
        response = _call_cls_api("SearchLog", resolved_region, params)
    except Exception as exc:
        return _error_result(
            exc,
            topic_id=topic_id,
            region_code=region_code,
            logs=[],
            total=0,
        )

    logs = [_format_log(item) for item in response.get("Results") or []]
    analysis_records = []
    for record in response.get("AnalysisRecords") or []:
        try:
            analysis_records.append(json.loads(record))
        except (json.JSONDecodeError, TypeError):
            analysis_records.append(record)
    return {
        "success": True,
        "data_source": CLS_DATA_SOURCE,
        "topic_id": topic_id,
        "region_code": resolved_region,
        "start_time": start_time,
        "end_time": end_time,
        "query_window": {
            "start": _format_timestamp_ms(start_time),
            "end": _format_timestamp_ms(end_time),
            "timezone": "Asia/Shanghai",
        },
        "query": query or "",
        "limit": limit,
        "total": len(logs),
        "logs": logs,
        "analysis": bool(response.get("Analysis")),
        "analysis_records": analysis_records,
        "columns": response.get("Columns") or [],
        "context": response.get("Context", ""),
        "list_over": response.get("ListOver"),
        "request_id": response.get("RequestId", ""),
        "evidence_scope": "结果仅覆盖指定 Topic、query_window 和 query 条件",
        "cannot_conclude": [
            "不能据此断言服务正常或没有故障",
            "不能据此断言其他 Topic 或其他时间范围没有相关日志",
        ],
        "message": f"腾讯云 CLS 返回 {len(logs)} 条真实日志",
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=8003,
        path="/mcp",
    )
