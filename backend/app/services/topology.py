import logging
from collections import deque
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from app.models.service import ServiceDependency

logger = logging.getLogger("alert_buster.topology")

import time

def invalidate_topology_cache(db: Optional[Session] = None):
    if db is not None and hasattr(db, "info"):
        db.info.pop("_topology_cache", None)

def build_topology_graph(db: Session) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Fetches all ServiceDependency rows and constructs:
      - downstream_adj: parent_service -> list of child_services (parent -> child)
      - upstream_adj: child_service -> list of parent_services (child -> parent)
    Caches on the active db Session instance (db.info) to eliminate redundant network
    queries during high-volume alert processing without leaking across sessions or tests.
    """
    if hasattr(db, "info") and "_topology_cache" in db.info:
        return db.info["_topology_cache"]

    all_deps = db.query(ServiceDependency).all()
    downstream_adj: Dict[str, List[str]] = {}
    upstream_adj: Dict[str, List[str]] = {}
    
    for dep in all_deps:
        parent = dep.parent_service
        child = dep.child_service
        downstream_adj.setdefault(parent, []).append(child)
        upstream_adj.setdefault(child, []).append(parent)
        
    res = (downstream_adj, upstream_adj)
    if hasattr(db, "info"):
        db.info["_topology_cache"] = res
    return res

def get_downstream_services(
    db: Session,
    service_id: str,
    max_depth: int = 5,
    downstream_adj: Optional[Dict[str, List[str]]] = None
) -> Dict[str, int]:
    """
    Finds all downstream services reachable from service_id up to max_depth hops using BFS.
    Direction: parent_service -> child_service -> grandchild_service...
    
    Returns:
      Dict[str, int]: mapping downstream service_id -> shortest hop distance (1..max_depth).
      
    Safety features:
      - Safe cycle handling (never loops infinitely).
      - Strict max_depth enforcement.
      - Efficient BFS traversal with visited tracking.
    """
    if not service_id or max_depth <= 0:
        return {}

    if downstream_adj is None:
        downstream_adj, _ = build_topology_graph(db)

    visited: Dict[str, int] = {}
    queue = deque([(service_id, 0)])

    while queue:
        curr, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for child in downstream_adj.get(curr, []):
            if child == service_id:
                # Cycle returning to origin
                continue
            next_depth = depth + 1
            if child not in visited:
                visited[child] = next_depth
                queue.append((child, next_depth))
            elif next_depth < visited[child]:
                # Found a shorter path to this service
                visited[child] = next_depth
                queue.append((child, next_depth))

    return visited

def get_upstream_services(
    db: Session,
    service_id: str,
    max_depth: int = 5,
    upstream_adj: Optional[Dict[str, List[str]]] = None
) -> Dict[str, int]:
    """
    Finds all upstream services reachable from service_id up to max_depth hops using BFS.
    Direction: child_service -> parent_service -> grandparent_service...
    
    Returns:
      Dict[str, int]: mapping upstream service_id -> shortest hop distance (1..max_depth).
      
    Safety features:
      - Safe cycle handling.
      - Strict max_depth enforcement.
      - Efficient BFS traversal with visited tracking.
    """
    if not service_id or max_depth <= 0:
        return {}

    if upstream_adj is None:
        _, upstream_adj = build_topology_graph(db)

    visited: Dict[str, int] = {}
    queue = deque([(service_id, 0)])

    while queue:
        curr, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for parent in upstream_adj.get(curr, []):
            if parent == service_id:
                # Cycle returning to origin
                continue
            next_depth = depth + 1
            if parent not in visited:
                visited[parent] = next_depth
                queue.append((parent, next_depth))
            elif next_depth < visited[parent]:
                visited[parent] = next_depth
                queue.append((parent, next_depth))

    return visited

def are_services_topologically_related(
    db: Session,
    service_a: str,
    service_b: str,
    max_depth: int = 5
) -> bool:
    """
    Determines whether service_a and service_b are topologically connected
    either downstream or upstream within max_depth hops.
    """
    if not service_a or not service_b:
        return False
    if service_a == service_b:
        return True

    downstream_adj, upstream_adj = build_topology_graph(db)
    
    # Check if B is downstream of A
    downstream_from_a = get_downstream_services(db, service_a, max_depth, downstream_adj=downstream_adj)
    if service_b in downstream_from_a:
        return True

    # Check if B is upstream of A
    upstream_from_a = get_upstream_services(db, service_a, max_depth, upstream_adj=upstream_adj)
    if service_b in upstream_from_a:
        return True

    return False

def get_all_related_services(
    db: Session,
    service_id: str,
    max_depth: int = 5
) -> Dict[str, int]:
    """
    Returns the union of all upstream and downstream services reachable from service_id within max_depth hops.
    Maps service_id -> shortest hop distance.
    """
    downstream_adj, upstream_adj = build_topology_graph(db)
    down = get_downstream_services(db, service_id, max_depth, downstream_adj=downstream_adj)
    up = get_upstream_services(db, service_id, max_depth, upstream_adj=upstream_adj)
    
    result = dict(down)
    for svc, dist in up.items():
        if svc not in result or dist < result[svc]:
            result[svc] = dist
    return result
