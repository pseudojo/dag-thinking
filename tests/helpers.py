"""Shared test helper functions and constants."""

from src.server import call_dag_thinking

PAYLOAD = (
    "The key finding from this analysis is that the current architecture has a critical bottleneck "
    "in the data pipeline. The assumption is that horizontal scaling will resolve the throughput issue. "
    "Evidence from load tests shows that latency doubles beyond 500 concurrent connections. "
    "Therefore, the conclusion is to implement a message queue to decouple producers from consumers. "
    "This result must be addressed before the next production release to avoid system failure."
)


def think(db_path, session_id, node_name, thought_type, payload=None, depends_on=None, note=""):
    return call_dag_thinking(
        db_path=db_path,
        action="think",
        session_id=session_id,
        node_name=node_name,
        thought_type=thought_type,
        payload=payload if payload is not None else PAYLOAD,
        depends_on=depends_on or [],
        note=note,
    )


def status(db_path, session_id):
    return call_dag_thinking(db_path=db_path, action="status", session_id=session_id)


def restore(db_path, session_id, ccr_hash_val=None):
    return call_dag_thinking(
        db_path=db_path, action="restore", session_id=session_id, ccr_hash=ccr_hash_val
    )


def invalidate(db_path, session_id, target_node, reason="test"):
    return call_dag_thinking(
        db_path=db_path,
        action="invalidate",
        session_id=session_id,
        target_node=target_node,
        reason=reason,
    )
